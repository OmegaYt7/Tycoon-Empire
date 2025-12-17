import aiohttp
import json
import logging
import asyncio
from datetime import datetime

# ═══════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ SUPABASE
# ═══════════════════════════════════════════════════════════

SUPABASE_URL = "https://tuvqserdclbgloysblrx.supabase.co"
SUPABASE_KEY = "sb_secret_bDIUtmYZ2Zx5Rz3EauEhlw_sbrmR6y9" 

http_session = None

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal, resolution=merge-duplicates"
}

async def get_session():
    """Возвращает живую сессию или создает новую."""
    global http_session
    if http_session is None or http_session.closed:
        # Устанавливаем тайм-ауты и коннектор для стабильности
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(enable_cleanup_closed=True)
        http_session = aiohttp.ClientSession(headers=HEADERS, timeout=timeout, connector=connector)
        logging.warning("✅ (Re)created Supabase session.")
    return http_session

async def reset_session():
    """Сбрасывает сессию принудительно (при ошибках сети)."""
    global http_session
    if http_session and not http_session.closed:
        await http_session.close()
    http_session = None
    logging.warning("🔌 Session reset due to error.")

async def perform_request(method, url, json_data=None):
    """
    Обертка для запросов с автоматическим ретраем (повторной попыткой)
    при разрыве соединения (Connection reset by peer).
    """
    for attempt in range(3):
        session = await get_session()
        try:
            if method == 'POST':
                async with session.post(url, json=json_data) as resp:
                    # Если успех - возвращаем статус
                    if resp.status in [200, 201, 204]:
                        return resp.status, None
                    # Если ошибка сервера (5xx) или лимит запросов (429) - пробуем снова
                    if resp.status >= 500 or resp.status == 429:
                        logging.warning(f"Server error {resp.status}, retrying...")
                        await asyncio.sleep(1)
                        continue
                    # Иначе возвращаем ошибку
                    return resp.status, await resp.text()
            elif method == 'GET':
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return 200, await resp.json()
                    return resp.status, None
                    
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            # Ловим разрывы соединения и ошибки DNS
            logging.error(f"Network error (attempt {attempt+1}/3): {e}")
            await reset_session() # Сбрасываем сессию, чтобы следующая попытка создала новую
            await asyncio.sleep(1)
            
    return 0, "Max retries exceeded"

async def save_user(user_id, user_data):
    """Сохраняет одного пользователя (Надежно)."""
    url = f"{SUPABASE_URL}/rest/v1/users"
    
    row = {
        "user_id": user_id,
        "username": user_data.get('username', 'Guest'),
        "nickname": user_data.get('nickname', 'Unknown'),
        "balance": user_data.get('balance', 0),
        "diamonds": user_data.get('diamonds', 0),
        "referrals": user_data.get('referrals', 0),
        "last_active": datetime.now().strftime("%Y-%m-%d"),
        "json_data": user_data
    }
    
    # Supabase требует список для upsert
    status, error = await perform_request('POST', url, json_data=[row])
    
    if status not in [200, 201, 204]:
        logging.error(f"❌ Failed to save user {user_id}: Status {status} | {error}")

async def save_all_users(users_dict):
    """Массовое сохранение (Надежно, с чанками)."""
    if not users_dict: return

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

    chunk_size = 50 
    url = f"{SUPABASE_URL}/rest/v1/users"
    
    # Разбиваем на пакеты по 50 штук
    for i in range(0, len(data_list), chunk_size):
        chunk = data_list[i:i + chunk_size]
        status, error = await perform_request('POST', url, json_data=chunk)
        
        if status not in [200, 201, 204]:
             logging.error(f"❌ Bulk save chunk failed: {status}")
        
        await asyncio.sleep(0.2)

async def load_all_users():
    """Загрузка всех пользователей."""
    url = f"{SUPABASE_URL}/rest/v1/users?select=user_id,json_data"
    
    status, data = await perform_request('GET', url)
    loaded_users = {}
    
    if status == 200 and data:
        for row in data:
            user_id = row['user_id']
            user_data = row['json_data']
            if isinstance(user_data, str):
                try: user_data = json.loads(user_data)
                except: continue
            loaded_users[int(user_id)] = user_data
        logging.warning(f"📥 Загружено {len(loaded_users)} пользователей.")
    else:
        logging.error(f"❌ Load Error: Status {status}")
        
    return loaded_users

async def export_users_to_json_file():
    """Экспорт базы в файл."""
    url = f"{SUPABASE_URL}/rest/v1/users?select=json_data"
    status, rows = await perform_request('GET', url)
    
    if status == 200 and rows:
        all_data = [row['json_data'] for row in rows]
        filename = "users_export.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
        return filename
    return None

async def close_session():
    """Закрытие сессии."""
    await reset_session()

# Если нужно создать таблицу, Supabase REST API не создает таблицы, это делается через SQL Editor в дашборде.
# Эта функция оставлена для совместимости, но она пустая.
async def create_table():
    pass
