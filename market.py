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
    LabeledPrice, PreCheckoutQuery
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
# КЛАВИАТУРЫ / ТЕКСТЫ
# ═══════════════════════════════════════════════════════════
def get_market_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pkg in DIAMOND_PACKAGES:
        diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
        label = f"💎 {diamonds_str}  -  от {pkg['stars_price']}⭐"
        kb.inline_keyboard.append([InlineKeyboardButton(text=label, callback_data=f"market_pkg_{pkg['key']}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market_close")])
    return kb


def get_market_text():
    return (
        "💎 **Рынок алмазов**\n\n"
        "Выбери пакет - оплатить можно Telegram Stars или картой/СБП.\n"
        "Алмазы придут на баланс сразу после оплаты."
    )


# ═══════════════════════════════════════════════════════════
# ВХОД В РЫНОК (вызывается из main.py по кнопке "💎 Рынок")
# ═══════════════════════════════════════════════════════════
async def market_menu(message: Message):
    if isinstance(message, CallbackQuery):
        message = message.message
    await message.answer(get_market_text(), reply_markup=get_market_kb(), parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════
# ХЕНДЛЕРЫ (все на отдельном роутере, регистрируются через dp.include_router)
# ═══════════════════════════════════════════════════════════
@router.callback_query(F.data == "market_close")
async def market_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "market_reopen")
async def market_reopen(callback: CallbackQuery):
    await callback.message.edit_text(get_market_text(), reply_markup=get_market_kb(), parse_mode="Markdown")


@router.callback_query(F.data.startswith("market_pkg_"))
async def market_package_view(callback: CallbackQuery):
    key = callback.data.replace("market_pkg_", "", 1)
    pkg = next((p for p in DIAMOND_PACKAGES if p["key"] == key), None)
    if not pkg:
        await callback.answer("Пакет не найден", show_alert=True)
        return

    diamonds_str = f"{pkg['diamonds']:,}".replace(",", " ")
    rows = [
        [InlineKeyboardButton(text=f"⭐ Оплатить {pkg['stars_price']} Stars", callback_data=f"market_pay_stars_{key}")],
    ]
    # Кнопка оплаты рублями появляется, только если админ настроил провайдера платежей
    if config.PAYMENT_PROVIDER_TOKEN:
        rows.append([InlineKeyboardButton(text=f"💳 Оплатить {pkg['rub_price']} ₽ (СБП/карта)", callback_data=f"market_pay_rub_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market_reopen")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.edit_text(f"💎 **{diamonds_str} алмазов**\n\nВыбери способ оплаты:", reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("market_pay_stars_"))
async def market_pay_stars(callback: CallbackQuery, bot: Bot):
    key = callback.data.replace("market_pay_stars_", "", 1)
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


@router.callback_query(F.data.startswith("market_pay_rub_"))
async def market_pay_rub(callback: CallbackQuery, bot: Bot):
    key = callback.data.replace("market_pay_rub_", "", 1)
    pkg = next((p for p in DIAMOND_PACKAGES if p["key"] == key), None)
    if not pkg:
        await callback.answer("Пакет не найден", show_alert=True)
        return

    if not config.PAYMENT_PROVIDER_TOKEN:
        await callback.answer("Оплата картой/СБП сейчас не настроена администратором.", show_alert=True)
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
