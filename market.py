"""
market.py
Рынок алмазов: покупка за Telegram Stars или за рубли (СБП/карта через
провайдера платежей). Вынесено в отдельный модуль, чтобы не раздувать
main.py, т.к. здесь дальше планируется много всего (новые пакеты, скидки,
промо-акции, статистика продаж и т.п.).

Подключение в main.py:
    import market
    market.setup(users, check_quest_notifications)
    dp.include_router(market.router)

- users_dict: тот же словарь users, что и в main.py (объект передаётся по
  ссылке, поэтому изменения здесь сразу видны в main.py и наоборот).
- check_quest_notifications: функция из main.py, которая проверяет и шлёт
  уведомления о выполненных заданиях (нужна, т.к. есть задания на "заработать
  N алмазов", и покупка тоже засчитывается в total_diamonds_earned).
"""
import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery
)

import config
import database
import admin_panel
from game_data import DIAMOND_PACKAGES

STATS_PAGE_SIZE = 10       # транзакций на странице в общей статистике
TOTALS_SCAN_CAP = 500      # сколько транзакций максимум просматриваем, чтобы посчитать общую сумму
DONATIONS_PAGE_SIZE = 5    # донатов на странице в профиле конкретного игрока

router = Router()

# Заполняются один раз при старте бота через setup()
_users = None
_check_quest_notifications = None


def setup(users_dict, check_quest_notifications=None):
    """Вызывается один раз из main.py при запуске, чтобы передать модулю
    доступ к общему словарю игроков и (опционально) функции проверки квестов."""
    global _users, _check_quest_notifications
    _users = users_dict
    _check_quest_notifications = check_quest_notifications


# ═══════════════════════════════════════════════════════════
# НИЖНЕЕ МЕНЮ РЫНКА (открывается по кнопке "💎 Рынок" из главного меню)
# Разделы "Бонусы" и "Маски" - заглушки на будущее, пока пишут "Скоро".
# Кнопка "🔙 Назад" не требует отдельного хендлера здесь - в main.py уже
# есть общий обработчик этого текста, который возвращает в главное меню.
# ═══════════════════════════════════════════════════════════
def get_market_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💎 Алмазы")],
        [KeyboardButton(text="🎁 Бонусы"), KeyboardButton(text="🎭 Маски")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True, one_time_keyboard=False)


async def market_menu(message: Message):
    """Вызывается из main.py по кнопке '💎 Рынок' - открывает нижнее меню рынка."""
    if isinstance(message, CallbackQuery):
        message = message.message
    await message.answer(
        "💎 **Рынок**\n\nЗдесь можно пополнить запасы за реальные деньги.",
        reply_markup=get_market_menu_kb(),
        parse_mode="Markdown"
    )


async def coming_soon(message: Message):
    """Заглушка для разделов, которые ещё не готовы (Бонусы, Маски)."""
    await message.answer("🔜 Скоро!")


# ═══════════════════════════════════════════════════════════
# РАЗДЕЛ "АЛМАЗЫ": два отдельных списка - оплата Stars и оплата СБП/картой.
# Каждая кнопка сразу запускает покупку конкретного пакета этим способом
# оплаты (без промежуточного шага "выбери способ оплаты").
# ═══════════════════════════════════════════════════════════
def get_diamonds_kb(mode="stars"):
    """mode: 'stars' или 'rub' - какой раздел оплаты сейчас показан.
    Кнопка внизу переключает раздел прямо в этом же сообщении (edit_text),
    без отправки нового - как вкладки."""
    rows = []
    row = []
    for pkg in DIAMOND_PACKAGES:
        diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
        if mode == "stars":
            label = f"💎{diamonds_str} - {pkg['stars_price']}⭐"
            cb = f"market_buy_stars_{pkg['key']}"
        else:
            label = f"💎{diamonds_str} - {pkg['rub_price']}₽"
            cb = f"market_buy_rub_{pkg['key']}"
        row.append(InlineKeyboardButton(text=label, callback_data=cb))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # Кнопка-переключатель раздела
    if mode == "stars":
        rows.append([InlineKeyboardButton(text="💳 Переключить на СБП/карту ➡️", callback_data="market_switch_rub")])
    else:
        rows.append([InlineKeyboardButton(text="⬅️ Переключить на Stars ⭐", callback_data="market_switch_stars")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_diamonds_text(mode="stars"):
    if mode == "stars":
        return (
            "💎 **Покупка алмазов**\n"
            "⭐ Раздел: **Telegram Stars**\n\n"
            "Чем больше пакет - тем дешевле"
        )
    return (
        "💎 **Покупка алмазов**\n"
        "💳 Раздел: **СБП/карта**\n\n"
        "Чем больше пакет - тем дешевле"
    )


async def diamonds_menu(message: Message):
    """Вызывается из main.py по кнопке '💎 Алмазы' в подменю рынка."""
    await message.answer(get_diamonds_text("stars"), reply_markup=get_diamonds_kb("stars"), parse_mode="Markdown")


@router.callback_query(F.data == "market_switch_rub")
async def market_switch_rub(callback: CallbackQuery):
    await callback.message.edit_text(get_diamonds_text("rub"), reply_markup=get_diamonds_kb("rub"), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "market_switch_stars")
async def market_switch_stars(callback: CallbackQuery):
    await callback.message.edit_text(get_diamonds_text("stars"), reply_markup=get_diamonds_kb("stars"), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("market_buy_stars_"))
async def market_pay_stars(callback: CallbackQuery, bot: Bot):
    key = callback.data.replace("market_buy_stars_", "", 1)
    pkg = next((p for p in DIAMOND_PACKAGES if p["key"] == key), None)
    if not pkg:
        await callback.answer("Пакет не найден", show_alert=True)
        return

    await callback.answer()
    diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{diamonds_str} 💎",
        description=f"Пакет из {diamonds_str} алмазов для Tycoon Empire",
        payload=f"diamonds|{pkg['key']}|{callback.from_user.id}",
        provider_token="",  # для Telegram Stars provider_token всегда пустая строка
        currency="XTR",
        prices=[LabeledPrice(label=f"{diamonds_str} алмазов", amount=pkg["stars_price"])],
    )


@router.callback_query(F.data.startswith("market_buy_rub_"))
async def market_pay_rub(callback: CallbackQuery, bot: Bot):
    key = callback.data.replace("market_buy_rub_", "", 1)
    pkg = next((p for p in DIAMOND_PACKAGES if p["key"] == key), None)
    if not pkg:
        await callback.answer("Пакет не найден", show_alert=True)
        return

    if not config.PAYMENT_PROVIDER_TOKEN:
        # СБП пока не подключён администратором (нужен provider_token от
        # платёжного провайдера, поддерживающего RUB - см. обсуждение в чате).
        await callback.answer(
            "💳 Оплата СБП/картой пока в разработке - скоро будет доступна!",
            show_alert=True
        )
        return

    await callback.answer()
    diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{diamonds_str} 💎",
        description=f"Пакет из {diamonds_str} алмазов для Tycoon Empire",
        payload=f"diamonds|{pkg['key']}|{callback.from_user.id}",
        provider_token=config.PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=f"{diamonds_str} алмазов", amount=pkg["rub_price"] * 100)],  # рубли в копейках
    )


def _tx_user_label(tx):
    if tx.source is not None and getattr(tx.source, "user", None):
        u = tx.source.user
        return f"@{u.username}" if u.username else f"ID {u.id}"
    return "неизвестный"


def _format_tx_line(tx):
    # amount у Telegram ВСЕГДА положительный - направление платежа
    # определяется тем, какое из полей заполнено: source (входящая, кто-то
    # заплатил боту) или receiver (исходящая - возврат или вывод), а не
    # знаком числа.
    date_str = tx.date.strftime("%d.%m %H:%M")
    if tx.source is not None:
        return f"✅ +{tx.amount}⭐ - {_tx_user_label(tx)} ({date_str})"
    elif tx.receiver is not None:
        return f"↩️ -{tx.amount}⭐ - возврат/вывод ({date_str})"
    return f"❔ {tx.amount}⭐ ({date_str})"


async def _compute_totals(bot: Bot, cap: int = TOTALS_SCAN_CAP):
    """Проходит по транзакциям бота пачками по 100 (максимум у Bot API),
    пока не наберёт cap штук или не кончатся записи, и считает сводные
    суммы. Несколько запросов подряд, но быстро - обычно 1-5 вызовов API."""
    total_earned = 0
    purchase_count = 0
    refund_amount = 0
    refund_count = 0
    offset = 0
    scanned = 0

    while scanned < cap:
        result = await bot.get_star_transactions(offset=offset, limit=100)
        batch = result.transactions
        if not batch:
            break
        for tx in batch:
            if tx.source is not None:
                total_earned += tx.amount
                purchase_count += 1
            elif tx.receiver is not None:
                refund_amount += tx.amount
                refund_count += 1
        scanned += len(batch)
        offset += len(batch)
        if len(batch) < 100:
            break

    return total_earned, purchase_count, refund_amount, refund_count, scanned


def _stats_nav_kb(offset, has_more):
    row = []
    if offset > 0:
        prev_offset = max(0, offset - STATS_PAGE_SIZE)
        row.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"market_stats_page_{prev_offset}"))
    if has_more:
        row.append(InlineKeyboardButton(text="➡️ След.", callback_data=f"market_stats_page_{offset + STATS_PAGE_SIZE}"))
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else None


async def _render_tx_page(bot: Bot, offset: int):
    result = await bot.get_star_transactions(offset=offset, limit=STATS_PAGE_SIZE)
    batch = result.transactions
    if not batch:
        text = "Транзакций пока нет." if offset == 0 else "Дальше транзакций нет."
    else:
        lines = [_format_tx_line(tx) for tx in batch]
        text = f"📜 **Транзакции** (с {offset + 1}):\n\n" + "\n".join(lines)
    has_more = len(batch) == STATS_PAGE_SIZE
    kb = _stats_nav_kb(offset, has_more)
    return text, kb


async def show_stars_stats(message: Message, bot: Bot):
    """Показывает статистику по звёздам: текущий баланс бота, сводку по всем
    транзакциям и отдельным сообщением - постраничный список самих транзакций
    (чтобы не получился один гигантский текст). Используются нативные методы
    Bot API, никакой отдельной базы для этого вести не нужно."""
    try:
        balance = await bot.get_my_star_balance()
    except Exception as e:
        await message.answer(f"⚠️ Не удалось получить баланс звёзд: {e}")
        return

    try:
        total_earned, purchase_count, refund_amount, refund_count, scanned = await _compute_totals(bot)
    except Exception as e:
        await message.answer(f"⚠️ Не удалось получить историю транзакций: {e}")
        return

    balance_str = f"{balance.amount:,}".replace(",", " ")
    earned_str = f"{total_earned:,}".replace(",", " ")

    header = (
        f"⭐ **Статистика Telegram Stars**\n\n"
        f"💰 Текущий баланс бота: **{balance_str} ⭐**\n"
        f"(ещё не выведено через Fragment)\n\n"
        f"📊 Из последних {scanned} транзакций:\n"
        f"✅ Покупок: **{purchase_count}** на сумму **{earned_str} ⭐**\n"
    )
    if refund_count:
        refund_str = f"{refund_amount:,}".replace(",", " ")
        header += f"↩️ Исходящих операций (возвраты/вывод): **{refund_count}** на сумму **{refund_str} ⭐**\n"
    if scanned == TOTALS_SCAN_CAP:
        header += f"\n_Просмотрено максимум {TOTALS_SCAN_CAP} записей - возможно, было больше._"

    await message.answer(header, parse_mode="Markdown")

    try:
        text, kb = await _render_tx_page(bot, 0)
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"⚠️ Не удалось получить список транзакций: {e}")


@router.callback_query(F.data.startswith("market_stats_page_"))
async def market_stats_page(callback: CallbackQuery, bot: Bot):
    if not admin_panel.is_admin(callback.from_user.id):
        return
    offset = int(callback.data.replace("market_stats_page_", "", 1))
    try:
        text, kb = await _render_tx_page(bot, offset)
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ═══════════════════════════════════════════════════════════
# ДОНАТЫ КОНКРЕТНОГО ИГРОКА (кнопка "📊 Статы донатов" в профиле в админке)
# ═══════════════════════════════════════════════════════════
def _format_donation_line(don):
    method_label = "⭐ Stars" if don["method"] == "stars" else "💳 СБП"
    if don["currency"] == "XTR":
        amount_str = f"{don['amount']} ⭐"
    else:
        amount_str = f"{don['amount'] / 100:.0f} {don['currency']}"
    diamonds_str = f"{don['diamonds']:,}".replace(",", " ")

    raw_date = don.get("date", "?")
    try:
        # Дата хранится в ISO-формате (с буквой T между датой и временем) -
        # для показа игроку/админу переводим в привычный вид ДД.ММ.ГГГГ ЧЧ:ММ
        date_str = datetime.fromisoformat(raw_date).strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        date_str = raw_date

    return f"{method_label} | {amount_str} → 💎{diamonds_str} | {date_str}"


def get_user_donations_text_kb(target_id, page, don_offset):
    user = _users.get(target_id) if _users else None
    if not user:
        return "⚠️ Игрок не найден.", None

    donations = user.get("donations", [])
    total_count = len(donations)

    if total_count == 0:
        text = f"📊 **Донаты игрока** `{target_id}`\n\nПока не задонатил ни разу."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_view_{target_id}_{page}")]
        ])
        return text, kb

    # Считаем сводку сразу по всем донатам (список обычно небольшой - это же не глобальная лента бота)
    total_stars = sum(d["amount"] for d in donations if d["method"] == "stars")
    total_rub = sum(d["amount"] for d in donations if d["method"] == "rub") / 100

    # Показываем последние сначала
    ordered = list(reversed(donations))
    page_items = ordered[don_offset:don_offset + DONATIONS_PAGE_SIZE]
    lines = [_format_donation_line(d) for d in page_items]

    text = (
        f"📊 **Донаты игрока** `{target_id}`\n\n"
        f"Всего донатов: **{total_count}**\n"
        f"⭐ Всего Stars: **{total_stars}**\n"
    )
    if total_rub:
        text += f"💳 Всего СБП: **{total_rub:.0f} ₽**\n"
    text += f"\n_(с {don_offset + 1} по {don_offset + len(page_items)})_\n\n" + "\n".join(lines)

    nav_row = []
    if don_offset > 0:
        prev_offset = max(0, don_offset - DONATIONS_PAGE_SIZE)
        nav_row.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"market_userdon_{target_id}_{page}_{prev_offset}"))
    if don_offset + DONATIONS_PAGE_SIZE < total_count:
        nav_row.append(InlineKeyboardButton(text="➡️ След.", callback_data=f"market_userdon_{target_id}_{page}_{don_offset + DONATIONS_PAGE_SIZE}"))

    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_view_{target_id}_{page}")])

    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("market_userdon_"))
async def market_user_donations(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    # market_userdon_{target_id}_{page}_{don_offset}
    target_id = int(parts[2])
    page = int(parts[3])
    don_offset = int(parts[4])

    text, kb = get_user_donations_text_kb(target_id, page, don_offset)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    # Telegram требует ответить в течение 10 секунд.
    # Подтверждаем всегда - реальная проверка (пакет существует и т.п.)
    # уже была сделана на шаге создания счёта.
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, bot: Bot):
    payload = message.successful_payment.invoice_payload
    try:
        _, pkg_key, _ = payload.split("|")
    except ValueError:
        logging.error(f"Некорректный payload оплаты: {payload}")
        return

    pkg = next((p for p in DIAMOND_PACKAGES if p["key"] == pkg_key), None)
    user_id = message.from_user.id

    if not pkg or _users is None or user_id not in _users:
        logging.error(f"Оплата прошла, но пакет/игрок не найден: payload={payload}, user_id={user_id}")
        await message.answer("⚠️ Оплата прошла, но произошла ошибка начисления алмазов. Напиши администратору - начислим вручную.")
        return

    user = _users[user_id]
    user["diamonds"] += pkg["diamonds"]
    user["total_diamonds_earned"] += pkg["diamonds"]

    currency = message.successful_payment.currency
    total_amount = message.successful_payment.total_amount
    method = "stars" if currency == "XTR" else "rub"

    # Записываем в личную историю донатов игрока (переживает сброс статов -
    # см. perform_user_wipe в admin_panel.py, там donations сохраняются отдельно)
    if "donations" not in user:
        user["donations"] = []
    user["donations"].append({
        "date": datetime.now().isoformat(timespec="seconds"),
        "diamonds": pkg["diamonds"],
        "method": method,
        "amount": total_amount,
        "currency": currency,
    })

    await database.save_user(user_id, user)

    # Покупка тоже засчитывается в задания вида "заработай N алмазов"
    if _check_quest_notifications:
        try:
            await _check_quest_notifications(message, user_id)
        except Exception as e:
            logging.warning(f"Ошибка проверки заданий после покупки алмазов: {e}")

    if currency == "XTR":
        paid_str = f"{total_amount} ⭐"
        method_label = "⭐ Stars"
    else:
        paid_str = f"{total_amount / 100:.0f} {currency}"
        method_label = "💳 СБП/карта"

    diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
    await message.answer(
        f"✅ **Оплата прошла успешно!**\n\n"
        f"Оплачено: {paid_str}\n"
        f"Начислено: 💎 {diamonds_str}\n\n"
        f"Спасибо за поддержку проекта!",
        parse_mode="Markdown"
    )

    # Уведомляем всех админов о донате
    buyer_username = message.from_user.username
    buyer_label = f"@{buyer_username}" if buyer_username else f"ID {user_id}"
    admin_text = (
        f"💰 **Новый донат!**\n\n"
        f"👤 Игрок: {buyer_label} (Telegram ID: `{user_id}`)\n"
        f"📦 Пакет: 💎 {diamonds_str}\n"
        f"💳 Способ: {method_label}\n"
        f"💵 Сумма: {paid_str}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="Markdown")
        except Exception as e:
            logging.warning(f"Не удалось уведомить админа {admin_id} о донате: {e}")
