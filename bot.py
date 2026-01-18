from aiogram import Bot, Dispatcher, executor, types
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

user_data = {}  # Хранит верх, низ, фото


@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer(
        "Привет 👋\n\n"
        "1️⃣ Отправь сообщение с ВЕРХНИМИ Premium эмодзи → ответь /top\n"
        "2️⃣ Отправь сообщение с НИЖНИМИ Premium эмодзи → ответь /bottom\n"
        "После этого присылай текст поста и фото, а я пришлю готовый пост"
    )


@dp.message_handler(commands=["top"])
async def set_top(msg: types.Message):
    if msg.reply_to_message:
        user_data.setdefault(msg.from_user.id, {})["top_id"] = msg.reply_to_message.message_id
        user_data[msg.from_user.id]["top_chat"] = msg.reply_to_message.chat.id
        await msg.answer("✅ Верхние эмодзи сохранены")
    else:
        await msg.answer("⚠️ Ответь командой /top на сообщение с верхними эмодзи")


@dp.message_handler(commands=["bottom"])
async def set_bottom(msg: types.Message):
    if msg.reply_to_message:
        user_data.setdefault(msg.from_user.id, {})["bottom_id"] = msg.reply_to_message.message_id
        user_data[msg.from_user.id]["bottom_chat"] = msg.reply_to_message.chat.id
        await msg.answer("✅ Нижние эмодзи сохранены")
    else:
        await msg.answer("⚠️ Ответь командой /bottom на сообщение с нижними эмодзи")


@dp.message_handler(content_types=types.ContentType.PHOTO)
async def save_photo(msg: types.Message):
    user_data.setdefault(msg.from_user.id, {})["photo"] = msg.photo[-1].file_id
    await msg.answer("📸 Фото сохранено")


@dp.message_handler(commands=["build"])
async def build_post(msg: types.Message):
    data = user_data.get(msg.from_user.id, {})

    # Проверяем, есть ли верх и низ
    if not data.get("top_id") or not data.get("bottom_id"):
        await msg.answer("❗ Сначала нужно задать верх и низ сообщений (/top и /bottom)")
        return

    if not msg.reply_to_message or not msg.reply_to_message.text:
        await msg.answer("⚠️ Ответь командой /build на сообщение с текстом поста")
        return

    text = msg.reply_to_message.text
    chat_id = msg.from_user.id

    # Сначала копируем верхние эмодзи
    await bot.copy_message(chat_id, data["top_chat"], data["top_id"])
    # Потом текст + фото
    if "photo" in data:
        await bot.send_photo(chat_id, data["photo"], caption=text)
    else:
        await bot.send_message(chat_id, text)
    # Потом копируем нижние эмодзи
    await bot.copy_message(chat_id, data["bottom_chat"], data["bottom_id"])

    await msg.answer("✅ Готово! Можешь копировать пост в канал.")


if __name__ == "__main__":
    executor.start_polling(dp)
