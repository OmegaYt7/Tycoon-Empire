"""
game_data.py
Статические игровые данные, вынесенные из main.py, чтобы не раздувать
главный файл: константы баланса, улучшения, здания, квесты и т.п.
Ничего исполняемого/логики здесь нет — только конфигурация.
"""

BASE_DIAMOND_CHANCE = 0.001
ITEMS_PER_PAGE = 10
NICKNAME_CHANGE_COST = 1000
NICKNAME_CHANGE_DAYS = 7

# --- ОПЫТ (XP) ---
# Базовый опыт для уровня 1 -> 2
XP_BASE_REQ = 100 
XP_MULTIPLIER = 1.4 # Коэффициент роста (каждый уровень требует на 20% больше)

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

# --- СПИСОК УЛУЧШЕНИЙ ---
upgrades_info = [
    {"key": "wooden_finger", "name": "🪵 Деревянный палец", "bonus": 1, "cost": 0, "funny": "С чего-то надо начинать!"},
    {"key": "stone_finger", "name": "🪨 Каменный палец", "bonus": 2, "cost": 50, "funny": "Тяжелый, зато надежный. Привет из палеолита!"},
    {"key": "normal_finger", "name": "😊 Обычный палец", "bonus": 5, "cost": 250, "funny": "Твой родной палец прошёл апгрейд!"},
    {"key": "copper_finger", "name": "🟠 Медный палец", "bonus": 12, "cost": 500, "funny": "Блестящий, как новая копейка!"},
    {"key": "steel_finger", "name": "🔩 Стальной палец", "bonus": 20, "cost": 2000, "funny": "Холодная сталь для горячих кликов."},
    
    {"key": "iron_finger", "name": "💪 Железный палец", "bonus": 50, "cost": 5000, "funny": "Терминатор отдыхает."},
    {"key": "silver_finger", "name": "🥈 Серебряный палец", "bonus": 100, "cost": 20000, "funny": "Серебро блестит, монстры дрожат."},
    {"key": "gold_finger", "name": "👑 Золотой палец", "bonus": 200, "cost": 20000, "funny": "Цыганский барон одобряет."},
    {"key": "emerald_finger", "name": "🟢 Изумрудный палец", "bonus": 500, "cost": 100000, "funny": "Сделан из цельного камня. Дорого-богато."},
    {"key": "titanium_finger", "name": "🔩 Титановый палец", "bonus": 1000, "cost": 500000, "funny": "Космический металл! Легкий, но мощный."},
    
    {"key": "diamond_finger", "name": "💎 Алмазный палец", "bonus": 5000, "cost": 1000000, "funny": "Самый твёрдый палец в мире."},
    {"key": "plasma_finger", "name": "⚡ Плазменный палец", "bonus": 10000, "cost": 10000000, "funny": "Горячая плазма! Осторожно, не обжгись."},
    {"key": "laser_finger", "name": "🚀 Лазерный палец", "bonus": 50000, "cost": 50000000, "funny": "ПЬЮ-ПЬЮ-ПЬЮ! Быстрее света."},
    {"key": "antimatter_finger", "name": "⚫ Антиматерия", "bonus": 100000, "cost": 100000000, "funny": "Тапает так мощно, что искажает пространство."},
    {"key": "quantum_finger", "name": "🔬 Квантовый палец", "bonus": 200000, "cost": 200000000, "funny": "Тапает в нескольких реальностях одновременно."},
    
    {"key": "magic_finger", "name": "🪄 Магический палец", "bonus": 500000, "cost": 500000000, "funny": "Абракадабра! Монеты из воздуха."},
    {"key": "cyber_finger", "name": "💻 Кибер-палец", "bonus": 1000000, "cost": 1000000000, "funny": "Взлом системы ради прибыли."},
    {"key": "robot_finger", "name": "🤖 Робо-палец", "bonus": 5000000, "cost": 5000000000, "funny": "Идеальная машина для заработка."},
    {"key": "alien_finger", "name": "👽 Инопланетный палец", "bonus": 10000000, "cost": 10000000000, "funny": "Технологии внеземных цивилизаций."},
    {"key": "dragon_finger", "name": "🐉 Драконий палец", "bonus": 20000000, "cost": 20000000000, "funny": "ОГНЕДЫШАЩИЙ ТАП-МОНСТР!"},
    
    {"key": "void_finger", "name": "⚫️ Палец Пустоты", "bonus": 50000000, "cost": 50000000000, "funny": "Тапает так, что даже само существование монет сомневается."},
    {"key": "celestial_finger", "name": "✨ Небесный Палец", "bonus": 100000000, "cost": 100000000000, "funny": "Сверкает, как миллиард звёзд. И тапает также мощно."},
    {"key": "harmonic_resonance", "name": "🎶 Гармоничный Резонанс", "bonus": 200000000, "cost": 500000000000, "funny": "Вибрация богатства, притягивающая монеты."},
    {"key": "crystal_core", "name": "🔮 Кристаллическое Ядро", "bonus": 500000000, "cost": 1000000000000, "funny": "Энергия чистого, сгенерированного богатства."},
    {"key": "poseidon_strike", "name": "🔱 Удар Посейдона", "bonus": 1000000000, "cost": 5000000000000, "funny": "Сотрясает основы рынка. И приносит триллионы."},
    
    {"key": "cosmic_storm", "name": "🌪 Космический Шторм", "bonus": 5000000000, "cost": 10000000000000, "funny": "Вихрь кликов, который сметает все на своем пути."},
    {"key": "paradox_finger", "name": "🌀 Парадоксальный Палец", "bonus": 10000000000, "cost": 20000000000000, "funny": "Он тапает и не тапает одновременно. Прибыль максимальна."},
    {"key": "divine_spark", "name": "🔥 Божественная Искра", "bonus": 20000000000, "cost": 50000000000000, "funny": "Искорка, способная зажечь финансовую вселенную."},
    {"key": "omnipower", "name": "🌟 Всемогущество", "bonus": 50000000000, "cost": 100000000000000, "funny": "Твой таповый потенциал безграничен."},
    {"key": "world_heart", "name": "❤️ Сердце Мира", "bonus": 100000000000, "cost": 200000000000000, "funny": "Каждое биение сердца — это твоя новая монета."}
]

# --- СПИСОК СООРУЖЕНИЙ ---
buildings_info = [
    {"key": "tent", "name": "⛺ Палатка", "base_income": 1, "upgrade_income_bonus": 1, "base_capacity": 100, "cost": 100, "upgrade_cost_base": 50, "upgrade_capacity_bonus": 100, "funny": "Живи на природе, копи мелочь."},
    {"key": "broken_shack", "name": "🛖 Сарай", "base_income": 5, "upgrade_income_bonus": 5, "base_capacity": 500, "cost": 500, "upgrade_cost_base": 100, "upgrade_capacity_bonus": 500, "funny": "Лучше, чем ничего."},
    {"key": "hut", "name": "🏠 Хижина", "base_income": 10, "upgrade_income_bonus": 10, "base_capacity": 1000, "cost": 1000, "upgrade_cost_base": 300, "upgrade_capacity_bonus": 1000, "funny": "Уютно и прибыльно."},
    {"key": "coffee_stand", "name": "☕ Кофейня", "base_income": 15, "upgrade_income_bonus": 15, "base_capacity": 2000, "cost": 5000, "upgrade_cost_base": 1000, "upgrade_capacity_bonus": 2000, "funny": "Кофе с собой! Клиенты в восторге."},
    {"key": "small_farm", "name": "🚜 Ферма", "base_income": 30, "upgrade_income_bonus": 20, "base_capacity": 5000, "cost": 10000, "upgrade_cost_base": 5000, "upgrade_capacity_bonus": 3000, "funny": "Экологически чистые монеты."},
    {"key": "shop", "name": "🛒 Магазин", "base_income": 50, "upgrade_income_bonus": 25, "base_capacity": 10000, "cost": 50000, "upgrade_cost_base": 10000, "upgrade_capacity_bonus": 5000, "funny": "Купи-продай."},
    {"key": "gas_station", "name": "⛽ Заправка", "base_income": 100, "upgrade_income_bonus": 50, "base_capacity": 20000, "cost": 200000, "upgrade_cost_base": 50000, "upgrade_capacity_bonus": 10000, "funny": "Бензин нынче дорогой."},
    {"key": "workshop", "name": "🛠️ Мастерская", "base_income": 250, "upgrade_income_bonus": 100, "base_capacity": 50000, "cost": 500000, "upgrade_cost_base": 100000, "upgrade_capacity_bonus": 20000, "funny": "Работа кипит."},
    {"key": "warehouse", "name": "🏬 Склад", "base_income": 500, "upgrade_income_bonus": 250, "base_capacity": 100000, "cost": 1000000, "upgrade_cost_base": 250000, "upgrade_capacity_bonus": 50000, "funny": "Место для твоих гор золота."},
    {"key": "hotel", "name": "🏨 Отель", "base_income": 1000, "upgrade_income_bonus": 500, "base_capacity": 200000, "cost": 2000000, "upgrade_cost_base": 500000, "upgrade_capacity_bonus": 100000, "funny": "Все включено, особенно прибыль."},
    
    {"key": "office", "name": "🏢 Офис", "base_income": 2000, "upgrade_income_bonus": 900, "base_capacity": 400000, "cost": 5000000, "upgrade_cost_base": 1000000, "upgrade_capacity_bonus": 180000, "funny": "Планктон работает на тебя."},
    {"key": "bank", "name": "🏦 Банк", "base_income": 5000, "upgrade_income_bonus": 2000, "base_capacity": 1000000, "cost": 10000000, "upgrade_cost_base": 2500000, "upgrade_capacity_bonus": 400000, "funny": "Хранилище переполнено."},
    {"key": "casino", "name": "🎰 Казино", "base_income": 10000, "upgrade_income_bonus": 3000, "base_capacity": 2000000, "cost": 20000000, "upgrade_cost_base": 5000000, "upgrade_capacity_bonus": 600000, "funny": "Казино всегда в выигрыше (ты тоже)."},
    {"key": "factory", "name": "🏭 Фабрика", "base_income": 25000, "upgrade_income_bonus": 5000, "base_capacity": 5000000, "cost": 50000000, "upgrade_cost_base": 10000000, "upgrade_capacity_bonus": 1000000, "funny": "Масштабное производство."},
    {"key": "supermarket", "name": "🛍️ Супермаркет", "base_income": 50000, "upgrade_income_bonus": 10000, "base_capacity": 10000000, "cost": 100000000, "upgrade_cost_base": 25000000, "upgrade_capacity_bonus": 2000000, "funny": "Очереди на кассах."},
    {"key": "corporation", "name": "🌆 Корпорация", "base_income": 75000, "upgrade_income_bonus": 25000, "base_capacity": 15000000, "cost": 200000000, "upgrade_cost_base": 50000000, "upgrade_capacity_bonus": 5000000, "funny": "Мировое господство."},
    {"key": "spaceport", "name": "🚀 Космодром", "base_income": 100000, "upgrade_income_bonus": 40000, "base_capacity": 20000000, "cost": 400000000, "upgrade_cost_base": 100000000, "upgrade_capacity_bonus": 8000000, "funny": "Туристы на Марс, деньги тебе."},
    {"key": "tech_hub", "name": "💻 Тех-Хаб", "base_income": 250000, "upgrade_income_bonus": 85000, "base_capacity": 50000000, "cost": 700000000, "upgrade_cost_base": 200000000, "upgrade_capacity_bonus": 17000000, "funny": "Кремниевая долина нервно курит."},
    {"key": "empire", "name": "🏰 Империя", "base_income": 500000, "upgrade_income_bonus": 250000, "base_capacity": 100000000, "cost": 1500000000, "upgrade_cost_base": 500000000, "upgrade_capacity_bonus": 50000000, "funny": "Ты — король мира."},
    {"key": "dyson_sphere", "name": "☀️ Сфера Дайсона", "base_income": 1000000, "upgrade_income_bonus": 400000, "base_capacity": 200000000, "cost": 3000000000, "upgrade_cost_base": 1000000000, "upgrade_capacity_bonus": 80000000, "funny": "Энергия целой звезды в кармане."},
    
    {"key": "electronic_judge", "name": "⚖️ Электронный Судья", "base_income": 5000000, "upgrade_income_bonus": 1000000, "base_capacity": 1000000000, "cost": 5000000000, "upgrade_cost_base": 2000000000, "upgrade_capacity_bonus": 200000000, "funny": "Искусственный интеллект, который решает, кто прав, а кто богат."},
    {"key": "data_farm", "name": "💾 Ферма данных", "base_income": 25000000, "upgrade_income_bonus": 5000000, "base_capacity": 5000000000, "cost": 20000000000, "upgrade_cost_base": 5000000000, "upgrade_capacity_bonus": 1000000000, "funny": "Самый дорогой товар в мире — информация, и она вся твоя."},
    {"key": "stock_exchange", "name": "📈 Фондовая Биржа", "base_income": 50000000, "upgrade_income_bonus": 23000000, "base_capacity": 10000000000, "cost": 100000000000, "upgrade_cost_base": 25000000000, "upgrade_capacity_bonus": 4600000000, "funny": "Когда ты чихаешь, мировой рынок падает."},
    {"key": "ocean_tunnel", "name": "🚇 Тоннель под Океаном", "base_income": 100000000, "upgrade_income_bonus": 35000000, "base_capacity": 20000000000, "cost": 200000000000, "upgrade_cost_base": 50000000000, "upgrade_capacity_bonus": 7000000000, "funny": "Зачем летать, если можно проехать? Самый длинный платный проезд."},
    {"key": "cloud_storage", "name": "☁️ Облачное Хранилище", "base_income": 300000000, "upgrade_income_bonus": 80000000, "base_capacity": 60000000000, "cost": 500000000000, "upgrade_cost_base": 100000000000, "upgrade_capacity_bonus": 16000000000, "funny": "Хранишь все мемы планеты и зарабатываешь на этом."},
    {"key": "immortal_storage", "name": "🔒 Хранилище Вечности", "base_income": 500000000, "upgrade_income_bonus": 175000000, "base_capacity": 100000000000, "cost": 1500000000000, "upgrade_cost_base": 500000000000, "upgrade_capacity_bonus": 35000000000, "funny": "Ты продаешь места для хранения сознания. Очень дорого."},
    {"key": "tax_committee", "name": "💸 Комитет по Налогам", "base_income": 750000000, "upgrade_income_bonus": 250000000, "base_capacity": 150000000000, "cost": 3000000000000, "upgrade_cost_base": 1000000000000, "upgrade_capacity_bonus": 50000000000, "funny": "Ты платишь налоги сам себе, а потом сам себе их возвращаешь."},
    {"key": "global_water_fund", "name": "💧 Мировой Фонд Воды", "base_income": 1000000000, "upgrade_income_bonus": 350000000, "base_capacity": 200000000000, "cost": 5000000000000, "upgrade_cost_base": 2000000000000, "upgrade_capacity_bonus": 70000000000, "funny": "Самый ценный ресурс планеты принадлежит тебе."},
    {"key": "time_factory", "name": "⏳ Фабрика Времени", "base_income": 5000000000, "upgrade_income_bonus": 1000000000, "base_capacity": 1000000000000, "cost": 8000000000000, "upgrade_cost_base": 4000000000000, "upgrade_capacity_bonus": 200000000000, "funny": "Производит дополнительные секунды для самых выгодных сделок."},
    {"key": "planet_editor", "name": "🌍 Главный Редактор Планеты", "base_income": 10000000000, "upgrade_income_bonus": 3500000000, "base_capacity": 2000000000000, "cost": 25000000000000, "upgrade_cost_base": 7000000000000, "upgrade_capacity_bonus": 700000000000, "funny": "Ты можешь стереть с карты города, которые не нравятся, но решил просто зарабатывать."}
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
    {"key": "build_5", "type": "buildings_count", "target": 5, "name": "🏗️ Начинающий прораб", "desc": "Построй любые 5 сооружений", "rew_coins": 5000, "rew_tap": 0, "rew_chance": 0},
    {"key": "build_10", "type": "buildings_count", "target": 10, "name": "🏗️ Главный архитектор", "desc": "Построй любые 10 сооружений", "rew_coins": 500000, "rew_tap": 0, "rew_chance": 0},
    {"key": "build_15", "type": "buildings_count", "target": 15, "name": "🏗️ Городской застройщик", "desc": "Построй любые 15 сооружений", "rew_coins": 30000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "build_20", "type": "buildings_count", "target": 20, "name": "🏗️ Бетонный магнат", "desc": "Построй любые 20 сооружений", "rew_coins": 1000000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "build_30", "type": "buildings_count", "target": 30, "name": "🏗️ Владелец Вселенной", "desc": "Построй любые 30 сооружений", "rew_coins": 5000000000000, "rew_tap": 0, "rew_chance": 0},
    
    # ТИП 3: КУПИТЬ УЛУЧШЕНИЯ
    {"key": "upg_5", "type": "upgrades_count", "target": 5, "name": "🖐️ Коллекционер рук", "desc": "Купи 5 разных пальцев", "rew_coins": 1000, "rew_tap": 10, "rew_chance": 0},
    {"key": "upg_10", "type": "upgrades_count", "target": 10, "name": "🖐️ Техно-эволюция", "desc": "Купи 10 разных пальцев", "rew_coins": 100000, "rew_tap": 500, "rew_chance": 0},
    {"key": "upg_15", "type": "upgrades_count", "target": 15, "name": "🖐️ Бог кликов", "desc": "Купи 15 разных пальцев", "rew_coins": 50000000, "rew_tap": 50000, "rew_chance": 0},
    {"key": "upg_20", "type": "upgrades_count", "target": 20, "name": "🖐️ Легендарный тап", "desc": "Купи 20 разных пальцев", "rew_coins": 5000000000, "rew_tap": 1000000, "rew_chance": 0},
    {"key": "upg_30", "type": "upgrades_count", "target": 30, "name": "🖐️ Абсолютная власть", "desc": "Купи 30 разных пальцев", "rew_coins": 50000000000000, "rew_tap": 10000000000, "rew_chance": 0},
    
    # ТИП 4: КЛИКИ
    {"key": "click_1k", "type": "clicks", "target": 1000, "name": "👆 Быстрый палец", "desc": "Сделай 1 000 тапов", "rew_coins": 100000, "rew_tap": 100, "rew_chance": 0},
    {"key": "click_5k", "type": "clicks", "target": 5000, "name": "👆 Клик-машина", "desc": "Сделай 5 000 тапов", "rew_coins": 500000, "rew_tap": 500, "rew_chance": 0},
    {"key": "click_20k", "type": "clicks", "target": 20000, "name": "👆 Скорость света", "desc": "Сделай 20 000 тапов", "rew_coins": 3000000, "rew_tap": 1000, "rew_chance": 0},
    {"key": "click_50k", "type": "clicks", "target": 50000, "name": "👆 Разрушитель экранов", "desc": "Сделай 50 000 тапов", "rew_coins": 10000000, "rew_tap": 50000, "rew_chance": 0},
    {"key": "click_100k", "type": "clicks", "target": 100000, "name": "👆 Титан кликов", "desc": "Сделай 100 000 тапов", "rew_coins": 100000000, "rew_tap": 100000, "rew_chance": 0},
    
    # ТИП 5: ДОХОД
    {"key": "inc_100", "type": "income", "target": 1000, "name": "💤 Маленький ручеек", "desc": "Достигни дохода 1 000 монет/мин", "rew_coins": 100000, "rew_tap": 0, "rew_chance": 0},
    {"key": "inc_1k", "type": "income", "target": 5000, "name": "💤 Денежная река", "desc": "Достигни дохода 5 000 монет/мин", "rew_coins": 1000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "inc_10k", "type": "income", "target": 10000, "name": "💤 Нефтяная вышка", "desc": "Достигни дохода 10 000 монет/мин", "rew_coins": 10000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "inc_50k", "type": "income", "target": 50000, "name": "💤 Банковский магнат", "desc": "Достигни дохода 50 000 монет/мин", "rew_coins": 100000000, "rew_tap": 0, "rew_chance": 0},
    {"key": "inc_100k", "type": "income", "target": 100000, "name": "💤 Хозяин мира", "desc": "Достигни дохода 100 000 монет/мин", "rew_coins": 1000000000, "rew_tap": 0, "rew_chance": 0},
    
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
