import os
import logging
import datetime
import json
from typing import Optional, Dict, List
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

# Конфигурация из переменных окружения
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

MOSCOW_TZ = pytz.timezone('Europe/Moscow')
PUSH_INTERVAL_DAYS = 4
DATA_FILE = 'bot_data.json'

# Глобальные переменные
class BotData:
    def __init__(self):
        self.next_push_date: Optional[datetime.date] = None
        self.active_chats: List[int] = []
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.load_data()
    
    def load_data(self):
        """Загрузить данные из файла"""
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if data.get('next_push_date'):
                    self.next_push_date = datetime.datetime.strptime(
                        data['next_push_date'], '%Y-%m-%d'
                    ).date()
                self.active_chats = data.get('active_chats', [])
                logger.info(f"Данные загружены: {data}")
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("Файл данных не найден, устанавливаем дату на завтра")
            # Устанавливаем первый пуш на завтра
            self.next_push_date = datetime.date.today() + datetime.timedelta(days=1)
            self.save_data()
    
    def save_data(self):
        """Сохранить данные в файл"""
        data = {
            'next_push_date': self.next_push_date.strftime('%Y-%m-%d') if self.next_push_date else None,
            'active_chats': self.active_chats,
            'last_updated': datetime.datetime.now().isoformat()
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Данные сохранены: {data}")
    
    def add_chat(self, chat_id: int):
        """Добавить чат в список активных"""
        if chat_id not in self.active_chats:
            self.active_chats.append(chat_id)
            self.save_data()
            logger.info(f"Добавлен чат: {chat_id}")

bot_data = BotData()

class PushScheduler:
    """Класс для управления расписанием пушей"""
    
    @staticmethod
    def calculate_next_push_date(start_date: datetime.date) -> datetime.date:
        """Рассчитать следующую дату пуша (каждые 4 дня), НО ТОЛЬКО В БУДУЩЕМ"""
        today = datetime.date.today()
        
        # Если дата в прошлом, вычисляем следующую в будущем
        if start_date <= today:
            # Находим разницу в днях
            days_passed = (today - start_date).days
            # Находим, сколько полных циклов прошло
            cycles_passed = days_passed // PUSH_INTERVAL_DAYS
            # Следующая дата = начальная дата + (циклы + 1) * интервал
            next_date = start_date + datetime.timedelta(days=(cycles_passed + 1) * PUSH_INTERVAL_DAYS)
            
            # Проверяем, что дата в будущем
            if next_date <= today:
                next_date += datetime.timedelta(days=PUSH_INTERVAL_DAYS)
        else:
            # Если дата в будущем, просто возвращаем ее
            next_date = start_date
        
        return next_date
    
    @staticmethod
    def calculate_next_push_from_today(start_date: datetime.date) -> datetime.date:
        """Рассчитать следующую дату пуша, начиная с СЕГОДНЯ"""
        today = datetime.date.today()
        
        # Если стартовая дата в будущем - возвращаем ее
        if start_date > today:
            return start_date
        
        # Находим, когда будет следующий пуш от стартовой даты
        days_since_start = (today - start_date).days
        # Сколько полных циклов прошло
        cycles = days_since_start // PUSH_INTERVAL_DAYS
        # Следующий цикл
        next_date = start_date + datetime.timedelta(days=(cycles + 1) * PUSH_INTERVAL_DAYS)
        
        # Убеждаемся, что дата в будущем
        while next_date <= today:
            next_date += datetime.timedelta(days=PUSH_INTERVAL_DAYS)
        
        return next_date
    
    @staticmethod
    def is_push_today() -> bool:
        """Проверить, является ли сегодня днем пуша"""
        if not bot_data.next_push_date:
            return False
        return bot_data.next_push_date == datetime.date.today()
    
    @staticmethod
    def is_push_tomorrow() -> bool:
        """Проверить, является ли завтра днем пуша"""
        if not bot_data.next_push_date:
            return False
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        return bot_data.next_push_date == tomorrow
    
    @staticmethod
    def days_until_next_push() -> int:
        """Количество дней до следующего пуша"""
        if not bot_data.next_push_date:
            return -1
        return (bot_data.next_push_date - datetime.date.today()).days

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    chat_id = update.effective_chat.id
    bot_data.add_chat(chat_id)
    
    # Если дата не установлена или в прошлом - устанавливаем на завтра
    if not bot_data.next_push_date or bot_data.next_push_date <= datetime.date.today():
        bot_data.next_push_date = datetime.date.today() + datetime.timedelta(days=1)
        bot_data.save_data()
    
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
            InlineKeyboardButton("🛠 Установить дату", callback_data="set_date"),
        ],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="🤖 Бот-напоминалка о пушах\n\nВыберите действие:",
        reply_markup=reply_markup,
    )
    logger.info(f"Бот запущен в чате {chat_id}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    action = query.data
    
    if action == "prepare_push":
        # Проверяем, действительно ли завтра пуш
        if PushScheduler.is_push_tomorrow():
            await send_prepare_reminder(chat_id, context, manual=True)
        else:
            next_push = bot_data.next_push_date if bot_data.next_push_date else "не установлена"
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Завтра НЕ пуш!\nСледующий пуш: {next_push}"
            )
    
    elif action == "send_push":
        # Проверяем, действительно ли сегодня пуш
        if PushScheduler.is_push_today():
            await send_push_day_reminder(chat_id, context, manual=True)
        else:
            next_push = bot_data.next_push_date if bot_data.next_push_date else "не установлена"
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Сегодня НЕ пуш!\nСледующий пуш: {next_push}"
            )
    
    elif action == "stats":
        await send_stats_reminder(chat_id, context, manual=True)
    
    elif action == "next_push":
        await show_next_push_date(chat_id, context)
    
    elif action == "set_date":
        await request_new_date(chat_id, context)
    
    logger.info(f"Кнопка {action} нажата в чате {chat_id}")

async def send_prepare_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE, manual: bool = False) -> None:
    """Отправить напоминание о подготовке пуша"""
    message = "⚡ Завтра пуш! Не забудь подготовить сообщения 📝"
    if manual:
        message = "🔔 Ручное напоминание:\n" + message
    
    await context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"Напоминание о подготовке отправлено в чат {chat_id}")

async def send_push_day_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE, manual: bool = False) -> None:
    """Отправить напоминание в день пуша"""
    message = "🚀 Пора отправлять пуш! 🔔"
    if manual:
        message = "🔔 Ручное напоминание:\n" + message
    
    await context.bot.send_message(chat_id=chat_id, text=message)
    
    # После пуша рассчитываем следующую дату
    if not manual:
        if bot_data.next_push_date:
            bot_data.next_push_date = PushScheduler.calculate_next_push_from_today(bot_data.next_push_date)
            bot_data.save_data()
            logger.info(f"Новая дата пуша после отправки: {bot_data.next_push_date}")
    
    logger.info(f"Напоминание о пуше отправлено в чат {chat_id}")

async def send_stats_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE, manual: bool = False) -> None:
    """Отправить напоминание о статистике"""
    message = "📈 Проверь статистику рассылки по неподтвержденным почтам!"
    if manual:
        message = "🔔 Ручное напоминание:\n" + message
    
    await context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"Напоминание о статистике отправлено в чат {chat_id}")

async def send_weekly_push_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправить еженедельное напоминание"""
    message = "💰 Пуш по тем, кто начал зарабатывать. Проверь рассылку 📊"
    await context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"Еженедельное напоминание отправлено в чат {chat_id}")

async def show_next_push_date(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать дату следующего пуша"""
    if not bot_data.next_push_date:
        bot_data.next_push_date = datetime.date.today() + datetime.timedelta(days=1)
        bot_data.save_data()
    
    days_left = PushScheduler.days_until_next_push()
    
    if days_left < 0:
        # Если дата в прошлом, исправляем
        bot_data.next_push_date = datetime.date.today() + datetime.timedelta(days=1)
        bot_data.save_data()
        days_left = 1
    
    if days_left == 0:
        message = f"🎯 Следующий пуш СЕГОДНЯ! ({bot_data.next_push_date})"
    elif days_left == 1:
        message = f"📅 Следующий пуш ЗАВТРА! ({bot_data.next_push_date})"
    else:
        message = f"📅 Следующий пуш через {days_left} дней ({bot_data.next_push_date})"
    
    await context.bot.send_message(chat_id=chat_id, text=message)
    logger.info(f"Дата следующего пуша показана в чате {chat_id}")

async def request_new_date(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запросить новую дату у пользователя"""
    await context.bot.send_message(
        chat_id=chat_id,
        text="📝 Введите новую дату начала пушей в формате:\n"
             "`ГГГГ-ММ-ДД`\n"
             "Например: `2026-01-19`\n\n"
             "❗ Дата должна быть в БУДУЩЕМ!",
        parse_mode='Markdown'
    )
    context.user_data['waiting_for_date'] = True
    logger.info(f"Запрос даты отправлен в чат {chat_id}")

async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ввода даты"""
    if not context.user_data.get('waiting_for_date'):
        return
    
    chat_id = update.effective_chat.id
    date_text = update.message.text.strip()
    
    try:
        new_date = datetime.datetime.strptime(date_text, "%Y-%m-%d").date()
        today = datetime.date.today()
        
        if new_date <= today:
            await update.message.reply_text(
                f"❌ Дата должна быть в БУДУЩЕМ!\n"
                f"Сегодня: {today}\n"
                f"Введите дату начиная с завтрашнего дня.",
                parse_mode='Markdown'
            )
            logger.warning(f"Попытка установить прошедшую дату: {new_date} в чате {chat_id}")
            return
        
        # Устанавливаем новую дату
        bot_data.next_push_date = new_date
        bot_data.save_data()
        
        # Перепланируем задания
        await reschedule_jobs(context.application)
        
        # Рассчитываем следующую дату от новой
        next_date = PushScheduler.calculate_next_push_from_today(new_date)
        
        await update.message.reply_text(
            f"✅ Новая дата пуша установлена: `{new_date}`\n"
            f"Следующий пуш: `{next_date}`\n\n"
            f"📅 Расписание:\n"
            f"• Завтра пуш: {next_date == today + datetime.timedelta(days=1)}\n"
            f"• Сегодня пуш: {new_date == today}",
            parse_mode='Markdown'
        )
        logger.info(f"Новая дата пуша установлена: {new_date} в чате {chat_id}")
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты!\n"
            "Используйте: `ГГГГ-ММ-ДД`\n"
            "Пример: `2026-01-19`",
            parse_mode='Markdown'
        )
        logger.warning(f"Неверный формат даты: {date_text} в чате {chat_id}")
    
    context.user_data['waiting_for_date'] = False

async def schedule_daily_tasks(application: Application) -> None:
    """Запланировать ежедневные задачи"""
    if not bot_data.scheduler:
        bot_data.scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    
    # Напоминание за день до пуша (11:00, 19:00, 23:30) - только если завтра действительно пуш
    reminders = [(11, 0), (19, 0), (23, 30)]
    for hour, minute in reminders:
        bot_data.scheduler.add_job(
            check_and_send_prepare_reminder,
            CronTrigger(hour=hour, minute=minute, timezone=MOSCOW_TZ),
            args=[application],
            id=f"prepare_{hour}_{minute}",
            misfire_grace_time=300
        )
    
    # Напоминание в день пуша (10:00) - только если сегодня действительно пуш
    bot_data.scheduler.add_job(
        check_and_send_push_day_reminder,
        CronTrigger(hour=10, minute=0, timezone=MOSCOW_TZ),
        args=[application],
        id="push_day_10_00",
        misfire_grace_time=300
    )
    
    # Ежедневная статистика (12:00)
    bot_data.scheduler.add_job(
        send_daily_stats_to_all,
        CronTrigger(hour=12, minute=0, timezone=MOSCOW_TZ),
        args=[application],
        id="daily_stats_12_00",
        misfire_grace_time=300
    )
    
    # Еженедельные пуши (вторник 12:00)
    bot_data.scheduler.add_job(
        send_weekly_push_to_all,
        CronTrigger(day_of_week="tue", hour=12, minute=0, timezone=MOSCOW_TZ),
        args=[application],
        id="weekly_push_tue_12_00",
        misfire_grace_time=300
    )
    
    bot_data.scheduler.start()
    logger.info("Ежедневные задачи запланированы")

async def reschedule_jobs(application: Application) -> None:
    """Перепланировать задания при изменении даты"""
    if bot_data.scheduler:
        bot_data.scheduler.remove_all_jobs()
        await schedule_daily_tasks(application)
        logger.info("Задания перепланированы")

async def check_and_send_prepare_reminder(application: Application) -> None:
    """Проверить и отправить напоминание за день до пуша"""
    if not bot_data.next_push_date:
        logger.warning("Дата пуша не установлена, пропускаем напоминание")
        return
    
    # Проверяем, действительно ли завтра пуш
    if PushScheduler.is_push_tomorrow():
        logger.info(f"Завтра пуш ({bot_data.next_push_date}), отправляем напоминания")
        for chat_id in bot_data.active_chats:
            try:
                await send_prepare_reminder(chat_id, application.bot)
            except Exception as e:
                logger.error(f"Ошибка отправки в чат {chat_id}: {e}")
    else:
        logger.info(f"Завтра не пуш, пропускаем напоминание. Следующий пуш: {bot_data.next_push_date}")

async def check_and_send_push_day_reminder(application: Application) -> None:
    """Проверить и отправить напоминание в день пуша"""
    if not bot_data.next_push_date:
        logger.warning("Дата пуша не установлена, пропускаем напоминание")
        return
    
    # Проверяем, действительно ли сегодня пуш
    if PushScheduler.is_push_today():
        logger.info(f"Сегодня пуш ({bot_data.next_push_date}), отправляем напоминания")
        for chat_id in bot_data.active_chats:
            try:
                await send_push_day_reminder(chat_id, application.bot)
            except Exception as e:
                logger.error(f"Ошибка отправки в чат {chat_id}: {e}")
        
        # После отправки пуша вычисляем следующую дату
        bot_data.next_push_date = PushScheduler.calculate_next_push_from_today(bot_data.next_push_date)
        bot_data.save_data()
        logger.info(f"Следующая дата пуша: {bot_data.next_push_date}")
    else:
        logger.info(f"Сегодня не пуш, пропускаем напоминание. Следующий пуш: {bot_data.next_push_date}")

async def send_daily_stats_to_all(application: Application) -> None:
    """Отправить ежедневное напоминание о статистике всем"""
    logger.info("Отправка ежедневной статистики")
    for chat_id in bot_data.active_chats:
        try:
            await send_stats_reminder(chat_id, application.bot)
        except Exception as e:
            logger.error(f"Ошибка отправки в чат {chat_id}: {e}")

async def send_weekly_push_to_all(application: Application) -> None:
    """Отправить еженедельное напоминание всем"""
    logger.info("Отправка еженедельного напоминания")
    for chat_id in bot_data.active_chats:
        try:
            await send_weekly_push_reminder(chat_id, application.bot)
        except Exception as e:
            logger.error(f"Ошибка отправки в чат {chat_id}: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)

def main() -> None:
    """Основная функция запуска бота"""
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_input)
    )
    application.add_error_handler(error_handler)
    
    # Запускаем планировщик при старте
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()
