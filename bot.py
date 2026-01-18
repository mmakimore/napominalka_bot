from aiogram import Bot, Dispatcher, executor, types
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

user_data = {}  # хранит шаблоны и фото


@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer(
        "Привет 👋\n\n"
        "1️⃣ Отправь сообщение с ВЕРХНИМИ Premium эмодзи\n"
        "2️⃣ Напиши /top\n\n"
        "3️⃣ Отправь сообщение с НИЖНИМИ Premium эмодзи\n"
        "4️⃣ Напиши /bottom\n\n"
        "После этого можешь собирать посты 😎"
    )


@dp.message_handler(commands=["top"])
async def set_top(msg: types.Message):
    if msg.reply_to_message and msg.reply_to_message.text:
        user_data.setdefault(msg.from_user.id, {})["top"] = msg.reply_to_message.text
        await msg.answer("✅ Верхние эмодзи сохранены")
    else:
        await msg.answer("⚠️ Ответь командой /top на сообщение с эмодзи")


@dp.message_handler(commands=["bottom"])
async def set_bottom(msg: types.Message):
    if msg.reply_to_message and msg.reply_to_message.text:
        user_data.setdefault(msg.from_user.id, {})["bottom"] = msg.reply_to_message.text
        await msg.answer("✅ Нижние эмодзи сохранены")
    else:
        await msg.answer("⚠️ Ответь командой /bottom на сообщение с эмодзи")


@dp.message_handler(content_types=types.ContentType.PHOTO)
async def save_photo(msg: types.Message):
    user_data.setdefault(msg.from_user.id, {})["photo"] = msg.photo[-1].file_id
    await msg.answer("📸 Фото сохранено")


@dp.message_handler(commands=["build"])
async def build_post(msg: types.Message):
    if not msg.reply_to_message or not msg.reply_to_message.text:
        await msg.answer("⚠️ Ответь /build на сообщение с ТЕКСТОМ поста")
        return

    data = user_data.get(msg.from_user.id, {})
    top = data.get("top")
    bottom = data.get("bottom")

    if not top or not bottom:
        await msg.answer("❗ Сначала задай верх и низ (/top и /bottom)")
        return

    text = msg.reply_to_message.text
    final_text = f"{top}\n\n{text}\n\n{bottom}"

    if "photo" in data:
        await bot.send_photo(
            msg.from_user.id,
            data["photo"],
            caption=final_text
        )
    else:
        await msg.answer(final_text)

    await msg.answer("✅ Готово. Можно копировать в канал.")


if __name__ == "__main__":
    executor.start_polling(dp)
