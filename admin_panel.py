import math
import asyncio
from datetime import date
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import config

# ID Администраторов теперь берутся из конфига
ADMIN_IDS = [5342285170]

ITEMS_PER_PAGE = 10

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def notify_new_player(bot, user_data):
    """Отправляет сообщение админам о новом игроке"""
    username_text = user_data.get('username')
    user_id = user_data.get('custom_id', '???')
    
    if username_text and username_text != "Guest":
        tg_link = f"@{username_text}"
    else:
        tg_link = "Без юзернейма"

    text = (
        "🆕 <b>НОВЫЙ ИГРОК!</b>\n"
        f"👤 Ник: {user_data['nickname']}\n"
        f"🆔 Game ID: <code>{user_id}</code>\n"
        f"📅 Дата: {user_data.get('registration_date', 'Сегодня')}\n"
        f"🔗 TG: {tg_link}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except:
            pass

# ═══════════════════════════════════════════════════════════
# МЕНЮ И КЛАВИАТУРЫ
# ═══════════════════════════════════════════════════════════

def admin_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Список игроков"), KeyboardButton(text="📢 Оповещение")],
        [KeyboardButton(text="💾 Выгрузка"), KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True, one_time_keyboard=False)

def export_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 ПОДТВЕРЖДАЮ", callback_data="admin_export_confirm")]
    ])

def broadcast_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠️ Тех. работы / Обновление", callback_data="broadcast_setup_update")],
        [InlineKeyboardButton(text="⚠️ Важное сообщение", callback_data="broadcast_setup_info")],
        # НОВАЯ КНОПКА
        [InlineKeyboardButton(text="✅ Работы завершены", callback_data="broadcast_send_finished_now")]
    ])

def broadcast_time_kb(msg_type):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 мин", callback_data=f"broadcast_send_{msg_type}_1"),
         InlineKeyboardButton(text="2 мин", callback_data=f"broadcast_send_{msg_type}_2")],
        [InlineKeyboardButton(text="5 мин", callback_data=f"broadcast_send_{msg_type}_5"),
         InlineKeyboardButton(text="10 мин", callback_data=f"broadcast_send_{msg_type}_10")]
    ])

# ═══════════════════════════════════════════════════════════
# ЛОГИКА ПРОСМОТРА ИГРОКОВ
# ═══════════════════════════════════════════════════════════

def get_users_keyboard(users_dict, page=0):
    users_list = sorted(users_dict.items(), key=lambda x: str(x[1].get('custom_id', '0')), reverse=True)
    
    total_items = len(users_list)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_users = users_list[start_idx:end_idx]
    
    kb = []
    for tg_id, data in current_users:
        raw_nick = data.get('nickname')
        nick_str = str(raw_nick) if raw_nick else "Без ника"
        nick_display = nick_str[:10]
        
        game_id = data.get('custom_id', '???')
        btn_text = f"{game_id} | {nick_display}"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"admin_view_{tg_id}_{page}")])
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Туда", callback_data=f"admin_page_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{max(1, total_pages)}", callback_data="ignore"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Сюда ➡️", callback_data=f"admin_page_{page+1}"))
    
    if nav_row:
        kb.append(nav_row)
        
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_user_profile_text(user_data, tg_id, passive_income, finger_name):
    username = user_data.get('username')
    
    if username and username != "Guest" and username != "User":
        tg_link = f"@{username}"
    else:
        tg_link = f'<a href="tg://user?id={tg_id}">User</a>'

    balance = f"{user_data.get('balance', 0):,}".replace(",", " ")
    diamonds = f"{user_data.get('diamonds', 0):,}".replace(",", " ")
    total_spent = f"{user_data.get('total_spent', 0):,}".replace(",", " ")
    passive = f"{passive_income:,}".replace(",", " ")
    tap_power = f"{user_data.get('tap_mult', 1):,}".replace(",", " ")
    
    last_active = user_data.get('last_active') or user_data.get('registration_date', 'Нет данных')

    text = (
        f"🕵️‍♂️ <b>ПРОФИЛЬ ИГРОКА (Админ)</b>\n\n"
        f"🆔 Game ID: <code>{user_data.get('custom_id', '???')}</code>\n"
        f"👤 Ник: {user_data.get('nickname', 'Не задан')}\n"
        f"🔗 Telegram: {tg_link} (ID: <code>{tg_id}</code>)\n"
        f"📅 Регистрация: {user_data.get('registration_date', 'Неизвестно')}\n"
        f"🕒 Последний вход: {last_active}\n\n"
        f"💰 Баланс: {balance}\n"
        f"💎 Алмазы: {diamonds}\n"
        f"💸 Потрачено: {total_spent}\n\n"
        f"⚡ Сила тапа: {tap_power}\n"
        f"🖐️ Палец: {finger_name}\n"
        f"💤 Пассив: {passive} / мин\n\n"
        f"📝 Заданий выполнено: {len(user_data.get('completed_quests', []))}\n"
        f"🔥 Серия дней: {user_data.get('daily_streak', 0)}\n"
        f"👥 Рефералов: {user_data.get('referrals', 0)}\n"
        f"👆 Всего тапов: {user_data.get('total_clicks', 0):,}".replace(",", " ")
    )
    return text

def get_user_profile_kb(target_id, page):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Стереть данные", callback_data=f"admin_wipe_ask_{target_id}_{page}")],
        [InlineKeyboardButton(text="🔙 Вернуться в список", callback_data=f"admin_page_{page}")]
    ])

def get_wipe_confirm_text(target_id):
    return (
        f"‼️ **ВЫ УВЕРЕНЫ?** ‼️\n\n"
        f"Вы собираетесь полностью обнулить игрока `{target_id}`.\n"
        f"Будут удалены:\n"
        f"- Весь баланс и алмазы\n"
        f"- Все здания и улучшения\n"
        f"- Все достижения и квесты\n"
        f"- Рефералы и статистика\n\n"
        f"Останется только Ник, Game ID и Дата регистрации.\n"
        f"Это действие **НЕОБРАТИМО**."
    )

def get_wipe_confirm_kb(target_id, page):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ ДА, СТЕРЕТЬ ВСЁ", callback_data=f"admin_wipe_confirm_{target_id}_{page}")],
        [InlineKeyboardButton(text="🔙 НЕТ, ОТМЕНА", callback_data=f"admin_view_{target_id}_{page}")]
    ])

async def perform_user_wipe(users_dict, target_id, upgrade_keys, building_keys):
    if target_id not in users_dict:
        return False
    u = users_dict[target_id]
    
    saved_nick = u.get("nickname")
    saved_custom_id = u.get("custom_id")
    saved_reg_date = u.get("registration_date")
    saved_username = u.get("username")
    
    upgrades = {key: 0 for key in upgrade_keys}
    upgrades["wooden_finger"] = 1
    
    buildings_levels = {key: 0 for key in building_keys}
    buildings_accumulated = {key: 0 for key in building_keys}
    buildings_last_update = {key: 0.0 for key in building_keys}
    
    users_dict[target_id] = {
        "username": saved_username,
        "nickname": saved_nick,
        "custom_id": saved_custom_id,
        "registration_date": saved_reg_date,
        "last_active": date.today().isoformat(),
        "last_nick_change": None, 
        "state": "active",
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
    return True

# ═══════════════════════════════════════════════════════════
# ЛОГИКА РАССЫЛКИ
# ═══════════════════════════════════════════════════════════

def get_broadcast_text(msg_type, minutes=""):
    if msg_type == "update":
        return (
            f"⚠️ **ВНИМАНИЕ: ОБНОВЛЕНИЕ!**\n\n"
            f"Через **{minutes} мин.** начнутся технические работы.\n"
            f"⛔ **Настоятельно не рекомендуем** играть, покупать или улучшать что-либо в это время.\n"
            f"💾 Ваши последние данные могут не сохраниться!\n\n"
            f"Ждите сообщения о завершении."
        )
    elif msg_type == "finished":
        # НОВЫЙ ТЕКСТ
        return (
            f"✅ **ТЕХНИЧЕСКИЕ РАБОТЫ ЗАВЕРШЕНЫ**\n\n"
            f"Бот снова работает в штатном режиме.\n"
            f"Спасибо за ожидание! Приятной игры! 🚀"
        )
    else:
        return (
            f"⚠️ **ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ**\n\n"
            f"Через **{minutes} мин.** вступит в силу изменение или исправление.\n\n"
            f"⛔ **Пожалуйста, приостановите игру!**\n"
            f"Не совершайте покупок и не кликайте в ближайшее время, чтобы избежать потери прогресса."
        )

async def perform_broadcast(bot, users_dict, text):
    count = 0
    for uid in users_dict:
        try:
            await bot.send_message(uid, text, parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05) 
        except:
            pass
    return count
