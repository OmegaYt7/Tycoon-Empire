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


async def show_stars_stats(message: Message, bot: Bot):
    """Показывает статистику по звёздам: текущий баланс бота (то, что ещё
    не выведено) и сводку по транзакциям (сколько всего заработано, сколько
    покупок, последние платежи). Используются нативные методы Bot API -
    никакой отдельной базы для этого вести не нужно, Telegram сам всё хранит."""
    try:
        balance = await bot.get_my_star_balance()
    except Exception as e:
        await message.answer(f"⚠️ Не удалось получить баланс звёзд: {e}")
        return

    try:
        # Bot API отдаёт максимум 100 транзакций за раз - для полной точности
        # на больших объёмах нужна пагинация через offset, но для старта
        # достаточно и одной пачки последних записей.
        result = await bot.get_star_transactions(limit=100)
        transactions = result.transactions
    except Exception as e:
        await message.answer(f"⚠️ Не удалось получить историю транзакций: {e}")
        return

    total_earned = 0
    purchase_count = 0
    refund_count = 0
    refund_amount = 0
    recent_lines = []

    for tx in transactions:
        # amount у Telegram ВСЕГДА положительный - направление платежа
        # определяется тем, какое из полей заполнено: source (входящая,
        # кто-то заплатил боту) или receiver (исходящая, например возврат
        # или вывод через Fragment), а не знаком числа.
        if tx.source is not None:
            total_earned += tx.amount
            purchase_count += 1
            user_label = "неизвестный пользователь"
            if getattr(tx.source, "user", None):
                u = tx.source.user
                user_label = f"@{u.username}" if u.username else f"ID {u.id}"
            if len(recent_lines) < 10:
                recent_lines.append(f"  +{tx.amount}⭐ - {user_label}")
        elif tx.receiver is not None:
            refund_count += 1
            refund_amount += tx.amount

    balance_str = f"{balance.amount:,}".replace(",", " ")
    earned_str = f"{total_earned:,}".replace(",", " ")

    text = (
        f"⭐ **Статистика Telegram Stars**\n\n"
        f"💰 Текущий баланс бота: **{balance_str} ⭐**\n"
        f"(ещё не выведено через Fragment)\n\n"
        f"📊 За последние {len(transactions)} транзакций:\n"
        f"✅ Покупок: **{purchase_count}** на сумму **{earned_str} ⭐**\n"
    )
    if refund_count:
        # Сюда попадают и возвраты игрокам, и выводы через Fragment -
        # Bot API не разделяет их отдельным полем, только по получателю
        refund_str = f"{refund_amount:,}".replace(",", " ")
        text += f"↩️ Исходящих операций (возвраты/вывод): **{refund_count}** на сумму **{refund_str} ⭐**\n"

    if recent_lines:
        text += "\n🕐 Последние покупки:\n" + "\n".join(recent_lines)

    if len(transactions) == 100:
        text += "\n\n_Показаны последние 100 транзакций - для полной истории нужна пагинация._"

    await message.answer(text, parse_mode="Markdown")


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
