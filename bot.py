import os
import subprocess
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    CallbackQuery
)
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Привіт! Надішли мені посилання на відео з Instagram Reels, TikTok або YouTube Shorts, "
        "і я завантажу його без водяного знаку! 🚀\n\n"
        "Працюю з форматами:\n"
        "• TikTok: vm.tiktok.com, www.tiktok.com\n"
        "• Instagram: www.instagram.com/reel\n"
        "• YouTube: youtu.be, youtube.com/shorts")

@dp.message(F.text | F.caption)
async def handle_links(message: Message):
    text = message.text or message.caption
    url = extract_url(text)
    
    if not url:
        await message.answer("🔴 Не знайдено посилання. Спробуй ще раз!")
        return

    wait_msg = None
    file_path = None
    
    try:
        wait_msg = await message.answer("⏳ Обробляю ваше відео...")
        file_path = await download_video(url)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError("Не вдалося завантажити відео")

        video = FSInputFile(file_path)
        await message.answer_video(
            video,
            caption="Ось ваше відео без водяного знаку! ✅",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Скачати ще", callback_data="download_more")]
            ]))
        
    except subprocess.TimeoutExpired:
        await message.answer("🔴 Час завантаження вийшов. Спробуйте ще раз.")
    except subprocess.CalledProcessError:
        await message.answer("🔴 Помилка завантаження відео. Перевірте посилання.")
    except Exception as e:
        await message.answer(f"🔴 Сталася помилка: {str(e)}")
    finally:
        if wait_msg:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
            except:
                pass
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

def extract_url(text: str) -> str | None:
    import re
    url_pattern = r'https?://(?:vm\.tiktok\.com|www\.tiktok\.com|www\.instagram\.com/reel|youtu\.be|youtube\.com/shorts)[^\s]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None

async def download_video(url: str) -> str:
    output_path = f"temp_video_{os.getpid()}.mp4"
    command = [
        "yt-dlp",
        "-f", "best[ext=mp4]",
        "-o", output_path,
        "--no-warnings",
        "--quiet",
        url
    ]
    
    subprocess.run(command, check=True, timeout=120)
    return output_path

@dp.callback_query(F.data == "download_more")
async def download_more(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Надішліть нове посилання на відео:")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())