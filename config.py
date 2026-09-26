import os
import re
from dotenv import load_dotenv

# Загружаем переменные из .env (если есть, актуально для локального теста)
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# URL базы данных (Neon)
DATABASE_URL = os.getenv("DATABASE_URL")

# ═══════════════════════════════════════════════════════════
# ID АДМИНИСТРАТОРОВ
# Поддерживаются ДВА способа одновременно (можно смешивать):
#
# 1) Одной переменной через запятую:
#    ADMIN_IDS = 12345,67890
#
# 2) Отдельной переменной на каждого админа (удобно на мобилке,
#    когда переменные добавляются по одной в отдельных окошках):
#    ADMIN_ID_1 = 12345
#    ADMIN_ID_2 = 67890
#    ADMIN_ID_3 = 111222
#    ...и так далее, номер в конце любой, порядок не важен.
# ═══════════════════════════════════════════════════════════
_admin_ids_set = set()

# Способ 1: старая переменная через запятую
_admin_env = os.getenv("ADMIN_IDS", "")
for _part in _admin_env.split(","):
    _part = _part.strip()
    if _part.isdigit():
        _admin_ids_set.add(int(_part))

# Способ 2: отдельные переменные ADMIN_ID_1, ADMIN_ID_2, ADMIN_ID1, ADMIN_ID2 и т.п.
_admin_id_pattern = re.compile(r"^ADMIN_ID_?\d+$", re.IGNORECASE)
for _key, _value in os.environ.items():
    if _admin_id_pattern.match(_key):
        _value = _value.strip()
        if _value.isdigit():
            _admin_ids_set.add(int(_value))

ADMIN_IDS = list(_admin_ids_set)

# ═══════════════════════════════════════════════════════════
# ТЕСТОВЫЙ РЕЖИМ
# Если включён (TEST_MODE=true в переменных окружения) — бот подключается
# к базе, читает из неё как обычно, но НИЧЕГО не записывает и не изменяет.
# Удобно, чтобы гонять тесты и не засорять/не портить реальные данные игроков.
# ═══════════════════════════════════════════════════════════
TEST_MODE = os.getenv("TEST_MODE", "false").strip().lower() in ("1", "true", "yes", "on")
