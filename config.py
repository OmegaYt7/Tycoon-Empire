import os
from dotenv import load_dotenv

# Загружаем переменные из .env (если есть, актуально для локального теста)
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# URL базы данных (Neon)
DATABASE_URL = os.getenv("DATABASE_URL")

# ID администраторов.
# В переменных окружения задавать строкой через запятую: 12345,67890
admin_env = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in admin_env.split(",") if x.strip().isdigit()]

# Если админов нет в env, оставляем пустой список или дефолтный (для страховки)
if not ADMIN_IDS:
    ADMIN_IDS = []
