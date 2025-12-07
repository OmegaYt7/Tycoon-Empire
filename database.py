import asyncpg
import json
import logging
import asyncio
from datetime import datetime, timedelta

# Твоя строка подключения к Neon DB
DB_URI = "postgresql://neondb_owner:npg_sC4FRJhbmk8d@ep-billowing-credit-a4q1jnbn-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Глобальная переменная для пула соединений
pool = None

async def create_pool():
    """Создает пул соединений при запуске бота."""
    global pool
    try:
        pool = await asyncpg.create_pool(dsn=DB_URI)
        logging.warning("✅ Успешное подключение к Neon DB (asyncpg)")
    except Exception as e:
        logging.error(f"❌ Ошибка подключения к БД: {e}")

async def create_table():
    """Создает таблицу, если она не существует."""
    if pool is None:
        await create_pool()
        
    async with pool.acquire() as conn:
        # Используем JSONB для хранения всей структуры данных игрока
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                nickname TEXT,
                balance BIGINT,
                diamonds INTEGER,
                referrals INTEGER,
                last_active DATE,
                json_data JSONB
            )
        ''')

async def save_all_users(users_dict):
    """
    Асинхронно сохраняет всех пользователей.
    Использует массовую вставку (executemany) для высокой скорости.
    """
    if not users_dict:
        return

    if pool is None:
        await create_pool()

    today = datetime.now().date()
    data_list = []

    # Подготовка данных для массовой вставки
    for user_id, data in users_dict.items():
        # Копируем данные, чтобы не менять оригинал
        temp_data = data.copy()
        
        # Сериализуем JSON
        json_str = json.dumps(temp_data, ensure_ascii=False)
        
        # Извлекаем основные поля для колонок
        username = data.get('username', 'Guest')
        nickname = data.get('nickname', 'Unknown')
        balance = data.get('balance', 0)
        diamonds = data.get('diamonds', 0)
        referrals = data.get('referrals', 0)

        # Добавляем кортеж данных в список
        data_list.append((
            user_id, username, nickname, balance, diamonds, referrals, today, json_str
        ))

    # Выполняем запрос
    query = '''
        INSERT INTO users (user_id, username, nickname, balance, diamonds, referrals, last_active, json_data)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            nickname = EXCLUDED.nickname,
            balance = EXCLUDED.balance,
            diamonds = EXCLUDED.diamonds,
            referrals = EXCLUDED.referrals,
            last_active = EXCLUDED.last_active,
            json_data = EXCLUDED.json_data
    '''

    try:
        async with pool.acquire() as conn:
            await conn.executemany(query, data_list)
    except Exception as e:
        logging.error(f"Ошибка при сохранении базы: {e}")

async def load_all_users():
    """Загружает всех пользователей из БД в словарь при запуске."""
    if pool is None:
        await create_pool()
        
    await create_table()
    
    # Удаляем неактивных перед загрузкой
    await delete_inactive_users()
    
    loaded_users = {}
    try:
        async with pool.acquire() as conn:
            # Забираем только user_id и json_data, так как в json_data есть всё
            rows = await conn.fetch("SELECT user_id, json_data FROM users")
            
            for row in rows:
                user_id = row['user_id']
                json_val = row['json_data']
                
                # asyncpg автоматически декодирует JSONB в dict или str
                if isinstance(json_val, str):
                    user_data = json.loads(json_val)
                else:
                    user_data = json_val
                
                loaded_users[user_id] = user_data
                
        logging.warning(f"Загружено {len(loaded_users)} пользователей из Neon DB.")
    except Exception as e:
        logging.error(f"Ошибка загрузки пользователей: {e}")
        
    return loaded_users

async def delete_inactive_users(days=90):
    """Удаляет пользователей, которые не заходили более 90 дней."""
    if pool is None:
        await create_pool()
        
    cutoff_date = datetime.now().date() - timedelta(days=days)
    
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM users WHERE last_active < $1", cutoff_date)
            # result возвращает строку типа "DELETE 5"
            deleted_count = result.split()[-1]
            if int(deleted_count) > 0:
                logging.warning(f"🧹 Удалено {deleted_count} неактивных профилей.")
    except Exception as e:
        logging.error(f"Ошибка удаления неактивных: {e}")

async def export_users_to_json_file():
    """Выгружает базу в JSON файл и возвращает имя файла."""
    if pool is None:
        await create_pool()
        
    try:
        async with pool.acquire() as conn:
            # Берем актуальные данные прямо из БД
            rows = await conn.fetch("SELECT json_data FROM users")
            
        all_data = []
        for row in rows:
            json_val = row['json_data']
            if isinstance(json_val, str):
                all_data.append(json.loads(json_val))
            else:
                all_data.append(json_val)
        
        filename = "users_export.json"
        # Запись в файл (синхронная операция, но для админ-команды допустимо)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
            
        return filename
    except Exception as e:
        logging.error(f"Ошибка экспорта: {e}")
        raise e