"""
daily_login.py
Ежедневная награда (7-дневный календарь) + мини-игры на бонус.

Награда за день НЕ фиксированная - считается от текущего пассивного дохода
игрока (passive_per_minute), поэтому одинаково ощутима что для новичка,
что для игрока с миллиардами: это X минут его собственного дохода.

После получения награды игроку случайно выпадает одна из 5 мини-игр:
крестики-нолики, найди пару, камень-ножницы-бумага, слот-машина, угадай
число. Выигрыш - доп.бонус монетами, проигрыш - ничего (без наказаний).

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


def _calc_reward_coins(user, day):
    minutes = REWARD_MINUTES.get(day, 15)
    passive = user.get("passive_per_minute", 0)
    reward = int(passive * minutes)
    return max(reward, MIN_REWARD_PER_DAY * day)


def _get_streak_state(user):
    """Возвращает (claimed_today: bool, current_day: int 1..7, streak: int).
    current_day - это День календаря, который либо уже забран сегодня,
    либо доступен для получения прямо сейчас."""
    today = date.today()
    last_date_str = user.get("last_login_reward_date")
    streak = user.get("login_streak", 0)

    if last_date_str == today.isoformat():
        # Уже забирал сегодня
        current_day = ((streak - 1) % 7) + 1
        return True, current_day, streak

    if last_date_str:
        last_date = date.fromisoformat(last_date_str)
        if (today - last_date).days > 1:
            streak = 0  # пропустил день - цикл сбрасывается на День 1

    current_day = (streak % 7) + 1
    return False, current_day, streak


def get_calendar_kb(claimed_today, current_day):
    rows = []
    row = []
    for day in range(1, 8):
        if day < current_day or (day == current_day and claimed_today):
            label = f"✅{day}"
            cb = "daily_noop"
        elif day == current_day:
            label = f"🎁{day}"
            cb = "daily_claim"
        else:
            label = f"🔒{day}"
            cb = "daily_noop"
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

    claimed_today, current_day, _ = _get_streak_state(user)

    if claimed_today:
        text = (
            "🎁 **Ежедневная награда**\n\n"
            "Сегодняшняя награда уже забрана - возвращайся завтра!"
        )
    else:
        text = (
            "🎁 **Ежедневная награда**\n\n"
            f"Собери награду за День {current_day} из 7!\n"
            "Пропустишь день - серия начнётся заново."
        )

    kb = get_calendar_kb(claimed_today, current_day)
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

    claimed_today, current_day, streak = _get_streak_state(user)
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
    await database.save_user(user_id, user)

    # Бонус для мини-игры - половина сегодняшней награды, но не меньше 100
    _game_bonus[user_id] = max(reward_coins // 2, 100)

    coins_str = f"{reward_coins:,}".replace(",", " ")
    text = (
        f"✅ **День {current_day} получен!**\n\n"
        f"💰 +{coins_str} монет{bonus_text}\n\n"
        f"Хочешь испытать удачу и сыграть на доп.бонус?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Сыграть на бонус!", callback_data="daily_play_game")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ═══════════════════════════════════════════════════════════
# ОБЩАЯ ЛОГИКА ЗАВЕРШЕНИЯ ЛЮБОЙ МИНИ-ИГРЫ
# ═══════════════════════════════════════════════════════════
async def _apply_result_and_get_text(user_id, won, result_text):
    user = _users.get(user_id) if _users else None
    if won and user:
        bonus = _game_bonus.pop(user_id, 200)
        user["balance"] += bonus
        await database.save_user(user_id, user)
        bonus_str = f"{bonus:,}".replace(",", " ")
        result_text += f"\n\n💰 Бонус: +{bonus_str} монет!"
    else:
        _game_bonus.pop(user_id, None)
        result_text += "\n\nНе повезло - в следующий раз получится!"
    return result_text


async def finish_minigame(callback: CallbackQuery, won: bool, result_text: str):
    """Для игр, где это первый и единственный edit+answer за этот callback."""
    text = await _apply_result_and_get_text(callback.from_user.id, won, result_text)
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()


async def finish_minigame_silent(callback: CallbackQuery, won: bool, result_text: str):
    """Как finish_minigame, но без повторного callback.answer() - для игр,
    где answer() уже был вызван раньше в этом же хендлере (Найди пару)."""
    text = await _apply_result_and_get_text(callback.from_user.id, won, result_text)
    await callback.message.edit_text(text, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════
# ВЫБОР СЛУЧАЙНОЙ МИНИ-ИГРЫ
# ═══════════════════════════════════════════════════════════
@router.callback_query(F.data == "daily_play_game")
async def daily_play_game(callback: CallbackQuery, bot: Bot):
    game = random.choice(["ttt", "memory", "rps", "slot", "guess"])
    if game == "ttt":
        await start_tictactoe(callback)
    elif game == "memory":
        await start_memory(callback)
    elif game == "rps":
        await start_rps(callback)
    elif game == "slot":
        await start_slot(callback, bot)
    elif game == "guess":
        await start_guess(callback)


# ═══════════════════════════════════════════════════════════
# ИГРА 1: КАМЕНЬ-НОЖНИЦЫ-БУМАГА
# ═══════════════════════════════════════════════════════════
RPS_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
RPS_EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}


async def start_rps(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🪨", callback_data="rps_rock"),
        InlineKeyboardButton(text="📄", callback_data="rps_paper"),
        InlineKeyboardButton(text="✂️", callback_data="rps_scissors"),
    ]])
    await callback.message.edit_text("✊✋✌️ **Камень-ножницы-бумага**\n\nВыбирай!", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("rps_"))
async def rps_play(callback: CallbackQuery):
    user_choice = callback.data.replace("rps_", "", 1)
    bot_choice = random.choice(list(RPS_BEATS.keys()))

    if user_choice == bot_choice:
        result_text = "🤝 Ничья!"
        won = False
    elif RPS_BEATS[user_choice] == bot_choice:
        result_text = "🎉 Ты выиграл!"
        won = True
    else:
        result_text = "😢 Ты проиграл."
        won = False

    text = f"{RPS_EMOJI[user_choice]} против {RPS_EMOJI[bot_choice]}\n\n{result_text}"
    await finish_minigame(callback, won, text)


# ═══════════════════════════════════════════════════════════
# ИГРА 2: УГАДАЙ ЧИСЛО (1-10)
# ═══════════════════════════════════════════════════════════
_guess_target = {}


async def start_guess(callback: CallbackQuery):
    target = random.randint(1, 10)
    _guess_target[callback.from_user.id] = target

    rows, row = [], []
    for n in range(1, 11):
        row.append(InlineKeyboardButton(text=str(n), callback_data=f"guess_{n}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text("🎲 **Угадай число от 1 до 10!**", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("guess_"))
async def guess_play(callback: CallbackQuery):
    user_id = callback.from_user.id
    guess_val = int(callback.data.replace("guess_", "", 1))
    target = _guess_target.pop(user_id, random.randint(1, 10))

    won = (guess_val == target)
    text = f"Ты выбрал {guess_val}, загадано было {target}.\n\n" + ("🎉 Угадал!" if won else "😢 Не угадал.")
    await finish_minigame(callback, won, text)


# ═══════════════════════════════════════════════════════════
# ИГРА 3: СЛОТ-МАШИНА (нативный дайс Telegram - никакой ручной анимации не нужно)
# ═══════════════════════════════════════════════════════════
async def start_slot(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id

    try:
        dice_msg = await bot.send_dice(chat_id=user_id, emoji="🎰")
    except Exception as e:
        logging.warning(f"Не удалось отправить слот-машину: {e}")
        return

    await asyncio.sleep(2.5)  # ждём, пока проиграется анимация барабанов

    value = dice_msg.dice.value - 1  # 0..63
    reel1, reel2, reel3 = value % 4, (value // 4) % 4, (value // 16) % 4
    won = (reel1 == reel2 == reel3)

    text = "🎰 **Слот-машина**\n\n" + ("🎉 Джекпот! Три одинаковых символа!" if won else "😢 Не в этот раз.")
    text = await _apply_result_and_get_text(user_id, won, text)
    await bot.send_message(user_id, text, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════
# ИГРА 4: КРЕСТИКИ-НОЛИКИ (игрок X, бот O с простой логикой выиграть/заблокировать)
# ═══════════════════════════════════════════════════════════
_ttt_boards = {}

TTT_LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def _ttt_check_winner(board):
    for a, b, c in TTT_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "draw"
    return None


def _ttt_bot_move(board):
    empties = [i for i, v in enumerate(board) if not v]
    for i in empties:  # 1. выиграть, если можно
        b = board[:]; b[i] = "O"
        if _ttt_check_winner(b) == "O":
            return i
    for i in empties:  # 2. заблокировать игрока
        b = board[:]; b[i] = "X"
        if _ttt_check_winner(b) == "X":
            return i
    if 4 in empties:  # 3. занять центр
        return 4
    return random.choice(empties)


def _ttt_render_kb(board):
    symbols = {None: "⬜", "X": "❌", "O": "⭕"}
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            cb = f"ttt_{i}" if not board[i] else "daily_noop"
            row.append(InlineKeyboardButton(text=symbols[board[i]], callback_data=cb))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_tictactoe(callback: CallbackQuery):
    board = [None] * 9
    _ttt_boards[callback.from_user.id] = board
    await callback.message.edit_text(
        "❌⭕ **Крестики-нолики**\nТы играешь за ❌, бот - за ⭕",
        reply_markup=_ttt_render_kb(board), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ttt_"))
async def ttt_move(callback: CallbackQuery):
    user_id = callback.from_user.id
    board = _ttt_boards.get(user_id)
    if not board:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    idx = int(callback.data.replace("ttt_", "", 1))
    if board[idx]:
        await callback.answer("Уже занято!", show_alert=True)
        return

    board[idx] = "X"
    winner = _ttt_check_winner(board)

    if not winner:
        bot_idx = _ttt_bot_move(board)
        board[bot_idx] = "O"
        winner = _ttt_check_winner(board)

    if winner:
        del _ttt_boards[user_id]
        if winner == "X":
            result_text, won = "❌⭕ **Крестики-нолики**\n\n🎉 Ты выиграл!", True
        elif winner == "O":
            result_text, won = "❌⭕ **Крестики-нолики**\n\n😢 Бот выиграл.", False
        else:
            result_text, won = "❌⭕ **Крестики-нолики**\n\n🤝 Ничья.", False
        await finish_minigame(callback, won, result_text)
    else:
        await callback.message.edit_text(
            "❌⭕ **Крестики-нолики**\nТы играешь за ❌, бот - за ⭕",
            reply_markup=_ttt_render_kb(board), parse_mode="Markdown"
        )
        await callback.answer()


# ═══════════════════════════════════════════════════════════
# ИГРА 5: НАЙДИ ПАРУ (3 пары, 6 карточек, максимум 3 попытки)
# ═══════════════════════════════════════════════════════════
_memory_games = {}
MEMORY_EMOJIS = ["🍎", "🍌", "🍇"]
MEMORY_MAX_ATTEMPTS = 3


def _memory_render_kb(game):
    cards, revealed, matched = game["cards"], game["revealed"], game["matched"]
    rows, row = [], []
    for i in range(6):
        text = cards[i] if (matched[i] or revealed[i]) else "❓"
        cb = "daily_noop" if matched[i] else f"mem_{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_memory(callback: CallbackQuery):
    cards = MEMORY_EMOJIS * 2
    random.shuffle(cards)
    game = {"cards": cards, "revealed": [False] * 6, "matched": [False] * 6, "first_pick": None, "attempts": 0}
    _memory_games[callback.from_user.id] = game
    await callback.message.edit_text(
        f"🃏 **Найди пару**\nУ тебя {MEMORY_MAX_ATTEMPTS} попытки, чтобы собрать все 3 пары!",
        reply_markup=_memory_render_kb(game), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mem_"))
async def memory_pick(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = _memory_games.get(user_id)
    if not game:
        await callback.answer("Игра не найдена, начни заново", show_alert=True)
        return

    idx = int(callback.data.replace("mem_", "", 1))
    if game["matched"][idx] or game["revealed"][idx]:
        await callback.answer()
        return

    if game["first_pick"] is None:
        # Первая карта в этой попытке - просто открываем и ждём вторую
        game["revealed"][idx] = True
        game["first_pick"] = idx
        await callback.message.edit_reply_markup(reply_markup=_memory_render_kb(game))
        await callback.answer()
        return

    # Вторая карта - показываем обе, ждём немного, потом проверяем совпадение
    first = game["first_pick"]
    game["revealed"][idx] = True
    game["attempts"] += 1

    await callback.message.edit_reply_markup(reply_markup=_memory_render_kb(game))
    await callback.answer()
    await asyncio.sleep(1.2)

    if game["cards"][first] == game["cards"][idx]:
        game["matched"][first] = True
        game["matched"][idx] = True

    game["revealed"][first] = False
    game["revealed"][idx] = False
    game["first_pick"] = None

    if all(game["matched"]):
        del _memory_games[user_id]
        await finish_minigame_silent(callback, True, "🃏 **Найди пару**\n\n🎉 Все пары найдены!")
        return

    if game["attempts"] >= MEMORY_MAX_ATTEMPTS:
        del _memory_games[user_id]
        await finish_minigame_silent(callback, False, "🃏 **Найди пару**\n\n😢 Попытки закончились.")
        return

    await callback.message.edit_text(
        f"🃏 **Найди пару**\nПопытка {game['attempts']}/{MEMORY_MAX_ATTEMPTS}",
        reply_markup=_memory_render_kb(game), parse_mode="Markdown"
    )
