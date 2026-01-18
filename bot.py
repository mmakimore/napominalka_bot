import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Дата первого пуша ---
next_push_date = datetime(2026, 1, 19)  # Можно менять через функцию set_next_push

# --- Функции напоминаний ---
def remind_prepare_push():
    logging.info("⚡ Напоминание: Завтра пуш! Не забудь подготовить сообщения 📝")

def remind_send_push():
    logging.info("🚀 Напоминание: Пора отправлять пуш! 🔔")

def remind_weekly_push():
    logging.info("💰 Еженедельный пуш по тем, кто начал зарабатывать. Проверь рассылку 📊")

def remind_check_stats():
    logging.info("📈 Проверка статистики рассылки по неподтвержденным почтам!")

# --- Планирование пушей ---
scheduler = BackgroundScheduler()

def schedule_next_push():
    global next_push_date
    scheduler.remove_all_jobs()

    # Подготовка на день раньше
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

    # Еженедельный пуш (вторник — подготовка к среде)
    scheduler.add_job(remind_weekly_push, 'cron', day_of_week='tue', hour=12, minute=0)

    logging.info(f"📅 Следующий пуш назначен на {next_push_date.strftime('%d.%m.%Y')}")

def set_next_push(year, month, day):
    """Ручная установка следующей даты пуша"""
    global next_push_date
    next_push_date = datetime(year, month, day)
    schedule_next_push()
    logging.info(f"✅ Ручная установка следующей даты пуша: {next_push_date.strftime('%d.%m.%Y')}")

def auto_increment_push():
    """После пуша автоматически ставим следующий через 4 дня"""
    global next_push_date
    next_push_date += timedelta(days=4)
    schedule_next_push()
    logging.info(f"➡️ Следующий пуш автоматически назначен на {next_push_date.strftime('%d.%m.%Y')}")

# --- Запуск ---
schedule_next_push()
scheduler.start()
logging.info("Бот-напоминалка запущен! 🚀")

# --- Для тестирования: держим скрипт в активном цикле ---
try:
    import time
    while True:
        time.sleep(60)
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    logging.info("Бот остановлен.")
