from psycopg2cffi import psycopg2
import json
import logging
from datetime import datetime, timedelta

# Твоя строка подключения к Neon DB
DB_URI = "postgresql://neondb_owner:npg_sC4FRJhbmk8d@ep-billowing-credit-a4q1jnbn-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def get_connection():
    return psycopg2.connect(DB_URI)

def create_table():
    """Создает таблицу в PostgreSQL, если она не существует."""
    conn = get_connection()
    c = conn.cursor()
    # Используем JSONB для хранения сложных данных, это фишка Postgres
    c.execute('''
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
    conn.commit()
    conn.close()

def save_all_users(users_dict):
    """Сохраняет пользователей в PostgreSQL. Использует Upsert (On Conflict)."""
    if not users_dict:
        return

    conn = get_connection()
    c = conn.cursor()
    
    # Дата сегодня для поля last_active
    today = datetime.now().date()

    for user_id, data in users_dict.items():
        # Подготовка данных
        temp_data = data.copy()
        json_str = json.dumps(temp_data, ensure_ascii=False)
        
        username = data.get('username', 'Guest')
        nickname = data.get('nickname', 'Unknown')
        balance = data.get('balance', 0)
        diamonds = data.get('diamonds', 0)
        referrals = data.get('referrals', 0)

        # SQL запрос для Postgres (INSERT ... ON CONFLICT DO UPDATE)
        c.execute('''
            INSERT INTO users (user_id, username, nickname, balance, diamonds, referrals, last_active, json_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                nickname = EXCLUDED.nickname,
                balance = EXCLUDED.balance,
                diamonds = EXCLUDED.diamonds,
                referrals = EXCLUDED.referrals,
                last_active = EXCLUDED.last_active,
                json_data = EXCLUDED.json_data
        ''', (user_id, username, nickname, balance, diamonds, referrals, today, json_str))

    conn.commit()
    conn.close()

def load_all_users():
    """Загружает всех пользователей из Postgres в словарь."""
    create_table() # Гарантируем наличие таблицы
    
    # Сначала удаляем старых (кто не заходил 90 дней)
    delete_inactive_users()
    
    conn = get_connection()
    c = conn.cursor()
    
    try:
        c.execute("SELECT user_id, json_data FROM users")
        rows = c.fetchall()
    except Exception as e:
        logging.error(f"Ошибка чтения БД: {e}")
        return {}
    finally:
        conn.close()
    
    loaded_users = {}
    for row in rows:
        user_id = row[0]
        user_data = row[1] # В psycopg2 JSONB автоматически конвертируется в dict
        
        # Если вдруг вернулась строка (зависит от версии драйвера), парсим
        if isinstance(user_data, str):
            user_data = json.loads(user_data)
            
        loaded_users[user_id] = user_data
            
    logging.warning(f"Загружено {len(loaded_users)} пользователей из Neon DB.")
    return loaded_users

def delete_inactive_users(days=90):
    """Удаляет пользователей, которые не активны более 90 дней."""
    conn = get_connection()
    c = conn.cursor()
    cutoff_date = datetime.now().date() - timedelta(days=days)
    
    c.execute("DELETE FROM users WHERE last_active < %s", (cutoff_date,))
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    if deleted_count > 0:
        logging.warning(f"🧹 Удалено {deleted_count} неактивных пользователей.")

def export_users_to_json_file():
    """Выгружает всю базу в JSON файл для админа."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT json_data FROM users")
    rows = c.fetchall()
    conn.close()
    
    all_data = [row[0] for row in rows] # Собираем список всех словарей
    
    filename = "users_export.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
        
    return filename