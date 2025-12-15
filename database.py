import aiohttp
import json
import logging
import asyncio
from datetime import datetime, timedelta

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
    "Prefer": "return=minimal",
    "Connection": "keep-alive"
}

# ═══════════════════════════════════════════════════════════
# ФУНКЦИИ БАЗЫ ДАННЫХ
# ═══════════════════════════════════════════════════════════

async def create_pool():
    global http_session
    if http_session is None:
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        http_session = aiohttp.ClientSession(headers=HEADERS, timeout=timeout)
        logging.warning("✅ Инициализация сессии Supabase...")

async def close_session():
    global http_session
    if http_session:
        await http_session.close()
        logging.warning("🔌 Сессия Supabase закрыта.")

async def create_table():
    pass

async def save_user(user_id, user_data):
    """Сохраняет одного пользователя. Мгновенная запись."""
    global http_session
    if http_session is None: await create_pool()
    
    url = f"{SUPABASE_URL}/rest/v1/users"
    headers = {"Prefer": "resolution=merge-duplicates"}
    
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
    
    try:
        async with http_session.post(url, headers=headers, json=[row]) as resp:
            if resp.status not in [200, 201, 204]:
                logging.error(f"Save User Error {user_id}: {resp.status}")
    except Exception as e:
        logging.error(f"Save User Exception {user_id}: {e}")

async def save_all_users(users_dict):
    """Массовое сохранение с задержкой, чтобы не получить бан API."""
    if not users_dict: return

    global http_session
    if http_session is None: await create_pool()

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
    headers = {"Prefer": "resolution=merge-duplicates"} 
    
    for i in range(0, len(data_list), chunk_size):
        chunk = data_list[i:i + chunk_size]
        try:
            async with http_session.post(url, headers=headers, json=chunk) as resp:
                if resp.status not in [200, 201, 204]:
                    logging.error(f"Bulk Save Error: {resp.status}")
            # Небольшая пауза между чанками, чтобы Supabase не ругался
            await asyncio.sleep(0.1) 
        except Exception as e:
            logging.error(f"Bulk Save Exception: {e}")

async def load_all_users():
    global http_session
    if http_session is None: return {}

    loaded_users = {}
    url = f"{SUPABASE_URL}/rest/v1/users?select=user_id,json_data"
    
    try:
        async with http_session.get(url) as resp:
            if resp.status == 200:
                rows = await resp.json()
                for row in rows:
                    user_id = row['user_id']
                    user_data = row['json_data']
                    if isinstance(user_data, str):
                        try: user_data = json.loads(user_data)
                        except: continue
                    loaded_users[int(user_id)] = user_data
                logging.warning(f"📥 Загружено {len(loaded_users)} пользователей.")
            else:
                logging.error(f"Load Error: {resp.status}")
    except Exception as e:
        logging.error(f"Load Exception: {e}")
        
    return loaded_users

async def export_users_to_json_file():
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
    except Exception:
        pass
    return None
