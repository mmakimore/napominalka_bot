import logging
import datetime
from typing import Optional
from dateutil.relativedelta import relativedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
PUSH_INTERVAL_DAYS = 4

# Глобальные переменные
next_push_date: Optional[datetime.date] = None
scheduler: Optional[AsyncIOScheduler] = None

class PushScheduler:
    """Класс для управления расписанием пушей"""
    
    @staticmethod
    def calculate_next_push_date(start_date: datetime.date) -> datetime.date:
        """Рассчитать следующую дату пуша (каждые 4 дня)"""
        today = datetime.date.today()
        
        # Если начальная дата в будущем
        if start_date > today:
            return start_date
        
        # Вычисляем количество дней с последнего пуша
        days_passed = (today - start_date).days
        periods_passed = days_passed // PUSH_INTERVAL_DAYS
        next_date = start_date + datetime.timedelta(days=(periods_passed + 1) * PUSH_INTERVAL_DAYS)
        
        return next_date
    
    @staticmethod
    def is_push_day(date: datetime.date) -> bool:
        """Проверить, является ли дата днем пуша"""
        if not next_push_date:
            return False
        return date == next_push_date
    
    @staticmethod
    def days_until_next_push() -> int:
        """Количество дней до следующего пуша"""
        if not next_push_date:
            return -1
        return (next_push_date - datetime.date.today()).days

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start - показывает меню кнопок"""
    keyboard = [
        [
            InlineKeyboardButton("⚡ Подготовка пуша", callback_data="prepare_push"),
            InlineKeyboardButton("🚀 Отправка пуша", callback_data="send_push"),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="stats"),
            InlineKeyboardButton("📅 Следующий пуш", callback_data="next_push"),
        ],
        [
            InlineKeyboardButton("🛠 Установить новую дату", callback_data="set_date"),
        ],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text="Привет! Я бот-напоминалка о пушах. Выберите действие:",
        reply_markup=reply_markup,
    )
    logger.info(f"Bot started in chat {chat_id}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    action = query.data
    
    if action == "prepare_push":
        await send_prepare_reminder(chat_id, context, manual=True)
    elif action == "send_push":
        await send_push_day_reminder(chat_id, context, manual=True)
    elif action == "stats":
        await send_stats_reminder(chat_id, context, manual=True)
    elif action == "next_push":
        await show_next_push_date(chat_id, context)
    elif action == "set_date":
        await request_new_date(chat_id, context)
    
    logger.info(f"Button {action} pressed in chat {chat_id}")

async def send_prepare_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE, manual: bool = False) -> None:
    """Отправить напоминание о подготовке пуша"""
    message = "⚡ Завтра пуш! Не забудь подготовить сообщения 📝"
    if manual:
        message = "Ручное напоминание: " + message
    
    await context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"Prepare reminder sent to chat {chat_id}")

async def send_push_day_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE, manual: bool = False) -> None:
    """Отправить напоминание в день пуша"""
    message = "🚀 Пора отправлять пуш! 🔔"
    if manual:
        message = "Ручное напоминание: " + message
    
    await context.bot.send_message(chat_id=chat_id, text=message)
    
    # Автоматически рассчитываем следующую дату пуша
    if not manual and next_push_date:
        global next_push_date
        next_push_date = PushScheduler.calculate_next_push_date(next_push_date)
        logger.info(f"Next push date calculated: {next_push_date}")
    
    logger.info(f"Push day reminder sent to chat {chat_id}")

async def send_stats_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE, manual: bool = False) -> None:
    """Отправить напоминание о статистике"""
    message = "📈 Проверь статистику рассылки по неподтвержденным почтам!"
    if manual:
        message = "Ручное напоминание: " + message
    
    await context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"Stats reminder sent to chat {chat_id}")

async def send_weekly_push_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправить еженедельное напоминание"""
    message = "💰 Пуш по тем, кто начал зарабатывать. Проверь рассылку 📊"
    await context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"Weekly push reminder sent to chat {chat_id}")

async def show_next_push_date(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать дату следующего пуша"""
    if not next_push_date:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Дата следующего пуша не установлена. Используйте кнопку 'Установить новую дату'."
        )
        return
    
    days_left = PushScheduler.days_until_next_push()
    if days_left == 0:
        message = f"🎯 Следующий пуш сегодня! ({next_push_date})"
    elif days_left == 1:
        message = f"📅 Следующий пуш завтра! ({next_push_date})"
    else:
        message = f"📅 Следующий пуш через {days_left} дней ({next_push_date})"
    
    await context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"Next push date shown in chat {chat_id}")

async def request_new_date(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запросить новую дату у пользователя"""
    await context.bot.send_message(
        chat_id=chat_id,
        text="Введите новую дату начала пушей в формате ГГГГ-ММ-ДД (например, 2024-01-19):"
    )
    # Устанавливаем состояние ожидания даты
    context.user_data['waiting_for_date'] = True
    logger.info(f"Date request sent to chat {chat_id}")

async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ввода даты"""
    if not context.user_data.get('waiting_for_date'):
        return
    
    chat_id = update.effective_chat.id
    date_text = update.message.text.strip()
    
    try:
        # Парсим дату
        new_date = datetime.datetime.strptime(date_text, "%Y-%m-%d").date()
        
        # Устанавливаем новую дату
        global next_push_date
        next_push_date = new_date
        
        # Перепланируем задания
        await reschedule_jobs(context.application)
        
        await update.message.reply_text(
            f"✅ Новая дата пуша установлена: {new_date}\n"
            f"Следующий пуш: {PushScheduler.calculate_next_push_date(new_date)}"
        )
        logger.info(f"New push date set: {new_date} in chat {chat_id}")
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД (например, 2024-01-19)"
        )
        logger.warning(f"Invalid date format received: {date_text} in chat {chat_id}")
    
    # Сбрасываем состояние
    context.user_data['waiting_for_date'] = False

async def schedule_daily_tasks(application: Application) -> None:
    """Запланировать ежедневные задачи"""
    global scheduler
    
    if not scheduler:
        scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    
    # Напоминание за день до пуша (в 11:00, 19:00, 23:30)
    for hour, minute in [(11, 0), (19, 0), (23, 30)]:
        scheduler.add_job(
            check_and_send_prepare_reminder,
            CronTrigger(hour=hour, minute=minute, timezone=MOSCOW_TZ),
            args=[application],
            id=f"prepare_reminder_{hour}_{minute}"
        )
    
    # Напоминание в день пуша (в 10:00)
    scheduler.add_job(
        check_and_send_push_day_reminder,
        CronTrigger(hour=10, minute=0, timezone=MOSCOW_TZ),
        args=[application],
        id="push_day_reminder"
    )
    
    # Ежедневная проверка статистики (в 12:00)
    scheduler.add_job(
        send_daily_stats,
        CronTrigger(hour=12, minute=0, timezone=MOSCOW_TZ),
        args=[application],
        id="daily_stats"
    )
    
    # Еженедельные пуши (вторник в 12:00)
    scheduler.add_job(
        send_weekly_push,
        CronTrigger(day_of_week="tue", hour=12, minute=0, timezone=MOSCOW_TZ),
        args=[application],
        id="weekly_push"
    )
    
    scheduler.start()
    logger.info("Daily tasks scheduled")

async def reschedule_jobs(application: Application) -> None:
    """Перепланировать задания при изменении даты"""
    global scheduler
    
    if scheduler:
        scheduler.remove_all_jobs()
        await schedule_daily_tasks(application)
        logger.info("Jobs rescheduled")

async def check_and_send_prepare_reminder(application: Application) -> None:
    """Проверить и отправить напоминание за день до пуша"""
    if not next_push_date:
        return
    
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    
    if PushScheduler.is_push_day(tomorrow):
        # Отправляем во все активные чаты
        # В реальном приложении нужно хранить список активных чатов
        chat_id = get_active_chat_id()  # Нужно реализовать получение chat_id
        if chat_id:
            await send_prepare_reminder(chat_id, application.bot)
            logger.info(f"Auto prepare reminder sent to chat {chat_id}")

async def check_and_send_push_day_reminder(application: Application) -> None:
    """Проверить и отправить напоминание в день пуша"""
    if not next_push_date:
        return
    
    today = datetime.date.today()
    
    if PushScheduler.is_push_day(today):
        chat_id = get_active_chat_id()
        if chat_id:
            await send_push_day_reminder(chat_id, application.bot)
            logger.info(f"Auto push day reminder sent to chat {chat_id}")

async def send_daily_stats(application: Application) -> None:
    """Отправить ежедневное напоминание о статистике"""
    chat_id = get_active_chat_id()
    if chat_id:
        await send_stats_reminder(chat_id, application.bot)
        logger.info(f"Auto stats reminder sent to chat {chat_id}")

async def send_weekly_push(application: Application) -> None:
    """Отправить еженедельное напоминание"""
    chat_id = get_active_chat_id()
    if chat_id:
        await send_weekly_push_reminder(chat_id, application.bot)
        logger.info(f"Auto weekly push reminder sent to chat {chat_id}")

def get_active_chat_id() -> Optional[int]:
    """
    Получить ID активного чата.
    В реальном приложении нужно хранить список активных чатов в БД.
    Здесь возвращаем последний активный чат или None.
    """
    # Заглушка - нужно реализовать логику хранения chat_id
    # Например, можно использовать базу данных или файл
    return None

def main() -> None:
    """Основная функция запуска бота"""
    # Токен бота (нужно получить у @BotFather)
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_input))
    
    # Запускаем планировщик задач
    application.job_queue.run_once(
        lambda context: schedule_daily_tasks(application),
        when=0
    )
    
    # Инициализируем начальную дату (можно загрузить из файла)
    global next_push_date
    try:
        # Попытка загрузить дату из файла
        with open("next_push_date.txt", "r") as f:
            date_str = f.read().strip()
            next_push_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            logger.info(f"Loaded next push date from file: {next_push_date}")
    except (FileNotFoundError, ValueError):
        # Устанавливаем дату по умолчанию
        next_push_date = datetime.date(2024, 1, 19)
        logger.info(f"Using default next push date: {next_push_date}")
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPESES)

if __name__ == "__main__":
    main()
