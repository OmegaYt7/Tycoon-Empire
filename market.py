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
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery
)

import config
import database
from game_data import DIAMOND_PACKAGES

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
def get_diamonds_kb():
    rows = []

    # --- Раздел 1: оплата Telegram Stars (работает всегда) ---
    stars_row = []
    for pkg in DIAMOND_PACKAGES:
        diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
        label = f"💎{diamonds_str} - {pkg['stars_price']}⭐"
        stars_row.append(InlineKeyboardButton(text=label, callback_data=f"market_buy_stars_{pkg['key']}"))
        if len(stars_row) == 2:
            rows.append(stars_row)
            stars_row = []
    if stars_row:
        rows.append(stars_row)

    # Разделитель между секциями (не кликабельный по смыслу, просто заголовок)
    rows.append([InlineKeyboardButton(text="💳 - - - ОПЛАТА СБП/КАРТОЙ - - - 💳", callback_data="market_noop")])

    # --- Раздел 2: оплата СБП/картой ---
    rub_row = []
    for pkg in DIAMOND_PACKAGES:
        diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
        label = f"💎{diamonds_str} - {pkg['rub_price']}₽"
        rub_row.append(InlineKeyboardButton(text=label, callback_data=f"market_buy_rub_{pkg['key']}"))
        if len(rub_row) == 2:
            rows.append(rub_row)
            rub_row = []
    if rub_row:
        rows.append(rub_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def diamonds_menu(message: Message):
    """Вызывается из main.py по кнопке '💎 Алмазы' в подменю рынка."""
    text = (
        "💎 **Покупка алмазов**\n\n"
        "⭐ Сверху - оплата Telegram Stars (работает сразу)\n"
        "💳 Снизу - оплата СБП/картой\n\n"
        "Чем больше пакет - тем дешевле 1 алмаз!"
    )
    await message.answer(text, reply_markup=get_diamonds_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "market_noop")
async def market_noop(callback: CallbackQuery):
    # Кнопка-разделитель, ничего не делает, просто гасим "часики" на кнопке
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


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    # Telegram требует ответить в течение 10 секунд.
    # Подтверждаем всегда - реальная проверка (пакет существует и т.п.)
    # уже была сделана на шаге создания счёта.
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
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
    await database.save_user(user_id, user)

    # Покупка тоже засчитывается в задания вида "заработай N алмазов"
    if _check_quest_notifications:
        try:
            await _check_quest_notifications(message, user_id)
        except Exception as e:
            logging.warning(f"Ошибка проверки заданий после покупки алмазов: {e}")

    currency = message.successful_payment.currency
    total_amount = message.successful_payment.total_amount
    if currency == "XTR":
        paid_str = f"{total_amount} ⭐"
    else:
        paid_str = f"{total_amount / 100:.0f} {currency}"

    diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
    await message.answer(
        f"✅ **Оплата прошла успешно!**\n\n"
        f"Оплачено: {paid_str}\n"
        f"Начислено: 💎 {diamonds_str}\n\n"
        f"Спасибо за поддержку проекта!",
        parse_mode="Markdown"
    )
