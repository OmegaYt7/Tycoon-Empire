"""
daily_login.py
Ежедневная награда (7-дневный календарь) + СВОЯ уникальная мини-игра на
каждый день цикла (не рандом, а строго закреплено):
  День 1 - Лисичка, что делаешь? (Simon Says)
  День 2 - Логика (найди лишнее)
  День 3 - Взрывные крестики-нолики (5x5, 4 в ряд, скрытые мины)
  День 4 - Слова (собери слово по буквам)
  День 5 - Найди пару (5x5, с джокером-приколюхой)
  День 6 - Собери картинку по памяти (5x5, запомни узор)
  День 7 - Детектив (улики -> вычисли виновного)

Награда за день считается от текущего пассивного дохода игрока, поэтому
одинаково ощутима что для новичка, что для игрока с миллиардами.

Состояния дня в календаре:
  🔒 - день ещё не открыт
  🎁 - награда доступна к получению
  🎮 - награда получена, мини-игра этого дня ещё не сыграна
  ✅ - всё сделано на сегодня

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

# Бонус мини-игры, выданный при клейме награды, хранится тут до конца игры
# (не в БД - это чисто временное состояние текущей сессии).
_game_bonus = {}


def setup(users_dict, recalculate_user_stats=None):
    global _users, _recalculate_user_stats
    _users = users_dict
    _recalculate_user_stats = recalculate_user_stats


# ═══════════════════════════════════════════════════════════
# РАСЧЁТ НАГРАДЫ И ЛОГИКА КАЛЕНДАРЯ
# ═══════════════════════════════════════════════════════════
REWARD_MINUTES = {1: 15, 2: 20, 3: 25, 4: 30, 5: 40, 6: 50, 7: 70}
DAY7_BONUS_DIAMONDS = 10
MIN_REWARD_PER_DAY = 500  # подстраховка для игроков без пассивного дохода

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
    """Возвращает (claimed_today, current_day 1..7, streak, game_played)."""
    today = date.today()
    last_date_str = user.get("last_login_reward_date")
    streak = user.get("login_streak", 0)

    if last_date_str == today.isoformat():
        current_day = ((streak - 1) % 7) + 1
        return True, current_day, streak, user.get("login_game_played", False)

    if last_date_str:
        last_date = date.fromisoformat(last_date_str)
        if (today - last_date).days > 1:
            streak = 0  # пропустил день - цикл сбрасывается на День 1

    current_day = (streak % 7) + 1
    return False, current_day, streak, False


def get_calendar_kb(claimed_today, current_day, game_played, is_admin=False):
    rows, row = [], []
    for day in range(1, 8):
        if is_admin:
            # Тестовый режим для админов: любой день всегда кликабелен -
            # сразу запускает игру этого дня, минуя реальный цикл наград.
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
    """Вызывается из main.py по кнопке '🎁 Ежедневная награда'."""
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

    # Бонус за победу в мини-игре - половина сегодняшней награды, но не меньше 100
    _game_bonus[user_id] = max(reward_coins // 2, 100)

    coins_str = f"{reward_coins:,}".replace(",", " ")
    game_name = DAY_GAME_NAMES[current_day]
    text = (
        f"✅ **День {current_day} получен!**\n\n"
        f"💰 +{coins_str} монет{bonus_text}\n\n"
        f"Сегодняшняя игра: {game_name}\nСыграй, чтобы получить доп.бонус!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"▶️ Играть: {game_name}", callback_data="daily_playday")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("daily_admintest_"))
async def daily_admin_test(callback: CallbackQuery, bot: Bot):
    if not admin_panel.is_admin(callback.from_user.id):
        return

    day = int(callback.data.replace("daily_admintest_", "", 1))
    starters = {
        1: start_fox_game, 2: start_logic_game, 3: start_exploding_ttt,
        4: start_words_game, 5: start_memory_game, 6: start_picture_game,
        7: start_detective_game,
    }
    starter = starters[day]
    # На всякий случай выдаём тестовый бонус-фонд, чтобы победа тоже
    # отработала как обычно (без реального клейма награды через daily_claim)
    _game_bonus.setdefault(callback.from_user.id, 200)
    if day == 3:
        await starter(callback, bot)
    else:
        await starter(callback)


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

    starters = {
        1: start_fox_game, 2: start_logic_game, 3: start_exploding_ttt,
        4: start_words_game, 5: start_memory_game, 6: start_picture_game,
        7: start_detective_game,
    }
    starter = starters[current_day]
    if current_day == 3:
        await starter(callback, bot)
    else:
        await starter(callback)


# ═══════════════════════════════════════════════════════════
# ОБЩАЯ ЛОГИКА ЗАВЕРШЕНИЯ ЛЮБОЙ МИНИ-ИГРЫ ДНЯ
# ═══════════════════════════════════════════════════════════
async def _apply_result_and_get_text(user_id, won, result_text):
    user = _users.get(user_id) if _users else None
    if user:
        user["login_game_played"] = True
        if won:
            bonus = _game_bonus.pop(user_id, 200)
            user["balance"] += bonus
            bonus_str = f"{bonus:,}".replace(",", " ")
            result_text += f"\n\n💰 Бонус: +{bonus_str} монет!"
        else:
            _game_bonus.pop(user_id, None)
            result_text += "\n\nНе повезло - в следующий раз получится! Возвращайся завтра за новым днём."
        await database.save_user(user_id, user)
    return result_text


async def finish_daily_game(callback: CallbackQuery, won: bool, result_text: str):
    """Для игр, где это последний edit+answer в текущем callback."""
    text = await _apply_result_and_get_text(callback.from_user.id, won, result_text)
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()


async def finish_daily_game_silent(callback: CallbackQuery, won: bool, result_text: str):
    """Как finish_daily_game, но без повторного callback.answer()."""
    text = await _apply_result_and_get_text(callback.from_user.id, won, result_text)
    await callback.message.edit_text(text, parse_mode="Markdown")


async def finish_daily_game_new_message(user_id: int, bot: Bot, won: bool, result_text: str):
    """Для игр, где ответ шлётся отдельным сообщением (взрыв.крестики через bot.send_message)."""
    text = await _apply_result_and_get_text(user_id, won, result_text)
    await bot.send_message(user_id, text, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 1: ЛИСИЧКА, ЧТО ДЕЛАЕШЬ? (Simon Says)
# ═══════════════════════════════════════════════════════════
_fox_games = {}
FOX_EMOJI = ["🐾", "🍃", "🎵", "🔥"]
FOX_SEQUENCE_LEN = 5


async def start_fox_game(callback: CallbackQuery):
    sequence = [random.choice(FOX_EMOJI) for _ in range(FOX_SEQUENCE_LEN)]
    _fox_games[callback.from_user.id] = {"sequence": sequence, "position": 0}
    await callback.answer()

    shown = ""
    for emoji in sequence:
        shown += (" ➡️ " if shown else "") + emoji
        await callback.message.edit_text(f"🦊 **Лисичка, что делаешь?**\n\nЗапоминай:\n\n{shown}", parse_mode="Markdown")
        await asyncio.sleep(0.8)

    await asyncio.sleep(0.6)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=e, callback_data=f"fox_{e}") for e in FOX_EMOJI
    ]])
    await callback.message.edit_text(
        "🦊 **Лисичка, что делаешь?**\n\nА теперь повтори по порядку!",
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

    if picked != expected:
        del _fox_games[user_id]
        await finish_daily_game(callback, False, "🦊 **Лисичка, что делаешь?**\n\n😢 Не то! Правильная последовательность была:\n" + " ➡️ ".join(game["sequence"]))
        return

    game["position"] += 1
    if game["position"] == len(game["sequence"]):
        del _fox_games[user_id]
        await finish_daily_game(callback, True, "🦊 **Лисичка, что делаешь?**\n\n🎉 Всё верно, ты повторил всю последовательность!")
        return

    await callback.answer(f"✅ Верно! Дальше... ({game['position']}/{len(game['sequence'])})")


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 2: ЛОГИКА (найди лишнее)
# ═══════════════════════════════════════════════════════════
LOGIC_SETS = [
    ["🍎", "🍌", "🍇", "🚗"],
    ["⚽", "🏀", "🎾", "📕"],
    ["🐶", "🐱", "🐭", "🌳"],
    ["☀️", "🌙", "⭐", "🍕"],
    ["🔥", "💧", "🌪️", "🎸"],
    ["🚗", "✈️", "🚢", "🍰"],
]
_logic_answers = {}


async def start_logic_game(callback: CallbackQuery):
    items = random.choice(LOGIC_SETS)[:]
    odd_item = items[-1]
    random.shuffle(items)
    _logic_answers[callback.from_user.id] = odd_item

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=e, callback_data=f"logic_{e}") for e in items
    ]])
    await callback.message.edit_text(
        "🧠 **Логика**\n\nНайди лишний предмет!", reply_markup=kb, parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("logic_"))
async def logic_play(callback: CallbackQuery):
    user_id = callback.from_user.id
    picked = callback.data.replace("logic_", "", 1)
    correct = _logic_answers.pop(user_id, None)

    won = (picked == correct)
    text = "🧠 **Логика**\n\n" + ("🎉 Верно, это лишнее!" if won else f"😢 Не угадал. Лишним был {correct}")
    await finish_daily_game(callback, won, text)


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 3: ВЗРЫВНЫЕ КРЕСТИКИ-НОЛИКИ (5x5, 4 в ряд, скрытые мины)
# ═══════════════════════════════════════════════════════════
_ettt_games = {}
ETTT_SIZE = 5
ETTT_MINES_COUNT = 3
ETTT_WIN_LEN = 4


def _ettt_idx(r, c):
    return r * ETTT_SIZE + c


def _ettt_would_win(board, idx, symbol):
    r, c = divmod(idx, ETTT_SIZE)
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dr, dc in directions:
        count = 1
        for sign in (1, -1):
            rr, cc = r + dr * sign, c + dc * sign
            while 0 <= rr < ETTT_SIZE and 0 <= cc < ETTT_SIZE and board[_ettt_idx(rr, cc)] == symbol:
                count += 1
                rr += dr * sign
                cc += dc * sign
        if count >= ETTT_WIN_LEN:
            return True
    return False


def _ettt_line_potential(board, idx, symbol):
    r, c = divmod(idx, ETTT_SIZE)
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    total = 0
    for dr, dc in directions:
        count = 1
        for sign in (1, -1):
            rr, cc = r + dr * sign, c + dc * sign
            while 0 <= rr < ETTT_SIZE and 0 <= cc < ETTT_SIZE and board[_ettt_idx(rr, cc)] == symbol:
                count += 1
                rr += dr * sign
                cc += dc * sign
        total += count ** 2
    return total


def _ettt_bot_move(board):
    empties = [i for i, v in enumerate(board) if v is None]
    for i in empties:
        if _ettt_would_win(board, i, "O"):
            return i
    for i in empties:
        if _ettt_would_win(board, i, "X"):
            return i
    scored = [(_ettt_line_potential(board, i, "O") + _ettt_line_potential(board, i, "X") * 0.8, i) for i in empties]
    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:3] if len(scored) >= 3 else scored
    return random.choice(top)[1]


def _ettt_render_kb(board):
    symbols = {None: "⬜", "X": "❌", "O": "⭕", "MINE": "💥"}
    rows = []
    for r in range(ETTT_SIZE):
        row = []
        for c in range(ETTT_SIZE):
            i = _ettt_idx(r, c)
            cb = f"ettt_{i}" if board[i] is None else "daily_noop"
            row.append(InlineKeyboardButton(text=symbols[board[i]], callback_data=cb))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_exploding_ttt(callback: CallbackQuery, bot: Bot):
    board = [None] * (ETTT_SIZE * ETTT_SIZE)
    mines = set(random.sample(range(len(board)), ETTT_MINES_COUNT))
    _ettt_games[callback.from_user.id] = {"board": board, "mines": mines}
    await callback.message.edit_text(
        "💥 **Взрывные крестики-нолики**\nТы - ❌, бот - ⭕. Собери 4 в ряд!\n(на поле спрятаны мины - будь осторожен)",
        reply_markup=_ettt_render_kb(board), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ettt_"))
async def ettt_move(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    game = _ettt_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    board, mines = game["board"], game["mines"]
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
        if _ettt_would_win(board, idx, "X"):
            del _ettt_games[user_id]
            await finish_daily_game(callback, True, "💥 **Взрывные крестики-нолики**\n\n🎉 Ты собрал 4 в ряд и победил!")
            return
        await callback.answer()

    if all(v is not None for v in board):
        del _ettt_games[user_id]
        await finish_daily_game(callback, False, "💥 **Взрывные крестики-нолики**\n\n🤝 Поле заполнено, ничья.")
        return

    # Ход бота (тоже может подорваться на мине - тогда просто теряет попытку)
    bot_idx = _ettt_bot_move(board)
    if bot_idx in mines:
        board[bot_idx] = "MINE"
        mines.discard(bot_idx)
    else:
        board[bot_idx] = "O"
        if _ettt_would_win(board, bot_idx, "O"):
            del _ettt_games[user_id]
            await callback.message.edit_reply_markup(reply_markup=_ettt_render_kb(board))
            await finish_daily_game_new_message(user_id, bot, False, "💥 **Взрывные крестики-нолики**\n\n😢 Бот собрал 4 в ряд.")
            return

    if all(v is not None for v in board):
        del _ettt_games[user_id]
        await callback.message.edit_reply_markup(reply_markup=_ettt_render_kb(board))
        await finish_daily_game_new_message(user_id, bot, False, "💥 **Взрывные крестики-нолики**\n\n🤝 Поле заполнено, ничья.")
        return

    await callback.message.edit_reply_markup(reply_markup=_ettt_render_kb(board))


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 4: СЛОВА (собери слово по буквам)
# ═══════════════════════════════════════════════════════════
WORDS_POOL = ["ТАЙКУН", "ИМПЕРИЯ", "МОНЕТА", "АЛМАЗ", "БИЗНЕС", "ЗАВОД", "ПРИБЫЛЬ", "БОГАЧ", "ВЛАСТЬ", "ДОХОД", "КАПИТАЛ"]
_words_games = {}
WORDS_MAX_MISTAKES = 3


def _words_render_kb(game):
    rows, row = [], []
    for i, letter in enumerate(game["shuffled"]):
        text = "•" if i in game["picked"] else letter
        cb = "daily_noop" if i in game["picked"] else f"word_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_words_game(callback: CallbackQuery):
    target = random.choice(WORDS_POOL)
    shuffled = list(target)
    random.shuffle(shuffled)
    game = {"target": target, "shuffled": shuffled, "picked": set(), "progress": 0, "mistakes": 0}
    _words_games[callback.from_user.id] = game

    text = f"📝 **Слова**\nСобери слово из {len(target)} букв по порядку!\nОшибок допустимо: {WORDS_MAX_MISTAKES}"
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

    letter = game["shuffled"][i]
    expected = game["target"][game["progress"]]

    if letter == expected:
        game["picked"].add(i)
        game["progress"] += 1
        if game["progress"] == len(game["target"]):
            del _words_games[user_id]
            await finish_daily_game(callback, True, f"📝 **Слова**\n\n🎉 Собрано слово: **{game['target']}**!")
            return
        await callback.answer("✅ Верно!")
    else:
        game["mistakes"] += 1
        if game["mistakes"] >= WORDS_MAX_MISTAKES:
            del _words_games[user_id]
            await finish_daily_game(callback, False, f"📝 **Слова**\n\n😢 Слишком много ошибок. Слово было: **{game['target']}**")
            return
        await callback.answer(f"❌ Не та буква ({game['mistakes']}/{WORDS_MAX_MISTAKES})", show_alert=True)
        return

    await callback.message.edit_text(
        f"📝 **Слова**\nСобери слово из {len(game['target'])} букв по порядку!\nОшибок: {game['mistakes']}/{WORDS_MAX_MISTAKES}",
        reply_markup=_words_render_kb(game), parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 5: НАЙДИ ПАРУ (5x5, с джокером-приколюхой)
# ═══════════════════════════════════════════════════════════
_pairs5_games = {}
PAIRS5_EMOJIS = ["🍎", "🍌", "🍇", "🍉", "🍒", "🥝", "🍑", "🍋", "🥥", "🍍", "🥭", "🍈"]  # 12 пар
PAIRS5_MAX_ATTEMPTS = 9
WILDCARD = "👑"


def _pairs5_render_kb(game):
    cards, revealed, matched = game["cards"], game["revealed"], game["matched"]
    rows, row = [], []
    for i in range(25):
        text = cards[i] if (matched[i] or revealed[i]) else "❓"
        cb = "daily_noop" if matched[i] else f"pair5_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == 5:
            rows.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_memory_game(callback: CallbackQuery):
    cards = PAIRS5_EMOJIS * 2 + [WILDCARD]
    random.shuffle(cards)
    game = {"cards": cards, "revealed": [False] * 25, "matched": [False] * 25, "first_pick": None, "attempts": 0}
    _pairs5_games[callback.from_user.id] = game
    await callback.message.edit_text(
        f"🃏 **Найди пару**\n{WILDCARD} - джокер, совпадает с чем угодно!\nПопыток: {PAIRS5_MAX_ATTEMPTS}",
        reply_markup=_pairs5_render_kb(game), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pair5_"))
async def memory5_pick(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _pairs5_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    idx = int(callback.data.replace("pair5_", "", 1))
    if game["matched"][idx] or game["revealed"][idx]:
        await callback.answer()
        return

    if game["first_pick"] is None:
        game["revealed"][idx] = True
        game["first_pick"] = idx
        await callback.message.edit_reply_markup(reply_markup=_pairs5_render_kb(game))
        await callback.answer()
        return

    first = game["first_pick"]
    game["revealed"][idx] = True
    game["attempts"] += 1

    await callback.message.edit_reply_markup(reply_markup=_pairs5_render_kb(game))
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
        del _pairs5_games[user_id]
        await finish_daily_game_silent(callback, True, "🃏 **Найди пару**\n\n🎉 Все пары найдены!")
        return

    if game["attempts"] >= PAIRS5_MAX_ATTEMPTS:
        del _pairs5_games[user_id]
        await finish_daily_game_silent(callback, False, "🃏 **Найди пару**\n\n😢 Попытки закончились.")
        return

    await callback.message.edit_text(
        f"🃏 **Найди пару**\nПопытка {game['attempts']}/{PAIRS5_MAX_ATTEMPTS}",
        reply_markup=_pairs5_render_kb(game), parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 6: СОБЕРИ КАРТИНКУ ПО ПАМЯТИ (5x5, запомни узор)
# ═══════════════════════════════════════════════════════════
_picture_games = {}
PICTURE_PATTERNS = [
    # 1 = закрашенная клетка, растянуто построчно 5x5
    [0,1,0,1,0, 1,1,1,1,1, 1,1,1,1,1, 0,1,1,1,0, 0,0,1,0,0],  # сердце
    [0,0,1,0,0, 0,1,1,1,0, 1,1,1,1,1, 0,1,1,1,0, 0,0,1,0,0],  # ромб
    [0,0,1,0,0, 0,0,1,0,0, 1,1,1,1,1, 0,0,1,0,0, 0,0,1,0,0],  # крест
]
PICTURE_MAX_MISTAKES = 3


def _picture_render_kb(game, memorize_phase):
    rows, row = [], []
    for i in range(25):
        if memorize_phase:
            text = "🟩" if game["pattern"][i] else "⬜"
            cb = "daily_noop"
        else:
            if i in game["correct_taps"]:
                text = "✅"
            elif i in game["wrong_taps"]:
                text = "❌"
            else:
                text = "❓"
            cb = "daily_noop" if (i in game["correct_taps"] or i in game["wrong_taps"]) else f"pic_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == 5:
            rows.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_picture_game(callback: CallbackQuery):
    pattern = random.choice(PICTURE_PATTERNS)
    game = {"pattern": pattern, "correct_taps": set(), "wrong_taps": set(), "mistakes": 0}
    _picture_games[callback.from_user.id] = game

    await callback.message.edit_text(
        "🎨 **Собери картинку по памяти**\n\nЗапоминай, где закрашено!",
        reply_markup=_picture_render_kb(game, memorize_phase=True), parse_mode="Markdown"
    )
    await callback.answer()
    await asyncio.sleep(4)

    await callback.message.edit_text(
        f"🎨 **Собери картинку по памяти**\n\nТеперь повтори узор! Ошибок допустимо: {PICTURE_MAX_MISTAKES}",
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

    if game["mistakes"] >= PICTURE_MAX_MISTAKES:
        del _picture_games[user_id]
        await finish_daily_game(callback, False, "🎨 **Собери картинку по памяти**\n\n😢 Слишком много ошибок.")
        return

    if len(game["correct_taps"]) == total_filled:
        del _picture_games[user_id]
        await finish_daily_game(callback, True, "🎨 **Собери картинку по памяти**\n\n🎉 Узор полностью восстановлен!")
        return

    await callback.message.edit_text(
        f"🎨 **Собери картинку по памяти**\nОшибок: {game['mistakes']}/{PICTURE_MAX_MISTAKES}",
        reply_markup=_picture_render_kb(game, memorize_phase=False), parse_mode="Markdown"
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════
# ДЕНЬ 7: ДЕТЕКТИВ (улики -> вычисли виновного)
# ═══════════════════════════════════════════════════════════
_detective_games = {}
DETECTIVE_CASES = [
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
]


async def start_detective_game(callback: CallbackQuery):
    case = random.choice(DETECTIVE_CASES)
    _detective_games[callback.from_user.id] = {"case": case, "step": 0}

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➡️ Далее", callback_data="det_next")]])
    await callback.message.edit_text(f"🔍 **Детектив**\n\n{case['intro']}", reply_markup=kb, parse_mode="Markdown")
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
    await finish_daily_game(callback, won, text)
