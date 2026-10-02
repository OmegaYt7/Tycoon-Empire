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
    is_admin = admin_panel.is_admin(user_id)

    if is_admin:
        text = "🎁 **Ежедневная награда**\n\n🧪 Ты админ - все 7 дней доступны для теста, жми любой!"
    elif claimed_today and game_played:
        text = "🎁 **Ежедневная награда**\n\nСегодня всё забрано и сыграно - возвращайся завтра!"
    elif claimed_today and not game_played:
        text = f"🎁 **Ежедневная награда**\n\nНаграда за День {current_day} уже получена!\n🎮 Осталось сыграть загадочную игру дня - жми и узнаешь!"
    else:
        text = (
            f"🎁 **Ежедневная награда**\n\n"
            f"Собери награду за День {current_day} из 7!\n"
            f"🎮 Какая сегодня игра - секрет, узнаешь после получения награды!\n"
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
    text = (
        f"✅ **День {current_day} получен!**\n\n"
        f"💰 +{coins_str} монет{bonus_text}\n\n"
        f"🎮 Сегодня тебя ждёт загадочная игра - жми и узнаешь какая!\n"
        f"3 уровня сложности - чем дальше пройдёшь, тем больше бонус!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Играть (сюрприз!)", callback_data="daily_playday")]
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
# ДЕНЬ 2: ЛОГИКА
# Генерируется ПРОЦЕДУРНО - вариантов тысячи, не повторится месяцами.
#   Уровень 1/2: НАСТОЯЩАЯ логическая задача на транзитивность - дана цепочка
#                сравнений ("А тяжелее Б, Б тяжелее В"), нужно сделать вывод,
#                кто самый/самый. На уровне 2 утверждения даются вперемешку
#                (не по порядку) - нужно самому выстроить цепочку в уме.
#   Уровень 3: числовая последовательность одного из 4 типов (арифметическая,
#              геометрическая, квадраты, Фибоначчи) со случайными параметрами.
# ═══════════════════════════════════════════════════════════
_logic_games = {}

LOGIC_NAMES = ["Антон", "Борис", "Вика", "Галя", "Денис", "Елена", "Женя", "Иван", "Катя", "Лена", "Миша", "Настя", "Олег", "Паша", "Рита", "Саша"]
LOGIC_RELATIONS = [
    {"more": "тяжелее", "max_q": "самый тяжёлый", "min_q": "самый лёгкий"},
    {"more": "выше", "max_q": "самый высокий", "min_q": "самый низкий"},
    {"more": "старше", "max_q": "самый старший", "min_q": "самый младший"},
    {"more": "быстрее", "max_q": "самый быстрый", "min_q": "самый медленный"},
    {"more": "богаче", "max_q": "самый богатый", "min_q": "самый бедный"},
    {"more": "сильнее", "max_q": "самый сильный", "min_q": "самый слабый"},
]


def _gen_logic_order_riddle(n_people, shuffle_statements):
    rel = random.choice(LOGIC_RELATIONS)
    names = random.sample(LOGIC_NAMES, n_people)
    # names[0] - "больше всех" по выбранному признаку, names[-1] - "меньше всех"
    statements = [f"{names[i]} {rel['more']} {names[i + 1]}" for i in range(n_people - 1)]
    order = statements[:]
    if shuffle_statements:
        random.shuffle(order)

    ask_min = random.random() < 0.5
    answer, question = (names[-1], rel["min_q"]) if ask_min else (names[0], rel["max_q"])

    options = names[:]
    random.shuffle(options)
    correct_index = options.index(answer)

    stmt_text = "\n".join(f"- {s}" for s in order)
    text = f"{stmt_text}\n\nКто {question}?"
    return options, correct_index, text


def _gen_logic_sequence():
    kind = random.choice(["arith", "geom", "square", "fib"])
    if kind == "arith":
        start, step = random.randint(1, 10), random.randint(2, 9)
        seq = [start + step * i for i in range(4)]
        answer = start + step * 4
    elif kind == "geom":
        start, ratio = random.randint(1, 3), random.randint(2, 3)
        seq = [start * (ratio ** i) for i in range(4)]
        answer = start * (ratio ** 4)
    elif kind == "square":
        offset = random.randint(0, 3)
        seq = [(offset + i) ** 2 for i in range(1, 5)]
        answer = (offset + 5) ** 2
    else:
        a, b = random.randint(1, 5), random.randint(1, 5)
        seq = [a, b]
        for _ in range(2):
            seq.append(seq[-1] + seq[-2])
        answer = seq[-1] + seq[-2]

    wrong = set()
    while len(wrong) < 3:
        delta = random.choice([-3, -2, -1, 1, 2, 3])
        candidate = answer + delta
        if candidate > 0 and candidate != answer:
            wrong.add(candidate)
    options = [answer] + list(wrong)
    random.shuffle(options)
    correct_index = options.index(answer)
    seq_str = ", ".join(str(x) for x in seq)
    text = f"Продолжи последовательность:\n**{seq_str}, ?**"
    return [str(o) for o in options], correct_index, text


async def start_logic_game(callback: CallbackQuery, level: int = 1):
    if level == 1:
        options, correct_index, subtext = _gen_logic_order_riddle(3, shuffle_statements=False)
    elif level == 2:
        options, correct_index, subtext = _gen_logic_order_riddle(4, shuffle_statements=True)
    else:
        options, correct_index, subtext = _gen_logic_sequence()

    _logic_games[callback.from_user.id] = {"level": level, "correct_index": correct_index}
    text = f"🧠 **Логика** ({LEVEL_NAMES[level]})\n\n{subtext}"
    per_row = 4 if level == 3 else 2  # цифры короткие - в ряд; имена - по 2, чтобы не теснились
    rows, row = [], []
    for i, opt in enumerate(options):
        row.append(InlineKeyboardButton(text=opt, callback_data=f"logic_ans_{i}"))
        if len(row) == per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
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
    1: {"size": 3, "win_len": 3, "mines": 0, "strength": "weak", "think_delay": 0.5},
    2: {"size": 4, "win_len": 3, "mines": 1, "strength": "medium", "think_delay": 0.9},
    3: {"size": 5, "win_len": 4, "mines": 3, "strength": "strong", "think_delay": 1.4},
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

    # Бот "думает" - пауза растёт со сложностью, чтобы чувствовался вес хода
    await callback.message.edit_text(
        f"💥 **Взрывные крестики-нолики** ({LEVEL_NAMES[level]})\n🤔 Бот думает...",
        reply_markup=_ettt_render_kb(board, size), parse_mode="Markdown"
    )
    await asyncio.sleep(cfg["think_delay"])

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
    """Буквы НЕ пропадают из раскладки при правильном тапе - на их месте
    остаётся точка (•), позиции остальных букв не сдвигаются."""
    rows, row = [], []
    for i, letter in enumerate(game["letters"]):
        text = "•" if i in game["picked"] else letter
        cb = "daily_noop" if i in game["picked"] else f"word_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
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

    game = {"target": target, "letters": letters, "picked": set(), "progress": 0, "mistakes": 0, "level": level, "reshuffle": cfg["reshuffle"]}
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
    if i in game["picked"]:
        await callback.answer()
        return

    letter = game["letters"][i]
    expected = game["target"][game["progress"]]

    if letter == expected:
        game["picked"].add(i)
        game["progress"] += 1
        if game["reshuffle"]:
            # На сложном уровне буквы на ЕЩЁ НЕ угаданных позициях перемешиваются
            # заново между собой (сами позиции с точками не трогаем)
            free_positions = [j for j in range(len(game["letters"])) if j not in game["picked"]]
            free_letters = [game["letters"][j] for j in free_positions]
            random.shuffle(free_letters)
            for pos, letter_val in zip(free_positions, free_letters):
                game["letters"][pos] = letter_val
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
        f"🃏 **Найди пару** ({LEVEL_NAMES[level]})\n{WILDCARD} - джокер: совпадает с любой картой и сразу закрывает всю её пару!\nДопустимо ошибок: {cfg['attempts']} (совпадения бесплатны)",
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

    await callback.message.edit_reply_markup(reply_markup=_pairs_render_kb(game))
    await callback.answer()
    await asyncio.sleep(1.2)

    first_is_joker = game["cards"][first] == WILDCARD
    idx_is_joker = game["cards"][idx] == WILDCARD
    is_match = (game["cards"][first] == game["cards"][idx] or first_is_joker or idx_is_joker)

    if first_is_joker or idx_is_joker:
        # ВАЖНО (фикс бага): джокер - одна карта, а карт всего нечётное число
        # (2*пар+1). Если просто "съесть" джокером одну карту пары, её
        # настоящий близнец останется на поле без пары навсегда, и игру
        # невозможно выиграть. Поэтому джокер сразу закрывает ТРИ клетки:
        # себя, выбранную карту и её настоящую пару - чётность сохраняется.
        other = idx if first_is_joker else first
        game["matched"][first] = True
        game["matched"][idx] = True
        other_emoji = game["cards"][other]
        twin = next((i for i, c in enumerate(game["cards"]) if c == other_emoji and i != other and not game["matched"][i]), None)
        if twin is not None:
            game["matched"][twin] = True
    elif is_match:
        game["matched"][first] = True
        game["matched"][idx] = True
    else:
        # Попытка тратится ТОЛЬКО при ошибке - угаданные пары бесплатны
        game["attempts"] += 1

    game["revealed"][first] = False
    game["revealed"][idx] = False
    game["first_pick"] = None

    # Победа, если совпали ВСЕ обычные карты - джокер может случайно
    # остаться непойманным (если игрок угадал все пары напрямую, ни разу
    # его не тронув), и это тоже честная победа, а не зависание.
    real_cards_done = all(game["matched"][i] for i in range(len(game["cards"])) if game["cards"][i] != WILDCARD)
    if real_cards_done:
        del _pairs_games[user_id]
        await _game_round_end(callback, 5, game["level"], True, "🃏 **Найди пару**\n\n🎉 Все пары найдены!", answered=True)
        return

    if game["attempts"] >= game["max_attempts"]:
        del _pairs_games[user_id]
        await _game_round_end(callback, 5, game["level"], False, "🃏 **Найди пару**\n\n😢 Попытки закончились.", answered=True)
        return

    await callback.message.edit_text(
        f"🃏 **Найди пару** ({LEVEL_NAMES[game['level']]})\nОшибок: {game['attempts']}/{game['max_attempts']}",
        reply_markup=_pairs_render_kb(game), parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 6: СОБЕРИ КАРТИНКУ ПО ПАМЯТИ
# Переделано в пространственную "Саймон говорит": клетки загораются ПО ОДНОЙ
# в определённом порядке, игрок должен повторить ИМЕННО В ТОМ ЖЕ ПОРЯДКЕ
# (не просто найти все закрашенные - порядок имеет значение, это сильно
# сложнее старой версии и не решается случайным перебором).
# ═══════════════════════════════════════════════════════════
_picture_games = {}
PICTURE_LEVEL_CFG = {
    1: {"size": 4, "seq_len": 4, "delay": 0.7},
    2: {"size": 5, "seq_len": 6, "delay": 0.55},
    3: {"size": 6, "seq_len": 8, "delay": 0.4},
}


def _picture_render_kb(size, done_count, highlight_idx=None):
    """done_count клеток уже правильно повторены (показываем их как ✅,
    остальные как ❓); highlight_idx - клетка, которая сейчас "горит" во
    время фазы показа последовательности."""
    rows, row = [], []
    for i in range(size * size):
        if highlight_idx is not None and i == highlight_idx:
            text, cb = "🟩", "daily_noop"
        else:
            text, cb = "❓", f"pic_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == size:
            rows.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _picture_render_progress_kb(size, sequence, position):
    """Клавиатура на этапе повтора: уже верно нажатые (по порядку) клетки
    отмечены ✅, остальные - как обычные кликабельные ❓."""
    done = set(sequence[:position])
    rows, row = [], []
    for i in range(size * size):
        text = "✅" if i in done else "❓"
        cb = "daily_noop" if i in done else f"pic_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == size:
            rows.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_picture_game(callback: CallbackQuery, level: int = 1):
    cfg = PICTURE_LEVEL_CFG[level]
    size = cfg["size"]
    total = size * size
    sequence = random.sample(range(total), cfg["seq_len"])  # уникальные позиции без повторов
    _picture_games[callback.from_user.id] = {"size": size, "sequence": sequence, "position": 0, "level": level}
    await callback.answer()

    for step, idx in enumerate(sequence):
        kb = _picture_render_kb(size, step, highlight_idx=idx)
        await callback.message.edit_text(
            f"🎨 **Собери картинку по памяти** ({LEVEL_NAMES[level]})\nЗапоминай порядок! ({step + 1}/{len(sequence)})",
            reply_markup=kb, parse_mode="Markdown"
        )
        await asyncio.sleep(cfg["delay"])

    kb = _picture_render_progress_kb(size, sequence, 0)
    await callback.message.edit_text(
        f"🎨 **Собери картинку по памяти** ({LEVEL_NAMES[level]})\nА теперь повтори в ТОМ ЖЕ порядке!",
        reply_markup=kb, parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("pic_"))
async def picture_play(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _picture_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    idx = int(callback.data.replace("pic_", "", 1))
    expected = game["sequence"][game["position"]]

    if idx != expected:
        del _picture_games[user_id]
        order_str = " → ".join(str(n) for n in game["sequence"])
        await _game_round_end(callback, 6, game["level"], False, f"🎨 **Собери картинку по памяти**\n\n😢 Не тот порядок! Правильная последовательность клеток была: {order_str}")
        return

    game["position"] += 1
    if game["position"] == len(game["sequence"]):
        del _picture_games[user_id]
        await _game_round_end(callback, 6, game["level"], True, "🎨 **Собери картинку по памяти**\n\n🎉 Весь порядок повторён без ошибок!")
        return

    kb = _picture_render_progress_kb(game["size"], game["sequence"], game["position"])
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(f"✅ Верно! ({game['position']}/{len(game['sequence'])})")


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 7: ДЕТЕКТИВ
# Полностью процедурная генерация (сценарий + имена + признаки собираются
# случайно из больших пулов - реальных уникальных комбинаций тысячи, не
# повторится за месяцы игры), и вместо угадайки с одного тыка теперь
# настоящая интерактивная дедукция: ошибся - тебе называют, какой именно
# улике не соответствовал этот подозреваемый, он выбывает, и есть
# ограниченное число попыток (нельзя просто перебрать всех подряд).
# ═══════════════════════════════════════════════════════════
_detective_games = {}

DETECTIVE_DIMENSIONS = [
    {"clue": "у преступника есть доступ к месту преступления ночью", "true": "есть доступ ночью", "false": "доступа ночью нет"},
    {"clue": "преступник был на месте в день происшествия", "true": "был на месте в тот день", "false": "в тот день там не был"},
    {"clue": "рост преступника выше 180 см", "true": "рост выше 180 см", "false": "рост обычный"},
    {"clue": "преступник умеет пользоваться отмычкой", "true": "умеет вскрывать замки", "false": "не умеет вскрывать замки"},
    {"clue": "преступник конфликтовал с начальством", "true": "конфликтовал с начальством", "false": "конфликтов не было"},
    {"clue": "у преступника нет алиби на вечер происшествия", "true": "алиби нет", "false": "есть алиби"},
    {"clue": "преступник знал секретный код доступа", "true": "знал код доступа", "false": "код не знал"},
    {"clue": "у преступника были испачканы руки", "true": "руки испачканы", "false": "руки чистые"},
    {"clue": "преступник недавно брал отгул", "true": "недавно брал отгул", "false": "отгулов не брал"},
    {"clue": "у преступника есть судимость", "true": "есть судимость", "false": "судимости нет"},
]
DETECTIVE_SCENARIOS = [
    "🔍 Из сейфа офиса пропала крупная сумма денег!",
    "🔍 На заводе кто-то испортил дорогой станок!",
    "🔍 Пропал редкий экспонат из музея!",
    "🔍 Со склада исчезла партия товара!",
    "🔍 Из кассы магазина пропала выручка!",
    "🔍 Кто-то взломал сервер компании!",
    "🔍 В гараже кто-то повредил служебную машину!",
    "🔍 Из архива пропали важные документы!",
]
DETECTIVE_SUSPECT_POOL = [
    ("Анна", "бухгалтер"), ("Виктор", "охранник"), ("Игорь", "механик"), ("Дима", "курьер"),
    ("Оля", "уборщица"), ("Пётр", "мастер"), ("Сергей", "сторож"), ("Марина", "кассир"),
    ("Настя", "стажёр"), ("Олег", "инженер"), ("Ира", "менеджер"), ("Клим", "техник"),
    ("Вера", "секретарь"), ("Борис", "грузчик"), ("Соня", "продавец"), ("Артём", "водитель"),
]
DETECTIVE_LEVEL_CFG = {1: {"suspects": 3, "clues": 2, "max_wrong": 1}, 2: {"suspects": 4, "clues": 3, "max_wrong": 2}, 3: {"suspects": 5, "clues": 4, "max_wrong": 2}}


def _gen_detective_case(level):
    cfg = DETECTIVE_LEVEL_CFG[level]
    dims = random.sample(DETECTIVE_DIMENSIONS, cfg["clues"])
    picked = random.sample(DETECTIVE_SUSPECT_POOL, cfg["suspects"])
    scenario = random.choice(DETECTIVE_SCENARIOS)

    traits = [[random.random() < 0.5 for _ in dims] for _ in picked]
    culprit_idx = random.randrange(len(picked))
    traits[culprit_idx] = [True] * len(dims)

    # Гарантируем, что виновный - единственный, кто подходит под ВСЕ улики
    for i in range(len(picked)):
        if i == culprit_idx:
            continue
        if all(traits[i]):
            traits[i][random.randrange(len(dims))] = False

    suspects = []  # короткое имя для кнопки
    dossiers = []  # полное досье для текста сообщения
    fail_reason = []
    for i, (name, profession) in enumerate(picked):
        desc = ", ".join(dims[d]["true"] if traits[i][d] else dims[d]["false"] for d in range(len(dims)))
        suspects.append(name)
        dossiers.append(f"**{i + 1}. {name}** ({profession}) - {desc}")
        first_fail = next((d for d in range(len(dims)) if not traits[i][d]), None)
        fail_reason.append(first_fail)

    clues = [f"Улика {i + 1}: {dims[i]['clue']}." for i in range(len(dims))]
    return {
        "intro": scenario, "clues": clues, "suspects": suspects, "dossiers": dossiers,
        "culprit": culprit_idx, "fail_reason": fail_reason, "max_wrong": cfg["max_wrong"],
    }


async def start_detective_game(callback: CallbackQuery, level: int = 1):
    case = _gen_detective_case(level)
    _detective_games[callback.from_user.id] = {"case": case, "step": 0, "level": level, "wrong": 0, "eliminated": set()}

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

    dossiers = "\n".join(case["dossiers"])
    await _detective_show_suspects(callback, game, f"🔍 **Детектив**\n\n{shown_clues}\n\n👤 **Досье подозреваемых:**\n{dossiers}\n\nКого обвинишь?")


async def _detective_show_suspects(callback: CallbackQuery, game, header_text: str):
    case = game["case"]
    rows, row = [], []
    for i, name in enumerate(case["suspects"]):
        if i in game["eliminated"]:
            continue
        row.append(InlineKeyboardButton(text=name, callback_data=f"det_guess_{i}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    wrong_left = case["max_wrong"] - game["wrong"]
    text = header_text + f"\n\n❗ Неверных обвинений в запасе: {wrong_left}"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("det_guess_"))
async def det_guess(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _detective_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    case = game["case"]
    picked = int(callback.data.replace("det_guess_", "", 1))

    if picked == case["culprit"]:
        del _detective_games[user_id]
        culprit_name = case["suspects"][case["culprit"]]
        await _game_round_end(callback, 7, game["level"], True, f"🔍 **Детектив**\n\n🎉 Дело раскрыто! Виновен был {culprit_name}!")
        return

    game["wrong"] += 1
    game["eliminated"].add(picked)
    fail_dim = case["fail_reason"][picked]
    suspect_name = case["suspects"][picked]

    if fail_dim is not None:
        reason = f"❌ {suspect_name} не подходит: не совпадает Улика {fail_dim + 1}."
    else:
        reason = f"❌ {suspect_name} невиновен."

    shown_clues = "\n".join(case["clues"])
    dossiers = "\n".join(case["dossiers"])

    if game["wrong"] > case["max_wrong"]:
        del _detective_games[user_id]
        culprit_name = case["suspects"][case["culprit"]]
        await _game_round_end(callback, 7, game["level"], False, f"🔍 **Детектив**\n\n{reason}\n\n😢 Попытки закончились. Виновен был: {culprit_name}")
        return

    await _detective_show_suspects(callback, game, f"🔍 **Детектив**\n\n{shown_clues}\n\n👤 **Досье подозреваемых:**\n{dossiers}\n\n{reason}\nПопробуй ещё раз - кого обвинишь?")
