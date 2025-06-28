import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

# Новый способ инициализации бота (aiogram >= 3.7.0)
bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Привіт! Я твій бот. 🇺🇦")

@dp.message(Command("help"))
async def help(message: Message):
    await message.answer("Доступні команди: /start, /help")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())