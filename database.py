import asyncpg
import json
import logging
import os
import sys
import asyncio
import config

pool = None
_pool_lock = asyncio.Lock()

# Ошибки, при которых имеет смысл пересоздать пул и попробовать снова
# (обрыв соединения из-за "усыпления" Neon на бесплатном тарифе, сетевые сбои и т.п.)
_CONNECTION_ERRORS = (
    asyncpg.exceptions.InterfaceError,
    asyncpg.exceptions.ConnectionDoesNotExistError,
    asyncpg.exceptions.ConnectionFailureError,
    asyncpg.exceptions.TooManyConnectionsError,
    ConnectionResetError,
    ConnectionRefusedError,
    OSError,
)


async def create_pool(force=False):
    """Создаёт пул соединений. Если force=True — пересоздаёт даже если пул уже есть
    (используется при восстановлении после обрыва связи)."""
    global pool
    async with _pool_lock:
        if pool is not None and not force:
            return pool

        if pool is not None:
            try:
                await pool.close()
            except Exception:
                pass
            pool = None

        if not config.DATABASE_URL:
            logging.error("❌ ОШИБКА: Не найдена переменная DATABASE_URL! Укажите её в настройках хостинга (Environment Variables).")
            sys.exit(1)

        try:
            pool = await asyncpg.create_pool(
                dsn=config.DATABASE_URL,
                ssl="require",
                min_size=1,
                max_size=10,
                command_timeout=30,
                max_inactive_connection_lifetime=60,  # не держим "протухшие" соединения дольше минуты
            )
            logging.warning("✅ Пул соединений с Neon DB (SSL) создан.")
            await init_db()
        except Exception as e:
            logging.error(f"❌ Ошибка подключения к БД: {e}")
            if not force:
                # При самом первом запуске без базы — нет смысла жить дальше
                sys.exit(1)
            pool = None
            raise
        return pool


async def _with_retry(action, *, retries=2, base_delay=1.0):
    """Выполняет action() (корутину без аргументов), при обрыве связи
    пересоздаёт пул и пробует ещё раз (до `retries` дополнительных попыток)."""
    global pool
    last_exc = None
    for attempt in range(retries + 1):
        try:
            if pool is None:
                await create_pool(force=True)
            return await action()
        except _CONNECTION_ERRORS as e:
            last_exc = e
            logging.warning(
                f"⚠️ Обрыв соединения с БД (попытка {attempt + 1}/{retries + 1}): {e}. Пересоздаю пул..."
            )
            try:
                await create_pool(force=True)
            except Exception:
                pass
            await asyncio.sleep(base_delay * (attempt + 1))
        except Exception as e:
            # Ошибка не связана с соединением (например, синтаксис SQL) — повторять бессмысленно
            last_exc = e
            break
    raise last_exc


async def close_session():
    global pool
    if pool:
        await pool.close()
        logging.warning("🔌 Соединение с БД закрыто.")


async def init_db():
    """Создает таблицу, если она не существует"""
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                nickname TEXT,
                balance BIGINT DEFAULT 0,
                json_data JSONB,
                last_updated TIMESTAMP DEFAULT NOW()
            );
        """)
        logging.warning("📊 Таблица users проверена/создана.")


async def save_user(user_id, user_data):
    """Сохраняет одного пользователя (Upsert). Возвращает True/False.
    В TEST_MODE запись пропускается (данные живут только в памяти процесса)."""
    if config.TEST_MODE:
        logging.warning(f"🧪 TEST_MODE: сохранение user_id={user_id} пропущено (в БД не записано).")
        return True

    username = user_data.get('username', 'Guest')
    nickname = user_data.get('nickname', 'Unknown')
    balance = int(user_data.get('balance', 0))
    json_str = json.dumps(user_data, ensure_ascii=False)

    async def _do():
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, nickname, balance, json_data, last_updated)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    nickname = EXCLUDED.nickname,
                    balance = EXCLUDED.balance,
                    json_data = EXCLUDED.json_data,
                    last_updated = NOW();
            """, user_id, username, nickname, balance, json_str)

    try:
        await _with_retry(_do)
        return True
    except Exception as e:
        logging.error(f"Save User Error {user_id}: {e}")
        return False


async def save_all_users(users_dict):
    """Массовое сохранение через транзакцию. Возвращает True/False.
    В TEST_MODE запись пропускается (данные живут только в памяти процесса)."""
    if not users_dict:
        return True

    if config.TEST_MODE:
        logging.warning(f"🧪 TEST_MODE: автосохранение {len(users_dict)} игроков пропущено (в БД не записано).")
        return True

    logging.warning("💾 Начинаю автосохранение...")

    data_list = []
    for user_id, data in users_dict.items():
        username = data.get('username', 'Guest')
        nickname = data.get('nickname', 'Unknown')
        balance = int(data.get('balance', 0))
        json_str = json.dumps(data, ensure_ascii=False)
        data_list.append((user_id, username, nickname, balance, json_str))

    async def _do():
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany("""
                    INSERT INTO users (user_id, username, nickname, balance, json_data, last_updated)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        nickname = EXCLUDED.nickname,
                        balance = EXCLUDED.balance,
                        json_data = EXCLUDED.json_data,
                        last_updated = NOW();
                """, data_list)

    try:
        await _with_retry(_do)
        logging.warning("✅ Автосохранение завершено.")
        return True
    except Exception as e:
        logging.error(f"Bulk Save Error: {e}")
        return False


async def load_all_users():
    """Загружает всех пользователей при старте"""
    loaded_users = {}

    async def _do():
        async with pool.acquire() as conn:
            return await conn.fetch("SELECT user_id, json_data FROM users")

    try:
        rows = await _with_retry(_do)
        for row in rows:
            user_id = row['user_id']
            try:
                user_data = json.loads(row['json_data'])
                loaded_users[int(user_id)] = user_data
            except Exception:
                continue
        logging.warning(f"📥 Загружено {len(loaded_users)} пользователей из Neon DB.")
    except Exception as e:
        logging.error(f"Load Error: {e}")

    return loaded_users


async def delete_user(user_id):
    """Полностью удаляет пользователя из базы (не обнуление, а именно удаление строки).
    В TEST_MODE удаление тоже пропускается, чтобы не портить реальные данные во время тестов."""
    if config.TEST_MODE:
        logging.warning(f"🧪 TEST_MODE: удаление user_id={user_id} пропущено (в БД не применено).")
        return True

    async def _do():
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM users WHERE user_id = $1;", user_id)

    try:
        await _with_retry(_do)
        return True
    except Exception as e:
        logging.error(f"Delete User Error {user_id}: {e}")
        return False


async def export_users_to_json_file():
    """Экспорт для админки"""
    filename = "users_export.json"

    async def _do():
        async with pool.acquire() as conn:
            return await conn.fetch("SELECT json_data FROM users")

    try:
        rows = await _with_retry(_do)
        all_data = [json.loads(row['json_data']) for row in rows]
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
        return filename
    except Exception as e:
        logging.error(f"Export Error: {e}")
        return None
