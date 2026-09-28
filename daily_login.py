"""
daily_login.py
Ежедневная награда (7-дневный календарь) + СВОЯ уникальная мини-игра на
каждый день цикла, и у КАЖДОЙ игры теперь 3 уровня сложности (лестница):
  🟢 Уровень 1 (маленькое поле, легко)
  🟡 Уровень 2 (среднее поле)
  🔴 Уровень 3 (большое поле, сложно)

Прогресс работает как "рискни или забери":
  - Выиграл уровень < 3 -> можно забрать награду и закончить,
    либо пойти дальше на следующий (более сложный и более прибыльный) уровень.
  - Выиграл уровень 3 -> игра дня завершена автоматически с максимальным бонусом.
  - Проиграл -> можно повторить ТОТ ЖЕ уровень заново, либо закончить и забрать
    то, что уже было пройдено раньше (если ничего не пройдено - бонуса нет).

Игры по дням:
  День 1 - Лисичка, что делаешь? (Simon Says, длина последовательности растёт)
  День 2 - Логика (найди лишнее -> найди лишнее из большего списка -> числовая последовательность)
  День 3 - Взрывные крестики-нолики (3x3 -> 4x4 -> 5x5, бот сильнее с каждым уровнем)
  День 4 - Слова (короткое слово -> длиннее слово с "пустышками" -> длинное слово с перемешиванием)
  День 5 - Найди пару (с джокером-приколюхой, поле растёт)
  День 6 - Собери картинку по памяти (поле растёт, времени на запоминание меньше)
  День 7 - Детектив (3 подозреваемых -> 4 -> 5, улик больше)

Подключение в main.py:
    import daily_login
    daily_login.setup(users, recalculate_user_stats)
    dp.include_router(daily_login.router)
"""
import random
import asyncio
import logging
from datetime import date
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database
import admin_panel

router = Router()

_users = None
_recalculate_user_stats = None

# Базовый бонус-фонд, выданный при клейме награды (до множителя за уровень)
_game_bonus = {}
# Текущий уровень сложности игрока в рамках сессии одной дневной игры
_level_progress = {}  # user_id -> {"day": int, "level": int}

LEVEL_NAMES = {1: "🟢 Уровень 1", 2: "🟡 Уровень 2", 3: "🔴 Уровень 3"}
LEVEL_BONUS_MULT = {0: 0, 1: 1, 2: 2, 3: 3}


def setup(users_dict, recalculate_user_stats=None):
    global _users, _recalculate_user_stats
    _users = users_dict
    _recalculate_user_stats = recalculate_user_stats


# ═══════════════════════════════════════════════════════════
# РАСЧЁТ НАГРАДЫ И ЛОГИКА КАЛЕНДАРЯ
# ═══════════════════════════════════════════════════════════
REWARD_MINUTES = {1: 15, 2: 20, 3: 25, 4: 30, 5: 40, 6: 50, 7: 70}
DAY7_BONUS_DIAMONDS = 10
MIN_REWARD_PER_DAY = 500

DAY_GAME_NAMES = {
    1: "🦊 Лисичка, что делаешь?",
    2: "🧠 Логика",
    3: "💥 Взрывные крестики-нолики",
    4: "📝 Слова",
    5: "🃏 Найди пару",
    6: "🎨 Собери картинку по памяти",
    7: "🔍 Детектив",
}


def _calc_reward_coins(user, day):
    minutes = REWARD_MINUTES.get(day, 15)
    passive = user.get("passive_per_minute", 0)
    reward = int(passive * minutes)
    return max(reward, MIN_REWARD_PER_DAY * day)


def _get_streak_state(user):
    today = date.today()
    last_date_str = user.get("last_login_reward_date")
    streak = user.get("login_streak", 0)

    if last_date_str == today.isoformat():
        current_day = ((streak - 1) % 7) + 1
        return True, current_day, streak, user.get("login_game_played", False)

    if last_date_str:
        last_date = date.fromisoformat(last_date_str)
        if (today - last_date).days > 1:
            streak = 0

    current_day = (streak % 7) + 1
    return False, current_day, streak, False


def get_calendar_kb(claimed_today, current_day, game_played, is_admin=False):
    rows, row = [], []
    for day in range(1, 8):
        if is_admin:
            label, cb = f"🧪{day}", f"daily_admintest_{day}"
        elif day < current_day or (day == current_day and claimed_today and game_played):
            label, cb = f"✅{day}", "daily_noop"
        elif day == current_day and claimed_today and not game_played:
            label, cb = f"🎮{day}", "daily_playday"
        elif day == current_day:
            label, cb = f"🎁{day}", "daily_claim"
        else:
            label, cb = f"🔒{day}", "daily_noop"
        row.append(InlineKeyboardButton(text=label, callback_data=cb))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def daily_menu(message: Message):
    user_id = message.from_user.id
    user = _users.get(user_id) if _users else None
    if not user:
        return

    claimed_today, current_day, _, game_played = _get_streak_state(user)
    game_name = DAY_GAME_NAMES[current_day]
    is_admin = admin_panel.is_admin(user_id)

    if is_admin:
        text = "🎁 **Ежедневная награда**\n\n🧪 Ты админ - все 7 дней доступны для теста, жми любой!"
    elif claimed_today and game_played:
        text = "🎁 **Ежедневная награда**\n\nСегодня всё забрано и сыграно - возвращайся завтра!"
    elif claimed_today and not game_played:
        text = f"🎁 **Ежедневная награда**\n\nНаграда за День {current_day} уже получена!\nОсталось сыграть: {game_name}"
    else:
        text = (
            f"🎁 **Ежедневная награда**\n\n"
            f"Собери награду за День {current_day} из 7!\n"
            f"Сегодняшняя игра: {game_name}\n"
            f"Пропустишь день - серия начнётся заново."
        )

    kb = get_calendar_kb(claimed_today, current_day, game_played, is_admin)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "daily_noop")
async def daily_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "daily_claim")
async def daily_claim(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = _users.get(user_id) if _users else None
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    claimed_today, current_day, streak, _ = _get_streak_state(user)
    if claimed_today:
        await callback.answer("Уже забрано сегодня!", show_alert=True)
        return

    if _recalculate_user_stats:
        _recalculate_user_stats(user_id)

    streak += 1
    current_day = ((streak - 1) % 7) + 1

    reward_coins = _calc_reward_coins(user, current_day)
    user["balance"] += reward_coins

    bonus_text = ""
    if current_day == 7:
        user["diamonds"] += DAY7_BONUS_DIAMONDS
        user["total_diamonds_earned"] += DAY7_BONUS_DIAMONDS
        bonus_text = f"\n💎 Бонус за 7 день: +{DAY7_BONUS_DIAMONDS} алмазов!"

    user["login_streak"] = streak
    user["last_login_reward_date"] = date.today().isoformat()
    user["login_game_played"] = False
    await database.save_user(user_id, user)

    _game_bonus[user_id] = max(reward_coins // 2, 100)
    _level_progress.pop(user_id, None)

    coins_str = f"{reward_coins:,}".replace(",", " ")
    game_name = DAY_GAME_NAMES[current_day]
    text = (
        f"✅ **День {current_day} получен!**\n\n"
        f"💰 +{coins_str} монет{bonus_text}\n\n"
        f"Сегодняшняя игра: {game_name}\n"
        f"3 уровня сложности - чем дальше пройдёшь, тем больше бонус!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"▶️ Играть: {game_name}", callback_data="daily_playday")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


async def _launch_level(callback: CallbackQuery, bot: Bot, day: int, level: int):
    _level_progress[callback.from_user.id] = {"day": day, "level": level}
    starters = {
        1: start_fox_game, 2: start_logic_game, 3: start_exploding_ttt,
        4: start_words_game, 5: start_memory_game, 6: start_picture_game,
        7: start_detective_game,
    }
    starter = starters[day]
    if day == 3:
        await starter(callback, bot, level)
    else:
        await starter(callback, level)


@router.callback_query(F.data == "daily_playday")
async def daily_playday(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    user = _users.get(user_id) if _users else None
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    claimed_today, current_day, _, game_played = _get_streak_state(user)
    if not claimed_today:
        await callback.answer("Сначала забери награду за сегодня!", show_alert=True)
        return
    if game_played:
        await callback.answer("Игра за сегодня уже сыграна!", show_alert=True)
        return

    await _launch_level(callback, bot, current_day, 1)


@router.callback_query(F.data.startswith("daily_admintest_"))
async def daily_admin_test(callback: CallbackQuery, bot: Bot):
    if not admin_panel.is_admin(callback.from_user.id):
        return
    day = int(callback.data.replace("daily_admintest_", "", 1))
    _game_bonus.setdefault(callback.from_user.id, 200)
    await _launch_level(callback, bot, day, 1)


# ═══════════════════════════════════════════════════════════
# ЛЕСТНИЦА СЛОЖНОСТИ: общий финал раунда для ВСЕХ 7 игр
# ═══════════════════════════════════════════════════════════
async def _bank_and_finish(callback: CallbackQuery, day: int, cleared_level: int, result_text: str):
    user_id = callback.from_user.id
    user = _users.get(user_id) if _users else None
    if user:
        user["login_game_played"] = True
        base_bonus = _game_bonus.pop(user_id, 200)
        mult = LEVEL_BONUS_MULT.get(cleared_level, 0)
        bonus = base_bonus * mult
        if bonus > 0:
            user["balance"] += bonus
            bonus_str = f"{bonus:,}".replace(",", " ")
            result_text += f"\n\n💰 Итоговый бонус: +{bonus_str} монет!"
        else:
            result_text += "\n\nБез бонуса в этот раз - возвращайся завтра за новым днём."
        await database.save_user(user_id, user)
    _level_progress.pop(user_id, None)
    await callback.message.edit_text(result_text, parse_mode="Markdown")
    await callback.answer()


async def _bank_and_finish_new_message(user_id: int, bot: Bot, day: int, cleared_level: int, result_text: str):
    user = _users.get(user_id) if _users else None
    if user:
        user["login_game_played"] = True
        base_bonus = _game_bonus.pop(user_id, 200)
        mult = LEVEL_BONUS_MULT.get(cleared_level, 0)
        bonus = base_bonus * mult
        if bonus > 0:
            user["balance"] += bonus
            bonus_str = f"{bonus:,}".replace(",", " ")
            result_text += f"\n\n💰 Итоговый бонус: +{bonus_str} монет!"
        else:
            result_text += "\n\nБез бонуса в этот раз - возвращайся завтра за новым днём."
        await database.save_user(user_id, user)
    _level_progress.pop(user_id, None)
    await bot.send_message(user_id, result_text, parse_mode="Markdown")


async def _game_round_end(callback: CallbackQuery, day: int, level: int, won: bool, result_text: str, answered: bool = False):
    """Показывает результат раунда + кнопки лестницы (продолжить/забрать при победе,
    повторить/закончить при поражении). Ничего не начисляет само по себе - начисление
    происходит только через _bank_and_finish (см. lvl_bank/lvl_next handlers)."""
    if won and level >= 3:
        # Финальный уровень пройден - авто-банк по максимуму
        await _bank_and_finish(callback, day, level, result_text + "\n\n🏆 Максимальный уровень пройден!")
        return

    if won:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"➡️ Дальше: {LEVEL_NAMES[level + 1]}", callback_data=f"lvl_next_{day}_{level + 1}")],
            [InlineKeyboardButton(text="✅ Забрать награду и закончить", callback_data=f"lvl_bank_{day}_{level}")],
        ])
        text = result_text + f"\n\nПройден {LEVEL_NAMES[level]}! Продолжить дальше (сложнее, но выгоднее) или забрать награду?"
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🔁 Повторить {LEVEL_NAMES[level]}", callback_data=f"lvl_retry_{day}_{level}")],
            [InlineKeyboardButton(text="🏳️ Закончить на сегодня", callback_data=f"lvl_bank_{day}_{level - 1}")],
        ])
        text = result_text + f"\n\nМожешь повторить {LEVEL_NAMES[level]} ещё раз, либо закончить с тем, что уже пройдено."

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    if not answered:
        await callback.answer()


@router.callback_query(F.data.startswith("lvl_bank_"))
async def lvl_bank(callback: CallbackQuery):
    parts = callback.data.split("_")
    day, level = int(parts[2]), int(parts[3])
    await _bank_and_finish(callback, day, level, "🏁 Игра завершена.")


@router.callback_query(F.data.startswith("lvl_next_"))
async def lvl_next(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    day, level = int(parts[2]), int(parts[3])
    await _launch_level(callback, bot, day, level)


@router.callback_query(F.data.startswith("lvl_retry_"))
async def lvl_retry(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    day, level = int(parts[2]), int(parts[3])
    await _launch_level(callback, bot, day, level)


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 1: ЛИСИЧКА, ЧТО ДЕЛАЕШЬ? (Simon Says)
# ═══════════════════════════════════════════════════════════
_fox_games = {}
FOX_EMOJI = ["🐾", "🍃", "🎵", "🔥", "⭐", "💎"]
FOX_LEVELS = {1: {"len": 4, "delay": 0.9}, 2: {"len": 6, "delay": 0.7}, 3: {"len": 8, "delay": 0.55}}


async def start_fox_game(callback: CallbackQuery, level: int = 1):
    cfg = FOX_LEVELS[level]
    pool = FOX_EMOJI[:4] if level == 1 else FOX_EMOJI
    sequence = [random.choice(pool) for _ in range(cfg["len"])]
    _fox_games[callback.from_user.id] = {"sequence": sequence, "position": 0, "level": level, "pool": pool}
    await callback.answer()

    shown = ""
    for emoji in sequence:
        shown += (" ➡️ " if shown else "") + emoji
        await callback.message.edit_text(
            f"🦊 **Лисичка, что делаешь?** ({LEVEL_NAMES[level]})\n\nЗапоминай:\n\n{shown}", parse_mode="Markdown"
        )
        await asyncio.sleep(cfg["delay"])

    await asyncio.sleep(0.6)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=e, callback_data=f"fox_{e}") for e in pool
    ]])
    await callback.message.edit_text(
        f"🦊 **Лисичка, что делаешь?** ({LEVEL_NAMES[level]})\n\nА теперь повтори по порядку!",
        reply_markup=kb, parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("fox_"))
async def fox_play(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _fox_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    picked = callback.data.replace("fox_", "", 1)
    expected = game["sequence"][game["position"]]
    level = game["level"]

    if picked != expected:
        del _fox_games[user_id]
        text = "🦊 **Лисичка, что делаешь?**\n\n😢 Не то! Правильная последовательность была:\n" + " ➡️ ".join(game["sequence"])
        await _game_round_end(callback, 1, level, False, text)
        return

    game["position"] += 1
    if game["position"] == len(game["sequence"]):
        del _fox_games[user_id]
        await _game_round_end(callback, 1, level, True, "🦊 **Лисичка, что делаешь?**\n\n🎉 Всё верно, ты повторил всю последовательность!")
        return

    await callback.answer(f"✅ Верно! Дальше... ({game['position']}/{len(game['sequence'])})")


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 2: ЛОГИКА (найди лишнее -> больше вариантов -> числовая последовательность)
# ═══════════════════════════════════════════════════════════
_logic_games = {}

LOGIC_L1_SETS = [
    {"category": "Фрукты", "items": ["🍎", "🍌", "🍇"], "odd": "🚗"},
    {"category": "Спорт", "items": ["⚽", "🏀", "🎾"], "odd": "📕"},
    {"category": "Животные", "items": ["🐶", "🐱", "🐭"], "odd": "🌳"},
]
LOGIC_L2_SETS = [
    {"category": "Небесные тела и явления", "items": ["☀️", "🌙", "⭐", "☁️", "🌈"], "odd": "🍕"},
    {"category": "Транспорт", "items": ["🚗", "✈️", "🚢", "🚂", "🚲"], "odd": "🍰"},
]
LOGIC_L3_SEQUENCES = [
    {"seq": [2, 4, 6, 8], "answer": 10, "options": [9, 10, 11, 12]},
    {"seq": [1, 2, 4, 8], "answer": 16, "options": [12, 14, 16, 18]},
    {"seq": [1, 4, 9, 16], "answer": 25, "options": [20, 22, 24, 25]},
    {"seq": [3, 6, 9, 12], "answer": 15, "options": [13, 14, 15, 16]},
]


async def start_logic_game(callback: CallbackQuery, level: int = 1):
    if level == 1:
        data = random.choice(LOGIC_L1_SETS)
        options = data["items"] + [data["odd"]]
        random.shuffle(options)
        correct_index = options.index(data["odd"])
        text = f"🧠 **Логика** ({LEVEL_NAMES[level]})\n\nКатегория: **{data['category']}**\nНайди лишний предмет!"
    elif level == 2:
        data = random.choice(LOGIC_L2_SETS)
        options = data["items"] + [data["odd"]]
        random.shuffle(options)
        correct_index = options.index(data["odd"])
        text = f"🧠 **Логика** ({LEVEL_NAMES[level]})\n\nКатегория: **{data['category']}**\nНайди лишний предмет!"
    else:
        data = random.choice(LOGIC_L3_SEQUENCES)
        options = [str(o) for o in data["options"]]
        correct_index = data["options"].index(data["answer"])
        seq_str = ", ".join(str(x) for x in data["seq"])
        text = f"🧠 **Логика** ({LEVEL_NAMES[level]})\n\nПродолжи последовательность:\n{seq_str}, ?"

    _logic_games[callback.from_user.id] = {"level": level, "correct_index": correct_index}
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=opt, callback_data=f"logic_ans_{i}") for i, opt in enumerate(options)
    ]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("logic_ans_"))
async def logic_play(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _logic_games.pop(user_id, None)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    picked = int(callback.data.replace("logic_ans_", "", 1))
    won = (picked == game["correct_index"])
    text = "🧠 **Логика**\n\n" + ("🎉 Верно!" if won else "😢 Не угадал в этот раз.")
    await _game_round_end(callback, 2, game["level"], won, text)


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 3: ВЗРЫВНЫЕ КРЕСТИКИ-НОЛИКИ (3x3 -> 4x4 -> 5x5, бот сильнее)
# ═══════════════════════════════════════════════════════════
_ettt_games = {}
ETTT_LEVELS = {
    1: {"size": 3, "win_len": 3, "mines": 0, "strength": "weak"},
    2: {"size": 4, "win_len": 3, "mines": 1, "strength": "medium"},
    3: {"size": 5, "win_len": 4, "mines": 3, "strength": "strong"},
}


def _ettt_idx(size, r, c):
    return r * size + c


def _ettt_would_win(board, size, win_len, idx, symbol):
    r, c = divmod(idx, size)
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dr, dc in directions:
        count = 1
        for sign in (1, -1):
            rr, cc = r + dr * sign, c + dc * sign
            while 0 <= rr < size and 0 <= cc < size and board[_ettt_idx(size, rr, cc)] == symbol:
                count += 1
                rr += dr * sign
                cc += dc * sign
        if count >= win_len:
            return True
    return False


def _ettt_line_potential(board, size, idx, symbol):
    r, c = divmod(idx, size)
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    total = 0
    for dr, dc in directions:
        count = 1
        for sign in (1, -1):
            rr, cc = r + dr * sign, c + dc * sign
            while 0 <= rr < size and 0 <= cc < size and board[_ettt_idx(size, rr, cc)] == symbol:
                count += 1
                rr += dr * sign
                cc += dc * sign
        total += count ** 2
    return total


def _ettt_bot_move(board, size, win_len, strength):
    empties = [i for i, v in enumerate(board) if v is None]

    if strength == "weak":
        # Слабый бот: блокирует только иногда, в остальном рандом
        for i in empties:
            if _ettt_would_win(board, size, win_len, i, "O"):
                return i
        if random.random() < 0.4:
            for i in empties:
                if _ettt_would_win(board, size, win_len, i, "X"):
                    return i
        return random.choice(empties)

    for i in empties:
        if _ettt_would_win(board, size, win_len, i, "O"):
            return i
    for i in empties:
        if _ettt_would_win(board, size, win_len, i, "X"):
            return i

    if strength == "medium":
        return random.choice(empties)

    # strong: полноценный эвристический выбор среди топ-3
    scored = [(_ettt_line_potential(board, size, i, "O") + _ettt_line_potential(board, size, i, "X") * 0.8, i) for i in empties]
    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:3] if len(scored) >= 3 else scored
    return random.choice(top)[1]


def _ettt_render_kb(board, size):
    symbols = {None: "⬜", "X": "❌", "O": "⭕", "MINE": "💥"}
    rows = []
    for r in range(size):
        row = []
        for c in range(size):
            i = _ettt_idx(size, r, c)
            cb = f"ettt_{i}" if board[i] is None else "daily_noop"
            row.append(InlineKeyboardButton(text=symbols[board[i]], callback_data=cb))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_exploding_ttt(callback: CallbackQuery, bot: Bot, level: int = 1):
    cfg = ETTT_LEVELS[level]
    size = cfg["size"]
    board = [None] * (size * size)
    mines = set(random.sample(range(len(board)), cfg["mines"])) if cfg["mines"] else set()
    _ettt_games[callback.from_user.id] = {"board": board, "mines": mines, "level": level, "cfg": cfg}

    mine_note = "\n(на поле спрятаны мины - будь осторожен)" if cfg["mines"] else ""
    await callback.message.edit_text(
        f"💥 **Взрывные крестики-нолики** ({LEVEL_NAMES[level]})\nТы - ❌, бот - ⭕. Собери {cfg['win_len']} в ряд!{mine_note}",
        reply_markup=_ettt_render_kb(board, size), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ettt_"))
async def ettt_move(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    game = _ettt_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    board, mines, cfg, level = game["board"], game["mines"], game["cfg"], game["level"]
    size, win_len, strength = cfg["size"], cfg["win_len"], cfg["strength"]

    idx = int(callback.data.replace("ettt_", "", 1))
    if board[idx] is not None:
        await callback.answer("Уже занято!", show_alert=True)
        return

    if idx in mines:
        board[idx] = "MINE"
        mines.discard(idx)
        await callback.answer("💥 БАБАХ! Клетка взорвалась, ход сгорел.", show_alert=True)
    else:
        board[idx] = "X"
        if _ettt_would_win(board, size, win_len, idx, "X"):
            del _ettt_games[user_id]
            await callback.message.edit_reply_markup(reply_markup=_ettt_render_kb(board, size))
            await _game_round_end(callback, 3, level, True, f"💥 **Взрывные крестики-нолики**\n\n🎉 Ты собрал {win_len} в ряд и победил!", answered=True)
            return
        await callback.answer()

    if all(v is not None for v in board):
        del _ettt_games[user_id]
        await callback.message.edit_reply_markup(reply_markup=_ettt_render_kb(board, size))
        await _game_round_end(callback, 3, level, False, "💥 **Взрывные крестики-нолики**\n\n🤝 Поле заполнено, ничья.", answered=True)
        return

    bot_idx = _ettt_bot_move(board, size, win_len, strength)
    if bot_idx in mines:
        board[bot_idx] = "MINE"
        mines.discard(bot_idx)
    else:
        board[bot_idx] = "O"
        if _ettt_would_win(board, size, win_len, bot_idx, "O"):
            del _ettt_games[user_id]
            await callback.message.edit_reply_markup(reply_markup=_ettt_render_kb(board, size))
            await _game_round_end(callback, 3, level, False, "💥 **Взрывные крестики-нолики**\n\n😢 Бот собрал линию первым.", answered=True)
            return

    if all(v is not None for v in board):
        del _ettt_games[user_id]
        await callback.message.edit_reply_markup(reply_markup=_ettt_render_kb(board, size))
        await _game_round_end(callback, 3, level, False, "💥 **Взрывные крестики-нолики**\n\n🤝 Поле заполнено, ничья.", answered=True)
        return

    await callback.message.edit_reply_markup(reply_markup=_ettt_render_kb(board, size))


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 4: СЛОВА (короче без пустышек -> длиннее с пустышками -> длинное с перемешиванием)
# ═══════════════════════════════════════════════════════════
_words_games = {}
WORDS_L1 = ["БАНК", "ЗАВОД", "ДОХОД", "БОГАЧ", "АЛМАЗ"]
WORDS_L2 = ["ТАЙКУН", "МОНЕТА", "БИЗНЕС", "ВЛАСТЬ", "КАПИТАЛ", "ПРИБЫЛЬ", "ИМПЕРИЯ"]
WORDS_L3 = ["ИНВЕСТОР", "СОСТОЯНИЕ", "ЭКОНОМИКА", "МИЛЛИОНЕР", "АКЦИОНЕР"]
DECOY_POOL = list("ЙЦУКЕНГШЩЗФЫВАПРОЛДЖЭЯЧСМИТЬБЮ")
WORDS_MAX_MISTAKES = 3
WORDS_LEVEL_CFG = {1: {"pool": WORDS_L1, "decoys": 0, "reshuffle": False},
                   2: {"pool": WORDS_L2, "decoys": 2, "reshuffle": False},
                   3: {"pool": WORDS_L3, "decoys": 3, "reshuffle": True}}


def _words_render_kb(game):
    rows, row = [], []
    for i, letter in enumerate(game["remaining"]):
        row.append(InlineKeyboardButton(text=letter, callback_data=f"word_{i}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_words_game(callback: CallbackQuery, level: int = 1):
    cfg = WORDS_LEVEL_CFG[level]
    target = random.choice(cfg["pool"])
    letters = list(target)
    decoy_choices = [c for c in DECOY_POOL if c not in letters]
    letters += random.sample(decoy_choices, min(cfg["decoys"], len(decoy_choices)))
    random.shuffle(letters)

    game = {"target": target, "remaining": letters, "progress": 0, "mistakes": 0, "level": level, "reshuffle": cfg["reshuffle"]}
    _words_games[callback.from_user.id] = game

    text = f"📝 **Слова** ({LEVEL_NAMES[level]})\nСобери слово из {len(target)} букв по порядку!\nОшибок допустимо: {WORDS_MAX_MISTAKES}"
    await callback.message.edit_text(text, reply_markup=_words_render_kb(game), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("word_"))
async def words_play(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _words_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    i = int(callback.data.replace("word_", "", 1))
    if i >= len(game["remaining"]):
        await callback.answer()
        return

    letter = game["remaining"][i]
    expected = game["target"][game["progress"]]

    if letter == expected:
        game["remaining"].pop(i)
        game["progress"] += 1
        if game["reshuffle"]:
            random.shuffle(game["remaining"])
        if game["progress"] == len(game["target"]):
            del _words_games[user_id]
            await _game_round_end(callback, 4, game["level"], True, f"📝 **Слова**\n\n🎉 Собрано слово: **{game['target']}**!")
            return
        await callback.answer("✅ Верно!")
    else:
        game["mistakes"] += 1
        if game["mistakes"] >= WORDS_MAX_MISTAKES:
            del _words_games[user_id]
            await _game_round_end(callback, 4, game["level"], False, f"📝 **Слова**\n\n😢 Слишком много ошибок. Слово было: **{game['target']}**")
            return
        await callback.answer(f"❌ Не та буква ({game['mistakes']}/{WORDS_MAX_MISTAKES})", show_alert=True)
        return

    await callback.message.edit_text(
        f"📝 **Слова** ({LEVEL_NAMES[game['level']]})\nСобери слово из {len(game['target'])} букв по порядку!\nОшибок: {game['mistakes']}/{WORDS_MAX_MISTAKES}",
        reply_markup=_words_render_kb(game), parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 5: НАЙДИ ПАРУ (с джокером - поле растёт по уровням)
# ═══════════════════════════════════════════════════════════
_pairs_games = {}
PAIRS_EMOJI_POOL = ["🍎", "🍌", "🍇", "🍉", "🍒", "🥝", "🍑", "🍋", "🥥", "🍍", "🥭", "🍈"]
WILDCARD = "👑"
PAIRS_LEVEL_CFG = {1: {"pairs": 4, "attempts": 6}, 2: {"pairs": 8, "attempts": 10}, 3: {"pairs": 12, "attempts": 9}}


def _pairs_render_kb(game):
    cards, revealed, matched = game["cards"], game["revealed"], game["matched"]
    rows, row = [], []
    for i in range(len(cards)):
        text = cards[i] if (matched[i] or revealed[i]) else "❓"
        cb = "daily_noop" if matched[i] else f"pair_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_memory_game(callback: CallbackQuery, level: int = 1):
    cfg = PAIRS_LEVEL_CFG[level]
    emojis = PAIRS_EMOJI_POOL[:cfg["pairs"]]
    cards = emojis * 2 + [WILDCARD]
    random.shuffle(cards)
    game = {
        "cards": cards, "revealed": [False] * len(cards), "matched": [False] * len(cards),
        "first_pick": None, "attempts": 0, "level": level, "max_attempts": cfg["attempts"],
    }
    _pairs_games[callback.from_user.id] = game
    await callback.message.edit_text(
        f"🃏 **Найди пару** ({LEVEL_NAMES[level]})\n{WILDCARD} - джокер, совпадает с чем угодно!\nПопыток: {cfg['attempts']}",
        reply_markup=_pairs_render_kb(game), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pair_"))
async def memory_pick(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _pairs_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    idx = int(callback.data.replace("pair_", "", 1))
    if game["matched"][idx] or game["revealed"][idx]:
        await callback.answer()
        return

    if game["first_pick"] is None:
        game["revealed"][idx] = True
        game["first_pick"] = idx
        await callback.message.edit_reply_markup(reply_markup=_pairs_render_kb(game))
        await callback.answer()
        return

    first = game["first_pick"]
    game["revealed"][idx] = True
    game["attempts"] += 1

    await callback.message.edit_reply_markup(reply_markup=_pairs_render_kb(game))
    await callback.answer()
    await asyncio.sleep(1.2)

    is_match = (game["cards"][first] == game["cards"][idx] or game["cards"][first] == WILDCARD or game["cards"][idx] == WILDCARD)
    if is_match:
        game["matched"][first] = True
        game["matched"][idx] = True

    game["revealed"][first] = False
    game["revealed"][idx] = False
    game["first_pick"] = None

    if all(game["matched"]):
        del _pairs_games[user_id]
        await _game_round_end(callback, 5, game["level"], True, "🃏 **Найди пару**\n\n🎉 Все пары найдены!", answered=True)
        return

    if game["attempts"] >= game["max_attempts"]:
        del _pairs_games[user_id]
        await _game_round_end(callback, 5, game["level"], False, "🃏 **Найди пару**\n\n😢 Попытки закончились.", answered=True)
        return

    await callback.message.edit_text(
        f"🃏 **Найди пару** ({LEVEL_NAMES[game['level']]})\nПопытка {game['attempts']}/{game['max_attempts']}",
        reply_markup=_pairs_render_kb(game), parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 6: СОБЕРИ КАРТИНКУ ПО ПАМЯТИ (поле растёт, времени меньше)
# ═══════════════════════════════════════════════════════════
_picture_games = {}
PICTURE_LEVEL_CFG = {1: {"size": 4, "mistakes": 3, "memorize": 5}, 2: {"size": 5, "mistakes": 3, "memorize": 4}, 3: {"size": 6, "mistakes": 4, "memorize": 3}}


def _pattern_diamond(size):
    center = (size - 1) / 2
    radius = size / 2 - 0.4
    return [1 if abs(r - center) + abs(c - center) <= radius else 0 for r in range(size) for c in range(size)]


def _pattern_cross(size):
    mid = size // 2
    mid2 = mid - 1 if size % 2 == 0 else mid
    return [1 if (r in (mid, mid2) or c in (mid, mid2)) else 0 for r in range(size) for c in range(size)]


def _pattern_ring(size):
    return [1 if (r == 0 or r == size - 1 or c == 0 or c == size - 1) else 0 for r in range(size) for c in range(size)]


def _picture_render_kb(game, memorize_phase):
    size = game["size"]
    rows, row = [], []
    for i in range(size * size):
        if memorize_phase:
            text, cb = ("🟩" if game["pattern"][i] else "⬜"), "daily_noop"
        else:
            if i in game["correct_taps"]:
                text = "✅"
            elif i in game["wrong_taps"]:
                text = "❌"
            else:
                text = "❓"
            cb = "daily_noop" if (i in game["correct_taps"] or i in game["wrong_taps"]) else f"pic_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == size:
            rows.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_picture_game(callback: CallbackQuery, level: int = 1):
    cfg = PICTURE_LEVEL_CFG[level]
    size = cfg["size"]
    pattern = random.choice([_pattern_diamond(size), _pattern_cross(size), _pattern_ring(size)])
    game = {"pattern": pattern, "size": size, "correct_taps": set(), "wrong_taps": set(), "mistakes": 0, "level": level, "max_mistakes": cfg["mistakes"]}
    _picture_games[callback.from_user.id] = game

    await callback.message.edit_text(
        f"🎨 **Собери картинку по памяти** ({LEVEL_NAMES[level]})\n\nЗапоминай, где закрашено!",
        reply_markup=_picture_render_kb(game, memorize_phase=True), parse_mode="Markdown"
    )
    await callback.answer()
    await asyncio.sleep(cfg["memorize"])

    await callback.message.edit_text(
        f"🎨 **Собери картинку по памяти** ({LEVEL_NAMES[level]})\n\nТеперь повтори узор! Ошибок допустимо: {cfg['mistakes']}",
        reply_markup=_picture_render_kb(game, memorize_phase=False), parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("pic_"))
async def picture_play(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _picture_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    idx = int(callback.data.replace("pic_", "", 1))
    if idx in game["correct_taps"] or idx in game["wrong_taps"]:
        await callback.answer()
        return

    if game["pattern"][idx]:
        game["correct_taps"].add(idx)
    else:
        game["wrong_taps"].add(idx)
        game["mistakes"] += 1

    total_filled = sum(game["pattern"])

    if game["mistakes"] >= game["max_mistakes"]:
        del _picture_games[user_id]
        await _game_round_end(callback, 6, game["level"], False, "🎨 **Собери картинку по памяти**\n\n😢 Слишком много ошибок.")
        return

    if len(game["correct_taps"]) == total_filled:
        del _picture_games[user_id]
        await _game_round_end(callback, 6, game["level"], True, "🎨 **Собери картинку по памяти**\n\n🎉 Узор полностью восстановлен!")
        return

    await callback.message.edit_text(
        f"🎨 **Собери картинку по памяти** ({LEVEL_NAMES[game['level']]})\nОшибок: {game['mistakes']}/{game['max_mistakes']}",
        reply_markup=_picture_render_kb(game, memorize_phase=False), parse_mode="Markdown"
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 7: ДЕТЕКТИВ (3 подозреваемых -> 4 -> 5, улик больше)
# ═══════════════════════════════════════════════════════════
_detective_games = {}
DETECTIVE_CASES = {
    1: [{
        "intro": "🔍 Пропал кошелёк в кафе! Есть 3 подозреваемых.",
        "clues": ["Улика 1: преступник сидел за столиком у окна.", "Улика 2: у преступника была синяя куртка."],
        "suspects": ["Настя (не у окна, синяя куртка)", "Олег (у окна, синяя куртка)", "Ира (у окна, красная куртка)"],
        "culprit": 1,
    }],
    2: [
        {
            "intro": "🔍 Из сейфа офиса пропала крупная сумма денег! Есть 4 подозреваемых.",
            "clues": [
                "Улика 1: преступник заходил в офис после 22:00.",
                "Улика 2: у преступника были испачканы руки в мазуте.",
                "Улика 3: преступник знал код от сейфа.",
            ],
            "suspects": ["Анна (бухгалтер)", "Виктор (охранник)", "Игорь (механик)", "Дима (курьер)"],
            "culprit": 2,
        },
        {
            "intro": "🔍 На заводе кто-то испортил станок! Есть 4 подозреваемых.",
            "clues": [
                "Улика 1: у преступника есть доступ к цеху ночью.",
                "Улика 2: преступник конфликтовал с начальником на прошлой неделе.",
                "Улика 3: на месте нашли отпечаток ботинка 44 размера.",
            ],
            "suspects": ["Оля (уборщица)", "Пётр (сменный мастер)", "Сергей (охранник)", "Марина (бухгалтер)"],
            "culprit": 1,
        },
    ],
    3: [{
        "intro": "🔍 Со склада пропала партия товара! Есть 5 подозреваемых.",
        "clues": [
            "Улика 1: у преступника есть доступ к складу ночью.",
            "Улика 2: преступник был на работе в день кражи.",
            "Улика 3: рост преступника выше 180 см.",
            "Улика 4: преступник умеет пользоваться отмычкой.",
        ],
        "suspects": [
            "Игорь (доступ есть, был на работе, рост 175, отмычкой не владеет)",
            "Соня (доступа к складу нет)",
            "Борис (доступ есть, в тот день не работал)",
            "Клим (доступ есть, был на работе, рост 185, владеет отмычкой)",
            "Вера (доступ есть, была на работе, рост 190, отмычкой не владеет)",
        ],
        "culprit": 3,
    }],
}


async def start_detective_game(callback: CallbackQuery, level: int = 1):
    case = random.choice(DETECTIVE_CASES[level])
    _detective_games[callback.from_user.id] = {"case": case, "step": 0, "level": level}

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➡️ Далее", callback_data="det_next")]])
    await callback.message.edit_text(f"🔍 **Детектив** ({LEVEL_NAMES[level]})\n\n{case['intro']}", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "det_next")
async def det_next(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _detective_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    case = game["case"]
    game["step"] += 1
    step = game["step"]
    shown_clues = "\n".join(case["clues"][:step])

    if step < len(case["clues"]):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➡️ Далее", callback_data="det_next")]])
        await callback.message.edit_text(f"🔍 **Детектив**\n\n{shown_clues}", reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        return

    rows = [[InlineKeyboardButton(text=name, callback_data=f"det_guess_{i}")] for i, name in enumerate(case["suspects"])]
    text = f"🔍 **Детектив**\n\n{shown_clues}\n\nКто виновен?"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("det_guess_"))
async def det_guess(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _detective_games.pop(user_id, None)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    case = game["case"]
    picked = int(callback.data.replace("det_guess_", "", 1))
    won = (picked == case["culprit"])
    culprit_name = case["suspects"][case["culprit"]]

    text = "🔍 **Детектив**\n\n" + (
        "🎉 Дело раскрыто! Ты вычислил виновного!" if won
        else f"😢 Мимо. На самом деле виновен был: {culprit_name}"
    )
    await _game_round_end(callback, 7, game["level"], won, text)
