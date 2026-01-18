import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

# --- Логирование ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Настройки бота ---
TOKEN = "7923754810:AAEdfhrn8n7k-6WOSjV9OGEigP9uRYSrjk0"
bot = Bot(TOKEN)
CHAT_ID = None  # Будет определён при первом /start

# --- Дата следующего пуша ---
next_push_date = datetime(2026, 1, 19)

# --- Планировщик ---
scheduler = BackgroundScheduler()

# --- Функции напоминаний ---
def remind_prepare_push():
    if CHAT_ID:
        bot.send_message(chat_id=CHAT_ID, text="⚡ Завтра пуш! Не забудь подготовить сообщения 📝")

def remind_send_push():
    if CHAT_ID:
        bot.send_message(chat_id=CHAT_ID, text="🚀 Пора отправлять пуш! 🔔")

def remind_weekly_push():
    if CHAT_ID:
        bot.send_message(chat_id=CHAT_ID, text="💰 Еженедельный пуш по тем, кто начал зарабатывать 📊")

def remind_check_stats():
    if CHAT_ID:
        bot.send_message(chat_id=CHAT_ID, text="📈 Проверь статистику рассылки по неподтвержденным почтам!")

# --- Планирование пушей ---
def schedule_next_push():
    global next_push_date
    scheduler.remove_all_jobs()

    # Подготовка за день
    prep_times = [
        (next_push_date - timedelta(days=1)).replace(hour=11, minute=0),
        (next_push_date - timedelta(days=1)).replace(hour=19, minute=0),
        (next_push_date - timedelta(days=1)).replace(hour=23, minute=30)
    ]
    for t in prep_times:
        scheduler.add_job(remind_prepare_push, 'date', run_date=t)

    # В день пуша
    send_time = next_push_date.replace(hour=10, minute=0)
    scheduler.add_job(remind_send_push, 'date', run_date=send_time)

    # Ежедневная проверка статистики
    scheduler.add_job(remind_check_stats, 'cron', hour=12, minute=0)

    # Еженедельный пуш (вторник подготовка к среде)
    scheduler.add_job(remind_weekly_push, 'cron', day_of_week='tue', hour=12, minute=0)

    logging.info(f"📅 Следующий пуш: {next_push_date.strftime('%d.%m.%Y')}")

# --- Кнопки ---
def main_menu():
    keyboard = [
        [InlineKeyboardButton("⚡ Подготовка пуша", callback_data='prepare')],
        [InlineKeyboardButton("🚀 Отправка пуша", callback_data='send')],
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("📅 Следующий пуш", callback_data='next')],
        [InlineKeyboardButton("🛠 Установить новую дату", callback_data='setpush')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Обработчики ---
def start(update: Update, context: CallbackContext):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    update.message.reply_text("Привет! Я твой помощник по пушам 😊", reply_markup=main_menu())

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    global next_push_date

    if query.data == 'prepare':
        remind_prepare_push()
        query.edit_message_text(text="✅ Напоминание о подготовке пуша отправлено!", reply_markup=main_menu())
    elif query.data == 'send':
        remind_send_push()
        query.edit_message_text(text="✅ Напоминание об отправке пуша отправлено!", reply_markup=main_menu())
    elif query.data == 'stats':
        remind_check_stats()
        query.edit_message_text(text="✅ Напоминание о статистике отправлено!", reply_markup=main_menu())
    elif query.data == 'next':
        query.edit_message_text(text=f"📅 Следующий пуш: {next_push_date.strftime('%d.%m.%Y')}", reply_markup=main_menu())
    elif query.data == 'setpush':
        query.edit_message_text(text="🛠 Напиши новую дату пуша в формате ГГГГ-ММ-ДД", reply_markup=None)
        context.user_data['awaiting_date'] = True

def set_push_date(update: Update, context: CallbackContext):
    if context.user_data.get('awaiting_date'):
        try:
            global next_push_date
            next_push_date = datetime.strptime(update.message.text.strip(), "%Y-%m-%d")
            schedule_next_push()
            update.message.reply_text(f"✅ Новая дата пуша установлена: {next_push_date.strftime('%d.%m.%Y')}", reply_markup=main_menu())
            context.user_data['awaiting_date'] = False
        except:
            update.message.reply_text("❌ Неверный формат! Используй: ГГГГ-ММ-ДД")

# --- Запуск бота ---
updater = Updater(TOKEN, use_context=True)
updater.dispatcher.add_handler(CommandHandler("start", start))
updater.dispatcher.add_handler(CallbackQueryHandler(button))
updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, set_push_date))

# Планируем первый пуш
schedule_next_push()
scheduler.start()
logging.info("Бот с кнопками запущен! 🚀")

updater.start_polling()
updater.idle()
