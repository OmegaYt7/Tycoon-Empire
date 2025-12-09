import asyncio
import logging
import random
import math
import os
from datetime import datetime, timedelta, date
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ReactionTypeEmoji,
    FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

# Импорты модулей
import config
import database
import promocodes
import admin_panel

logging.basicConfig(level=logging.WARNING)
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
users = {}

# ═══════════════════════════════════════════════════════════
# ФОНОВОЕ СОХРАНЕНИЕ
# ═══════════════════════════════════════════════════════════
async def autosave_loop():
    while True:
        await asyncio.sleep(120)
        try:
            # Добавлено await
            await database.save_all_users(users)
        except Exception as e:
            logging.error(f"Ошибка автосохранения: {e}")

# ═══════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ И ДАННЫЕ
# ═══════════════════════════════════════════════════════════

BASE_DIAMOND_CHANCE = 0.001
ITEMS_PER_PAGE = 10
NICKNAME_CHANGE_COST = 1000
NICKNAME_CHANGE_DAYS = 7

FUNNY_RESPONSES = [
    "Моя твоя не понимать... Тапай лучше! 👆",
    "Интересная мысль, но я всего лишь бот-магнат 🤖",
    "Это код от ядерного чемоданчика? Нет? Тогда работай!",
    "Меньше слов, больше тапов! 🔨",
    "Я не чат-бот, я бизнес-партнер! 💼",
    "Эээ... Что? 😅",
    "Команду не распознал, но лайк за старание (нет).",
]

funny_spam = [
    "Воу-воу, полегче, Флэш! ⚡️",
    "Экран сейчас треснет, я серьезно! 📱🔨",
    "Ты киборг или просто много кофе выпил? ☕️🤖",
    "Пожарных уже вызвали, палец дымится! 🚒💨",
    "Автокликер? Или у тебя судорога? 🤔",
    "Эй, дай серверу отдышаться! 😮‍💨",
    "Не так быстро, ковбой! 🤠",
    "Твоя скорость нарушает законы физики! 🛑"
]

DAILY_QUESTS_CONFIG = [
    {"key": "daily_clicks", "name": "👆 Разминка пальцев", "desc": "Сделай 200 кликов за сегодня", "target": 200, "reward_diamonds": 1},
    {"key": "daily_upgrade", "name": "🔨 Ремонтные работы", "desc": "Улучши любое здание 1 раз", "target": 1, "reward_diamonds": 1},
    {"key": "daily_claim", "name": "💰 Сборщик дани", "desc": "Забери доход с любых зданий 10 раз", "target": 10, "reward_diamonds": 1}
]

# --- СПИСОК УЛУЧШЕНИЙ (30 ШТУК) ---
upgrades_info = [
    {"key": "wooden_finger", "name": "🪵 Деревянный палец", "bonus": 1, "cost": 0, "funny": "С чего-то надо начинать!"},
    {"key": "stone_finger", "name": "🪨 Каменный палец", "bonus": 2, "cost": 50, "funny": "Тяжелый, зато надежный. Привет из палеолита!"},
    {"key": "normal_finger", "name": "😊 Обычный палец", "bonus": 3, "cost": 150, "funny": "Твой родной палец прошёл апгрейд!"},
    {"key": "copper_finger", "name": "🟠 Медный палец", "bonus": 5, "cost": 300, "funny": "Блестящий, как новая копейка!"},
    {"key": "steel_finger", "name": "🔩 Стальной палец", "bonus": 8, "cost": 500, "funny": "Холодная сталь для горячих кликов."},
    {"key": "iron_finger", "name": "💪 Железный палец", "bonus": 12, "cost": 1000, "funny": "Терминатор отдыхает."},
    {"key": "silver_finger", "name": "🥈 Серебряный палец", "bonus": 20, "cost": 2500, "funny": "Серебро блестит, монстры дрожат."},
    {"key": "gold_finger", "name": "👑 Золотой палец", "bonus": 35, "cost": 5000, "funny": "Цыганский барон одобряет."},
    {"key": "emerald_finger", "name": "🟢 Изумрудный палец", "bonus": 50, "cost": 10000, "funny": "Сделан из цельного камня. Дорого-богато."},
    {"key": "titanium_finger", "name": "🔩 Титановый палец", "bonus": 75, "cost": 25000, "funny": "Космический металл! Легкий, но мощный."},
    {"key": "diamond_finger", "name": "💎 Алмазный палец", "bonus": 120, "cost": 50000, "funny": "Самый твёрдый палец в мире."},
    {"key": "plasma_finger", "name": "⚡ Плазменный палец", "bonus": 200, "cost": 100000, "funny": "Горячая плазма! Осторожно, не обжгись."},
    {"key": "laser_finger", "name": "🚀 Лазерный палец", "bonus": 350, "cost": 250000, "funny": "ПЬЮ-ПЬЮ-ПЬЮ! Быстрее света."},
    {"key": "antimatter_finger", "name": "⚫ Антиматерия", "bonus": 500, "cost": 500000, "funny": "Тапает так мощно, что искажает пространство."},
    {"key": "quantum_finger", "name": "🔬 Квантовый палец", "bonus": 750, "cost": 1000000, "funny": "Тапает в нескольких реальностях одновременно."},
    {"key": "magic_finger", "name": "🪄 Магический палец", "bonus": 1200, "cost": 2000000, "funny": "Абракадабра! Монеты из воздуха."},
    {"key": "cyber_finger", "name": "💻 Кибер-палец", "bonus": 2000, "cost": 5000000, "funny": "Взлом системы ради прибыли."},
    {"key": "robot_finger", "name": "🤖 Робо-палец", "bonus": 3500, "cost": 10000000, "funny": "Идеальная машина для заработка."},
    {"key": "alien_finger", "name": "👽 Инопланетный палец", "bonus": 5000, "cost": 25000000, "funny": "Технологии внеземных цивилизаций."},
    {"key": "dragon_finger", "name": "🐉 Драконий палец", "bonus": 10000, "cost": 50000000, "funny": "ОГНЕДЫШАЩИЙ ТАП-МОНСТР!"},
    {"key": "black_hole_finger", "name": "🕳️ Палец Чёрной Дыры", "bonus": 18000, "cost": 120000000, "funny": "Засасывает монеты из других галактик."},
    {"key": "nebula_finger", "name": "🌌 Туманный палец", "bonus": 30000, "cost": 300000000, "funny": "Рождает новые звезды и новые капиталы."},
    {"key": "supernova_finger", "name": "💥 Сверхновая", "bonus": 55000, "cost": 750000000, "funny": "Взрывная прибыль!"},
    {"key": "neutron_finger", "name": "☢️ Нейтронный палец", "bonus": 90000, "cost": 2000000000, "funny": "Невероятная плотность богатства."},
    {"key": "galactic_finger", "name": "🌀 Галактический палец", "bonus": 150000, "cost": 5000000000, "funny": "Вся галактика у твоих ног."},
    {"key": "infinity_finger", "name": "♾️ Палец Бесконечности", "bonus": 250000, "cost": 15000000000, "funny": "Щелчок — и ты богат."},
    {"key": "time_lord_finger", "name": "⏳ Повелитель Времени", "bonus": 450000, "cost": 40000000000, "funny": "Тапает в прошлом, будущем и настоящем."},
    {"key": "reality_bender", "name": "🧬 Искажатель Реальности", "bonus": 800000, "cost": 100000000000, "funny": "Твои деньги реальны, остальное — иллюзия."},
    {"key": "multiverse_finger", "name": "🌐 Мультивселенная", "bonus": 1500000, "cost": 300000000000, "funny": "Собирает дань со всех параллельных миров."},
    {"key": "creator_finger", "name": "🙏 Палец Создателя", "bonus": 3000000, "cost": 1000000000000, "funny": "Да будет свет... и деньги!"}
]

# --- СПИСОК СООРУЖЕНИЙ (30 ШТУК) ---
buildings_info = [
    # 1-10: Начало
    {"key": "tent", "name": "⛺ Палатка", "base_income": 1, "base_capacity": 100, "cost": 50, "upgrade_cost_base": 25, "upgrade_capacity_bonus": 50, "funny": "Живи на природе, копи мелочь."},
    {"key": "broken_shack", "name": "🛖 Сарай", "base_income": 3, "base_capacity": 400, "cost": 200, "upgrade_cost_base": 100, "upgrade_capacity_bonus": 200, "funny": "Лучше, чем ничего."},
    {"key": "hut", "name": "🏠 Хижина", "base_income": 8, "base_capacity": 1000, "cost": 500, "upgrade_cost_base": 250, "upgrade_capacity_bonus": 500, "funny": "Уютно и прибыльно."},
    {"key": "coffee_stand", "name": "☕ Кофейня", "base_income": 15, "base_capacity": 2000, "cost": 1000, "upgrade_cost_base": 500, "upgrade_capacity_bonus": 1000, "funny": "Кофе с собой! Клиенты в восторге."},
    {"key": "small_farm", "name": "🚜 Ферма", "base_income": 30, "base_capacity": 3500, "cost": 2500, "upgrade_cost_base": 1200, "upgrade_capacity_bonus": 1500, "funny": "Экологически чистые монеты."},
    {"key": "shop", "name": "🛒 Магазин", "base_income": 60, "base_capacity": 7500, "cost": 5000, "upgrade_cost_base": 2500, "upgrade_capacity_bonus": 3500, "funny": "Купи-продай."},
    {"key": "gas_station", "name": "⛽ Заправка", "base_income": 120, "base_capacity": 15000, "cost": 12000, "upgrade_cost_base": 6000, "upgrade_capacity_bonus": 7500, "funny": "Бензин нынче дорогой."},
    {"key": "workshop", "name": "🛠️ Мастерская", "base_income": 250, "base_capacity": 30000, "cost": 25000, "upgrade_cost_base": 12000, "upgrade_capacity_bonus": 15000, "funny": "Работа кипит."},
    {"key": "warehouse", "name": "🏬 Склад", "base_income": 500, "base_capacity": 60000, "cost": 60000, "upgrade_cost_base": 30000, "upgrade_capacity_bonus": 30000, "funny": "Место для твоих гор золота."},
    {"key": "hotel", "name": "🏨 Отель", "base_income": 1000, "base_capacity": 120000, "cost": 150000, "upgrade_cost_base": 75000, "upgrade_capacity_bonus": 60000, "funny": "Все включено, особенно прибыль."},
    
    # 11-20: Бизнес
    {"key": "office", "name": "🏢 Офис", "base_income": 2000, "base_capacity": 250000, "cost": 350000, "upgrade_cost_base": 175000, "upgrade_capacity_bonus": 125000, "funny": "Планктон работает на тебя."},
    {"key": "bank", "name": "🏦 Банк", "base_income": 5000, "base_capacity": 600000, "cost": 1000000, "upgrade_cost_base": 500000, "upgrade_capacity_bonus": 300000, "funny": "Хранилище переполнено."},
    {"key": "casino", "name": "🎰 Казино", "base_income": 10000, "base_capacity": 1200000, "cost": 2500000, "upgrade_cost_base": 1250000, "upgrade_capacity_bonus": 600000, "funny": "Казино всегда в выигрыше (ты тоже)."},
    {"key": "factory", "name": "🏭 Фабрика", "base_income": 25000, "base_capacity": 3000000, "cost": 5000000, "upgrade_cost_base": 2500000, "upgrade_capacity_bonus": 1500000, "funny": "Масштабное производство."},
    {"key": "supermarket", "name": "🛍️ Супермаркет", "base_income": 50000, "base_capacity": 6000000, "cost": 15000000, "upgrade_cost_base": 7500000, "upgrade_capacity_bonus": 3000000, "funny": "Очереди на кассах."},
    {"key": "corporation", "name": "🌆 Корпорация", "base_income": 100000, "base_capacity": 12000000, "cost": 50000000, "upgrade_cost_base": 25000000, "upgrade_capacity_bonus": 6000000, "funny": "Мировое господство."},
    {"key": "spaceport", "name": "🚀 Космодром", "base_income": 250000, "base_capacity": 30000000, "cost": 150000000, "upgrade_cost_base": 75000000, "upgrade_capacity_bonus": 15000000, "funny": "Туристы на Марс, деньги тебе."},
    {"key": "tech_hub", "name": "💻 Тех-Хаб", "base_income": 500000, "base_capacity": 60000000, "cost": 500000000, "upgrade_cost_base": 250000000, "upgrade_capacity_bonus": 30000000, "funny": "Кремниевая долина нервно курит."},
    {"key": "empire", "name": "🏰 Империя", "base_income": 1000000, "base_capacity": 120000000, "cost": 2000000000, "upgrade_cost_base": 1000000000, "upgrade_capacity_bonus": 60000000, "funny": "Ты — король мира."},
    {"key": "dyson_sphere", "name": "☀️ Сфера Дайсона", "base_income": 5000000, "base_capacity": 600000000, "cost": 10000000000, "upgrade_cost_base": 5000000000, "upgrade_capacity_bonus": 300000000, "funny": "Энергия целой звезды в кармане."},
    
    # 21-30: Мега-структуры
    {"key": "quantum_center", "name": "⚛️ Квантовый центр", "base_income": 12000000, "base_capacity": 1500000000, "cost": 35000000000, "upgrade_cost_base": 17000000000, "upgrade_capacity_bonus": 750000000, "funny": "Вычисляет прибыль быстрее света."},
    {"key": "underwater_city", "name": "🌊 Подводный город", "base_income": 25000000, "base_capacity": 3000000000, "cost": 100000000000, "upgrade_cost_base": 50000000000, "upgrade_capacity_bonus": 1500000000, "funny": "Нет налогов на дне океана."},
    {"key": "weather_control", "name": "⚡ Контроль погоды", "base_income": 60000000, "base_capacity": 7500000000, "cost": 300000000000, "upgrade_cost_base": 150000000000, "upgrade_capacity_bonus": 3500000000, "funny": "Продаем солнечные дни."},
    {"key": "orbital_station", "name": "🛰️ Орбитальная станция", "base_income": 150000000, "base_capacity": 18000000000, "cost": 1000000000000, "upgrade_cost_base": 500000000000, "upgrade_capacity_bonus": 9000000000, "funny": "Отель с видом на Землю."},
    {"key": "space_elevator", "name": "🏗️ Космический лифт", "base_income": 400000000, "base_capacity": 50000000000, "cost": 3500000000000, "upgrade_cost_base": 1700000000000, "upgrade_capacity_bonus": 25000000000, "funny": "Доставка на орбиту за копейки."},
    {"key": "moon_base", "name": "🌑 Лунная база", "base_income": 1000000000, "base_capacity": 120000000000, "cost": 10000000000000, "upgrade_cost_base": 5000000000000, "upgrade_capacity_bonus": 60000000000, "funny": "Добыча редких ресурсов."},
    {"key": "mars_colony", "name": "🔴 Колония на Марсе", "base_income": 2500000000, "base_capacity": 300000000000, "cost": 35000000000000, "upgrade_cost_base": 17000000000000, "upgrade_capacity_bonus": 150000000000, "funny": "Новый дом для человечества."},
    {"key": "artificial_sun", "name": "☀️ Искусственное Солнце", "base_income": 7000000000, "base_capacity": 850000000000, "cost": 120000000000000, "upgrade_cost_base": 60000000000000, "upgrade_capacity_bonus": 420000000000, "funny": "Вечная энергия, вечная прибыль."},
    {"key": "galactic_bank", "name": "🌌 Галактический банк", "base_income": 20000000000, "base_capacity": 2500000000000, "cost": 500000000000000, "upgrade_cost_base": 250000000000000, "upgrade_capacity_bonus": 1200000000000, "funny": "Валюта всех цивилизаций здесь."},
    {"key": "universal_core", "name": "💠 Ядро Вселенной", "base_income": 50000000000, "base_capacity": 6000000000000, "cost": 2000000000000000, "upgrade_cost_base": 1000000000000000, "upgrade_capacity_bonus": 3000000000000, "funny": "Ты управляешь самим мирозданием."}
]

# --- СПИСОК ОСНОВНЫХ ЗАДАНИЙ ---
main_quests_info = [
    # ТИП 1: НАКОПИТЬ МОНЕТЫ
    {"key": "bal_1k", "type": "balance", "target": 1000, "name": "💰 Первые шаги", "desc": "Накопи на балансе 1 000 монет", "rew_coins": 1000, "rew_tap": 0, "rew_chance": 0},
    {"key": "bal_50k", "type": "balance", "target": 50000, "name": "💰 Мешок с деньгами", "desc": "Накопи на балансе 50 000 монет", "rew_coins": 10000, "rew_tap": 0, "rew_chance": 0},
    {"key": "bal_250k", "type": "balance", "target": 250000, "name": "💰 Богатей", "desc": "Накопи на балансе 250 000 монет", "rew_coins": 50000, "rew_tap": 0, "rew_chance": 0},
    {"key": "bal_1m", "type": "balance", "target": 1000000, "name": "💰 Миллионер", "desc": "Накопи на балансе 1 000 000 монет", "rew_coins": 200000, "rew_tap": 0, "rew_chance": 0},
    {"key": "bal_10m", "type": "balance", "target": 10000000, "name": "💰 Мультимиллионер", "desc": "Накопи на балансе 10 000 000 монет", "rew_coins": 1000000, "rew_tap": 0, "rew_chance": 0},
    
    # ТИП 2: ПОСТРОИТЬ ЗДАНИЯ
    {"key": "build_5", "type": "buildings_count", "target": 5, "name": "🏗️ Начинающий прораб", "desc": "Построй любые 5 сооружений", "rew_coins": 2000, "rew_tap": 0, "rew_chance": 0},
    {"key": "build_10", "type": "buildings_count", "target": 10, "name": "🏗️ Главный архитектор", "desc": "Построй любые 10 сооружений", "rew_coins": 125000, "rew_tap": 0, "rew_chance": 0},
    {"key": "build_15", "type": "buildings_count", "target": 15, "name": "🏗️ Городской застройщик", "desc": "Построй любые 15 сооружений", "rew_coins": 10000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "build_20", "type": "buildings_count", "target": 20, "name": "🏗️ Бетонный магнат", "desc": "Построй любые 20 сооружений", "rew_coins": 6000000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "build_30", "type": "buildings_count", "target": 30, "name": "🏗️ Владелец Вселенной", "desc": "Построй любые 30 сооружений", "rew_coins": 1500000000000000, "rew_tap": 0, "rew_chance": 0},
    
    # ТИП 3: КУПИТЬ УЛУЧШЕНИЯ
    {"key": "upg_5", "type": "upgrades_count", "target": 5, "name": "🖐️ Коллекционер рук", "desc": "Купи 5 разных пальцев", "rew_coins": 500, "rew_tap": 10, "rew_chance": 0},
    {"key": "upg_10", "type": "upgrades_count", "target": 10, "name": "🖐️ Техно-эволюция", "desc": "Купи 10 разных пальцев", "rew_coins": 20000, "rew_tap": 100, "rew_chance": 0},
    {"key": "upg_15", "type": "upgrades_count", "target": 15, "name": "🖐️ Бог кликов", "desc": "Купи 15 разных пальцев", "rew_coins": 900000, "rew_tap": 500, "rew_chance": 0},
    {"key": "upg_20", "type": "upgrades_count", "target": 20, "name": "🖐️ Легендарный тап", "desc": "Купи 20 разных пальцев", "rew_coins": 45000000, "rew_tap": 2500, "rew_chance": 0},
    {"key": "upg_30", "type": "upgrades_count", "target": 30, "name": "🖐️ Абсолютная власть", "desc": "Купи 30 разных пальцев", "rew_coins": 750000000000, "rew_tap": 100000, "rew_chance": 0},
    
    # ТИП 4: КЛИКИ (ОБНОВЛЕНО ПО ТВОЕМУ ЗАПРОСУ)
    {"key": "click_1k", "type": "clicks", "target": 1000, "name": "👆 Быстрый палец", "desc": "Сделай 1 000 тапов", "rew_coins": 100000, "rew_tap": 50, "rew_chance": 0},
    {"key": "click_5k", "type": "clicks", "target": 5000, "name": "👆 Клик-машина", "desc": "Сделай 5 000 тапов", "rew_coins": 500000, "rew_tap": 200, "rew_chance": 0},
    {"key": "click_20k", "type": "clicks", "target": 20000, "name": "👆 Скорость света", "desc": "Сделай 20 000 тапов", "rew_coins": 3000000, "rew_tap": 500, "rew_chance": 0},
    {"key": "click_50k", "type": "clicks", "target": 50000, "name": "👆 Разрушитель экранов", "desc": "Сделай 50 000 тапов", "rew_coins": 10000000, "rew_tap": 1000, "rew_chance": 0},
    {"key": "click_100k", "type": "clicks", "target": 100000, "name": "👆 Титан кликов", "desc": "Сделай 100 000 тапов", "rew_coins": 100000000, "rew_tap": 5000, "rew_chance": 0},
    
    # ТИП 5: ДОХОД
    {"key": "inc_100", "type": "income", "target": 1000, "name": "💤 Маленький ручеек", "desc": "Достигни дохода 1 000 монет/мин", "rew_coins": 100000, "rew_tap": 0, "rew_chance": 0},
    {"key": "inc_1k", "type": "income", "target": 5000, "name": "💤 Денежная река", "desc": "Достигни дохода 5 000 монет/мин", "rew_coins": 1000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "inc_5k", "type": "income", "target": 10000, "name": "💤 Нефтяная вышка", "desc": "Достигни дохода 10 000 монет/мин", "rew_coins": 10000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "inc_20k", "type": "income", "target": 100000, "name": "💤 Банковский магнат", "desc": "Достигни дохода 100 000 монет/мин", "rew_coins": 100000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "inc_100k", "type": "income", "target": 1000000, "name": "💤 Хозяин мира", "desc": "Достигни дохода 1 000 000 монет/мин", "rew_coins": 10000000000, "rew_tap": 0, "rew_chance": 0},
    
    # ТИП 6: ПОТРАТИТЬ
    {"key": "spend_100k", "type": "spent", "target": 100000, "name": "💸 Шопоголик", "desc": "Потрать в сумме 100 000 монет", "rew_coins": 10000, "rew_tap": 0, "rew_chance": 0},
    {"key": "spend_500k", "type": "spent", "target": 500000, "name": "💸 Крупный инвестор", "desc": "Потрать в сумме 500 000 монет", "rew_coins": 100000, "rew_tap": 0, "rew_chance": 0},
    {"key": "spend_1m", "type": "spent", "target": 1000000, "name": "💸 Золотой кит", "desc": "Потрать в сумме 1 000 000 монет", "rew_coins": 200000, "rew_tap": 0, "rew_chance": 0},
    {"key": "spend_5m", "type": "spent", "target": 5000000, "name": "💸 Акула бизнеса", "desc": "Потрать в сумме 5 000 000 монет", "rew_coins": 1000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "spend_20m", "type": "spent", "target": 20000000, "name": "💸 Король расходов", "desc": "Потрать в сумме 20 000 000 монет", "rew_coins": 5000000, "rew_tap": 0, "rew_chance": 0},

    # ТИП 7: ЗАРАБОТАТЬ АЛМАЗЫ
    {"key": "diam_100", "type": "earned_diamonds", "target": 100, "name": "💎 Искатель сокровищ I", "desc": "Заработай 100 алмазов", "rew_coins": 0, "rew_tap": 0, "rew_diamonds": 10, "rew_chance": 0.001},
    {"key": "diam_500", "type": "earned_diamonds", "target": 500, "name": "💎 Искатель сокровищ II", "desc": "Заработай 500 алмазов", "rew_coins": 0, "rew_tap": 0, "rew_diamonds": 25, "rew_chance": 0.001},
    {"key": "diam_1000", "type": "earned_diamonds", "target": 1000, "name": "💎 Искатель сокровищ III", "desc": "Заработай 1 000 алмазов", "rew_coins": 0, "rew_tap": 0, "rew_diamonds": 50, "rew_chance": 0.002},
    {"key": "diam_5000", "type": "earned_diamonds", "target": 5000, "name": "💎 Искатель сокровищ IV", "desc": "Заработай 5 000 алмазов", "rew_coins": 0, "rew_tap": 0, "rew_diamonds": 100, "rew_chance": 0.002},
    {"key": "diam_10000", "type": "earned_diamonds", "target": 10000, "name": "💎 Искатель сокровищ V", "desc": "Заработай 10 000 алмазов", "rew_coins": 0, "rew_tap": 0, "rew_diamonds": 500, "rew_chance": 0.003},
]

# ═══════════════════════════════════════════════════════════
# РЕГИСТРАЦИЯ И ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════════
def check_daily_reset(user):
    today = date.today().isoformat()
    if user["daily_progress"]["date"] != today:
        user["daily_progress"] = {
            "date": today,
            "clicks": 0, "upgrades": 0, "claims": 0, "completed": [], "all_done": False, "notified": []
        }

def generate_unique_id():
    while True:
        part1 = random.randint(100, 999)
        part2 = random.randint(100, 999)
        new_id = f"{part1} {part2}"
        is_unique = True
        for u in users.values():
            if u.get("custom_id") == new_id:
                is_unique = False
                break
        if is_unique:
            return new_id

def get_current_finger_info(user):
    current_finger_name = upgrades_info[0]["name"]
    current_finger_bonus = user['tap_mult']
    for info in reversed(upgrades_info):
        if user["upgrades"][info["key"]] == 1:
            current_finger_name = info["name"]
            break
    return current_finger_name, current_finger_bonus

# --- МЕНЮ ---
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Профиль"), KeyboardButton(text="🏪 Магазин")],
        [KeyboardButton(text="🏗️ Сооружения"), KeyboardButton(text="📝 Задания")],
        [KeyboardButton(text="🏆 Топ-10"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="💰 Тапать монеты")]
    ], resize_keyboard=True, one_time_keyboard=False)

def profile_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Рефералка")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True, one_time_keyboard=False)

def settings_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Сменить ник"), KeyboardButton(text="🔒 Конфиденциальность")],
        [KeyboardButton(text="ℹ️ О игре"), KeyboardButton(text="👮‍♂️ Админ панель")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True, one_time_keyboard=False)

def cancel_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True, one_time_keyboard=True)

def tap_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💥 ТАПАЙ СЮДА! 💥", callback_data="tap")]])

async def update_passive_income(user_id: int):
    if user_id not in users: return
    user = users[user_id]
    now = datetime.now().timestamp()
    for info in buildings_info:
        key = info["key"]
        level = user["buildings_levels"][key]
        if level > 0 and user["buildings_last_update"][key] > 0:
            minutes_passed = (now - user["buildings_last_update"][key]) / 60
            full_minutes = int(minutes_passed)
            income_per_min = info["base_income"] * level
            earned = income_per_min * full_minutes
            current_accum = user["buildings_accumulated"][key]
            capacity = info["base_capacity"] + info["upgrade_capacity_bonus"] * (level - 1)
            new_accum = min(current_accum + earned, capacity)
            user["buildings_accumulated"][key] = new_accum
            user["buildings_last_update"][key] += full_minutes * 60

def calculate_passive(user):
    passive = 0
    for info in buildings_info:
        level = user["buildings_levels"][info["key"]]
        if level > 0:
            passive += info["base_income"] * level
    user["passive_per_minute"] = passive

def get_progress_bar(current, target, length=10):
    percent = min(current / target, 1.0)
    filled_length = int(length * percent)
    bar = "🟩" * filled_length + "⬜" * (length - filled_length)
    return f"{bar} {int(percent * 100)}%"

# --- УВЕДОМЛЕНИЯ О ЗАДАНИЯХ ---

async def check_quest_notifications(message: Message, user_id: int):
    user = users[user_id]
    if "notified_quests" not in user:
        user["notified_quests"] = []
        
    for quest in main_quests_info:
        key = quest["key"]
        if key in user["completed_quests"]: continue
        if key in user["notified_quests"]: continue

        current_val = 0
        target = quest["target"]
        if quest["type"] == "balance": current_val = user["balance"]
        elif quest["type"] == "buildings_count": current_val = sum(1 for lvl in user["buildings_levels"].values() if lvl > 0)
        elif quest["type"] == "upgrades_count": current_val = sum(user["upgrades"].values())
        elif quest["type"] == "clicks": current_val = user["total_clicks"]
        elif quest["type"] == "income": calculate_passive(user); current_val = user["passive_per_minute"]
        elif quest["type"] == "spent": current_val = user["total_spent"]
        elif quest["type"] == "earned_diamonds": current_val = user["total_diamonds_earned"]
        
        if current_val >= target:
            user["notified_quests"].append(key)
            try:
                await bot.send_message(
                    user_id, 
                    f"🎉 **ЗАДАНИЕ ВЫПОЛНЕНО!**\n\n"
                    f"✅ {quest['name']}\n"
                    f"Зайди в 📝 Задания, чтобы забрать награду!"
                )
            except:
                pass

async def check_daily_notifications(user_id: int):
    user = users[user_id]
    if "notified" not in user["daily_progress"]:
        user["daily_progress"]["notified"] = []
        
    for quest in DAILY_QUESTS_CONFIG:
        key = quest["key"]
        if key in user["daily_progress"]["notified"]: continue
        if key in user["daily_progress"]["completed"]: continue
        
        current = 0
        if key == "daily_clicks": current = user["daily_progress"]["clicks"]
        elif key == "daily_upgrade": current = user["daily_progress"]["upgrades"]
        elif key == "daily_claim": current = user["daily_progress"]["claims"]
        
        if current >= quest["target"]:
            user["daily_progress"]["notified"].append(key)
            try:
                await bot.send_message(
                    user_id,
                    f"🎉 **ЕЖЕДНЕВНОЕ ЗАДАНИЕ ГОТОВО!**\n\n"
                    f"✅ {quest['name']}\n"
                    f"Забери награду в разделе 📅 Ежедневные задания!"
                )
            except:
                pass

async def show_main_interface(message: Message, user_id: int):
    user = users[user_id]
    finger_name, finger_bonus = get_current_finger_info(user)
    safe_nick = str(user['nickname']).replace("<", "&lt;").replace(">", "&gt;")
    
    # ФОРМАТИРОВАНИЕ БОНУСА (с пробелом в скобках)
    bonus_fmt = f"{finger_bonus:,}".replace(",", " ")
    
    text = (f"🌟<b>Добро пожаловать в Tycoon Empire!</b>🌟\n\n"
            f"Ты — будущий миллиардер! Начинай тапать и строй свою империю прямо сейчас!\n\n"
            f"🆔 Твой ID: <code>{user['custom_id']}</code>\n"
            f"👤 Ник: <b>{safe_nick}</b>\n"
            f"💰 Баланс: {user['balance']:,} монет\n"
            f"💎 Алмазы: {user['diamonds']:,}\n"
            f"🖐️ Текущий палец: {finger_name} (+{bonus_fmt} за тап)\n\n"
            f"Жми большую кнопку ниже и начинай богатеть! 💸").replace(",", " ")
    
    sent = await message.answer(text, reply_markup=tap_button(), parse_mode="HTML")
    user["tap_message_id"] = sent.message_id
    await message.answer("🚀 Главное меню:", reply_markup=main_menu())

# ═══════════════════════════════════════════════════════════
# /start и РЕГИСТРАЦИЯ НИКА
# ═══════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    
    if user_id not in users:
        await database.create_table() 
        
        upgrades = {info["key"]: 0 for info in upgrades_info}
        upgrades["wooden_finger"] = 1
        buildings_levels = {info["key"]: 0 for info in buildings_info}
        buildings_accumulated = {info["key"]: 0 for info in buildings_info}
        buildings_last_update = {info["key"]: 0.0 for info in buildings_info}
        custom_id = generate_unique_id()
        
        users[user_id] = {
            "username": message.from_user.username or "User",
            "nickname": None,
            "custom_id": custom_id,
            "registration_date": date.today().isoformat(),
            "last_active": date.today().isoformat(),
            "last_nick_change": None, 
            "state": "registering_nickname",
            "privacy_enabled": True, 
            "balance": 0, 
            "diamonds": 0,
            "total_diamonds_earned": 0,
            "diamond_chance_bonus": 0.0,
            "tap_mult": 1,
            "passive_per_minute": 0,
            "referrals": 0,
            "total_clicks": 0,
            "total_spent": 0,
            "upgrades": upgrades,
            "buildings_levels": buildings_levels,
            "buildings_accumulated": buildings_accumulated,
            "buildings_last_update": buildings_last_update,
            "completed_quests": [],
            "notified_quests": [],
            "daily_streak": 0,
            "last_daily_done_date": None,
            "daily_progress": {
                "date": date.today().isoformat(),
                "clicks": 0, "upgrades": 0, "claims": 0, "completed": [], "all_done": False, "notified": []
            },
            "tap_message_id": None,
            "shop_message_id": None,
            "buildings_message_id": None,
            "last_tap_time": 0.0
        }
        
        args = message.text.split()
        if len(args) > 1:
            try:
                ref_id = int(args[1])
                if ref_id != user_id and ref_id in users:
                    users[ref_id]["referrals"] += 1
                    users[ref_id]["balance"] += 1000
                    users[ref_id]["diamonds"] += 1
                    users[user_id]["balance"] += 500
                    try:
                        await bot.send_message(ref_id, f"🎉 По вашей ссылке зарегистрировался новый игрок!\nНаграда: +1000 монет и +1 алмаз 💎")
                    except:
                        pass
                    await message.answer("🎉 Ты пришёл по приглашению!\nБонус: +500 монет! 🔥")
            except:
                pass

        welcome_text = (
            "👋 **Привет, будущий магнат!**\n\n"
            "Ты попал в мир **Tycoon Empire**, где тебе предстоит:\n"
            "👆 Тапать и зарабатывать монеты\n"
            "🖐️ Покупать новые пальцы для мощного тапа\n"
            "🏗️ Строить здания и получать пассивный доход\n"
            "💎 Искать редкие алмазы\n"
            "🏆 Стать самым богатым в топе!\n\n"
            "Для начала, как нам тебя называть?\n"
            "Напиши свой **Никнейм** (макс. 15 символов, можно смайлики)."
        )
        
        await message.answer(welcome_text, reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
        return

    if users[user_id].get("state") == "registering_nickname":
        await message.answer("Пожалуйста, введи свой никнейм для продолжения.")
        return

    # Обновляем активность при старте
    users[user_id]["last_active"] = date.today().isoformat()
    calculate_passive(users[user_id])
    await show_main_interface(message, user_id)

# ═══════════════════════════════════════════════════════════
# СИСТЕМА ПРОМОКОДОВ
# ═══════════════════════════════════════════════════════════
@dp.message(Command("promo"))
async def promo_handler(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("❌ Ты кто вообще? Жми /start")
        return

    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        try:
            emoji = random.choice(promocodes.REACTION_LIST_HELP)
            await message.react([ReactionTypeEmoji(emoji=emoji)])
        except: pass
        await message.answer(promocodes.HELP_MESSAGE, parse_mode="HTML")
        return

    code = args[1].strip()
    user = users[user_id]
    success, response_text, reaction_emoji = promocodes.activate_promo(user, code)
    
    try:
        await message.react([ReactionTypeEmoji(emoji=reaction_emoji)])
    except: pass

    await message.answer(response_text, parse_mode="HTML")

@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    
    if user_id in users:
        current_username = message.from_user.username
        if users[user_id].get("username") != current_username:
            users[user_id]["username"] = current_username
        # Обновляем last_active при любой активности
        users[user_id]["last_active"] = date.today().isoformat()

    if user_id in users and users[user_id].get("state") == "registering_nickname":
        user = users[user_id]
        text = message.text.strip()
        if len(text) > 15:
            await message.answer("❌ Ник слишком длинный! Максимум 15 символов.\nПопробуй снова.")
            return
        
        user["nickname"] = text
        safe_name = str(text).replace("<", "&lt;").replace(">", "&gt;")
        await admin_panel.notify_new_player(bot, user)
        await message.answer(f"✅ Отличный ник: <b>{safe_name}</b>", reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
        user["state"] = "active"
        calculate_passive(user)
        await show_main_interface(message, user_id)
        return
    
    if user_id in users and users[user_id].get("state") == "changing_nickname":
        if message.text == "❌ Отмена":
            users[user_id]["state"] = "active"
            await message.answer("⚙️ **Меню настроек**", reply_markup=settings_menu(), parse_mode="Markdown")
            return

        user = users[user_id]
        new_nick = message.text.strip()

        if len(new_nick) > 15:
             await message.answer("❌ Ник слишком длинный!", reply_markup=cancel_menu())
             return
        if user["diamonds"] < NICKNAME_CHANGE_COST:
            user["state"] = "active"
            await message.answer("❌ Ошибка: Не хватает алмазов.", reply_markup=settings_menu())
            return
            
        user["diamonds"] -= NICKNAME_CHANGE_COST
        user["nickname"] = new_nick
        user["last_nick_change"] = date.today().isoformat()
        user["state"] = "active"
        
        safe_nick = str(new_nick).replace("<", "&lt;").replace(">", "&gt;")
        cost_str = f"{NICKNAME_CHANGE_COST:,}".replace(",", " ")
        await message.answer(f"✅ Ник успешно изменён на <b>{safe_nick}</b>!\nСписано: {cost_str} 💎", parse_mode="HTML", reply_markup=settings_menu())
        return

    if message.text == "💰 Тапать монеты": await show_tap(message)
    elif message.text == "📊 Профиль": await profile(message)
    elif message.text == "🏪 Магазин": await shop(message)
    elif message.text == "🏗️ Сооружения": await buildings_shop(message)
    elif message.text == "📝 Задания": await quests_menu(message)
    elif message.text == "👥 Рефералка": await referral(message)
    elif message.text == "🏆 Топ-10": await top10_menu(message)
    elif message.text == "⚙️ Настройки": await message.answer("⚙️ **Меню настроек**", reply_markup=settings_menu(), parse_mode="Markdown")
    elif message.text == "🔙 Назад": await message.answer("🚀 Главное меню:", reply_markup=main_menu())
    elif message.text == "🔒 Конфиденциальность": await privacy_settings(message)
    elif message.text == "ℹ️ О игре": await about_game(message)
    elif message.text == "📝 Сменить ник": await request_nick_change(message)
    elif message.text == "👮‍♂️ Админ панель": await open_admin_panel(message)
    elif message.text == "👥 Список игроков":
        if admin_panel.is_admin(user_id):
            kb = admin_panel.get_users_keyboard(users, page=0)
            await message.answer("👥 **Список игроков:**", reply_markup=kb)
    elif message.text == "📢 Оповещение":
        if admin_panel.is_admin(user_id):
            await message.answer("📡 **Центр оповещений**\nВыберите тип сообщения:", reply_markup=admin_panel.broadcast_type_kb(), parse_mode="Markdown")
    elif message.text == "💾 Выгрузка":
        if admin_panel.is_admin(user_id):
            await message.answer("⚠️ **Выгрузка базы данных**\n\nСкачать файл данных?", reply_markup=admin_panel.export_confirm_kb(), parse_mode="Markdown")
    else:
        try:
            await message.react([ReactionTypeEmoji(emoji="🤔")])
            await message.reply(random.choice(FUNNY_RESPONSES))
        except: pass

@dp.callback_query(F.data == "admin_export_confirm")
async def export_data_handler(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    
    await callback.message.edit_text("⏳ **Начинаю выгрузку...**")
    
    try:
        # Добавлено await
        await database.save_all_users(users)
        
        # Добавлено await
        filename = await database.export_users_to_json_file()
        
        file = FSInputFile(filename)
        await bot.send_document(callback.from_user.id, file, caption="✅ **Полная база данных игроков**")
        
        os.remove(filename)
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка выгрузки: {e}")

# --- ОБРАБОТЧИКИ РАССЫЛКИ ---
@dp.callback_query(F.data.startswith("broadcast_setup_"))
async def broadcast_setup_handler(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    msg_type = callback.data.replace("broadcast_setup_", "")
    # Тексты setup находятся в admin_panel, здесь мы просто показываем выбор времени
    text = "⏳ **Выберите время до начала события:**"
    await callback.message.edit_text(text, reply_markup=admin_panel.broadcast_time_kb(msg_type), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("broadcast_send_"))
async def broadcast_send_handler(callback: CallbackQuery):
    if not admin_panel.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    msg_type = parts[2]
    minutes = parts[3]
    
    # Получаем текст из admin_panel
    send_text = admin_panel.get_broadcast_text(msg_type, minutes)
    
    await callback.message.edit_text("⏳ **Рассылка запущена...**\nБот не будет отвечать некоторое время.", parse_mode="Markdown")
    
    # Запускаем рассылку через admin_panel
    count = await admin_panel.perform_broadcast(bot, users, send_text)
            
    await callback.message.answer(f"✅ **Рассылка завершена!**\nПолучили: {count} чел.", parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════
# СМЕНА НИКА
# ═══════════════════════════════════════════════════════════
async def request_nick_change(message: Message):
    user = users[message.from_user.id]
    if user.get("last_nick_change"):
        last_change = date.fromisoformat(user["last_nick_change"])
        days_passed = (date.today() - last_change).days
        if days_passed < NICKNAME_CHANGE_DAYS:
            days_left = NICKNAME_CHANGE_DAYS - days_passed
            await message.answer(f"⏳ Смена ника доступна через {days_left} дн.")
            return

    cost_str = f"{NICKNAME_CHANGE_COST:,}".replace(",", " ")
    text = (
        "📝 **СМЕНА НИКА**\n\n"
        f"Стоимость: **{cost_str} 💎**\n"
        f"Кулдаун: **{NICKNAME_CHANGE_DAYS} дней**\n\n"
        "Вы уверены, что хотите сменить ник?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сменить", callback_data="confirm_nick_change")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "confirm_nick_change")
async def confirm_nick_change_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    cost_str = f"{NICKNAME_CHANGE_COST:,}".replace(",", " ")
    
    if user["diamonds"] < NICKNAME_CHANGE_COST:
        await callback.answer(f"❌ Не хватает алмазов!\nНужно: {cost_str} 💎", show_alert=True)
        return
        
    user["state"] = "changing_nickname"
    await callback.message.answer("✍️ **Введите новый ник:**\n(Максимум 15 символов)", reply_markup=cancel_menu(), parse_mode="Markdown")
    await callback.answer()

# ═══════════════════════════════════════════════════════════
# АДМИН ПАНЕЛЬ
# ═══════════════════════════════════════════════════════════
async def open_admin_panel(message: Message):
    user_id = message.from_user.id
    if not admin_panel.is_admin(user_id):
        await message.answer("⛔ **Вход только для администрации!**", parse_mode="Markdown")
        return
    await message.answer("👮‍♂️ **Панель Администратора**", reply_markup=admin_panel.admin_main_menu())

@dp.callback_query(F.data.startswith("admin_page_"))
async def admin_pagination(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not admin_panel.is_admin(user_id): return
    page = int(callback.data.replace("admin_page_", ""))
    kb = admin_panel.get_users_keyboard(users, page=page)
    try: await callback.message.edit_reply_markup(reply_markup=kb)
    except: pass

@dp.callback_query(F.data.startswith("admin_view_"))
async def admin_view_user(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not admin_panel.is_admin(user_id): return
    parts = callback.data.split("_")
    target_tg_id = int(parts[2])
    page = int(parts[3])
    
    target_user = users.get(target_tg_id)
    if not target_user:
        await callback.answer("Игрок не найден", show_alert=True)
        return
        
    # Считаем данные для расширенного профиля
    passive_income = 0
    for info in buildings_info:
        level = target_user["buildings_levels"].get(info["key"], 0)
        if level > 0:
            passive_income += info["base_income"] * level
            
    finger_name = upgrades_info[0]["name"]
    for info in reversed(upgrades_info):
        if target_user["upgrades"].get(info["key"], 0) == 1:
            finger_name = info["name"]
            break
            
    text = admin_panel.get_user_profile_text(target_user, target_tg_id, passive_income, finger_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Вернуться в список", callback_data=f"admin_page_{page}")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════
async def privacy_settings(message: Message):
    user = users[message.from_user.id]
    status = "✅ Включено" if user.get("privacy_enabled", True) else "❌ Отключено"
    text = (f"🔒 **Настройки конфиденциальности**\n\n"
            f"Этот параметр отвечает за то, будет ли ваш ник в Топ-10 кликабельным (ссылка на профиль Телеграм).\n\n"
            f"👉 **Внимание:** Кликабельность ссылки также зависит от ваших настроек Telegram.\n"
            f"Если в **Конфиденциальность -> Пересылка сообщений** у вас стоит 'Никто' или 'Мои контакты', "
            f"то незнакомые люди не смогут открыть ваш профиль, даже если здесь стоит ✅.\n\n"
            f"Текущий статус: **{status}**")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Включить", callback_data="privacy_on"),
         InlineKeyboardButton(text="❌ Отключить", callback_data="privacy_off")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.in_(["privacy_on", "privacy_off"]))
async def privacy_toggle(callback: CallbackQuery):
    user = users[callback.from_user.id]
    enable = callback.data == "privacy_on"
    user["privacy_enabled"] = enable
    status_text = "Включено" if enable else "Отключено"
    await callback.answer(f"Конфиденциальность: {status_text}", show_alert=False)
    status_icon = "✅ Включено" if enable else "❌ Отключено"
    text = (f"🔒 **Настройки конфиденциальности**\n\n"
            f"Этот параметр отвечает за то, будет ли ваш ник в Топ-10 кликабельным (ссылка на профиль Телеграм).\n\n"
            f"👉 **Внимание:** Кликабельность ссылки также зависит от ваших настроек Telegram.\n"
            f"Если в **Конфиденциальность -> Пересылка сообщений** у вас стоит 'Никто' или 'Мои контакты', "
            f"то незнакомые люди не смогут открыть ваш профиль, даже если здесь стоит ✅.\n\n"
            f"Текущий статус: **{status_icon}**")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Включить", callback_data="privacy_on"),
         InlineKeyboardButton(text="❌ Отключить", callback_data="privacy_off")]
    ])
    try: await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except: pass

async def about_game(message: Message):
    text = (
        "ℹ️ **О ИГРЕ: Tycoon Empire**\n\n"
        "Строй свою империю, кликай и побеждай!\n\n"
        "📢 **Наш канал:** [TycoonEmpireOfficial](https://t.me/TycoonEmpireOfficial)\n"
        "📄 **Вся информация:** [Читать тут](https://teletype.in/@shadowdragonr/TycoonEmpireBot)\n\n"
        "✍️ **Поддержка / Предложения:**\n"
        "Нашли ошибку? Есть идея? Пишите: [ShadowDragonR](https://t.me/ShadowDragonR)"
    )
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

# ═══════════════════════════════════════════════════════════
# ТАП
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "tap")
async def tap(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in users: return
    await update_passive_income(user_id)
    user = users[user_id]
    check_daily_reset(user)
    now = datetime.now().timestamp()
    if now - user["last_tap_time"] < 0.5:
        await callback.answer(random.choice(funny_spam), show_alert=False)
        return
    earn = user["tap_mult"]
    user["balance"] += earn
    user["total_clicks"] += 1
    user["daily_progress"]["clicks"] += 1
    user["last_tap_time"] = now
    
    current_chance = BASE_DIAMOND_CHANCE + user["diamond_chance_bonus"]
    diamond_alert = ""
    if random.random() < current_chance:
        user["diamonds"] += 1
        user["total_diamonds_earned"] += 1
        diamond_alert = "\n💎 ВЫПАЛ АЛМАЗ! 💎"
    
    msg_earn = f"💥 +{earn:,} монет!".replace(",", " ") + diamond_alert
    await callback.answer(msg_earn, show_alert=bool(diamond_alert))
    await check_quest_notifications(callback.message, user_id)
    await check_daily_notifications(user_id)
    
    finger_name, _ = get_current_finger_info(user)
    bonus_fmt = f"{earn:,}".replace(",", " ")
    text = (f"🌟<b>Добро пожаловать в Tycoon Empire!</b>🌟\n\n"
            f"💰 Баланс: {user['balance']:,} монет\n"
            f"💎 Алмазы: {user['diamonds']:,}\n"
            f"🖐️ За тап: +{bonus_fmt} монет\n"
            f"🖐️ Текущий палец: {finger_name}\n\n"
            f"Ты становишься всё ближе к вершине! 🔥\n"
            f"Продолжай тапать!").replace(",", " ")
    try: await callback.message.edit_text(text, reply_markup=tap_button(), parse_mode="HTML")
    except: pass

async def show_tap(message: Message):
    user_id = message.from_user.id
    await update_passive_income(user_id)
    user = users[user_id]
    finger_name, finger_bonus = get_current_finger_info(user)
    bonus_fmt = f"{finger_bonus:,}".replace(",", " ")
    text = (f"🌟<b>Добро пожаловать в Tycoon Empire!</b>🌟\n\n"
            f"💰 Баланс: {user['balance']:,} монет\n"
            f"💎 Алмазы: {user['diamonds']:,}\n"
            f"🖐️ За тап: +{bonus_fmt} монет\n"
            f"🖐️ Текущий палец: {finger_name}\n\n"
            f"Жми большую кнопку и богатей! 💸").replace(",", " ")
    if user["tap_message_id"]:
        try:
            await bot.edit_message_text(text, message.chat.id, user["tap_message_id"], reply_markup=tap_button(), parse_mode="HTML")
            return
        except: pass
    sent = await message.answer(text, reply_markup=tap_button(), parse_mode="HTML")
    user["tap_message_id"] = sent.message_id

# ═══════════════════════════════════════════════════════════
# СИСТЕМА ЗАДАНИЙ
# ═══════════════════════════════════════════════════════════
async def quests_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ежедневные задания", callback_data="quests_daily")],
        [InlineKeyboardButton(text="📜 Основные задания", callback_data="quests_main")]
    ])
    await message.answer("🎯 **Центр заданий**\n\nВыполняй задания и получай монеты и алмазы!", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "quests_daily")
async def quests_daily(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    check_daily_reset(user)
    if len(user["daily_progress"]["completed"]) >= 3:
        now = datetime.now()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        delta = tomorrow - now
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_left = f"{hours:02}:{minutes:02}:{seconds:02}"
        await callback.answer(f"✅ Всё выполнено!\nОбновление через: {time_left}", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for q in DAILY_QUESTS_CONFIG:
        key = q["key"]
        if key in user["daily_progress"]["completed"]: continue
        name_text = f"{q['name']} (+{q['reward_diamonds']} 💎)"
        kb.inline_keyboard.append([InlineKeyboardButton(text=name_text, callback_data=f"view_daily_{key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="quests_back_root")])
    streak_fmt = f"{user['daily_streak']:,}".replace(",", " ")
    text = (f"📅 **Ежедневные задания**\n🔥 Серия: **{streak_fmt} дн.**\nСброс в 00:00")
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_daily_"))
async def view_daily(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    key = callback.data.replace("view_daily_", "", 1)
    quest = next((q for q in DAILY_QUESTS_CONFIG if q["key"] == key), None)
    if not quest: return
    current = 0
    if key == "daily_clicks": current = user["daily_progress"]["clicks"]
    elif key == "daily_upgrade": current = user["daily_progress"]["upgrades"]
    elif key == "daily_claim": current = user["daily_progress"]["claims"]
    target = quest["target"]
    progress_bar = get_progress_bar(current, target)
    text = (f"📅 **{quest['name']}**\nℹ️ {quest['desc']}\n🎁 Награда: **{quest['reward_diamonds']} 💎**\n\n📊 Прогресс:\n{current} / {target}\n{progress_bar}")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if current >= target:
        kb.inline_keyboard.append([InlineKeyboardButton(text="✅ ЗАБРАТЬ", callback_data=f"claim_daily_{key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="quests_daily")])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("claim_daily_"))
async def claim_daily(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    key = callback.data.replace("claim_daily_", "", 1)
    if key in user["daily_progress"]["completed"]: return
    quest = next((q for q in DAILY_QUESTS_CONFIG if q["key"] == key), None)
    user["diamonds"] += quest["reward_diamonds"]
    user["total_diamonds_earned"] += quest["reward_diamonds"]
    user["daily_progress"]["completed"].append(key)
    await callback.answer(f"💎 +{quest['reward_diamonds']} алмаз!", show_alert=True)
    if len(user["daily_progress"]["completed"]) >= 3:
        user["daily_streak"] += 1
        user["last_daily_done_date"] = date.today().isoformat()
        await callback.message.answer(f"🔥 **ВСЕ ЗАДАНИЯ ВЫПОЛНЕНЫ!** 🔥\nСерия: {user['daily_streak']} дней!")
    await quests_daily(callback)

@dp.callback_query(F.data == "quests_main")
async def quests_main_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    last_type = None
    for quest in main_quests_info:
        current_type = quest["type"]
        if last_type is not None and current_type != last_type:
            kb.inline_keyboard.append([InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━", callback_data="ignore")])
        last_type = current_type
        key = quest["key"]
        status_icon = "✅" if key in user["completed_quests"] else ""
        name_text = f"{status_icon} {quest['name']}"
        kb.inline_keyboard.append([InlineKeyboardButton(text=name_text, callback_data=f"view_quest_{key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="quests_back_root")])
    try: await callback.message.edit_text("📜 **Основные задания**", reply_markup=kb, parse_mode="Markdown")
    except: await callback.message.answer("📜 **Основные задания**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "ignore")
async def ignore_click(callback: CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data == "quests_back_root")
async def quests_back_root(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ежедневные задания", callback_data="quests_daily")],
        [InlineKeyboardButton(text="📜 Основные задания", callback_data="quests_main")]
    ])
    await callback.message.edit_text("🎯 **Центр заданий**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_quest_"))
async def view_quest(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    quest_key = callback.data.replace("view_quest_", "", 1)
    quest = next((q for q in main_quests_info if q["key"] == quest_key), None)
    if not quest: return

    is_completed = quest_key in user["completed_quests"]
    current_progress = 0
    target = quest["target"]
    
    if quest["type"] == "balance": current_progress = user["balance"]
    elif quest["type"] == "buildings_count": current_progress = sum(1 for lvl in user["buildings_levels"].values() if lvl > 0)
    elif quest["type"] == "upgrades_count": current_progress = sum(user["upgrades"].values())
    elif quest["type"] == "clicks": current_progress = user["total_clicks"]
    elif quest["type"] == "income": calculate_passive(user); current_progress = user["passive_per_minute"]
    elif quest["type"] == "spent": current_progress = user["total_spent"]
    elif quest["type"] == "earned_diamonds": current_progress = user["total_diamonds_earned"]
    
    progress_bar = get_progress_bar(current_progress, target)
    formatted_current = f"{current_progress:,}".replace(",", " ")
    formatted_target = f"{target:,}".replace(",", " ")
    status_text = "✅ Выполнено" if is_completed else f"📊 Прогресс:\n{formatted_current} / {formatted_target}\n{progress_bar}"
    
    reward_parts = []
    if quest['rew_coins'] > 0: reward_parts.append(f"{quest['rew_coins']:,} монет".replace(",", " "))
    if quest.get('rew_diamonds', 0) > 0: reward_parts.append(f"{quest['rew_diamonds']} 💎")
    
    # ЗДЕСЬ ДОБАВЛЕН ПРОБЕЛ В ЧИСЛО
    if quest['rew_tap'] > 0: reward_parts.append(f"{quest['rew_tap']:,} к тапу".replace(",", " "))
    
    if quest['rew_chance'] > 0: reward_parts.append(f"{quest['rew_chance']*100:.1f}% к шансу получения алмаза")
    
    reward_text = "**" + " + ".join(reward_parts) + "**"

    text = (f"📜 **{quest['name']}**\nℹ️ {quest['desc']}\n🎁 Награда: {reward_text}\n\n{status_text}")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if not is_completed:
        kb.inline_keyboard.append([InlineKeyboardButton(text="✅ ЗАВЕРШИТЬ", callback_data=f"complete_quest_{quest_key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="quests_main")])
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except:
        pass

@dp.callback_query(F.data.startswith("complete_quest_"))
async def complete_quest(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    quest_key = callback.data.replace("complete_quest_", "", 1)
    quest = next((q for q in main_quests_info if q["key"] == quest_key), None)
    if quest_key in user["completed_quests"]: return
    current_val = 0
    target = quest["target"]
    if quest["type"] == "balance": current_val = user["balance"]
    elif quest["type"] == "buildings_count": current_val = sum(1 for lvl in user["buildings_levels"].values() if lvl > 0)
    elif quest["type"] == "upgrades_count": current_val = sum(user["upgrades"].values())
    elif quest["type"] == "clicks": current_val = user["total_clicks"]
    elif quest["type"] == "income": calculate_passive(user); current_val = user["passive_per_minute"]
    elif quest["type"] == "spent": current_val = user["total_spent"]
    elif quest["type"] == "earned_diamonds": current_val = user["total_diamonds_earned"]
    if current_val < target:
        await callback.answer("❌ Условия не выполнены!", show_alert=True)
        return
    user["completed_quests"].append(quest_key)
    user["balance"] += quest.get("rew_coins", 0)
    user["diamonds"] += quest.get("rew_diamonds", 0)
    user["tap_mult"] += quest.get("rew_tap", 0)
    user["diamond_chance_bonus"] += quest.get("rew_chance", 0)
    await callback.answer("🎉 Задание выполнено!", show_alert=True)
    new_data = f"view_quest_{quest_key}"
    new_callback = callback.model_copy(update={'data': new_data})
    await view_quest(new_callback)

# ═══════════════════════════════════════════════════════════
# ПРОФИЛЬ
# ═══════════════════════════════════════════════════════════
async def profile(message: Message):
    user_id = message.from_user.id
    await update_passive_income(user_id)
    user = users[user_id]
    calculate_passive(user)
    current_finger_name, current_finger_bonus = get_current_finger_info(user)
    total_chance = (BASE_DIAMOND_CHANCE + user["diamond_chance_bonus"]) * 100
    safe_nick = str(user['nickname']).replace("<", "&lt;").replace(">", "&gt;")
    reg_date = user.get("registration_date", "Неизвестно") 
    tap_bonus_fmt = f"{current_finger_bonus:,}".replace(",", " ")
    quest_count_fmt = f"{len(user['completed_quests']):,}".replace(",", " ")
    streak_fmt = f"{user['daily_streak']:,}".replace(",", " ")
    text = (f"👑 <b>ТВОЙ ПРОФИЛЬ</b> 👑\n\n"
            f"👤 Ник: <b>{safe_nick}</b>\n"
            f"📅 В игре с: {reg_date}\n"
            f"🆔 ID: <code>{user['custom_id']}</code>\n"
            f"💰 Баланс: {user['balance']:,} монет\n"
            f"💎 Алмазы: {user['diamonds']:,} (Шанс: {total_chance:.1f}%)\n"
            f"🔥 За один тап: + {tap_bonus_fmt} монет\n"
            f"🕒 Пассивный доход: + {user['passive_per_minute']:,} монет/мин\n"
            f"👆 Всего кликов: {user['total_clicks']:,}\n"
            f"💸 Всего потрачено: {user['total_spent']:,}\n"
            f"👥 Друзей: {user['referrals']:,}\n"
            f"📝 Основных заданий: {quest_count_fmt}\n"
            f"📅 Серия ежедневных: {streak_fmt} дн.\n"
            f"🖐️ Палец: {current_finger_name}\n\n"
            f"Ты уже на пути к миллиарду! 🚀").replace(",", " ")
    await message.answer(text, parse_mode="HTML", reply_markup=profile_menu())

# ═══════════════════════════════════════════════════════════
# МАГАЗИН ПАЛЬЦЕВ И СООРУЖЕНИЙ
# ═══════════════════════════════════════════════════════════
async def shop(message: Message, page=0):
    if isinstance(message, CallbackQuery): message = message.message
    await update_passive_income(message.chat.id)
    user = users[message.chat.id]
    if user["shop_message_id"]:
        try: await bot.delete_message(message.chat.id, user["shop_message_id"])
        except: pass
    total_items = len(upgrades_info)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_items = upgrades_info[start_idx:end_idx]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, info in enumerate(current_items):
        idx_in_global = start_idx + i
        key = info["key"]
        bought = user["upgrades"][key]
        unlocked = idx_in_global == 0 or user["upgrades"][upgrades_info[idx_in_global-1]["key"]] == 1
        if bought: kb.inline_keyboard.append([InlineKeyboardButton(text=f"{info['name']} ✅", callback_data="bought_finger")])
        elif unlocked: kb.inline_keyboard.append([InlineKeyboardButton(text=info['name'], callback_data=f"view_finger_{key}_{page}")])
        else: kb.inline_keyboard.append([InlineKeyboardButton(text=f"{info['name']} 🔒", callback_data="locked_finger")])
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Туда", callback_data=f"shop_page_{page-1}"))
    if page < total_pages - 1: nav_row.append(InlineKeyboardButton(text="Сюда ➡️", callback_data=f"shop_page_{page+1}"))
    if nav_row: kb.inline_keyboard.append(nav_row)
    text = (f"🏪 **МАГАЗИН УЛУЧШЕНИЙ** (Стр. {page+1}/{total_pages})\n\nВыбери новый палец и стань ещё богаче!")
    sent = await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    user["shop_message_id"] = sent.message_id

@dp.callback_query(F.data.startswith("shop_page_"))
async def shop_page_nav(callback: CallbackQuery):
    page = int(callback.data.replace("shop_page_", "", 1))
    await callback.message.delete()
    await shop(callback.message, page)

@dp.callback_query(F.data.in_(["locked_finger", "bought_finger"]))
async def locked_bought_finger(callback: CallbackQuery):
    if callback.data == "locked_finger": await callback.answer("🔒 Сначала купи предыдущий!", show_alert=True)
    else: await callback.answer("✅ Уже твой!", show_alert=False)

@dp.callback_query(F.data.startswith("view_finger_"))
async def view_upgrade(callback: CallbackQuery):
    user = users[callback.from_user.id]
    data_parts = callback.data.replace("view_finger_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in upgrades_info if x["key"] == key), None)
    if not info: return
    text = (f"✨ **{info['name']}** ✨\n\n💪 Даёт: **+{info['bonus']}** монет за тап\n{info['funny']}\n💸 Цена: **{info['cost']:,}** монет").replace(",", " ")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 КУПИТЬ СЕЙЧАС", callback_data=f"buy_finger_{key}_{page}")],
        [InlineKeyboardButton(text="🔙 Назад в магазин", callback_data=f"shop_page_{page}")]
    ])
    await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_finger_"))
async def buy_upgrade(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    data_parts = callback.data.replace("buy_finger_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in upgrades_info if x["key"] == key), None)
    if not info: return
    if user["upgrades"][key] == 1: return
    if user["balance"] < info["cost"]:
        await callback.answer("❌ Не хватает монет!", show_alert=True)
        return
    user["balance"] -= info["cost"]
    user["total_spent"] += info["cost"]
    user["upgrades"][key] = 1
    user["tap_mult"] += info["bonus"]
    await callback.answer(f"🎉 Ты купил {info['name']}!", show_alert=True)
    await check_quest_notifications(callback.message, user_id)
    try: await callback.message.delete()
    except: pass
    await shop(callback.message, page)

async def buildings_shop(message: Message, page=0):
    if isinstance(message, CallbackQuery): message = message.message
    user_id = message.chat.id
    await update_passive_income(user_id)
    user = users[user_id]
    calculate_passive(user)
    if user["buildings_message_id"]:
        try: await bot.delete_message(message.chat.id, user["buildings_message_id"])
        except: pass
    total_items = len(buildings_info)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_items = buildings_info[start_idx:end_idx]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, info in enumerate(current_items):
        idx_in_global = start_idx + i
        key = info["key"]
        level = user["buildings_levels"][key]
        unlocked = idx_in_global == 0 or user["buildings_levels"][buildings_info[idx_in_global-1]["key"]] > 0
        if level > 0: kb.inline_keyboard.append([InlineKeyboardButton(text=f"{info['name']} (Ур. {level})", callback_data=f"view_building_{key}_{page}")])
        elif unlocked: kb.inline_keyboard.append([InlineKeyboardButton(text=info['name'], callback_data=f"view_building_{key}_{page}")])
        else: kb.inline_keyboard.append([InlineKeyboardButton(text=f"{info['name']} 🔒", callback_data="locked_building")])
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Туда", callback_data=f"build_page_{page-1}"))
    if page < total_pages - 1: nav_row.append(InlineKeyboardButton(text="Сюда ➡️", callback_data=f"build_page_{page+1}"))
    if nav_row: kb.inline_keyboard.append(nav_row)
    text = (f"🏗️ **МАГАЗИН СООРУЖЕНИЙ** (Стр. {page+1}/{total_pages})\n\nСтрой здания и получай пассивный доход!\nКаждое здание приносит монеты каждую минуту автоматически 🔥\nЗабери монеты вручную, когда накопится минимум!")
    sent = await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    user["buildings_message_id"] = sent.message_id

@dp.callback_query(F.data.startswith("build_page_"))
async def build_page_nav(callback: CallbackQuery):
    page = int(callback.data.replace("build_page_", "", 1))
    await callback.message.delete()
    await buildings_shop(callback.message, page)

@dp.callback_query(F.data.in_(["locked_building"]))
async def locked_building(callback: CallbackQuery):
    await callback.answer("🔒 Сначала построй предыдущее здание!", show_alert=True)

@dp.callback_query(F.data.startswith("view_building_"))
async def view_building(callback: CallbackQuery):
    user_id = callback.from_user.id
    await update_passive_income(user_id)
    user = users[user_id]
    data_parts = callback.data.replace("view_building_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in buildings_info if x["key"] == key), None)
    if not info: return
    level = user["buildings_levels"][key]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if level == 0:
        text = (f"✨ **{info['name']}** ✨\n🕒 Даёт: **+{info['base_income']}** м/мин\n📦 Вместимость: **{info['base_capacity']:,}**\n{info['funny']}\n💸 Цена: **{info['cost']:,}**").replace(",", " ")
        kb.inline_keyboard.append([InlineKeyboardButton(text="🛒 ПОСТРОИТЬ", callback_data=f"buy_building_{key}_{page}")])
    else:
        current_income = info['base_income'] * level
        current_capacity = info['base_capacity'] + info['upgrade_capacity_bonus'] * (level - 1)
        accumulated = user["buildings_accumulated"][key]
        upgrade_cost = info['upgrade_cost_base'] * level
        text = (f"✨ **{info['name']} (Ур. {level})** ✨\n🕒 Доход: **+{current_income}** м/мин\n📦 Накоплено: **{accumulated:,} / {current_capacity:,}**\n{info['funny']}").replace(",", " ")
        if accumulated >= current_income: kb.inline_keyboard.append([InlineKeyboardButton(text=f"💰 Забрать {accumulated:,}", callback_data=f"claim_building_{key}_{page}")])
        if level < 10: kb.inline_keyboard.append([InlineKeyboardButton(text=f"⬆️ Улучшить ({upgrade_cost:,})", callback_data=f"upgrade_building_{key}_{page}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"build_page_{page}")])
    try: await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except: pass
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_building_"))
async def buy_building(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    data_parts = callback.data.replace("buy_building_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in buildings_info if x["key"] == key), None)
    if not info: return
    if user["buildings_levels"][key] > 0: return
    if user["balance"] < info["cost"]:
        await callback.answer("❌ Не хватает монет!", show_alert=True)
        return
    user["balance"] -= info["cost"]
    user["total_spent"] += info["cost"]
    user["buildings_levels"][key] = 1
    user["buildings_accumulated"][key] = 0
    user["buildings_last_update"][key] = datetime.now().timestamp()
    calculate_passive(user)
    await callback.answer(f"🎉 Построено: {info['name']}!", show_alert=True)
    await check_quest_notifications(callback.message, user_id)
    new_data = f"view_building_{key}_{page}"
    new_callback = callback.model_copy(update={'data': new_data})
    await view_building(new_callback)

@dp.callback_query(F.data.startswith("upgrade_building_"))
async def upgrade_building(callback: CallbackQuery):
    user_id = callback.from_user.id
    await update_passive_income(user_id)
    user = users[user_id]
    check_daily_reset(user)
    data_parts = callback.data.replace("upgrade_building_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in buildings_info if x["key"] == key), None)
    if not info: return
    level = user["buildings_levels"][key]
    upgrade_cost = info['upgrade_cost_base'] * level
    if user["balance"] < upgrade_cost:
        await callback.answer("❌ Не хватает монет!", show_alert=True)
        return
    user["balance"] -= upgrade_cost
    user["total_spent"] += upgrade_cost
    user["buildings_levels"][key] += 1
    user["daily_progress"]["upgrades"] += 1
    user["buildings_last_update"][key] = datetime.now().timestamp()
    calculate_passive(user)
    await callback.answer(f"🎉 Улучшено!", show_alert=True)
    await check_daily_notifications(user_id)
    new_data = f"view_building_{key}_{page}"
    new_callback = callback.model_copy(update={'data': new_data})
    await view_building(new_callback)

@dp.callback_query(F.data.startswith("claim_building_"))
async def claim_building(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = users[user_id]
    check_daily_reset(user)
    data_parts = callback.data.replace("claim_building_", "", 1).split("_")
    page = int(data_parts[-1])
    key = "_".join(data_parts[:-1])
    info = next((x for x in buildings_info if x["key"] == key), None)
    if not info: return
    accumulated = user["buildings_accumulated"][key]
    user["balance"] += accumulated
    user["daily_progress"]["claims"] += 1
    user["buildings_accumulated"][key] = 0
    user["buildings_last_update"][key] = datetime.now().timestamp()
    await callback.answer(f"🎉 Забрано {accumulated:,} монет!", show_alert=True)
    await check_daily_notifications(user_id)
    new_data = f"view_building_{key}_{page}"
    new_callback = callback.model_copy(update={'data': new_data})
    await view_building(new_callback)

# ═══════════════════════════════════════════════════════════
# РЕФЕРАЛКА И ТОП-10
# ═══════════════════════════════════════════════════════════
async def referral(message: Message):
    username = (await bot.get_me()).username
    link = f"https://t.me/{username}?start={message.from_user.id}"
    
    # ЗДЕСЬ ДОБАВЛЕН ПРОБЕЛ
    refs_count = f"{users[message.from_user.id]['referrals']:,}".replace(",", " ")
    
    text = (f"👥 **ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА** 👥\n\n{link}\n\nПриглашай друзей и получай бонусы за каждого!\nСейчас у тебя: {refs_count} друзей 🔥")
    await message.answer(text, disable_web_page_preview=True, parse_mode="Markdown")

async def top10_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 По монетам", callback_data="top10_balance")],
        [InlineKeyboardButton(text="💎 По алмазам", callback_data="top10_diamonds")],
        [InlineKeyboardButton(text="👥 По друзьям", callback_data="top10_referrals")]
    ])
    await message.answer("🏆 **ВЫБЕРИ КАТЕГОРИЮ ТОПА**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("top10_"))
async def show_top10_category(callback: CallbackQuery):
    category = callback.data.replace("top10_", "", 1)
    sort_key = None
    title = ""
    if category == "balance":
        sort_key = lambda x: x[1]["balance"]
        title = "💰 ТОП-10 БОГАЧЕЙ"
    elif category == "diamonds":
        sort_key = lambda x: x[1]["diamonds"]
        title = "💎 ТОП-10 ИСКАТЕЛЕЙ"
    elif category == "referrals":
        sort_key = lambda x: x[1]["referrals"]
        title = "👥 ТОП-10 ЛИДЕРОВ"
    top = sorted(users.items(), key=sort_key, reverse=True)[:10]
    if not top:
        await callback.answer("Пусто 😅", show_alert=True)
        return
    text = f"🏆 <b>{title}</b> 🏆\n\n"
    for i, (uid, data) in enumerate(top, 1):
        name_display = data.get('nickname') or data.get('username') or "Неизвестный"
        safe_name = str(name_display).replace("<", "&lt;").replace(">", "&gt;")
        privacy_on = data.get("privacy_enabled", True)
        if privacy_on: user_link = f'<a href="tg://user?id={uid}">{safe_name}</a>'
        else: user_link = safe_name
        if category == "balance": val = f"{data['balance']:,}".replace(",", " ") + " монет"
        elif category == "diamonds": val = f"{data['diamonds']:,}".replace(",", " ") + " 💎"
        elif category == "referrals": val = f"{data['referrals']:,}".replace(",", " ") + " друзей"
        text += f"{i}️⃣ {user_link} — {val}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_top10")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "back_top10")
async def back_top10(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 По монетам", callback_data="top10_balance")],
        [InlineKeyboardButton(text="💎 По алмазам", callback_data="top10_diamonds")],
        [InlineKeyboardButton(text="👥 По друзьям", callback_data="top10_referrals")]
    ])
    await callback.message.edit_text("🏆 **ВЫБЕРИ КАТЕГОРИЮ ТОПА**", reply_markup=kb, parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════
# ... (код до main)

# ═══════════════════════════════════════════════════════════
async def main():
    # 1. Сначала создаем пул/сессию (Подключение к БД)
    await database.create_pool() 
    
    try:
        # 2. Загружаем всех пользователей из БД в оперативную память
        loaded_data = await database.load_all_users()
        users.update(loaded_data)
        
        # 3. Запуск фонового сохранения
        asyncio.create_task(autosave_loop())
        
        # 4. Запускаем бота
        await dp.start_polling(bot)
        
    finally:
        # 5. Обязательно закрываем сессию aiohttp при выходе
        await database.close_session()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Нормальный выход
        pass # <--- Здесь был конфликт. Оставляем только эту строку с отступом.
