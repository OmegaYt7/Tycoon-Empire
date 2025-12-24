import asyncpg
import json
import logging
import os
import sys
import config

pool = None

async def create_pool():
    global pool
    if pool is None:
        # Проверка, установлена ли ссылка на базу
        if not config.DATABASE_URL:
            logging.error("❌ ОШИБКА: Не найдена переменная DATABASE_URL! Укажите её в настройках хостинга (Environment Variables).")
            sys.exit(1) # Останавливаем бота, если базы нет
            
        try:
            # Для Neon обязательно ssl="require"
            pool = await asyncpg.create_pool(
                dsn=config.DATABASE_URL,
                ssl="require",
                min_size=1,
                max_size=10
            )
            logging.warning("✅ Пул соединений с Neon DB (SSL) создан.")
            # Создаем таблицу сразу при подключении
            await init_db()
        except Exception as e:
            logging.error(f"❌ Ошибка подключения к БД: {e}")
            sys.exit(1)

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
    """Сохраняет одного пользователя (Upsert)"""
    if pool is None: await create_pool()
    
    username = user_data.get('username', 'Guest')
    nickname = user_data.get('nickname', 'Unknown')
    balance = int(user_data.get('balance', 0))
    json_str = json.dumps(user_data, ensure_ascii=False)

    try:
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
    except Exception as e:
        logging.error(f"Save User Error {user_id}: {e}")

async def save_all_users(users_dict):
    """Массовое сохранение через транзакцию"""
    if not users_dict: return
    if pool is None: await create_pool()

    logging.warning("💾 Начинаю автосохранение...")
    
    data_list = []
    for user_id, data in users_dict.items():
        username = data.get('username', 'Guest')
        nickname = data.get('nickname', 'Unknown')
        balance = int(data.get('balance', 0))
        json_str = json.dumps(data, ensure_ascii=False)
        data_list.append((user_id, username, nickname, balance, json_str))

    try:
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
        logging.warning("✅ Автосохранение завершено.")
    except Exception as e:
        logging.error(f"Bulk Save Error: {e}")

async def load_all_users():
    """Загружает всех пользователей при старте"""
    if pool is None: await create_pool()
    
    loaded_users = {}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, json_data FROM users")
            for row in rows:
                user_id = row['user_id']
                try:
                    user_data = json.loads(row['json_data'])
                    loaded_users[int(user_id)] = user_data
                except:
                    continue
        logging.warning(f"📥 Загружено {len(loaded_users)} пользователей из Neon DB.")
    except Exception as e:
        logging.error(f"Load Error: {e}")
        
    return loaded_users

async def export_users_to_json_file():
    """Экспорт для админки"""
    if pool is None: await create_pool()
    filename = "users_export.json"
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT json_data FROM users")
            all_data = [json.loads(row['json_data']) for row in rows]
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)
            return filename
    except Exception:
        pass
    return None
