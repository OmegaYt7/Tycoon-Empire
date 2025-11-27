import sqlite3
import json
import logging

DB_NAME = "game.db"

def create_table():
    """Создает таблицу, если она не существует."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Создаем таблицу. Основные поля для ТОПа храним отдельно, остальное в json_data
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            nickname TEXT,
            balance INTEGER,
            diamonds INTEGER,
            referrals INTEGER,
            json_data TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_all_users(users_dict):
    """Сохраняет ВСЕХ пользователей из памяти в БД."""
    if not users_dict:
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    data_to_insert = []
    
    for user_id, data in users_dict.items():
        temp_data = data.copy()
        json_str = json.dumps(temp_data, ensure_ascii=False)
        
        data_to_insert.append((
            user_id,
            data.get('username', 'Guest'),
            data.get('nickname', 'Unknown'),
            data.get('balance', 0),
            data.get('diamonds', 0),
            data.get('referrals', 0),
            json_str
        ))

    c.executemany('''
        INSERT OR REPLACE INTO users 
        (user_id, username, nickname, balance, diamonds, referrals, json_data) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', data_to_insert)
    
    conn.commit()
    conn.close()

def load_all_users():
    """Загружает всех пользователей из БД в словарь при запуске."""
    # СНАЧАЛА ГАРАНТИРУЕМ, ЧТО ТАБЛИЦА СУЩЕСТВУЕТ
    create_table()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("SELECT user_id, json_data FROM users")
        rows = c.fetchall()
    except sqlite3.OperationalError:
        # Если вдруг таблицы все еще нет (маловероятно, но для страховки)
        return {}
    finally:
        conn.close()
    
    loaded_users = {}
    for row in rows:
        user_id = row[0]
        json_str = row[1]
        try:
            user_data = json.loads(json_str)
            loaded_users[user_id] = user_data
        except Exception as e:
            logging.error(f"Ошибка загрузки данных пользователя {user_id}: {e}")
            
    logging.warning(f"Загружено {len(loaded_users)} пользователей из базы.")
    return loaded_users