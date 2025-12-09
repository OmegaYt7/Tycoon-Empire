import aiohttp
import json
import logging
import asyncio
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ SUPABASE
# ═══════════════════════════════════════════════════════════

SUPABASE_URL = "https://tuvqserdclbgloysblrx.supabase.co"
# 👇👇👇 ВСТАВЬТЕ СЮДА ВАШ КЛЮЧ, КОТОРЫЙ БЫЛ РАНЬШЕ 👇👇👇
SUPABASE_KEY = "sb_secret_bDIUtmYZ2Zx5Rz3EauEhlw_sbrmR6y9" 

# Глобальная переменная для HTTP сессии AIOHTTP
http_session = None

# Глобальная переменная для HTTP сессии AIOHTTP
http_session = None

# Заголовки для каждого запроса
# Добавлен Connection: keep-alive для стабильности
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
<<<<<<< HEAD
    "Prefer": "return=minimal",
    "Connection": "keep-alive"
=======
    "Prefer": "return=minimal" # Не возвращать данные после записи
>>>>>>> a8f8b8f234c582006e29058d380b89e2ebff9bb2
}

# ═══════════════════════════════════════════════════════════
# ФУНКЦИИ БАЗЫ ДАННЫХ
# ═══════════════════════════════════════════════════════════

async def create_pool():
    """Создает глобальную HTTP сессию для Supabase."""
    global http_session
    if http_session is None:
<<<<<<< HEAD
        # Увеличиваем таймауты для стабильности
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        http_session = aiohttp.ClientSession(headers=HEADERS, timeout=timeout)
=======
        http_session = aiohttp.ClientSession(headers=HEADERS)
>>>>>>> a8f8b8f234c582006e29058d380b89e2ebff9bb2
        logging.warning("✅ Инициализация глобальной HTTP сессии для Supabase...")
        
        # Проверка соединения
        url = f"{SUPABASE_URL}/rest/v1/"
        try:
            async with http_session.get(url) as resp:
                if resp.status == 200:
                    logging.warning("✅ Соединение с Supabase установлено!")
                else:
                    logging.error(f"❌ Ошибка соединения с Supabase: {resp.status}")
        except Exception as e:
            logging.error(f"❌ Критическая ошибка соединения с Supabase: {e}")

async def close_session():
    """Закрывает глобальную сессию при завершении работы бота."""
    global http_session
    if http_session:
        await http_session.close()
        logging.warning("🔌 HTTP сессия Supabase закрыта.")

async def create_table():
    """Функция-заглушка для совместимости."""
    pass

async def save_all_users(users_dict):
    """Сохраняет всех пользователей через HTTP запрос (UPSERT)."""
    if not users_dict:
        return

    global http_session
    if http_session is None:
        logging.error("❌ Сессия не инициализирована при сохранении!")
<<<<<<< HEAD
        # Пытаемся пересоздать сессию на лету, если она потерялась
        await create_pool()
        if http_session is None: return
=======
        return
>>>>>>> a8f8b8f234c582006e29058d380b89e2ebff9bb2

    today = datetime.now().strftime("%Y-%m-%d")
    data_list = []
    
    for user_id, data in users_dict.items():
        row = {
            "user_id": user_id,
            "username": data.get('username', 'Guest'),
            "nickname": data.get('nickname', 'Unknown'),
            "balance": data.get('balance', 0),
            "diamonds": data.get('diamonds', 0),
            "referrals": data.get('referrals', 0),
            "last_active": today,
            "json_data": data
        }
        data_list.append(row)

    chunk_size = 100
    url = f"{SUPABASE_URL}/rest/v1/users"
    
    # Заголовок для UPSERT
    upsert_headers = {"Prefer": "resolution=merge-duplicates"} 
    
<<<<<<< HEAD
    # Отправка данных чанками
    for i in range(0, len(data_list), chunk_size):
        chunk = data_list[i:i + chunk_size]
        try:
=======
    # Отправка данных
    for i in range(0, len(data_list), chunk_size):
        chunk = data_list[i:i + chunk_size]
        try:
            # Используем глобальную сессию
>>>>>>> a8f8b8f234c582006e29058d380b89e2ebff9bb2
            async with http_session.post(url, headers=upsert_headers, json=chunk) as resp:
                if resp.status not in [200, 201, 204]:
                    text = await resp.text()
                    logging.error(f"❌ Ошибка сохранения Supabase: {resp.status} - {text}")
<<<<<<< HEAD
        
        # --- ОБРАБОТКА ОШИБОК СЕТИ ---
        except ConnectionResetError:
            logging.warning("⚠️ Supabase сбросил соединение (Connection reset). Пропускаем этот цикл.")
        except aiohttp.ClientConnectorError:
            logging.warning("⚠️ Не удалось подключиться к Supabase. Проверьте интернет.")
        except aiohttp.ServerDisconnectedError:
            logging.warning("⚠️ Сервер разорвал соединение. Попробуем позже.")
=======
>>>>>>> a8f8b8f234c582006e29058d380b89e2ebff9bb2
        except Exception as e:
            logging.error(f"❌ Ошибка запроса POST к Supabase: {e}")

async def load_all_users():
    """Загружает всех пользователей из Supabase через GET запрос."""
    global http_session
    if http_session is None:
        logging.error("❌ Сессия не инициализирована при загрузке!")
        return {}

    loaded_users = {}
    url = f"{SUPABASE_URL}/rest/v1/users?select=user_id,json_data"
    
    try:
<<<<<<< HEAD
=======
        # Используем глобальную сессию
>>>>>>> a8f8b8f234c582006e29058d380b89e2ebff9bb2
        async with http_session.get(url) as resp:
            if resp.status == 200:
                rows = await resp.json()
                for row in rows:
                    user_id = row['user_id']
                    user_data = row['json_data']
                    
                    if isinstance(user_data, str):
<<<<<<< HEAD
                        try:
                            user_data = json.loads(user_data)
                        except:
                            continue # Пропускаем битые данные
=======
                        user_data = json.loads(user_data)
>>>>>>> a8f8b8f234c582006e29058d380b89e2ebff9bb2
                        
                    loaded_users[int(user_id)] = user_data
                
                logging.warning(f"📥 Загружено {len(loaded_users)} пользователей из Supabase.")
            else:
                text = await resp.text()
                logging.error(f"❌ Ошибка загрузки из Supabase: {resp.status} - {text}")
                
    except Exception as e:
        logging.error(f"❌ Критическая ошибка загрузки: {e}")
        
    return loaded_users

async def delete_inactive_users(days=90):
    """Удаляет неактивных пользователей."""
    global http_session
    if http_session is None: return

    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = f"{SUPABASE_URL}/rest/v1/users?last_active=lt.{cutoff_date}"
    
    try:
        async with http_session.delete(url) as resp:
            if resp.status == 204:
                logging.warning(f"🧹 Очистка старых пользователей выполнена.")
            else:
                logging.error(f"Ошибка очистки: {resp.status}")
    except Exception as e:
        logging.error(f"Ошибка запроса очистки: {e}")

async def export_users_to_json_file():
    """Выгружает базу в файл (скачивает всё из Supabase)."""
    global http_session
    if http_session is None: return None

    url = f"{SUPABASE_URL}/rest/v1/users?select=json_data"
    filename = "users_export.json"
    
    try:
        async with http_session.get(url) as resp:
            if resp.status == 200:
                rows = await resp.json()
                all_data = [row['json_data'] for row in rows]
                
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=4)
                return filename
            else:
                logging.error(f"Ошибка экспорта: {resp.status}")
    except Exception as e:
        logging.error(f"Ошибка экспорта: {e}")
    
    return None
