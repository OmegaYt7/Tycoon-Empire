import asyncio
import logging
import random
import math
import os
import signal
import sys
from aiohttp import web
from datetime import datetime, timedelta, date
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ReactionTypeEmoji,
    FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError

# Импорты модулей
import config
import database
import promocodes
import admin_panel

# Настройка логирования
logging.basicConfig(level=logging.WARNING)

# Инициализация бота через config
if not config.BOT_TOKEN:
    sys.exit("❌ Ошибка: BOT_TOKEN не найден в переменных окружения.")

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class AdminEdit(StatesGroup):
    """Состояние: админ вводит число для изменения статы игрока (см. admin_panel.py)."""
    waiting_value = State()
users = {}

# ═══════════════════════════════════════════════════════════
# ФОНОВОЕ СОХРАНЕНИЕ
# ═══════════════════════════════════════════════════════════
async def autosave_loop():
    consecutive_failures = 0
    while True:
        await asyncio.sleep(90)  # Сохраняем каждые 1.5 минуты (было 10 минут — слишком редко)
        try:
            ok = await database.save_all_users(users)
        except Exception as e:
            ok = False
            logging.error(f"Ошибка автосохранения: {e}")

        if ok:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            # Если БД не пишется несколько раз подряд — сразу сигналим админам,
            # чтобы не узнавать о проблеме постфактум от игроков
            if consecutive_failures in (2, 5) or consecutive_failures % 20 == 0:
                for admin_id in config.ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"⚠️ Автосохранение не работает уже {consecutive_failures} раз(а) подряд! "
                            f"Проверь подключение к базе данных (DATABASE_URL)."
                        )
                    except Exception:
                        pass

# ═══════════════════════════════════════════════════════════
# СЕРВЕР ДЛЯ PELLA / RENDER (ОБЯЗАТЕЛЬНО!)
# Этот код нужен, чтобы хостинг не выключил бота.
# Он не влияет на Neon базу данных.
# ═══════════════════════════════════════════════════════════
async def handle_health_check(request):
    return web.Response(text="Bot is running!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Берем порт из переменной окружения Pella, или ставим 8080 по умолчанию
    port = int(os.environ.get("PORT", 8080))
    
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.warning(f"🌐 Web server started on port {port}")


# ═══════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ И ДАННЫЕ
# ═══════════════════════════════════════════════════════════

from game_data import (
    BASE_DIAMOND_CHANCE, ITEMS_PER_PAGE, NICKNAME_CHANGE_COST, NICKNAME_CHANGE_DAYS,
    XP_BASE_REQ, XP_MULTIPLIER, FUNNY_RESPONSES, funny_spam, DAILY_QUESTS_CONFIG,
    upgrades_info, buildings_info, main_quests_info,
)

def get_progress_bar(current, total, length=10):
    percent = current / total
    if percent > 1: percent = 1
    filled_length = int(length * percent)
    # Используем красивые символы ▰ и ▱
    bar = '▰' * filled_length + '▱' * (length - filled_length)
    return bar


# ═══════════════════════════════════════════════════════════
# РЕГИСТРАЦИЯ И ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════════

def recalculate_user_stats(user_id):
    if user_id not in users: return
    user = users[user_id]
    current_tap = 0
    for info in upgrades_info:
        if user["upgrades"].get(info["key"]) == 1:
            current_tap += info["bonus"]
    quest_tap_bonus = 0
    quest_chance_bonus = 0.0
    for q_key in user["completed_quests"]:
        quest = next((q for q in main_quests_info if q["key"] == q_key), None)
        if quest:
            quest_tap_bonus += quest.get("rew_tap", 0)
            quest_chance_bonus += quest.get("rew_chance", 0)
    user["tap_mult"] = current_tap + quest_tap_bonus
    user["diamond_chance_bonus"] = quest_chance_bonus
    calculate_passive(user)

def check_daily_reset(user):
    today = date.today().isoformat()
    if user.get("last_daily_done_date"):
        last_done = date.fromisoformat(user["last_daily_done_date"])
        yesterday = date.today() - timedelta(days=1)
        if last_done < yesterday:
            user["daily_streak"] = 0
    if user["daily_progress"]["date"] != today:
        user["daily_progress"] = {
            "date": today,
            "clicks": 0, "upgrades": 0, "claims": 0, "completed": [], "all_done": False, "notified": []
        }

_level_exp_cache = {1: XP_BASE_REQ}

def get_level_exp(level):
    """Сколько опыта нужно, чтобы перейти с текущего `level` на level+1.

    ВАЖНО (баг, который тут был раньше): множитель роста (1.4 -> 2.5)
    возводился в степень (level - 1), то есть одновременно рос и сам
    множитель, и степень, в которую он возводится. Это давало ДВОЙНУЮ
    экспоненту: уже на 20 уровне требовалось ~15 млн XP, на 30 — ~300 млрд,
    на 40 — ~44 квадриллиона. Дальше прокачаться было физически невозможно.

    Исправление: множитель применяется НАКОПИТЕЛЬНО (умножаем предыдущее
    требование на текущий множитель), как и описано в комментарии ниже —
    это именно линейный рост самого множителя, а не двойная экспонента.
    """
    if level in _level_exp_cache:
        return _level_exp_cache[level]

    # ЛИНЕЙНЫЙ РОСТ МНОЖИТЕЛЯ:
    # Каждый уровень добавляет +0.025 к множителю.
    # 1 ур = 1.4
    # 5 ур = 1.5
    # 7 ур = 1.55
    # 9 ур = 1.6
    # 11 ур = 1.65
    growth = (level - 1) * 0.025
    current_mult = min(XP_MULTIPLIER + growth, 2.5)  # ограничитель, чтобы не улетело в космос

    prev_req = get_level_exp(level - 1)
    req = int(prev_req * current_mult)
    _level_exp_cache[level] = req
    return req

async def add_xp(user_id, amount):
    if user_id not in users: return
    user = users[user_id]
    
    if "xp" not in user: user["xp"] = 0
    if "level" not in user: user["level"] = 1
    
    user["xp"] += amount
    leveled_up = False
    rewards_text = []
    
    while True:
        needed = get_level_exp(user["level"])
        if user["xp"] >= needed:
            user["xp"] -= needed
            user["level"] += 1
            leveled_up = True
            
            lvl = user["level"]
            if lvl == 2: coins_reward = 2000
            elif lvl == 3: coins_reward = 5000
            elif lvl == 4: coins_reward = 10000
            elif lvl == 5: coins_reward = 20000
            else:
                base_reward = 20000
                multiplier = 1.5
                coins_reward = base_reward * (multiplier ** (lvl - 5))
            coins_reward = int(round(coins_reward, -3))
            
            user["balance"] += coins_reward
            rewards_text.append(f"💰 {coins_reward:,} монет".replace(",", " "))
            
            diam_bonus = 0
            
            # Если уровень делится на 5 (5, 10, 15, 20...)
            if lvl % 5 == 0:
                diam_bonus = lvl  # Награда равна самому уровню (15 ур = 15 алмазов)
            
            if diam_bonus > 0:
                user["diamonds"] += diam_bonus
                user["total_diamonds_earned"] += diam_bonus
                rewards_text.append(f"💎 {diam_bonus} алмазов")
        else:
            break
            
    if leveled_up:
        # Сохраняем сразу
        await database.save_user(user_id, user)
        try:
            reward_str = "\n".join(rewards_text)
            await bot.send_message(
                user_id,
                f"🎉 <b>НОВЫЙ УРОВЕНЬ!</b>\n\n"
                f"🆙 Ты достиг <b>{user['level']} уровня</b>!\n"
                f"🎁 Награды:\n{reward_str}",
                parse_mode="HTML"
            )
        except: pass

def get_xp_bar(current, target, length=8):
    percent = min(current / target, 1.0)
    filled_length = int(length * percent)
    bar = "🟦" * filled_length + "⬜" * (length - filled_length)
    return f"{bar} {current}/{target} XP"

def generate_unique_id():
    while True:
        part1 = random.randint(100, 999)
        part2 = random.randint(100, 999)
        new_id = f"{part1} {part2}"
        is_unique = True
        for u in users.values():
            if u.get("custom_id") == new_id:
                is_unique = False
                break
        if is_unique:
            return new_id

def get_current_finger_info(user):
    recalculate_user_stats(list(users.keys())[list(users.values()).index(user)]) 
    
    current_finger_name = upgrades_info[0]["name"]
    current_finger_bonus = user['tap_mult']
    
    for info in reversed(upgrades_info):
        if user["upgrades"].get(info["key"]) == 1:
            current_finger_name = info["name"]
            break
    return current_finger_name, current_finger_bonus

# --- МЕНЮ ---
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Профиль"), KeyboardButton(text="🏪 Магазин")],
        [KeyboardButton(text="🏗️ Сооружения"), KeyboardButton(text="📝 Задания")],
        [KeyboardButton(text="🏆 Топ-10"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="💰 Тапать монеты")]
    ], resize_keyboard=True, one_time_keyboard=False)

def profile_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Рефералка")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True, one_time_keyboard=False)

def settings_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Сменить ник"), KeyboardButton(text="🔒 Конфиденциальность")],
        [KeyboardButton(text="ℹ️ О игре"), KeyboardButton(text="👮‍♂️ Админ панель")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True, one_time_keyboard=False)

def cancel_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True, one_time_keyboard=True)

def tap_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💥 ТАПАЙ СЮДА! 💥", callback_data="tap")]])

async def update_passive_income(user_id: int):
    if user_id not in users: return
    user = users[user_id]
    
    recalculate_user_stats(user_id)
    
    now = datetime.now().timestamp()
    for info in buildings_info:
        key = info["key"]
        level = user["buildings_levels"].get(key, 0)
        
        if key not in user["buildings_last_update"]:
            user["buildings_last_update"][key] = now
            
        if level > 0:
            last_upd = user["buildings_last_update"][key]
            if last_upd > 0:
                minutes_passed = (now - last_upd) / 60
                full_minutes = int(minutes_passed)
                
                bonus = info.get("upgrade_income_bonus", info["base_income"])
                income_per_min = info["base_income"] + (bonus * (level - 1))
                
                earned = income_per_min * full_minutes
                
                current_accum = user["buildings_accumulated"].get(key, 0)
                capacity = info["base_capacity"] + info["upgrade_capacity_bonus"] * (level - 1)
                new_accum = min(current_accum + earned, capacity)
                
                user["buildings_accumulated"][key] = new_accum
                if full_minutes > 0:
                    user["buildings_last_update"][key] += full_minutes * 60

def calculate_passive(user):
    passive = 0
    for info in buildings_info:
        level = user["buildings_levels"].get(info["key"], 0)
        if level > 0:
            bonus = info.get("upgrade_income_bonus", info["base_income"])
            income_val = info["base_income"] + (bonus * (level - 1))
            passive += income_val
    user["passive_per_minute"] = passive

def get_server_tz_label():
    """Возвращает смещение часового пояса сервера, например 'UTC+00:00'.
    Ежедневный сброс заданий происходит в полночь ИМЕННО по этому времени —
    у игроков в разных часовых поясах локальная полночь будет отличаться,
    поэтому важно показывать это явно, а не просто "00:00"."""
    offset = datetime.now().astimezone().strftime('%z')  # напр. '+0000' или '+0300'
    if not offset:
        return "UTC"
    sign = offset[0]
    hours = offset[1:3]
    minutes = offset[3:5]
    return f"UTC{sign}{hours}:{minutes}"

def get_progress_bar(current, target, length=10):
    percent = min(current / target, 1.0)
    filled_length = int(length * percent)
    bar = "🟩" * filled_length + "⬜" * (length - filled_length)
    return f"{bar} {int(percent * 100)}%"

# --- УВЕДОМЛЕНИЯ О ЗАДАНИЯХ ---

async def check_quest_notifications(message: Message, user_id: int):
    user = users[user_id]
    if "notified_quests" not in user:
        user["notified_quests"] = []
        
    for quest in main_quests_info:
        key = quest["key"]
        if key in user["completed_quests"]: continue
        if key in user["notified_quests"]: continue

        current_val = 0
        target = quest["target"]
        if quest["type"] == "balance": current_val = user["balance"]
        elif quest["type"] == "buildings_count": current_val = sum(1 for lvl in user["buildings_levels"].values() if lvl > 0)
        elif quest["type"] == "upgrades_count": current_val = sum(user["upgrades"].values())
        elif quest["type"] == "clicks": current_val = user["total_clicks"]
        elif quest["type"] == "income": calculate_passive(user); current_val = user["passive_per_minute"]
        elif quest["type"] == "spent": current_val = user["total_spent"]
        elif quest["type"] == "earned_diamonds": current_val = user["total_diamonds_earned"]
        
        if current_val >= target:
            try:
                await bot.send_message(
                    user_id, 
                    f"🎉 **ЗАДАНИЕ ВЫПОЛНЕНО!**\n\n"
                    f"✅ {quest['name']}\n"
                    f"Зайди в 📝 Задания, чтобы забрать награду!"
                )
                user["notified_quests"].append(key)
            except TelegramForbiddenError:
                # Игрок заблокировал бота — уведомлять некого, помечаем,
                # чтобы не пытаться снова на каждом действии.
                user["notified_quests"].append(key)
            except Exception as e:
                # Временная ошибка (сеть, rate limit и т.п.) — НЕ помечаем
                # уведомление отправленным, чтобы попробовать снова при
                # следующем действии игрока вместо потери уведомления навсегда.
                logging.warning(f"Не удалось отправить уведомление о задании {key} игроку {user_id}: {e}")

async def check_daily_notifications(user_id: int):
    user = users[user_id]
    if "notified" not in user["daily_progress"]:
        user["daily_progress"]["notified"] = []
        
    for quest in DAILY_QUESTS_CONFIG:
        key = quest["key"]
        if key in user["daily_progress"]["notified"]: continue
        if key in user["daily_progress"]["completed"]: continue
        
        current = 0
        if key == "daily_clicks": current = user["daily_progress"]["clicks"]
        elif key == "daily_upgrade": current = user["daily_progress"]["upgrades"]
        elif key == "daily_claim": current = user["daily_progress"]["claims"]
        
        if current >= quest["target"]:
            try:
                await bot.send_message(
                    user_id,
                    f"🎉 **ЕЖЕДНЕВНОЕ ЗАДАНИЕ ГОТОВО!**\n\n"
                    f"✅ {quest['name']}\n"
                    f"Забери награду в разделе 📅 Ежедневные задания!"
                )
                user["daily_progress"]["notified"].append(key)
            except TelegramForbiddenError:
                user["daily_progress"]["notified"].append(key)
            except Exception as e:
                logging.warning(f"Не удалось отправить уведомление о ежедневном задании {key} игроку {user_id}: {e}")

async def show_main_interface(message: Message, user_id: int):
    user = users[user_id]
    recalculate_user_stats(user_id)
    finger_name, finger_bonus = get_current_finger_info(user)
    safe_nick = str(user['nickname']).replace("<", "&lt;").replace(">", "&gt;")
    bonus_fmt = f"{finger_bonus:,}".replace(",", " ")
    
    text = (f"🌟<b>Добро пожаловать в Tycoon Empire!</b>🌟\n\n"
            f"Ты — будущий миллиардер! Начинай тапать и строй свою империю прямо сейчас!\n\n"
            f"🆔 Твой ID: <code>{user['custom_id']}</code>\n"
            f"👤 Ник: <b>{safe_nick}</b>\n"
            f"💰 Баланс: {user['balance']:,} монет\n"
            f"💎 Алмазы: {user['diamonds']:,}\n"
            f"🖐️ Текущий палец: {finger_name} (+{bonus_fmt} за тап)\n\n"
            f"Жми большую кнопку ниже и начинай богатеть! 💸").replace(",", " ")
    
    sent = await message.answer(text, reply_markup=tap_button(), parse_mode="HTML")
    user["tap_message_id"] = sent.message_id
    await message.answer("🚀 Главное меню:", reply_markup=main_menu())

# ═══════════════════════════════════════════════════════════
# /start и РЕГИСТРАЦИЯ НИКА
# ═══════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    
    # ИСПРАВЛЕНИЕ: Убрали вызов database.create_table(), так как это делается при запуске бота
    
    if user_id not in users:
        upgrades = {info["key"]: 0 for info in upgrades_info}
        upgrades["wooden_finger"] = 1
        buildings_levels = {info["key"]: 0 for info in buildings_info}
        buildings_accumulated = {info["key"]: 0 for info in buildings_info}
        buildings_last_update = {info["key"]: 0.0 for info in buildings_info}
        custom_id = generate_unique_id()
        
        users[user_id] = {
            "username": message.from_user.username or "User",
            "nickname": None,
            "custom_id": custom_id,
            "registration_date": date.today().isoformat(),
            "last_active": date.today().isoformat(),
            "last_nick_change": None, 
            "state": "registering_nickname",
            "privacy_enabled": True, 
            "balance": 0, 
            "diamonds": 0,
            "total_diamonds_earned": 0,
            "diamond_chance_bonus": 0.0,
            "tap_mult": 1,
            "passive_per_minute": 0,
            "referrals": 0,
            "total_clicks": 0,
            "total_spent": 0,
            "xp": 0,
            "level": 1,
            "upgrades": upgrades,
            "buildings_levels": buildings_levels,
            "buildings_accumulated": buildings_accumulated,
            "buildings_last_update": buildings_last_update,
            "completed_quests": [],
            "notified_quests": [],
            "daily_streak": 0,
            "last_daily_done_date": None,
            "daily_progress": {
                "date": date.today().isoformat(),
                "clicks": 0, "upgrades": 0, "claims": 0, "completed": [], "all_done": False, "notified": []
            },
            "tap_message_id": None,
            "shop_message_id": None,
            "buildings_message_id": None,
            "last_tap_time": 0.0
        }
        
        args = message.text.split()
        if len(args) > 1:
            try:
                ref_id = int(args[1])
                if ref_id != user_id and ref_id in users:
                    users[ref_id]["referrals"] += 1
                    users[ref_id]["balance"] += 1000
                    users[ref_id]["diamonds"] += 1
                    users[user_id]["balance"] += 500
                    try:
                        await bot.send_message(ref_id, f"🎉 По вашей ссылке зарегистрировался новый игрок!\nНаграда: +1000 монет и +1 алмаз 💎")
                    except:
                        pass
                    await message.answer("🎉 Ты пришёл по приглашению!\nБонус: +500 монет! 🔥")
            except:
                pass

        welcome_text = (
            "👋 **Привет, будущий магнат!**\n\n"
            "Ты попал в мир **Tycoon Empire**, где тебе предстоит:\n"
            "👆 Тапать и зарабатывать монеты\n"
            "🖐️ Покупать новые пальцы для мощного тапа\n"
            "🏗️ Строить здания и получать пассивный доход\n"
            "💎 Искать редкие алмазы\n"
            "🏆 Стать самым богатым в топе!\n\n"
            "Для начала, как нам тебя называть?\n"
            "Напиши свой **Никнейм** (макс. 15 символов, можно смайлики)."
        )
        
        await message.answer(welcome_text, reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
        return

    if users[user_id].get("state") == "registering_nickname":
        await message.answer("Пожалуйста, введи свой никнейм для продолжения.")
        return

    users[user_id]["last_active"] = date.today().isoformat()
    recalculate_user_stats(user_id)
    await show_main_interface(message, user_id)

# ═══════════════════════════════════════════════════════════
# СИСТЕМА ПРОМОКОДОВ
# ═══════════════════════════════════════════════════════════
@dp.message(Command("promo"))
async def promo_handler(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("❌ Ты кто вообще? Жми /start")
        return

    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        try:
            emoji = random.choice(promocodes.REACTION_LIST_HELP)
            await message.react([ReactionTypeEmoji(emoji=emoji)])
        except: pass
        await message.answer(promocodes.HELP_MESSAGE, parse_mode="HTML")
        return

    code = args[1].strip()
    user = users[user_id]
    success, response_text, reaction_emoji = promocodes.activate_promo(user, code)
    
    try:
        await message.react([ReactionTypeEmoji(emoji=reaction_emoji)])
    except: pass

    await message.answer(response_text, parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
# АДМИН: ПРИЁМ ЧИСЛА ДЛЯ ИЗМЕНЕНИЯ СТАТЫ ИГРОКА
# Зарегистрирован ДО общего @dp.message(F.text), чтобы перехватывать
# ввод раньше, пока админ находится в состоянии AdminEdit.waiting_value.
# ═══════════════════════════════════════════════════════════
@dp.message(AdminEdit.waiting_value)
async def admin_edit_receive_value(message: Message, state: FSMContext):
    if not admin_panel.is_admin(message.from_user.id):
        return

    raw = (message.text or "").strip().replace(" ", "")
    try:
        value = int(raw)
    except (ValueError, TypeError):
        await message.answer("⚠️ Нужно целое число (можно отрицательное, например -500). Попробуй ещё раз или нажми «🔙 Отмена» в сообщении выше.")
        return

    data = await state.get_data()
    field = data.get("field")
    target_id = data.get("target_id")
    page = data.get("page")

    target_user = users.get(target_id)
    field_info = admin_panel.EDITABLE_FIELDS.get(field)

    if not target_user or not field_info:
        await message.answer("⚠️ Игрок или стата больше не найдены.")
        await state.clear()
        return

    old_value = target_user.get(field, 0)

    if field_info["mode"] == "add":
        new_value = old_value + value
    else:
        new_value = value
    target_user[field] = new_value

    await database.save_user(target_id, target_user)
    recalculate_user_stats(target_id)
    await state.clear()

    old_str = f"{old_value:,}".replace(",", " ")
    new_str = f"{new_value:,}".replace(",", " ")
    await message.answer(f"✅ {field_info['label']}: {old_str} → {new_str}")

    # Уведомляем игрока ТОЛЬКО при начислении (баланс/алмазы), не при прямой правке статы
    if field_info["mode"] == "add" and value != 0:
        try:
            verb = "начислено" if value > 0 else "списано"
            amount_str = f"{abs(value):,}".replace(",", " ")
            await bot.send_message(
                target_id,
                f"🎁 <b>Тебе {verb}:</b> {field_info['label']} — {amount_str}\n"
                f"Текущее значение: {new_str}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    # Показываем обновлённый профиль
    passive_income = target_user["passive_per_minute"]
    finger_name, _ = get_current_finger_info(target_user)
    profile_text = admin_panel.get_user_profile_text(target_user, target_id, passive_income, finger_name)
    profile_kb = admin_panel.get_user_profile_kb(target_id, page)
    await message.answer(profile_text, reply_markup=profile_kb, parse_mode="HTML")

@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id

    if user_id not in users:
        await message.answer("⚠️ Бот был перезагружен. Введите /start, чтобы продолжить.")
        return
    
    if user_id in users:
        current_username = message.from_user.username
        if users[user_id].get("username") != current_username:
            users[user_id]["username"] = current_username
        users[user_id]["last_active"] = date.today().isoformat()
        recalculate_user_stats(user_id)

    if user_id in users and users[user_id].get("state") == "registering_nickname":
        user = users[user_id]
        text = message.text.strip()
        if len(text) > 15:
            await message.answer("❌ Ник слишком длинный! Максимум 15 символов.\nПопробуй снова.")
            return
        
        user["nickname"] = text
        safe_name = str(text).replace("<", "&lt;").replace(">", "&gt;")
        await admin_panel.notify_new_player(bot, user)
        await message.answer(f"✅ Отличный ник: <b>{safe_name}</b>", reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
        user["state"] = "active"
        recalculate_user_stats(user_id)
        await show_main_interface(message, user_id)
        return
    
    if user_id in users and users[user_id].get("state") == "changing_nickname":
        if message.text == "❌ Отмена":
            users[user_id]["state"] = "active"
            await message.answer("⚙️ **Меню настроек**", reply_markup=settings_menu(), parse_mode="Markdown")
            return

        user = users[user_id]
        new_nick = message.text.strip()

        if len(new_nick) > 15:
             await message.answer("❌ Ник слишком длинный!", reply_markup=cancel_menu())
             return
        if user["diamonds"] < NICKNAME_CHANGE_COST:
            user["state"] = "active"
            await message.answer("❌ Ошибка: Не хватает алмазов.", reply_markup=settings_menu())
            return
            
        user["diamonds"] -= NICKNAME_CHANGE_COST
        user["nickname"] = new_nick
        user["last_nick_change"] = date.today().isoformat()
        user["state"] = "active"
        
        safe_nick = str(new_nick).replace("<", "&lt;").replace(">", "&gt;")
        cost_str = f"{NICKNAME_CHANGE_COST:,}".replace(",", " ")
        await message.answer(f"✅ Ник успешно изменён на <b>{safe_nick}</b>!\nСписано: {cost_str} 💎", parse_mode="HTML", reply_markup=settings_menu())
        return

    if message.text == "💰 Тапать монеты": await show_tap(message)
    elif message.text == "📊 Профиль": await profile(message)
    elif message.text == "🏪 Магазин": await shop(message)
    elif message.text == "🏗️ Сооружения": await buildings_shop(message)
    elif message.text == "📝 Задания": await quests_menu(message)
    elif message.text == "👥 Рефералка": await referral(message)
    elif message.text == "🏆 Топ-10": await top10_menu(message)
    elif message.text == "⚙️ Настройки": await message.answer("⚙️ **Меню настроек**", reply_markup=settings_menu(), parse_mode="Markdown")
    elif message.text == "🔙 Назад": await message.answer("🚀 Главное меню:", reply_markup=main_menu())
    elif message.text == "🔒 Конфиденциальность": await privacy_settings(message)
    elif message.text == "ℹ️ О игре": await about_game(message)
    elif message.text == "📝 Сменить ник": await request_nick_change(message)
    elif message.text == "👮‍♂️ Админ панель": await open_admin_panel(message)
    elif message.text == "👥 Список игроков":
        if admin_panel.is_admin(user_id):
            kb = admin_panel.get_users_keyboard(users, page=0)
            await message.answer("👥 **Список игроков:**", reply_markup=kb)
    elif message.text == "📢 Оповещение":
        if admin_panel.is_admin(user_id):
            await message.answer("📡 **Центр оповещений**\nВыберите тип сообщения:", reply_markup=admin_panel.broadcast_type_kb(), parse_mode="Markdown")
    elif message.text == "💾 Выгрузка":
        if admin_panel.is_admin(user_id):
            await message.answer("⚠️ **Выгрузка базы данных**\n\nСкачать файл данных?", reply_markup=admin_panel.export_confirm_kb(), parse_mode="Markdown")
    else:
        try:
            await message.react([ReactionTypeEmoji(emoji="🤔")])
            await message.reply(random.choice(FUNNY_RESPONSES))
        except: pass

@dp.callback_query(F.data == "admin_export_confirm")
async def export_data_handler(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    
    await callback.message.edit_text("⏳ **Начинаю выгрузку...**")
    
    try:
        await database.save_all_users(users)
        filename = await database.export_users_to_json_file()
        file = FSInputFile(filename)
        await bot.send_document(callback.from_user.id, file, caption="✅ **Полная база данных игроков**")
        os.remove(filename)
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка выгрузки: {e}")

# --- ОБРАБОТЧИКИ РАССЫЛКИ ---
@dp.callback_query(F.data.startswith("broadcast_setup_"))
async def broadcast_setup_handler(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    msg_type = callback.data.replace("broadcast_setup_", "")
    text = "⏳ **Выберите время до начала события:**"
    await callback.message.edit_text(text, reply_markup=admin_panel.broadcast_time_kb(msg_type), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("broadcast_send_"))
async def broadcast_send_handler(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    msg_type = parts[2]
    
    if msg_type == "finished":
        send_text = admin_panel.get_broadcast_text("finished")
        await callback.message.edit_text("🚀 **Отправка сообщения о завершении...**", parse_mode="Markdown")
        count = await admin_panel.perform_broadcast(bot, users, send_text)
        await callback.message.answer(f"✅ **Оповещение отправлено!**\nПолучили: {count} чел.", parse_mode="Markdown")
        return

    minutes = parts[3]
    send_text = admin_panel.get_broadcast_text(msg_type, minutes)
    await callback.message.edit_text("⏳ **Рассылка запущена...**\nБот не будет отвечать некоторое время.", parse_mode="Markdown")
    count = await admin_panel.perform_broadcast(bot, users, send_text)
    await callback.message.answer(f"✅ **Рассылка завершена!**\nПолучили: {count} чел.", parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════
# СМЕНА НИКА
# ═══════════════════════════════════════════════════════════
async def request_nick_change(message: Message):
    user = users[message.from_user.id]
    if user.get("last_nick_change"):
        last_change = date.fromisoformat(user["last_nick_change"])
        days_passed = (date.today() - last_change).days
        if days_passed < NICKNAME_CHANGE_DAYS:
            days_left = NICKNAME_CHANGE_DAYS - days_passed
            await message.answer(f"⏳ Смена ника доступна через {days_left} дн.")
            return

    cost_str = f"{NICKNAME_CHANGE_COST:,}".replace(",", " ")
    text = (
        "📝 **СМЕНА НИКА**\n\n"
        f"Стоимость: **{cost_str} 💎**\n"
        f"Кулдаун: **{NICKNAME_CHANGE_DAYS} дней**\n\n"
        "Вы уверены, что хотите сменить ник?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сменить", callback_data="confirm_nick_change")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "confirm_nick_change")
async def confirm_nick_change_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    cost_str = f"{NICKNAME_CHANGE_COST:,}".replace(",", " ")
    
    if user["diamonds"] < NICKNAME_CHANGE_COST:
        await callback.answer(f"❌ Не хватает алмазов!\nНужно: {cost_str} 💎", show_alert=True)
        return
        
    user["state"] = "changing_nickname"
    await callback.message.answer("✍️ **Введите новый ник:**\n(Максимум 15 символов)", reply_markup=cancel_menu(), parse_mode="Markdown")
    await callback.answer()

# ═══════════════════════════════════════════════════════════
# АДМИН ПАНЕЛЬ
# ═══════════════════════════════════════════════════════════
async def open_admin_panel(message: Message):
    user_id = message.from_user.id
    if not admin_panel.is_admin(user_id):
        await message.answer("⛔ **Вход только для администрации!**", parse_mode="Markdown")
        return
    await message.answer("👮‍♂️ **Панель Администратора**", reply_markup=admin_panel.admin_main_menu())

@dp.callback_query(F.data.startswith("admin_page_"))
async def admin_pagination(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not admin_panel.is_admin(user_id): return
    page = int(callback.data.replace("admin_page_", ""))
    kb = admin_panel.get_users_keyboard(users, page=page)
    try: await callback.message.edit_reply_markup(reply_markup=kb)
    except: pass

@dp.callback_query(F.data.startswith("admin_view_"))
async def admin_view_user(callback: CallbackQuery, state: FSMContext = None):
    user_id = callback.from_user.id
    if not admin_panel.is_admin(user_id): return
    if state:
        # Сбрасываем незавершённый ввод статы, если админ вернулся назад через эту кнопку
        await state.clear()
    parts = callback.data.split("_")
    target_tg_id = int(parts[2])
    page = int(parts[3])
    
    target_user = users.get(target_tg_id)
    if not target_user:
        await callback.answer("Игрок не найден", show_alert=True)
        return
    
    recalculate_user_stats(target_tg_id)
    passive_income = target_user["passive_per_minute"]
    finger_name, _ = get_current_finger_info(target_user)
            
    text = admin_panel.get_user_profile_text(target_user, target_tg_id, passive_income, finger_name)
    kb = admin_panel.get_user_profile_kb(target_tg_id, page)
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_editmenu_"))
async def admin_edit_menu(callback: CallbackQuery, state: FSMContext):
    if not admin_panel.is_admin(callback.from_user.id): return
    await state.clear()
    parts = callback.data.split("_")
    target_id = int(parts[2])
    page = int(parts[3])

    if target_id not in users:
        await callback.answer("Игрок не найден", show_alert=True)
        return

    kb = admin_panel.get_edit_stats_menu_kb(target_id, page)
    await callback.message.edit_text("✏️ <b>Какую стату изменить?</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("aeditf|"))
async def admin_edit_field_prompt(callback: CallbackQuery, state: FSMContext):
    if not admin_panel.is_admin(callback.from_user.id): return
    _, field, target_id_str, page_str = callback.data.split("|")
    target_id = int(target_id_str)
    page = int(page_str)

    target_user = users.get(target_id)
    if not target_user or field not in admin_panel.EDITABLE_FIELDS:
        await callback.answer("Игрок или стата не найдены", show_alert=True)
        return

    current_value = target_user.get(field, 0)
    text = admin_panel.get_edit_prompt_text(field, target_id, current_value)
    kb = admin_panel.get_edit_cancel_kb(target_id, page)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    await state.set_state(AdminEdit.waiting_value)
    await state.update_data(field=field, target_id=target_id, page=page)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_wipe_ask_"))
async def admin_wipe_ask(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    target_id = int(parts[3])
    page = int(parts[4])
    
    text = admin_panel.get_wipe_confirm_text(target_id)
    kb = admin_panel.get_wipe_confirm_kb(target_id, page)
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("admin_wipe_confirm_"))
async def admin_wipe_confirm(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    target_id = int(parts[3])
    page = int(parts[4])
    
    upgrade_keys = [info["key"] for info in upgrades_info]
    building_keys = [info["key"] for info in buildings_info]
    
    success = await admin_panel.perform_user_wipe(users, target_id, upgrade_keys, building_keys)
    
    if not success:
        await callback.answer("Ошибка: Игрок не найден!", show_alert=True)
        return
    
    await database.save_user(target_id, users[target_id])

    recalculate_user_stats(target_id)
    await callback.answer("✅ Данные игрока полностью стерты!", show_alert=True)
    new_data = f"admin_view_{target_id}_{page}"
    new_callback = callback.model_copy(update={'data': new_data})
    await admin_view_user(new_callback)

@dp.callback_query(F.data.startswith("admin_delete_ask_"))
async def admin_delete_ask(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    target_id = int(parts[3])
    page = int(parts[4])

    if target_id not in users:
        await callback.answer("Игрок не найден", show_alert=True)
        return

    text = admin_panel.get_delete_confirm_text(target_id)
    kb = admin_panel.get_delete_confirm_kb(target_id, page)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("admin_delete_confirm_"))
async def admin_delete_confirm(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    target_id = int(parts[3])
    page = int(parts[4])

    if target_id not in users:
        await callback.answer("Игрок не найден", show_alert=True)
        return

    # Удаляем из памяти и из базы данных
    del users[target_id]
    db_ok = await database.delete_user(target_id)

    if db_ok:
        await callback.answer("☠️ Игрок удалён навсегда (из бота и из базы).", show_alert=True)
    else:
        await callback.answer("⚠️ Удалено из бота, но при удалении из базы данных произошла ошибка. Проверь логи.", show_alert=True)

    # Возвращаемся к списку игроков, т.к. открывать удалённый профиль уже нельзя.
    # (не используем admin_pagination напрямую, т.к. она только меняет клавиатуру,
    # а тут ещё нужно вернуть текст со "Список игроков" вместо текста подтверждения)
    kb = admin_panel.get_users_keyboard(users, page=page)
    try:
        await callback.message.edit_text("👥 **Список игроков:**", reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════
async def privacy_settings(message: Message):
    user = users[message.from_user.id]
    status = "✅ Включено" if user.get("privacy_enabled", True) else "❌ Отключено"
    text = (f"🔒 **Настройки конфиденциальности**\n\n"
            f"Этот параметр отвечает за то, будет ли ваш ник в Топ-10 кликабельным (ссылка на профиль Телеграм).\n\n"
            f"👉 **Внимание:** Кликабельность ссылки также зависит от ваших настроек Telegram.\n"
            f"Если в **Конфиденциальность -> Пересылка сообщений** у вас стоит 'Никто' или 'Мои контакты', "
            f"то незнакомые люди не смогут открыть ваш профиль, даже если здесь стоит ✅.\n\n"
            f"Текущий статус: **{status}**")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Включить", callback_data="privacy_on"),
         InlineKeyboardButton(text="❌ Отключить", callback_data="privacy_off")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.in_(["privacy_on", "privacy_off"]))
async def privacy_toggle(callback: CallbackQuery):
    user = users[callback.from_user.id]
    enable = callback.data == "privacy_on"
    user["privacy_enabled"] = enable
    status_text = "Включено" if enable else "Отключено"
    await callback.answer(f"Конфиденциальность: {status_text}", show_alert=False)
    status_icon = "✅ Включено" if enable else "❌ Отключено"
    text = (f"🔒 **Настройки конфиденциальности**\n\n"
            f"Этот параметр отвечает за то, будет ли ваш ник в Топ-10 кликабельным (ссылка на профиль Телеграм).\n\n"
            f"👉 **Внимание:** Кликабельность ссылки также зависит от ваших настроек Telegram.\n"
            f"Если в **Конфиденциальность -> Пересылка сообщений** у вас стоит 'Никто' или 'Мои контакты', "
            f"то незнакомые люди не смогут открыть ваш профиль, даже если здесь стоит ✅.\n\n"
            f"Текущий статус: **{status_icon}**")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Включить", callback_data="privacy_on"),
         InlineKeyboardButton(text="❌ Отключить", callback_data="privacy_off")]
    ])
    try: await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except: pass

async def about_game(message: Message):
    text = (
        "ℹ️ **О ИГРЕ: Tycoon Empire**\n\n"
        "Строй свою империю, кликай и побеждай!\n\n"
        "📢 **Наш канал:** [TycoonEmpireOfficial](https://t.me/TycoonEmpireOfficial)\n"
        "📄 **Вся информация:** [Читать тут](https://teletype.in/@shadowdragonr/TycoonEmpireBot)\n\n"
        "✍️ **Поддержка / Предложения:**\n"
        "Нашли ошибку? Есть идея? Пишите: [ShadowDragonR](https://t.me/ShadowDragonR)"
    )
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

# ═══════════════════════════════════════════════════════════
# ТАП
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "tap")
async def tap(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in users: return
    await update_passive_income(user_id)
    user = users[user_id]
    check_daily_reset(user)
    
    now = datetime.now().timestamp()
    if now - user["last_tap_time"] < 0.5:
        await callback.answer(random.choice(funny_spam), show_alert=False)
        return
    earn = user["tap_mult"]
    user["balance"] += earn
    user["total_clicks"] += 1
    user["daily_progress"]["clicks"] += 1
    user["last_tap_time"] = now
    
    current_chance = BASE_DIAMOND_CHANCE + user["diamond_chance_bonus"]
    diamond_alert = ""
    if random.random() < current_chance:
        user["diamonds"] += 1
        user["total_diamonds_earned"] += 1
        diamond_alert = "\n💎 ВЫПАЛ АЛМАЗ! 💎"
    
    msg_earn = f"💥 +{earn:,} монет!".replace(",", " ") + diamond_alert
    await callback.answer(msg_earn, show_alert=bool(diamond_alert))
    await check_quest_notifications(callback.message, user_id)
    await check_daily_notifications(user_id)
    
    finger_name, _ = get_current_finger_info(user)
    bonus_fmt = f"{earn:,}".replace(",", " ")
    text = (f"🌟<b>Добро пожаловать в Tycoon Empire!</b>🌟\n\n"
            f"💰 Баланс: {user['balance']:,} монет\n"
            f"💎 Алмазы: {user['diamonds']:,}\n"
            f"🖐️ За тап: +{bonus_fmt} монет\n"
            f"🖐️ Текущий палец: {finger_name}\n\n"
            f"Ты становишься всё ближе к вершине! 🔥\n"
            f"Продолжай тапать!").replace(",", " ")
    try: await callback.message.edit_text(text, reply_markup=tap_button(), parse_mode="HTML")
    except: pass

async def show_tap(message: Message):
    user_id = message.from_user.id
    if user_id not in users: return
    await update_passive_income(user_id)
    user = users[user_id]
    recalculate_user_stats(user_id)
    finger_name, finger_bonus = get_current_finger_info(user)
    bonus_fmt = f"{finger_bonus:,}".replace(",", " ")
    text = (f"🌟<b>Добро пожаловать в Tycoon Empire!</b>🌟\n\n"
            f"💰 Баланс: {user['balance']:,} монет\n"
            f"💎 Алмазы: {user['diamonds']:,}\n"
            f"🖐️ За тап: +{bonus_fmt} монет\n"
            f"🖐️ Текущий палец: {finger_name}\n\n"
            f"Жми большую кнопку и богатей! 💸").replace(",", " ")
    if user["tap_message_id"]:
        try:
            await bot.edit_message_text(text, message.chat.id, user["tap_message_id"], reply_markup=tap_button(), parse_mode="HTML")
            return
        except: pass
    sent = await message.answer(text, reply_markup=tap_button(), parse_mode="HTML")
    user["tap_message_id"] = sent.message_id

# ═══════════════════════════════════════════════════════════
# СИСТЕМА ЗАДАНИЙ
# ═══════════════════════════════════════════════════════════
async def quests_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ежедневные задания", callback_data="quests_daily")],
        [InlineKeyboardButton(text="📜 Основные задания", callback_data="quests_main")]
    ])
    await message.answer("🎯 **Центр заданий**\n\nВыполняй задания и получай монеты и алмазы!", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "quests_daily")
async def quests_daily(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    check_daily_reset(user)
    if len(user["daily_progress"]["completed"]) >= 3:
        now = datetime.now()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        delta = tomorrow - now
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_left = f"{hours:02}:{minutes:02}:{seconds:02}"
        tz_label = get_server_tz_label()
        await callback.answer(
            f"✅ Всё выполнено!\nОбновление через: {time_left}\n🕒 Сброс в 00:00 ({tz_label})",
            show_alert=True
        )
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for q in DAILY_QUESTS_CONFIG:
        key = q["key"]
        if key in user["daily_progress"]["completed"]: continue
        name_text = f"{q['name']} (+{q['reward_diamonds']} 💎)"
        kb.inline_keyboard.append([InlineKeyboardButton(text=name_text, callback_data=f"view_daily_{key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="quests_back_root")])
    streak_fmt = f"{user['daily_streak']:,}".replace(",", " ")
    tz_label = get_server_tz_label()
    text = (f"📅 **Ежедневные задания**\n🔥 Серия: **{streak_fmt} дн.**\n🕒 Сброс в 00:00 ({tz_label}) — время сервера")
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_daily_"))
async def view_daily(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    key = callback.data.replace("view_daily_", "", 1)
    quest = next((q for q in DAILY_QUESTS_CONFIG if q["key"] == key), None)
    if not quest: return
    current = 0
    if key == "daily_clicks": current = user["daily_progress"]["clicks"]
    elif key == "daily_upgrade": current = user["daily_progress"]["upgrades"]
    elif key == "daily_claim": current = user["daily_progress"]["claims"]
    target = quest["target"]
    progress_bar = get_progress_bar(current, target)
    text = (f"📅 **{quest['name']}**\nℹ️ {quest['desc']}\n🎁 Награда: **{quest['reward_diamonds']} 💎**\n\n📊 Прогресс:\n{current} / {target}\n{progress_bar}")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if current >= target:
        kb.inline_keyboard.append([InlineKeyboardButton(text="✅ ЗАБРАТЬ", callback_data=f"claim_daily_{key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="quests_daily")])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("claim_daily_"))
async def claim_daily(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    key = callback.data.replace("claim_daily_", "", 1)
    if key in user["daily_progress"]["completed"]: return
    quest = next((q for q in DAILY_QUESTS_CONFIG if q["key"] == key), None)
    user["diamonds"] += quest["reward_diamonds"]
    user["total_diamonds_earned"] += quest["reward_diamonds"]
    user["daily_progress"]["completed"].append(key)
    await callback.answer(f"💎 +{quest['reward_diamonds']} алмаз!", show_alert=True)
    if len(user["daily_progress"]["completed"]) >= 3:
        user["daily_streak"] += 1
        user["last_daily_done_date"] = date.today().isoformat()
        await callback.message.answer(f"🔥 **ВСЕ ЗАДАНИЯ ВЫПОЛНЕНЫ!** 🔥\nСерия: {user['daily_streak']} дней!")
    await quests_daily(callback)

@dp.callback_query(F.data == "quests_main")
async def quests_main_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    last_type = None
    for quest in main_quests_info:
        current_type = quest["type"]
        if last_type is not None and current_type != last_type:
            kb.inline_keyboard.append([InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="ignore")])
        last_type = current_type
        key = quest["key"]
        status_icon = "✅" if key in user["completed_quests"] else ""
        name_text = f"{status_icon} {quest['name']}"
        kb.inline_keyboard.append([InlineKeyboardButton(text=name_text, callback_data=f"view_quest_{key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="quests_back_root")])
    try: await callback.message.edit_text("📜 **Основные задания**", reply_markup=kb, parse_mode="Markdown")
    except: await callback.message.answer("📜 **Основные задания**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "ignore")
async def ignore_click(callback: CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data == "quests_back_root")
async def quests_back_root(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ежедневные задания", callback_data="quests_daily")],
        [InlineKeyboardButton(text="📜 Основные задания", callback_data="quests_main")]
    ])
    await callback.message.edit_text("🎯 **Центр заданий**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_quest_"))
async def view_quest(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    quest_key = callback.data.replace("view_quest_", "", 1)
    quest = next((q for q in main_quests_info if q["key"] == quest_key), None)
    if not quest: return

    is_completed = quest_key in user["completed_quests"]
    current_progress = 0
    target = quest["target"]
    
    if quest["type"] == "balance": current_progress = user["balance"]
    elif quest["type"] == "buildings_count": current_progress = sum(1 for lvl in user["buildings_levels"].values() if lvl > 0)
    elif quest["type"] == "upgrades_count": current_progress = sum(user["upgrades"].values())
    elif quest["type"] == "clicks": current_progress = user["total_clicks"]
    elif quest["type"] == "income": calculate_passive(user); current_progress = user["passive_per_minute"]
    elif quest["type"] == "spent": current_progress = user["total_spent"]
    elif quest["type"] == "earned_diamonds": current_progress = user["total_diamonds_earned"]
    
    progress_bar = get_progress_bar(current_progress, target)
    formatted_current = f"{current_progress:,}".replace(",", " ")
    formatted_target = f"{target:,}".replace(",", " ")
    status_text = "✅ Выполнено" if is_completed else f"📊 Прогресс:\n{formatted_current} / {formatted_target}\n{progress_bar}"
    
    reward_parts = []
    if quest['rew_coins'] > 0: reward_parts.append(f"{quest['rew_coins']:,} монет".replace(",", " "))
    if quest.get('rew_diamonds', 0) > 0: reward_parts.append(f"{quest['rew_diamonds']} 💎")
    if quest['rew_tap'] > 0: reward_parts.append(f"{quest['rew_tap']:,} к тапу".replace(",", " "))
    if quest['rew_chance'] > 0: reward_parts.append(f"{quest['rew_chance']*100:.1f}% к шансу получения алмаза")
    
    reward_text = "**" + " + ".join(reward_parts) + "**"

    text = (f"📜 **{quest['name']}**\nℹ️ {quest['desc']}\n🎁 Награда: {reward_text}\n\n{status_text}")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if not is_completed:
        kb.inline_keyboard.append([InlineKeyboardButton(text="✅ ЗАВЕРШИТЬ", callback_data=f"complete_quest_{quest_key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="quests_main")])
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except:
        pass

@dp.callback_query(F.data.startswith("complete_quest_"))
async def complete_quest(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    quest_key = callback.data.replace("complete_quest_", "", 1)
    quest = next((q for q in main_quests_info if q["key"] == quest_key), None)
    if quest_key in user["completed_quests"]: return
    current_val = 0
    target = quest["target"]
    if quest["type"] == "balance": current_val = user["balance"]
    elif quest["type"] == "buildings_count": current_val = sum(1 for lvl in user["buildings_levels"].values() if lvl > 0)
    elif quest["type"] == "upgrades_count": current_val = sum(user["upgrades"].values())
    elif quest["type"] == "clicks": current_val = user["total_clicks"]
    elif quest["type"] == "income": calculate_passive(user); current_val = user["passive_per_minute"]
    elif quest["type"] == "spent": current_val = user["total_spent"]
    elif quest["type"] == "earned_diamonds": current_val = user["total_diamonds_earned"]
    if current_val < target:
        await callback.answer("❌ Условия не выполнены!", show_alert=True)
        return
    user["completed_quests"].append(quest_key)
    user["balance"] += quest.get("rew_coins", 0)
    user["diamonds"] += quest.get("rew_diamonds", 0)
    
    # Даем опыт за выполнение квеста (зависит от награды монет - чем сложнее, тем больше)
    xp_amount = max(10, int(math.sqrt(quest.get("rew_coins", 100))))
    await add_xp(user_id, xp_amount)
    
    recalculate_user_stats(user_id)
    await database.save_user(user_id, user)
    
    await callback.answer(f"🎉 Выполнено! (+{xp_amount} XP)", show_alert=True)
    new_data = f"view_quest_{quest_key}"
    new_callback = callback.model_copy(update={'data': new_data})
    await view_quest(new_callback)

# ═══════════════════════════════════════════════════════════
# ПРОФИЛЬ
# ═══════════════════════════════════════════════════════════
async def profile(message: Message):
    user_id = message.from_user.id
    await update_passive_income(user_id)
    user = users[user_id]
    recalculate_user_stats(user_id)
    current_finger_name, current_finger_bonus = get_current_finger_info(user)
    total_chance = (BASE_DIAMOND_CHANCE + user["diamond_chance_bonus"]) * 100
    safe_nick = str(user['nickname']).replace("<", "&lt;").replace(">", "&gt;")
    reg_date = user.get("registration_date", "Неизвестно") 
    tap_bonus_fmt = f"{current_finger_bonus:,}".replace(",", " ")
    quest_count_fmt = f"{len(user['completed_quests']):,}".replace(",", " ")
    streak_fmt = f"{user['daily_streak']:,}".replace(",", " ")
    
    # Опыт
    user_xp = user.get("xp", 0)
    user_lvl = user.get("level", 1)
    next_level_xp = get_level_exp(user_lvl)
    xp_bar = get_xp_bar(user_xp, next_level_xp)
    
    # Расчет недостающего опыта (чтобы переменная diff_xp существовала)
    diff_xp = next_level_xp - user_xp 
    
    text = (f"👑 <b>ТВОЙ ПРОФИЛЬ</b> 👑\n\n"
            f"👤 Ник: <b>{safe_nick}</b>\n"
            f"⭐️ <b>LVL:</b> {user_lvl}\n"
            f"💠 {xp_bar}\n"
            f"⚡️ До следующего уровня: <b>{diff_xp} XP</b>\n"
            f"📅 В игре с: {reg_date}\n"
            f"🆔 ID: <code>{user['custom_id']}</code>\n"
            f"💰 Баланс: {user['balance']:,} монет\n"
            f"💎 Алмазы: {user['diamonds']:,} (Шанс: {total_chance:.1f}%)\n"
            f"🔥 За один тап: + {tap_bonus_fmt} монет\n"
            f"🕒 Пассивный доход: + {user['passive_per_minute']:,} монет/мин\n"
            f"👆 Всего кликов: {user['total_clicks']:,}\n"
            f"💸 Всего потрачено: {user['total_spent']:,}\n"
            f"👥 Друзей: {user['referrals']:,}\n"
            f"📝 Основных заданий: {quest_count_fmt}\n"
            f"📅 Серия ежедневных: {streak_fmt} дн.\n"
            f"🖐️ Палец: {current_finger_name}\n\n"
            f"Ты уже на пути к миллиарду! 🚀").replace(",", " ")
    await message.answer(text, parse_mode="HTML", reply_markup=profile_menu())

# ═══════════════════════════════════════════════════════════
# МАГАЗИН ПАЛЬЦЕВ И СООРУЖЕНИЙ
# ═══════════════════════════════════════════════════════════
async def shop(message: Message, page=0):
    if isinstance(message, CallbackQuery): message = message.message
    await update_passive_income(message.chat.id)
    user = users[message.chat.id]
    if user["shop_message_id"]:
        try: await bot.delete_message(message.chat.id, user["shop_message_id"])
        except: pass
    total_items = len(upgrades_info)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_items = upgrades_info[start_idx:end_idx]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, info in enumerate(current_items):
        idx_in_global = start_idx + i
        key = info["key"]
        bought = user["upgrades"].get(key, 0)
        prev_key = upgrades_info[idx_in_global-1]["key"] if idx_in_global > 0 else None
        unlocked = idx_in_global == 0 or user["upgrades"].get(prev_key, 0) == 1
        
        if bought: kb.inline_keyboard.append([InlineKeyboardButton(text=f"{info['name']} ✅", callback_data="bought_finger")])
        elif unlocked: kb.inline_keyboard.append([InlineKeyboardButton(text=info['name'], callback_data=f"view_finger_{key}_{page}")])
        else: kb.inline_keyboard.append([InlineKeyboardButton(text=f"{info['name']} 🔒", callback_data="locked_finger")])
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Туда", callback_data=f"shop_page_{page-1}"))
    if page < total_pages - 1: nav_row.append(InlineKeyboardButton(text="Сюда ➡️", callback_data=f"shop_page_{page+1}"))
    if nav_row: kb.inline_keyboard.append(nav_row)
    text = (f"🏪 **МАГАЗИН УЛУЧШЕНИЙ** (Стр. {page+1}/{total_pages})\n\nВыбери новый палец и стань ещё богаче!")
    sent = await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    user["shop_message_id"] = sent.message_id

@dp.callback_query(F.data.startswith("shop_page_"))
async def shop_page_nav(callback: CallbackQuery):
    page = int(callback.data.replace("shop_page_", "", 1))
    await callback.message.delete()
    await shop(callback.message, page)

@dp.callback_query(F.data.in_(["locked_finger", "bought_finger"]))
async def locked_bought_finger(callback: CallbackQuery):
    if callback.data == "locked_finger": await callback.answer("🔒 Сначала купи предыдущий!", show_alert=True)
    else: await callback.answer("✅ Уже твой!", show_alert=False)

@dp.callback_query(F.data.startswith("view_finger_"))
async def view_upgrade(callback: CallbackQuery):
    user = users[callback.from_user.id]
    data_parts = callback.data.replace("view_finger_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in upgrades_info if x["key"] == key), None)
    if not info: return
    
    # ИЗМЕНЕНИЕ: добавлено :, к info['bonus'] для пробелов
    text = (f"✨ **{info['name']}** ✨\n\n💪 Даёт: **+{info['bonus']:,}** монет за тап\n{info['funny']}\n💸 Цена: **{info['cost']:,}** монет").replace(",", " ")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 КУПИТЬ СЕЙЧАС", callback_data=f"buy_finger_{key}_{page}")],
        [InlineKeyboardButton(text="🔙 Назад в магазин", callback_data=f"shop_page_{page}")]
    ])
    await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_finger_"))
async def buy_upgrade(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in users:
        await callback.answer("❌ Бот перезагружен. Введите /start")
        return
        
    user = users[user_id]
    data_parts = callback.data.replace("buy_finger_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in upgrades_info if x["key"] == key), None)
    if not info: return
    if user["upgrades"].get(key) == 1: return
    if user["balance"] < info["cost"]:
        await callback.answer("❌ Не хватает монет!", show_alert=True)
        return
    user["balance"] -= info["cost"]
    user["total_spent"] += info["cost"]
    user["upgrades"][key] = 1
    
    # ОПЫТ ЗА ПОКУПКУ ПАЛЬЦА
    xp_amount = max(5, int(math.sqrt(info["cost"])))
    await add_xp(user_id, xp_amount)
    
    recalculate_user_stats(user_id)
    await database.save_user(user_id, user)
    
    await callback.answer(f"🎉 Ты купил {info['name']}! (+{xp_amount} XP)", show_alert=True)
    # Проверяем ОБА типа заданий сразу (не только основные) — раньше это было
    # пропущено, и уведомление о выполненном задании приходило с задержкой
    # (только на следующем действии, например следующем тапе).
    await check_quest_notifications(callback.message, user_id)
    await check_daily_notifications(user_id)
    try: await callback.message.delete()
    except: pass
    await shop(callback.message, page)

async def buildings_shop(message: Message, page=0):
    if isinstance(message, CallbackQuery): message = message.message
    user_id = message.chat.id
    await update_passive_income(user_id)
    user = users[user_id]
    calculate_passive(user)
    if user["buildings_message_id"]:
        try: await bot.delete_message(message.chat.id, user["buildings_message_id"])
        except: pass
    total_items = len(buildings_info)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_items = buildings_info[start_idx:end_idx]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, info in enumerate(current_items):
        idx_in_global = start_idx + i
        key = info["key"]
        level = user["buildings_levels"].get(key, 0)
        prev_key = buildings_info[idx_in_global-1]["key"] if idx_in_global > 0 else None
        unlocked = idx_in_global == 0 or user["buildings_levels"].get(prev_key, 0) > 0
        if level > 0: kb.inline_keyboard.append([InlineKeyboardButton(text=f"{info['name']} (Ур. {level})", callback_data=f"view_building_{key}_{page}")])
        elif unlocked: kb.inline_keyboard.append([InlineKeyboardButton(text=info['name'], callback_data=f"view_building_{key}_{page}")])
        else: kb.inline_keyboard.append([InlineKeyboardButton(text=f"{info['name']} 🔒", callback_data="locked_building")])
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Туда", callback_data=f"build_page_{page-1}"))
    if page < total_pages - 1: nav_row.append(InlineKeyboardButton(text="Сюда ➡️", callback_data=f"build_page_{page+1}"))
    if nav_row: kb.inline_keyboard.append(nav_row)
    text = (f"🏗️ **МАГАЗИН СООРУЖЕНИЙ** (Стр. {page+1}/{total_pages})\n\nСтрой здания и получай пассивный доход!\nКаждое здание приносит монеты каждую минуту автоматически 🔥\nЗабери монеты вручную, когда накопится минимум!")
    sent = await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    user["buildings_message_id"] = sent.message_id

@dp.callback_query(F.data.startswith("build_page_"))
async def build_page_nav(callback: CallbackQuery):
    page = int(callback.data.replace("build_page_", "", 1))
    await callback.message.delete()
    await buildings_shop(callback.message, page)

@dp.callback_query(F.data.in_(["locked_building"]))
async def locked_building(callback: CallbackQuery):
    await callback.answer("🔒 Сначала построй предыдущее здание!", show_alert=True)

@dp.callback_query(F.data.startswith("view_building_"))
async def view_building(callback: CallbackQuery):
    user_id = callback.from_user.id
    await update_passive_income(user_id)
    user = users[user_id]
    data_parts = callback.data.replace("view_building_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in buildings_info if x["key"] == key), None)
    if not info: return
    level = user["buildings_levels"][key]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    income_base_fmt = f"{info['base_income']:,}".replace(",", " ")
    
    if level == 0:
        text = (f"✨ **{info['name']}** ✨\n🕒 Даёт: **+{income_base_fmt}** м/мин\n📦 Вместимость: **{info['base_capacity']:,}**\n{info['funny']}\n💸 Цена: **{info['cost']:,}**").replace(",", " ")
        kb.inline_keyboard.append([InlineKeyboardButton(text="🛒 ПОСТРОИТЬ", callback_data=f"buy_building_{key}_{page}")])
    else:
        bonus = info.get("upgrade_income_bonus", info["base_income"])
        current_income = info['base_income'] + (bonus * (level - 1))
        current_income_fmt = f"{current_income:,}".replace(",", " ")
        
        current_capacity = info['base_capacity'] + info['upgrade_capacity_bonus'] * (level - 1)
        accumulated = user["buildings_accumulated"][key]
        upgrade_cost = info['upgrade_cost_base'] * level
        
        text = (f"✨ **{info['name']} (Ур. {level})** ✨\n"
                f"🕒 Доход: **+{current_income_fmt}** м/мин\n"
                f"📦 Накоплено: **{accumulated:,} / {current_capacity:,}**\n"
                f"{info['funny']}").replace(",", " ")
        
        if accumulated >= current_income: 
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"💰 Забрать {accumulated:,}", callback_data=f"claim_building_{key}_{page}")])
        
        # ИЗМЕНЕНИЕ: Проверка на 10 уровень
        if level < 10:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"⬆️ Улучшить | {upgrade_cost:,}", callback_data=f"upgrade_building_{key}_{page}")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text="✅ Макс. уровень (10)", callback_data="ignore")])
        
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"build_page_{page}")])
    try: await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except: pass
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_building_"))
async def buy_building(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in users:
        await callback.answer("❌ Бот перезагружен. Введите /start")
        return

    user = users[user_id]
    data_parts = callback.data.replace("buy_building_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in buildings_info if x["key"] == key), None)
    if not info: return
    if user["buildings_levels"][key] > 0: return
    if user["balance"] < info["cost"]:
        await callback.answer("❌ Не хватает монет!", show_alert=True)
        return
    user["balance"] -= info["cost"]
    user["total_spent"] += info["cost"]
    user["buildings_levels"][key] = 1
    user["buildings_accumulated"][key] = 0
    user["buildings_last_update"][key] = datetime.now().timestamp()
    calculate_passive(user)
    
    # ОПЫТ ЗА ПОСТРОЙКУ
    xp_amount = max(10, int(math.sqrt(info["cost"])))
    await add_xp(user_id, xp_amount)
    
    await database.save_user(user_id, user)
    
    await callback.answer(f"🎉 Построено: {info['name']}! (+{xp_amount} XP)", show_alert=True)
    await check_quest_notifications(callback.message, user_id)
    await check_daily_notifications(user_id)
    new_data = f"view_building_{key}_{page}"
    new_callback = callback.model_copy(update={'data': new_data})
    await view_building(new_callback)

@dp.callback_query(F.data.startswith("upgrade_building_"))
async def upgrade_building(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in users:
        await callback.answer("❌ Бот перезагружен. Введите /start")
        return
        
    await update_passive_income(user_id)
    user = users[user_id]
    check_daily_reset(user)
    data_parts = callback.data.replace("upgrade_building_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in buildings_info if x["key"] == key), None)
    if not info: return
    
    level = user["buildings_levels"][key]
    
    # ИЗМЕНЕНИЕ: Защита от превышения уровня
    if level >= 10:
        await callback.answer("⛔ Достигнут максимальный уровень!", show_alert=True)
        return

    upgrade_cost = info['upgrade_cost_base'] * level
    if user["balance"] < upgrade_cost:
        await callback.answer("❌ Не хватает монет!", show_alert=True)
        return
    user["balance"] -= upgrade_cost
    user["total_spent"] += upgrade_cost
    user["buildings_levels"][key] += 1
    user["daily_progress"]["upgrades"] += 1
    user["buildings_last_update"][key] = datetime.now().timestamp()
    calculate_passive(user)
    
    # ОПЫТ ЗА УЛУЧШЕНИЕ
    xp_amount = max(5, int(math.sqrt(upgrade_cost)))
    await add_xp(user_id, xp_amount)
    
    await database.save_user(user_id, user)
    
    await callback.answer(f"🎉 Улучшено! (+{xp_amount} XP)", show_alert=True)
    # ВАЖНО: улучшение здания может увеличить пассивный доход или общую сумму
    # трат за один клик — а это как раз условия основных заданий типа "income"
    # и "spent". Раньше здесь проверялись только ежедневные задания, поэтому
    # такие основные задания "зависали" до следующего тапа.
    await check_quest_notifications(callback.message, user_id)
    await check_daily_notifications(user_id)
    new_data = f"view_building_{key}_{page}"
    new_callback = callback.model_copy(update={'data': new_data})
    await view_building(new_callback)

@dp.callback_query(F.data.startswith("claim_building_"))
async def claim_building(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in users:
        await callback.answer("❌ Бот перезагружен. Введите /start")
        return

    user = users[user_id]
    check_daily_reset(user)
    data_parts = callback.data.replace("claim_building_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in buildings_info if x["key"] == key), None)
    if not info: return
    accumulated = user["buildings_accumulated"][key]
    user["balance"] += accumulated
    user["daily_progress"]["claims"] += 1
    user["buildings_accumulated"][key] = 0
    user["buildings_last_update"][key] = datetime.now().timestamp()
    
    if accumulated > 0:
        await database.save_user(user_id, user)

    await callback.answer(f"🎉 Забрано {accumulated:,} монет!", show_alert=True)
    # Сбор дохода меняет баланс — а "balance"-задания проверяются в
    # check_quest_notifications, не в check_daily_notifications.
    await check_quest_notifications(callback.message, user_id)
    await check_daily_notifications(user_id)
    new_data = f"view_building_{key}_{page}"
    new_callback = callback.model_copy(update={'data': new_data})
    await view_building(new_callback)

# ═══════════════════════════════════════════════════════════
# РЕФЕРАЛКА И ТОП-10
# ═══════════════════════════════════════════════════════════
async def referral(message: Message):
    username = (await bot.get_me()).username
    link = f"https://t.me/{username}?start={message.from_user.id}"
    refs_count = f"{users[message.from_user.id]['referrals']:,}".replace(",", " ")
    
    text = (f"👥 **ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА** 👥\n\n{link}\n\nПриглашай друзей и получай бонусы за каждого!\nСейчас у тебя: {refs_count} друзей 🔥")
    await message.answer(text, disable_web_page_preview=True, parse_mode="Markdown")

async def top10_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 По монетам", callback_data="top10_balance")],
        [InlineKeyboardButton(text="💎 По алмазам", callback_data="top10_diamonds")],
        [InlineKeyboardButton(text="👥 По друзьям", callback_data="top10_referrals")]
    ])
    await message.answer("🏆 **ВЫБЕРИ КАТЕГОРИЮ ТОПА**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("top10_"))
async def show_top10_category(callback: CallbackQuery):
    category = callback.data.replace("top10_", "", 1)
    sort_key = None
    title = ""
    if category == "balance":
        sort_key = lambda x: x[1]["balance"]
        title = "💰 ТОП-10 БОГАЧЕЙ"
    elif category == "diamonds":
        sort_key = lambda x: x[1]["diamonds"]
        title = "💎 ТОП-10 ИСКАТЕЛЕЙ"
    elif category == "referrals":
        sort_key = lambda x: x[1]["referrals"]
        title = "👥 ТОП-10 ЛИДЕРОВ"
    top = sorted(users.items(), key=sort_key, reverse=True)[:10]
    if not top:
        await callback.answer("Пусто 😅", show_alert=True)
        return
    text = f"🏆 <b>{title}</b> 🏆\n\n"
    for i, (uid, data) in enumerate(top, 1):
        name_display = data.get('nickname') or data.get('username') or "Неизвестный"
        safe_name = str(name_display).replace("<", "&lt;").replace(">", "&gt;")
        privacy_on = data.get("privacy_enabled", True)
        if privacy_on: user_link = f'<a href="tg://user?id={uid}">{safe_name}</a>'
        else: user_link = safe_name
        if category == "balance": val = f"{data['balance']:,}".replace(",", " ") + " монет"
        elif category == "diamonds": val = f"{data['diamonds']:,}".replace(",", " ") + " 💎"
        elif category == "referrals": val = f"{data['referrals']:,}".replace(",", " ") + " друзей"
        text += f"{i}️⃣ {user_link} — {val}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_top10")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "back_top10")
async def back_top10(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 По монетам", callback_data="top10_balance")],
        [InlineKeyboardButton(text="💎 По алмазам", callback_data="top10_diamonds")],
        [InlineKeyboardButton(text="👥 По друзьям", callback_data="top10_referrals")]
    ])
    await callback.message.edit_text("🏆 **ВЫБЕРИ КАТЕГОРИЮ ТОПА**", reply_markup=kb, parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════
async def main():
    # 1. Даем серверу "проснуться"
    logging.warning("⏳ Ожидание инициализации сети...")
    await asyncio.sleep(2)

    # 2. Подключение к БД и создание таблиц
    # При вызове create_pool теперь создается и таблица (init_db)
    await database.create_pool() 
    
    # Настройка Graceful Shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    save_task = None

    def signal_handler():
        stop_event.set()
        # ВАЖНО: раньше сигнал только выставлял флаг, но dp.start_polling()
        # его не проверял и продолжал работать — хостинг "убивал" процесс
        # без финального сохранения. Теперь явно останавливаем поллинг.
        asyncio.create_task(dp.stop_polling())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try: loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError: pass

    try:
        # 3. Загрузка пользователей
        loaded_data = await database.load_all_users()
        users.update(loaded_data)
        for uid in users:
            recalculate_user_stats(uid)
        
        # 4. Запуск веб-сервера (Pella требует это!)
        await start_web_server()
        
        if config.TEST_MODE:
            logging.warning("🧪🧪🧪 БОТ ЗАПУЩЕН В TEST_MODE — ЗАПИСЬ В БАЗУ ДАННЫХ ОТКЛЮЧЕНА! 🧪🧪🧪")
        
        # 5. Фоновое сохранение
        save_task = asyncio.create_task(autosave_loop())
        
        # 6. Старт поллинга
        logging.warning("🚀 Бот запускается...")
        
        while True:
            try:
                await bot.delete_webhook(drop_pending_updates=True)
                await dp.start_polling(bot)
                # start_polling завершился без ошибки — значит его остановили
                # через dp.stop_polling() (сигнал завершения), выходим из цикла.
                break
            except Exception as e:
                logging.error(f"🌐 Ошибка сети Telegram: {e}. Рестарт через 10 сек...")
                await asyncio.sleep(10)
                if stop_event.is_set():
                    break
        
    finally:
        if save_task:
            save_task.cancel()
        # Финальное сохранение — гарантия, что при остановке бота (кнопка на
        # хостинге, редеплой и т.п.) не потеряются данные с момента последнего
        # автосохранения. В TEST_MODE ничего не запишется, как и задумано.
        try:
            logging.warning("💾 Финальное сохранение перед остановкой...")
            await database.save_all_users(users)
        except Exception as e:
            logging.error(f"Ошибка финального сохранения: {e}")
        await database.close_session()
        await bot.session.close()
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
