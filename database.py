import asyncpg
import json
import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, Any

# ⚠️ ВНИМАНИЕ: ВАША СТРОКА ПОДКЛЮЧЕНИЯ
# Убедитесь, что DB_URI содержит корректный URL от Neon DB.
DB_URI = "postgresql://neondb_owner:npg_sC4FRJhbmk8d@ep-billowing-credit-a4q1jnbn-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Глобальная переменная для пула соединений
pool = None

async def init_db_pool():
    """Инициализирует пул соединений при запуске бота."""
    global pool
    if pool is None:
        try:
            # Создание пула соединений
            pool = await asyncpg.create_pool(
                DB_URI,
                min_size=5,  # Минимальное количество соединений
                max_size=10, # Максимальное количество соединений
            )
            logging.warning("✅ Пул соединений PostgreSQL создан.")
        except Exception as e:
            logging.error(f"❌ Ошибка создания пула asyncpg: {e}")
            return False
    return True

async def create_table():
    """Создает таблицу в PostgreSQL, если она не существует."""
    await init_db_pool()
    async with pool.acquire() as conn:
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
    logging.warning("✅ Таблица users проверена/создана.")


async def save_all_users(users_dict: Dict[int, Dict[str, Any]]):
    """Сохраняет ВСЕХ пользователей из памяти в БД."""
    if not users_dict:
        return
    
    await init_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            today = datetime.now().date()
            data_to_insert = []
            
            for user_id, data in users_dict.items():
                temp_data = data.copy()
                json_data = json.dumps(temp_data, ensure_ascii=False)
                
                # Подготовка данных для UPSERT
                data_to_insert.append((
                    user_id,
                    data.get('username', 'Guest'),
                    data.get('nickname', 'Unknown'),
                    data.get('balance', 0),
                    data.get('diamonds', 0),
                    data.get('referrals', 0),
                    today,
                    json_data
                ))

            # Используем UPSERT (INSERT OR UPDATE)
            query = '''
                INSERT INTO users (user_id, username, nickname, balance, diamonds, referrals, last_active, json_data) 
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb) 
                ON CONFLICT (user_id) DO UPDATE SET 
                    username = EXCLUDED.username,
                    nickname = EXCLUDED.nickname,
                    balance = EXCLUDED.balance,
                    diamonds = EXCLUDED.diamonds,
                    referrals = EXCLUDED.referrals,
                    last_active = EXCLUDED.last_active,
                    json_data = EXCLUDED.json_data;
            '''
            await conn.executemany(query, data_to_insert)
            logging.warning(f"💾 Сохранено {len(data_to_insert)} пользователей.")


async def load_all_users():
    """Загружает всех пользователей из БД в словарь при запуске."""
    await init_db_pool()
    await create_table() # Гарантируем, что таблица есть

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, json_data FROM users")
    
    loaded_users = {}
    for record in rows:
        user_id = record['user_id']
        user_data = record['json_data']
        loaded_users[user_id] = user_data
        
    logging.warning(f"Загружено {len(loaded_users)} пользователей из Neon DB.")
    return loaded_users

async def export_users_to_json_file(filename: str = "users_export.json"):
    """
    Выгружает всю базу в JSON файл.
    (Для использования в main.py, например, в команде для админа)
    """
    await init_db_pool()
    async with pool.acquire() as conn:
        # Извлекаем только поле json_data, которое содержит полный словарь пользователя
        rows = await conn.fetch("SELECT json_data FROM users")
    
    all_users_data = [row['json_data'] for row in rows]

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_users_data, f, ensure_ascii=False, indent=4)
        logging.warning(f"📤 Данные успешно выгружены в {filename}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при выгрузке данных в JSON: {e}")
        return False