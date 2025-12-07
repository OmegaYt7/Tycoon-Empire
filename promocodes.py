import random
from datetime import datetime

# ═══════════════════════════════════════════════════════════
# СПИСКИ РЕАКЦИЙ (ТОЛЬКО РАЗРЕШЕННЫЕ TELEGRAM)
# ═══════════════════════════════════════════════════════════
# Используем только стандартные реакции: 🔥, 🎉, ⚡, 🤩, 🏆
REACTION_LIST_SUCCESS = ["🔥", "🎉", "⚡", "🤩", "🏆"]

# Используем: 😐, 🥱, 🌚 (Скука/Уже было)
REACTION_LIST_ALREADY = ["😐", "🥱", "🌚"]

# Используем: 👎, 💔, 🤨, 😢 (Ошибка/Неверно)
REACTION_LIST_INVALID = ["👎", "💔", "🤨", "😢"]

# ═══════════════════════════════════════════════════════════
# ТЕКСТ ПОМОЩИ
# ═══════════════════════════════════════════════════════════
HELP_MESSAGE = (
    "⌨️ <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n\n"
    "Есть секретный код? Вводи его сюда, чтобы получить бонусы.\n\n"
    "<b>Формат ввода:</b>\n"
    "<code>/promo</code> и название промокода"
)

# ═══════════════════════════════════════════════════════════
# ДАННЫЕ ПРОМОКОДОВ
# ═══════════════════════════════════════════════════════════
PROMO_DATA = {
    "Launch2025": {
        "coins": 1000,
        "diamonds": 1,
        "tap_bonus": 0,
        "expires": "2026-12-7" 
    }
}

def activate_promo(user, code_input):
    """
    Возвращает: (Успех(bool), Текст(str), Реакция(str))
    """
    # 1. Проверка существования (Вежливо)
    if code_input not in PROMO_DATA:
        return False, "🔍 <b>Код не найден.</b>\nКажется, закралась опечатка. Проверь символы и попробуй ещё раз!", random.choice(REACTION_LIST_INVALID)

    promo = PROMO_DATA[code_input]
    
    # 2. Проверка срока действия (Нормально)
    expiration_date = datetime.strptime(promo["expires"], "%Y-%m-%d")
    if datetime.now() > expiration_date:
        return False, "🕰 <b>Время вышло.</b>\nК сожалению, срок действия этого кода истёк. Нужно было спешить!", random.choice(REACTION_LIST_INVALID)

    # 3. Инициализация списка
    if "activated_promos" not in user:
        user["activated_promos"] = []

    # 4. Проверка на повтор (Легкая шутка)
    if code_input in user["activated_promos"]:
        return False, "👐 <b>Дежавю?</b>\nТы уже активировал этот бонус. Дважды в одну реку не войти!", random.choice(REACTION_LIST_ALREADY)

    # 5. АКТИВАЦИЯ (Позитивно)
    rewards_text = []
    
    if promo["coins"] > 0:
        user["balance"] += promo["coins"]
        rewards_text.append(f"💰 {promo['coins']:,} монет".replace(",", " "))
    
    if promo["diamonds"] > 0:
        user["diamonds"] += promo["diamonds"]
        if "total_diamonds_earned" in user:
            user["total_diamonds_earned"] += promo["diamonds"]
        rewards_text.append(f"💎 {promo['diamonds']} алмаз(ов)")

    if promo.get("tap_bonus", 0) > 0:
        user["tap_mult"] += promo["tap_bonus"]
        rewards_text.append(f"👆 +{promo['tap_bonus']} к тапу")

    user["activated_promos"].append(code_input)
    
    rewards_str = "\n".join(rewards_text)
    
    response = (
        f"🎉 <b>ПРОМОКОД ПРИНЯТ!</b>\n"
        f"Код: <code>{code_input}</code> сработал успешно.\n\n"
        f"<b>ТВОЯ НАГРАДА:</b>\n"
        f"{rewards_str}\n\n"
        f"<i>Приятной игры! 🚀</i>"
    )
    
    return True, response, random.choice(REACTION_LIST_SUCCESS)