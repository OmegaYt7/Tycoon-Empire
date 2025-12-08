import aiohttp
import json
import logging
import asyncio
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ SUPABASE
# ═══════════════════════════════════════════════════════════

SUPABASE_URL = "https://tuvqserdclbgloysblrx.supabase.co"
SUPABASE_KEY = "sb_secret_bDIUtmYZ2Zx5Rz3EauEhlw_sbrmR6y9" # Твой секретный ключ

# Заголовки для каждого запроса
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal" # Не возвращать данные после записи (экономит трафик)
}

# ═══════════════════════════════════════════════════════════
# ФУНКЦИИ БАЗЫ ДАННЫХ
# ═══════════════════════════════════════════════════════════

async def create_pool():
    """
    Для совместимости с main.py. 
    В aiohttp пулы работают иначе, но мы можем просто проверить соединение.
    """
    logging.warning("✅ Инициализация HTTP сессии для Supabase...")
    # Можно сделать тестовый запрос, чтобы убедиться, что всё ок
    async with aiohttp.ClientSession() as session:
        url = f"{SUPABASE_URL}/rest/v1/"
        async with session.get(url, headers=HEADERS) as resp:
            if resp.status == 200:
                logging.warning("✅ Соединение с Supabase установлено!")
            else:
                logging.error(f"❌ Ошибка соединения с Supabase: {resp.status}")

async def create_table():
    """
    В REST API таблицу лучше создавать через интерфейс Supabase (SQL Editor).
    Оставляем функцию пустой, чтобы main.py не ломался при вызове.
    """
    pass

async def save_all_users(users_dict):
    """
    Сохраняет всех пользователей через HTTP запрос (UPSERT).
    """
    if not users_dict:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    data_list = []

    # Подготовка данных для отправки
    for user_id, data in users_dict.items():
        # Подготавливаем JSON объект для поля json_data
        # Важно: Supabase требует, чтобы json был объектом или строкой, 
        # aiohttp сам сериализует dict в json при отправке, но для поля jsonb 
        # лучше отправлять словарь как есть, Supabase поймет.
        
        row = {
            "user_id": user_id,
            "username": data.get('username', 'Guest'),
            "nickname": data.get('nickname', 'Unknown'),
            "balance": data.get('balance', 0),
            "diamonds": data.get('diamonds', 0),
            "referrals": data.get('referrals', 0),
            "last_active": today,
            "json_data": data # Весь объект игрока кладем в колонку json_data
        }
        data_list.append(row)

    # Разбиваем на пачки по 100 штук, чтобы не превысить лимиты запроса
    chunk_size = 100
    url = f"{SUPABASE_URL}/rest/v1/users"
    
    # Заголовок для UPSERT (слияние дубликатов по ID)
    upsert_headers = HEADERS.copy()
    upsert_headers["Prefer"] = "resolution=merge-duplicates"

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(data_list), chunk_size):
            chunk = data_list[i:i + chunk_size]
            try:
                async with session.post(url, headers=upsert_headers, json=chunk) as resp:
                    if resp.status not in [200, 201, 204]:
                        text = await resp.text()
                        logging.error(f"❌ Ошибка сохранения Supabase: {resp.status} - {text}")
            except Exception as e:
                logging.error(f"❌ Ошибка запроса к Supabase: {e}")

async def load_all_users():
    """Загружает всех пользователей из Supabase через GET запрос."""
    loaded_users = {}
    url = f"{SUPABASE_URL}/rest/v1/users?select=user_id,json_data"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS) as resp:
                if resp.status == 200:
                    rows = await resp.json()
                    for row in rows:
                        user_id = row['user_id']
                        user_data = row['json_data']
                        
                        # Если вдруг пришло строкой (бывает в разных версиях)
                        if isinstance(user_data, str):
                            user_data = json.loads(user_data)
                            
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
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Синтаксис фильтрации Supabase: last_active=lt.DATE (lt = less than / меньше чем)
    url = f"{SUPABASE_URL}/rest/v1/users?last_active=lt.{cutoff_date}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=HEADERS) as resp:
                if resp.status == 204:
                    logging.warning(f"🧹 Очистка старых пользователей выполнена.")
                else:
                    logging.error(f"Ошибка очистки: {resp.status}")
    except Exception as e:
        logging.error(f"Ошибка запроса очистки: {e}")

async def export_users_to_json_file():
    """
    Выгружает базу в файл (скачивает всё из Supabase).
    """
    url = f"{SUPABASE_URL}/rest/v1/users?select=json_data"
    filename = "users_export.json"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS) as resp:
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