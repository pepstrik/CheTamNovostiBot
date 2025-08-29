import asyncio
import nest_asyncio
nest_asyncio.apply()

import logging
import random
import feedparser
import aiosqlite
from html import unescape 
import re
from datetime import datetime, timedelta, time

from telegram import (
    Update, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ChatPermissions, 
    InputTextMessageContent,
    InputMediaPhoto,
    ChatMember
)
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler, 
    filters, 
    ContextTypes,
    JobQueue
)

from config import PODCAST_BOT, ADMINS, PODCAST_chat_id, PODCAST_channel_id

# ——————————————————————————————————————————————————————————
# Логирование
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ——————————————————————————————————————————————————————————
# Настройки 
RSS_FEED = "https://st.zvuk.com/r/c8908758-89a7-431e-90bf-bb0f4c80bc97/rss.xml"
PODCAST_LINK = "https://chetamnovosti.ru"

PLATFORM_LINKS = [
    ("🎧 Apple Podcasts", "https://podcasts.apple.com/us/podcast/че-там-новости/id1523225500"),
    ("🎧 Яндекс Музыка", "https://music.yandex.com/album/11402620"),
    ("🎧 VK Подкасты", "https://vk.com/podcasts-197058964"),
    ("🎧 Саундстрим", "https://soundstream.media/playlist/che-tam-novosti"),    
    ("🎧 Spotify", "https://open.spotify.com/show/0eNkvFFle5c8NFo0GCS7WW"),
    ("🌐 Все платформы", "https://chetamnovosti.ru/#rec612439744")
]

# Время кэширования RSS (например, 1 день = 86400 секунд)
CACHE_EXPIRY = 86400  # 1 день
last_update_time = None
cached_feed = []

# Утилита для очистки HTML‑тегов
def clean_html(raw_html: str) -> str:
    # Убираем все теги <...>
    text = re.sub(r'<[^>]+>', '', raw_html or "")
    # Раскодируем HTML‑сущности, если есть
    return unescape(text).strip()

# Общая кнопка "Назад"
def get_back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back")]])

# ——————————————————————————————————————————————————————————
# SQL модели: users, actions, subscriptions, settings, moderation_logs

async def get_db_connection():
    return await aiosqlite.connect("bot.db")

async def get_user_count():
    try:
        db = await get_db_connection()
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        result = await cursor.fetchone()
        await db.close()
        return result[0]
    except Exception as e:
        logging.error(f"Ошибка при получении количества пользователей: {e}")
        return 0
    
async def init_db():
    try:
        async with aiosqlite.connect("bot.db") as db:
            # Создаем таблицу пользователей
            try:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_seen TEXT
                    )
                """)
            except Exception as e:
                logging.error(f"Ошибка при создании таблицы users: {e}")
            
            # Создаем таблицу действий
            try:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS actions (
                        id       INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id  INTEGER,
                        action   TEXT,
                        time     TEXT
                    )
                """)
            except Exception as e:
                logging.error(f"Ошибка при создании таблицы actions: {e}")

            # Создаем таблицу настроек
            try:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key   TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
            except Exception as e:
                logging.error(f"Ошибка при создании таблицы settings: {e}")

            # Создаем таблицу логов модерации
            try:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS moderation_logs (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id     INTEGER,
                        username    TEXT,
                        reason      TEXT,
                        timestamp   TEXT
                    )
                """)
            except Exception as e:
                logging.error(f"Ошибка при создании таблицы moderation_logs: {e}")

            # Коммитим изменения в базе данных
            try:
                await db.commit()
            except Exception as e:
                logging.error(f"Ошибка при коммите изменений в базе данных: {e}")
    except Exception as e:
        logging.error(f"Ошибка при подключении к базе данных: {e}")

        
# ——————————————————————————————————————————————————————————
# ---------- RSS ФУНКЦИИ ----------
async def update_episode_cache(context):
    global last_update_time, cached_feed

    try:
        feed = feedparser.parse(RSS_FEED)

        # Проверка на ошибки парсинга
        if feed.bozo:
            logging.error(f"Ошибка парсинга RSS: {feed.bozo_exception}")
            return

        # Обрабатываем только те записи, которые содержат title и link
        valid_entries = [(e.title, e.link) for e in feed.entries if hasattr(e, 'title') and hasattr(e, 'link')]
        
        # Кэшируем полученные данные
        cached_feed = valid_entries
        last_update_time = time.time()  # Обновляем время последнего кэширования

        logging.info("Кэш обновлен. Эпизоды загружены.")

    except Exception as e:
        logging.error(f"Ошибка при получении данных из RSS: {e}")

async def fetch_episodes_from_rss():
    try:
        feed = feedparser.parse(RSS_FEED)
        
        # Проверяем на ошибку парсинга
        if feed.bozo:
            logging.error(f"Ошибка парсинга RSS: {feed.bozo_exception}")
            return []
        
        episodes = []
        
        # Проходим по всем записям в RSS
        for entry in feed.entries:
            title = entry.get("title", "")
            url = entry.get("link", "")
            description = entry.get("description", "")  # Если описание отсутствует, будет пустая строка

            # Добавляем в список в формате (title, url, description)
            episodes.append((title, url, description))

        return episodes
    except Exception as e:
        logging.error(f"Ошибка при получении данных из RSS: {e}")
        return []


# ——————————————————————————————————————————————————————————
# Функция отправки сообщений с логированием и обработкой ошибок
async def send_html_with_logging(bot, chat_id, text, reply_markup=None, disable_web_page_preview=False):
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview  
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")
        await bot.send_message(chat_id, "❌ Произошла ошибка при отправке информации. Попробуйте позже.")

# ——————————————————————————————————————————————————————————
# Main menu keyboard

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ℹ️ О подкасте «Чё там новости?»", callback_data="about")],
        [InlineKeyboardButton("❓ FAQ или Часто задаваемые вопросы", callback_data="faq")],
        [InlineKeyboardButton("🎧 Свежие выпуски подкаста", callback_data="latest")],
        [InlineKeyboardButton("🎲 Случайный выпуск", callback_data="random")],
        [InlineKeyboardButton("🔍 Поиск по эпизодам", callback_data="search")],
        [InlineKeyboardButton("📱 Где нас слушать?", callback_data="platforms")],
        [InlineKeyboardButton("💡 Предложить новость или тему", callback_data="suggest")],
        [InlineKeyboardButton("👤 Хочу стать гостем", callback_data="guest")],
        [InlineKeyboardButton("📬 Контакты", callback_data="contact")]
    ])

# ——————————————————————————————————————————————————————————
# ХЭНДЛЕРЫ КОМАНД
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.utcnow().isoformat()  # Используем UTC для унифицированного времени

    # Сохраняем данные пользователя в базе
    await insert_user_data(user.id, user.username, user.first_name, now, update, context)

    # Отправляем главное меню после регистрации пользователя
    await update.message.reply_text(
        "Добро пожаловать! Выберите одно из действий ниже:",
        reply_markup=get_main_menu()  # Главное меню с кнопками
    )
async def insert_user_data(user_id, username, first_name, last_seen, update, context):
    try:
        async with aiosqlite.connect("users.db") as db:
            # Проверяем, существует ли уже пользователь в базе данных
            cursor = await db.execute("""
                SELECT COUNT(*) FROM users WHERE user_id = ?
            """, (user_id,))
            count = await cursor.fetchone()
            
            if count[0] == 0:
                # Если пользователя нет, добавляем его
                await db.execute("""
                    INSERT INTO users (user_id, username, first_name, last_seen)
                    VALUES (?, ?, ?, ?)
                """, (user_id, username, first_name, last_seen))
                await db.commit()
                logging.info(f"Пользователь {user_id} добавлен в базу данных.")
            else:
                logging.info(f"Пользователь {user_id} уже существует в базе данных.")
            
    except Exception as e:
        logging.error(f"Ошибка вставки данных пользователя {user_id}: {e}")


# ---------- ФУНКЦИИ ПОКАЗА ----------
async def show_about(update, context):
    text = (
        "ℹ️ <b>«Чё там новости?»</b> — это подкаст, где ведущие Катя и Таня делятся позитивными и неожиданными новостями,"
        "глядя на происходящее с разных сторон.\nБез негатива, с юмором и теплотой.\n"
        f"Больше — на сайте: {PODCAST_LINK}"
    )
    await send_html_with_logging(context.bot, update.effective_chat.id, text, reply_markup=get_back_button())


async def show_faq(update, context):
    text = (
        "❓ <b>FAQ или Часто задаваемые вопросы:</b>\n\n"
        "📍 <b>Где можно послушать наш подкаст?</b>\n"
        "На всех возможных платформах. Подробнее по кнопке «📱 Где слушать?»\n\n"
        "💡 <b>Можно ли предложить вам тему?</b>\n"
        "Да, конечно! Заполните форму по кнопке «💡 Предложить тему»\n\n"
        "👤 <b>Бывают ли у вас в подкасте гости?</b>\n"
        "Да. Мы любим общаться с интересными людьми.\n\n"
        "📆 <b>Как часто выходят выпуски?</b>\n"
        "Раз в неделю. Обычно по вторникам.\n\n"
        "🎙 <b>Как зовут ведущих?</b>\n"
        "Катя и Таня. А ещё иногда в микрофон посапывает корги по имени Марти.\n"
    )
    await send_html_with_logging(context.bot, update.effective_chat.id, text, reply_markup=get_back_button())


# ---------- ПОСЛЕДНИЕ ЭПИЗОДЫ ----------
async def show_latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        eps = await fetch_episodes_from_rss()
        logging.info(f"Fetched {len(eps)} episodes")
    except Exception as e:
        logging.error(f"Ошибка при получении данных из RSS: {e}")
        target = update.message or update.callback_query.message
        return await target.reply_text(
            "Произошла ошибка при поиске эпизодов. Попробуйте позже.",
            reply_markup=get_back_button()
        )

    if not eps:
        target = update.message or update.callback_query.message
        return await target.reply_text(
            "❌ Нет доступных эпизодов.",
            reply_markup=get_back_button()
        )

    chat_id = update.effective_chat.id if update.message else update.callback_query.message.chat.id
    last3 = eps[-3:][::-1]
    text = "🎙 <b>Три последних эпизода:</b>\n"
    for title, url, _ in last3:  # Мы не используем описание, поэтому заменили на "_"
        text += f"🔹 <b><a href=\"{url}\">{title}</a></b>\n"

    await send_html_with_logging(
        context.bot, chat_id, text,
        reply_markup=get_back_button(),
        disable_web_page_preview=True
    )


# ---------- СЛУЧАЙНЫЙ ЭПИЗОД ----------
async def show_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        eps = await fetch_episodes_from_rss()
        logging.info(f"Fetched {len(eps)} episodes")
    except Exception as e:
        logging.error(f"Ошибка при получении данных из RSS: {e}")
        target = update.message or update.callback_query.message
        return await target.reply_text(
            "Произошла ошибка при поиске эпизодов. Попробуйте позже.",
            reply_markup=get_back_button()
        )

    if not eps:
        target = update.message or update.callback_query.message
        return await target.reply_text(
            "❌ Нет доступных эпизодов.",
            reply_markup=get_back_button()
        )

    try:
        title, url, description = random.choice(eps)
        desc = clean_html(description)
        text = f"🎲 <b>Случайный эпизод:\n\n🔹 <a href=\"{url}\">{title}</a></b>"
        if desc:
            text += f"\n\n<i>{desc}</i>"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Другой случайный эпизод", callback_data="random")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
        ])

        if update.message:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        else:
            await update.callback_query.message.reply_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    
    except Exception as e:
        logging.error(f"Ошибка при обработке случайного эпизода: {e}")
        target = update.message or update.callback_query.message
        await target.reply_text(
            "Произошла ошибка при получении случайного эпизода. Попробуйте снова.",
            reply_markup=get_back_button()
        )

# Хэндлер для кнопки "Поиск"
async def search_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "🔍 Введите слово для поиска:",
        reply_markup=get_back_button()
    )
    context.user_data['in_search'] = True


# Функция для поиска по названиям и описаниям с проверкой наличия описания
# Список слов, по которым не будем искать
EXCLUDED_WORDS = ["хуй", "пизда", "херня", "блядь", "сука", "херня", "хер", "пиздец"]
MAX_RESULTS = 10  # Максимальное количество эпизодов, которое мы показываем

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("🔥 handle_search called with text: %r", update.message.text)
    # Выходим из режима поиска сразу, чтобы не задеть moderate_messages
    context.user_data.pop('in_search', None)
    
    query = update.message.text.strip().lower()

    # Проверяем, есть ли в запросе одно из исключённых слов
    if any(excluded_word in query for excluded_word in EXCLUDED_WORDS):
        return await update.message.reply_text("Ваш запрос содержит запрещённые слова. Попробуйте переформулировать запрос.")

    # Получаем эпизоды
    try:
        eps = await fetch_episodes_from_rss()  # Получаем эпизоды из RSS
        logging.info(f"Fetched {len(eps)} episodes")
    except Exception as e:
        logging.error(f"Ошибка при получении данных из RSS: {e}")
        return await update.message.reply_text("Произошла ошибка при поиске эпизодов. Попробуйте позже.")

    # Поиск по заголовкам и описаниям
    results = []
    for title, url, description in eps:
        if query in title.lower() or query in description.lower():
            results.append((title, url))

    # Если найдено больше результатов, чем MAX_RESULTS
    if len(results) > MAX_RESULTS:
        results = results[:MAX_RESULTS]  # Ограничиваем количество результатов
        await update.message.reply_text("Найдено слишком много эпизодов. Пожалуйста, уточните запрос.")

    # Если не найдено ни одного результата
    if not results:
        await update.message.reply_text(
            "К сожалению, ничего не нашлось. Попробуйте ввести другие слова.",
            reply_markup=get_back_button()
        )
    else:
        text = "🎙 <b>Результаты поиска:</b>\n" + "\n".join(
            f"🔹 <a href=\"{url}\">{title}</a>" for title, url in results
        )
        await update.message.reply_text(
            text, parse_mode="HTML", reply_markup=get_back_button(),
            disable_web_page_preview=True
        )

    return ConversationHandler.END  # выходим из состояния SEARCH

async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Пользователь нажал «⬅️ Назад» в процессе поиска
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.delete()
    return await start(update, context)

# Функция для отображения платформ
async def show_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(name, url=url)] for name, url in PLATFORM_LINKS] + [[InlineKeyboardButton("⬅️ Назад", callback_data="back")]]
        )
        
        # Отправляем информацию с кнопками
        await send_html_with_logging(context.bot, update.effective_chat.id, "📱 Где слушать подкаст?", reply_markup=kb)
    
    except Exception as e:
        logging.error(f"Ошибка при создании платформ для пользователя {update.effective_user.id}: {e}")
        await send_html_with_logging(context.bot, update.effective_chat.id, "❌ Произошла ошибка при получении информации о платформах. Попробуйте позже.")
        
# Функция для отображения формы предложений
async def show_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Форма", url="https://forms.gle/vb5meoNmCBXXhfcs8")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
        ])
        
        # Отправляем информацию с кнопками
        await send_html_with_logging(context.bot, update.effective_chat.id, "💡 Есть идея для нашего выпуска? Заполните форму:", reply_markup=kb)
    
    except Exception as e:
        logging.error(f"Ошибка при отображении формы предложений для пользователя {update.effective_user.id}: {e}")
        await send_html_with_logging(context.bot, update.effective_chat.id, "❌ Произошла ошибка при отображении формы предложений. Попробуйте позже.")

# Функция для отображения анкеты для гостей
async def show_guest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Анкета", url="https://forms.gle/MeXh6x3GemufBGmu9")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
        ])
        
        # Отправляем информацию с кнопками
        await send_html_with_logging(context.bot, update.effective_chat.id, "👤 Хотите стать гостем? Заполните анкету:", reply_markup=kb)
    
    except Exception as e:
        logging.error(f"Ошибка при отображении анкеты для гостей для пользователя {update.effective_user.id}: {e}")
        await send_html_with_logging(context.bot, update.effective_chat.id, "❌ Произошла ошибка при отображении анкеты для гостей. Попробуйте позже.")
        
# Функция для отображения контактной информации
async def show_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Написать через форму на сайте", url="https://chetamnovosti.ru/contact")],
            [InlineKeyboardButton("💬 Написать в ВК", url="https://vk.com/che_tam_novosti")],
            [InlineKeyboardButton("💬 Наш Инстаграм", url="https://instagram.com/che_tam_novosti/")],
            [InlineKeyboardButton("💬 Комментарии в Telegram", url="https://t.me/CheTamNovosti")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
        ])
        
        # Отправляем информацию с кнопками
        await send_html_with_logging(context.bot, update.effective_chat.id, "📬 Связаться с нами можно так:", reply_markup=kb)
    
    except Exception as e:
        logging.error(f"Ошибка при отображении контактов для пользователя {update.effective_user.id}: {e}")
        await send_html_with_logging(context.bot, update.effective_chat.id, "❌ Произошла ошибка при отображении контактов. Попробуйте позже.")
        
        
# ---------- МОДЕРАЦИЯ ----------

BANNED_WORDS = {"http://", "https://", "www.", "купить", "скидка", "spam", "хуй", "бляд", "еба", "пизд", "пидар", "хуй", "херня", "сука", "херня", "хер", "пиздец", "сука", "хуев", "пезд", "пидор"}
PHONE_RE = re.compile(r"(?:\+7|8)[\s\-]?\(?9\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")

async def moderate_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Если мы сейчас в режиме поиска — пропускаем
    if context.user_data.get('in_search'):
        logging.info("🛑 Skipping moderation because we are in search mode")
        return
    
    msg = update.message
    user = msg.from_user
    chat_id = msg.chat.id

    # 1) Проверяем статус участника (строка)
    member = await context.bot.get_chat_member(chat_id, user.id)
    if member.status in ("administrator", "creator"):
        # админы и создатель не модеруются
        return

    text = (msg.text or "").lower()    


    # 2) Проверка на запрещённые слова и номера
    if any(bad in text for bad in BANNED_WORDS) or PHONE_RE.search(text):
        try:
            # Удаляем сообщение
            await msg.delete()

            # Ограничиваем пользователя на 10 минут
            #await context.bot.restrict_chat_member(
            #    chat_id=chat_id,
            #    user_id=user.id,
            #    permissions=ChatPermissions(can_send_messages=False),
            #    until_date=datetime.utcnow() + timedelta(minutes=10)
            #)

            # Отправляем предупреждение
            warning = f"⚠️ @{user.username or user.first_name}, сообщение удалено за нарушение правил."
            await send_html_with_logging(
                context.bot,
                chat_id,
                warning,
                reply_markup=get_back_button()
            )

            logging.info(f"Модерация: удалено сообщение {msg.message_id} от {user.id} в чате {chat_id}")

        except Exception as e:
            logging.error(f"Ошибка при модерации сообщения {msg.message_id} от {user.id}: {e}")

# ---------- ПРИВЕТСТВИЕ В ГРУППЕ ----------

# Функция для приветствия нового члена группы с медиа
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.new_chat_members[0]
    
    # Персонализированное приветствие с fallback для имени пользователя
    first_name = user.first_name or "друг"
    username = user.username if user.username else "без имени пользователя"
    
    greeting_message = f"Привет, {first_name}! Добро пожаловать в нашу дружную тусовку! 🎉"

    # Дружелюбные правила поведения
    rules_message = (
        "\n\n🤝 <b>Правила поведения:</b>\n\n"
        "1. Будьте уважительны к другим участникам.\n"
        "2. Обсуждаем новости и идеи — без агрессии и оскорблений.\n"
        "3. Если есть предложения или вопросы, не стесняйтесь писать! 😊\n\n"
        "Мы здесь, чтобы общаться и делиться хорошими новостями, так что давайте делать это в дружественной атмосфере! 🌟"
    )

    try:
        # Отправка приветственного сообщения с правилами
        await update.message.reply_text(greeting_message + rules_message)

        # Отправка кнопок
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎧 Слушать подкаст", url="https://chetamnovosti.ru")],
            [InlineKeyboardButton("💡 Предложить тему", url="https://forms.gle/vb5meoNmCBXXhfcs8")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
        ])

        # Отправляем приветственное сообщение с кнопками
        await update.message.reply_text(greeting_message + rules_message, reply_markup=kb)

        # Логирование добавления нового пользователя
        logging.info(f"Новый пользователь {user.id} добавлен в группу: {first_name} (@{username})")

    except Exception as e:
        # Логирование ошибки при отправке сообщения
        logging.error(f"Ошибка при отправке приветственного сообщения для пользователя {user.id}: {e}")
        await update.message.reply_text("❌ Приветственное сообщение не удалось отправить. Попробуйте снова позже.")


        # Отправка изображения (например, логотипа подкаста)
        #photo_url = "https://yourpodcastsite.com/logo.png"  # Здесь URL изображения
        #await update.message.reply_photo(photo=photo_url, caption="Мы рады видеть вас!")
        
        # Отправка GIF (например, с приветствием или веселым моментом из подкаста)
        #gif_url = "https://yourpodcastsite.com/welcome_animation.gif"  # Здесь URL GIF
        #await update.message.reply_animation(animation=gif_url, caption="Добро пожаловать!")

            
# ---------- СТАТИСТИКА ----------
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return await send_html(context.bot, update.effective_chat.id, "❌ Нет прав.")
    
    try:
        async with aiosqlite.connect("users.db") as db:
            # Выполняем оба запроса в рамках одной транзакции
            async with db.begin():
                cur = await db.execute("SELECT COUNT(*) FROM users")
                users = (await cur.fetchone())[0]
                cur = await db.execute("SELECT COUNT(*) FROM actions")
                actions = (await cur.fetchone())[0]

        # Отправляем статистику
        await send_html(context.bot, update.effective_chat.id, f"👥 Пользователей: {users}\n⚙️ Действий: {actions}")
    
    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {e}")
        await send_html(context.bot, update.effective_chat.id, "❌ Ошибка при получении статистики. Попробуйте позже.")

async def _search_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.pop('in_search', False):
        # Если мы не в режиме поиска, пропускаем дальше
        return False  # PTB поймёт, что этот handler не был «отработан»
    # Иначе — реально обрабатываем
    return await handle_search(update, context)

# Обработчик кнопки "Назад"
async def handle_back(update, context):
    try:
        # Проверяем, существует ли сообщение и редактируем его
        if update.callback_query.message:
            logging.info("Editing message to return to main menu...")
            # Редактируем сообщение, отправляя главное меню
            await update.callback_query.message.edit_text(
                "Вы вернулись в главное меню.",
                reply_markup=get_main_menu()  # Главное меню
            )
        else:
            logging.error("Message to edit not found.")
    except Exception as e:
        logging.error(f"Ошибка при обработке кнопки 'Назад': {e}")
        await update.callback_query.answer("Ошибка при возвращении в главное меню. Попробуйте снова.")

# Словарь обработчиков кнопок
BUTTON_HANDLERS = {
    "about": show_about,
    "faq": show_faq,
    "latest": show_latest,
    "random": show_random,
    "platforms": show_platforms,
    "suggest": show_suggest,
    "guest": show_guest,
    "contact": show_contact,
    "back": handle_back,  
}

# Обработчик кнопок
async def handle_buttons(update, context):
    query = update.callback_query
    await query.answer()

    # Логируем данные callback
    logging.info(f"Received callback query: {query.data}")
    
    # Обрабатываем кнопку "Назад"
    if query.data == "back":
        try:
            logging.info("Returning to main menu...")
            # Отправляем главное меню при нажатии на кнопку "Назад"
            await update.callback_query.message.edit_text(
                "Вы вернулись в главное меню.",
                reply_markup=get_main_menu()  # Главное меню
            )
        except Exception as e:
            logging.error(f"Ошибка при обработке кнопки 'Назад': {e}")
            await query.answer("Ошибка при возвращении в главное меню. Попробуйте снова.")
    else:
        # Если это не кнопка "Назад", вызываем соответствующий обработчик
        handler = BUTTON_HANDLERS.get(query.data)
        if handler:
            try:
                await handler(update, context)
            except Exception as e:
                logging.error(f"Ошибка при обработке кнопки {query.data}: {e}")
                if update.callback_query.message:
                    await update.callback_query.message.reply_text("Произошла ошибка при обработке вашего запроса. Попробуйте снова.")
        else:
            logging.warning(f"Неизвестная кнопка: {query.data}")
            await start(update, context)  



# ---------- АВТОПОСТИНГ + РАССЫЛКА ----------
# Инициализация записи в settings
async def init_settings():
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT value FROM settings WHERE key='last_posted_url'")
        if not await cur.fetchone():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES ('last_posted_url', '')"
            )
            await db.commit()
            logging.info("Записана начальная настройка в таблицу settings.")

# Проверка нового эпизода
async def check_new_episode():
    eps = await fetch_episodes_from_rss()
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT value FROM settings WHERE key='last_posted_url'")
        row = await cur.fetchone()
        last_url = row[0] if row else None
        new_ep = eps[-1] if eps else None

        if new_ep and new_ep[1] != last_url:
            await db.execute(
                "REPLACE INTO settings (key, value) VALUES ('last_posted_url', ?)",
                (new_ep[1],)
            )
            await db.commit()
            return True
    return False

# Публикация нового эпизода
async def post_new_episode_to_channel_and_subs(context):
    try:
        # 1) Проверяем, есть ли новый эпизод
        if not await check_new_episode():
            logging.info("Новый выпуск не найден.")
            return

        # 2) Если есть — берём последний эпизод и публикуем
        eps = await fetch_episodes_from_rss()
        title, url, description = eps[-1]
        desc = clean_html(description)  # если вы хотите добавить описание
        text = (
            f"🎙 <b>Новый выпуск:</b>\n\n"
            f"🔹 <a href=\"{url}\">{title}</a>\n"
        )
        if desc:
            text += f"\n<i>{desc}</i>"

        # 2a) Публикация в канал
        await send_html_with_logging(context.bot, PODCAST_channel_id, text, disable_web_page_preview=True)

        # Рассылка подписчикам
        async with aiosqlite.connect("bot.db") as db:  # <-- тут тоже bot.db
            cur = await db.execute("SELECT user_id FROM subscriptions")
            subs = await cur.fetchall()
        for (uid,) in subs:
            await send_html_with_logging(
                context.bot, uid, text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back")]])
            )

        logging.info("Новый выпуск был опубликован.")
    except Exception as e:
        logging.error(f"Ошибка при публикации нового эпизода: {e}")


async def forcepost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("⛔ У вас нет доступа к этой команде.")
        return

    episodes = await fetch_episodes_from_rss()
    if not episodes:
        await update.message.reply_text("❗ Эпизоды не найдены.")
        return

    title, url, description = episodes[-1]
    desc = clean_html(description)

    text = (
        f"🎙 <b>Новый выпуск:</b>\n\n"
        f"🔹 <a href=\"{url}\">{title}</a>\n"
    )
    if desc:
        text += f"\n<i>{desc}</i>"

    try:
        logging.info(f"⏩ Публикуем новый выпуск в канал: {title}")  
        await send_html_with_logging(context.bot, PODCAST_channel_id, text, disable_web_page_preview=True)
        
        await update.message.reply_text("✅ Выпуск опубликован вручную.")
        logging.info("✅ Ручная публикация выполнена.")
    except Exception as e:
        logging.error(f"❌ Ошибка при ручной публикации: {e}")
        await update.message.reply_text(f"❌ Ошибка при публикации: {e}")
        
        
            
# ---------- ОБРАБОТКА ОШИБОК ----------
async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Отправляем сообщение об ошибке и добавляем кнопку "Назад"
    await send_html_with_logging(
        context.bot, 
        update.effective_chat.id, 
        "Что-то пошло не так. Попробуйте снова позже.",
        reply_markup=get_back_button()  # Кнопка "Назад"
    )
    # Логируем ошибку
    logging.error(f"Ошибка: {context.error}")
  
    
# ---------- ТОЧКА ВХОДА ----------
async def main():
    try:
        # Инициализируем таблицы и настройки при старте
        await init_db()  # Инициализация базы данных
        await init_settings()  # Инициализация настроек в таблице

        # Проверка нового эпизода перед запуском бота
        eps = await fetch_episodes_from_rss()
        logging.info(f"При старте RSS содержит {len(eps)} эпизодов, последний: {eps[-1][0]}")
    
        # Далее запускаем бота
        app = ApplicationBuilder().token(PODCAST_BOT).build()
        
        # Регистрируем обработчики
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("forcepost", forcepost_command))
        app.add_handler(CallbackQueryHandler(search_button, pattern="^search$"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _search_dispatcher), group=0)
        app.add_handler(CallbackQueryHandler(handle_buttons), group=1)
        app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.NEW_CHAT_MEMBERS, moderate_messages), group=2)

        # 1) запланировать отложенную публикацию _до_ обновления БД
        job_queue = app.job_queue
        # --- СРАЗУ ПУБЛИКОВАТЬ НОВЫЙ ЭПИЗОД ---
        # Планируем на момент старта (when=0), чтобы он выполнился сразу.
        job_queue.run_once(post_new_episode_to_channel_and_subs, when=0)
        # --- ДАЛЬНЕЙШИЕ ЗАДАЧИ ---
        # Обновлять кэш раз в час
        job_queue.run_repeating(update_episode_cache, interval=3600, first=0)
        # Автопостинг по будням
        job_queue.run_daily(
            post_new_episode_to_channel_and_subs,
            time=time(hour=7, minute=0),
            days=(1, 3, 5)
        )

        # Запуск бота
        logging.info("Бот успешно запущен.")
        await app.run_polling()

    except RuntimeError as e:
        if "Cannot close a running event loop" in str(e):
            pass
        logging.error(f"Ошибка при запуске бота: {e}")

# --- Запуск программы ---
if __name__ == "__main__":
    try:
        asyncio.run(main())  # Просто запускаем main
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.")
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
