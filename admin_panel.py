import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ АДМИНИСТРАЦИИ
# ═══════════════════════════════════════════════════════════
# Сюда добавляй ID администраторов через запятую
ADMIN_IDS = [5342285170]

ITEMS_PER_PAGE = 15

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ═══════════════════════════════════════════════════════════
# УВЕДОМЛЕНИЕ О НОВОМ ИГРОКЕ
# ═══════════════════════════════════════════════════════════
async def notify_new_player(bot, user_data):
    """Отправляет сообщение админам о новом игроке"""
    text = (
        "🆕 <b>НОВЫЙ ИГРОК!</b>\n"
        f"👤 Ник: {user_data['nickname']}\n"
        f"🆔 Game ID: <code>{user_data['custom_id']}</code>\n"
        f"📅 Дата: {user_data.get('registration_date', 'Сегодня')}\n"
        f"🔗 Telegram ID: {user_data.get('username', 'Нет юзернейма')}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            # Админ мог заблокировать бота, игнорируем ошибку
            pass

# ═══════════════════════════════════════════════════════════
# ГЕНЕРАЦИЯ КЛАВИАТУРЫ СПИСКА ИГРОКОВ
# ═══════════════════════════════════════════════════════════
def get_users_keyboard(users_dict, page=0):
    # Превращаем словарь users в список для пагинации
    # Сортируем, чтобы порядок был фиксированным (например, по ID)
    users_list = sorted(users_dict.items(), key=lambda x: x[0])
    
    total_items = len(users_list)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_users = users_list[start_idx:end_idx]
    
    kb = []
    
    # Кнопки с игроками
    for tg_id, data in current_users:
        # На кнопке: Game ID | Nickname (обрезка если длинный)
        nick = data.get('nickname', 'Без ника')[:10]
        game_id = data.get('custom_id', '???')
        btn_text = f"{game_id} | {nick}"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"admin_view_{tg_id}_{page}")])
    
    # Кнопки навигации
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Туда", callback_data=f"admin_page_{page-1}"))
    
    # Индикатор страницы
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{max(1, total_pages)}", callback_data="ignore"))

    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Сюда ➡️", callback_data=f"admin_page_{page+1}"))
    
    if nav_row:
        kb.append(nav_row)
        
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ═══════════════════════════════════════════════════════════
# ПРОСМОТР ПРОФИЛЯ ИГРОКА (ДЛЯ АДМИНА)
# ═══════════════════════════════════════════════════════════
def get_user_profile_text(user_data, tg_id):
    username = user_data.get('username', 'Нет')
    if username != 'Нет':
        username = f"@{username}"
        
    text = (
        f"🕵️‍♂️ <b>ПРОФИЛЬ ИГРОКА (Админ)</b>\n\n"
        f"🆔 Game ID: <code>{user_data['custom_id']}</code>\n"
        f"👤 Ник: {user_data.get('nickname', 'Не задан')}\n"
        f"🔗 Telegram: {username} (ID: {tg_id})\n"
        f"📅 Регистрация: {user_data.get('registration_date', 'Неизвестно')}\n"
        f"💰 Баланс: {user_data.get('balance', 0):,}\n"
        f"💎 Алмазы: {user_data.get('diamonds', 0)}\n"
        f"👥 Рефералов: {user_data.get('referrals', 0)}\n"
        f"👆 Тапов: {user_data.get('total_clicks', 0)}\n"
    )
    return text