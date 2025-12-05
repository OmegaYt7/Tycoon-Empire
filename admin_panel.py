import math
import asyncio
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ID Администраторов
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
        [InlineKeyboardButton(text="⚠️ Важное сообщение", callback_data="broadcast_setup_info")]
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
    # Сортировка по Game ID (custom_id) от большего к меньшему
    users_list = sorted(users_dict.items(), key=lambda x: str(x[1].get('custom_id', '0')), reverse=True)
    
    total_items = len(users_list)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_users = users_list[start_idx:end_idx]
    
    kb = []
    for tg_id, data in current_users:
        nick = data.get('nickname', 'Без ника')[:10]
        game_id = data.get('custom_id', '???')
        btn_text = f"{game_id} | {nick}"
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
    """
    Расширенный профиль игрока для админа.
    passive_income и finger_name передаются из main.py, так как требуют расчетов.
    """
    username = user_data.get('username')
    
    if username and username != "Guest" and username != "User":
        tg_link = f"@{username}"
    else:
        tg_link = f'<a href="tg://user?id={tg_id}">User</a>'

    # Форматирование чисел с пробелами
    balance = f"{user_data.get('balance', 0):,}".replace(",", " ")
    diamonds = f"{user_data.get('diamonds', 0):,}".replace(",", " ")
    total_spent = f"{user_data.get('total_spent', 0):,}".replace(",", " ")
    passive = f"{passive_income:,}".replace(",", " ")
    tap_power = f"{user_data.get('tap_mult', 1):,}".replace(",", " ")
    
    # Последняя активность (из БД или памяти)
    last_active = user_data.get('last_active') or user_data.get('registration_date', 'Нет данных')

    text = (
        f"🕵️‍♂️ <b>ПРОФИЛЬ ИГРОКА (Админ)</b>\n\n"
        f"🆔 Game ID: <code>{user_data['custom_id']}</code>\n"
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

# ═══════════════════════════════════════════════════════════
# ЛОГИКА РАССЫЛКИ (ТЕПЕРЬ ЗДЕСЬ)
# ═══════════════════════════════════════════════════════════

def get_broadcast_text(msg_type, minutes):
    """Возвращает текст оповещения в зависимости от типа."""
    if msg_type == "update":
        return (
            f"⚠️ **ВНИМАНИЕ: ОБНОВЛЕНИЕ!**\n\n"
            f"Через **{minutes} мин.** начнутся технические работы.\n"
            f"⛔ **Настоятельно не рекомендуем** играть, покупать или улучшать что-либо в это время.\n"
            f"💾 Ваши последние данные могут не сохраниться!\n\n"
            f"Ждите сообщения о завершении."
        )
    else:
        return (
            f"⚠️ **ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ**\n\n"
            f"Через **{minutes} мин.** вступит в силу изменение или исправление.\n\n"
            f"⛔ **Пожалуйста, приостановите игру!**\n"
            f"Не совершайте покупок и не кликайте в ближайшее время, чтобы избежать потери прогресса."
        )

async def perform_broadcast(bot, users_dict, text):
    """Рассылает сообщение всем пользователям из словаря."""
    count = 0
    for uid in users_dict:
        try:
            await bot.send_message(uid, text, parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05) # Небольшая задержка, чтобы не спамить API
        except:
            pass
    return count