import os
import subprocess
import asyncio
import logging
from datetime import datetime
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

def log_event(event: str, user_id: int = None, details: str = None):
    """Логирование событий"""
    log_msg = f"[EVENT] {event}"
    if user_id:
        log_msg += f" | User: {user_id}"
    if details:
        log_msg += f" | Details: {details}"
    logger.info(log_msg)

@dp.message(Command("start"))
async def start(message: Message):
    log_event("Command received", message.from_user.id, "/start")
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
    user_id = message.from_user.id
    
    log_event("Message received", user_id, f"Text: {text[:50]}...")
    
    if not url:
        log_event("No URL found", user_id)
        await message.answer("🔴 Не знайдено посилання. Спробуй ще раз!")
        return

    wait_msg = None
    file_path = None
    
    try:
        log_event("Video processing started", user_id, f"URL: {url}")
        wait_msg = await message.answer("⏳ Обробляю ваше відео...")
        
        start_time = datetime.now()
        file_path = await download_video(url)
        download_time = (datetime.now() - start_time).total_seconds()
        
        log_event("Video downloaded", user_id, 
                 f"Path: {file_path}, Size: {os.path.getsize(file_path)} bytes, "
                 f"Time: {download_time:.2f}s")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError("Не вдалося завантажити відео")

        video = FSInputFile(file_path)
        await message.answer_video(
            video,
            caption="Ось ваше відео без водяного знаку! ✅",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Скачати ще", callback_data="download_more")]
            ])
        )

        log_event("Video sent successfully", user_id)

    except Exception:
        # Catch any unexpected errors during the try block execution
        logger.error(f"An unexpected error occurred during video processing for user {user_id}", exc_info=True)
        # Optionally re-raise or handle specifically if needed
        # raise
    except subprocess.TimeoutExpired as e:
        logger.error(f"Timeout error for user {user_id}: {str(e)}")
        await message.answer("🔴 Час завантаження вийшов. Спробуйте ще раз.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Download failed for user {user_id}. URL: {url}. Error: {str(e)}")
        await message.answer("🔴 Помилка завантаження відео. Перевірте посилання.")
    except Exception as e:
        logger.error(f"Unexpected error for user {user_id}: {str(e)}", exc_info=True)
        await message.answer(f"🔴 Сталася неочікувана помилка. Спробуйте інше посилання.")
    finally:
        if wait_msg:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
            except Exception as e:
                logger.warning(f"Failed to delete wait message: {str(e)}")
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Temporary file removed: {file_path}")
            except Exception as e:
                logger.error(f"Failed to remove temp file {file_path}: {str(e)}")

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
    
    logger.debug(f"Download command: {' '.join(command)}")
    result = subprocess.run(command, check=True, timeout=120, capture_output=True, text=True)
    
    if result.stderr:
        logger.debug(f"yt-dlp stderr: {result.stderr}")
    if result.stdout:
        logger.debug(f"yt-dlp stdout: {result.stdout}")
    
    return output_path

@dp.callback_query(F.data == "download_more")
async def download_more(callback: CallbackQuery):
    log_event("Button pressed", callback.from_user.id, "download_more")
    await callback.answer()
    await callback.message.answer("Надішліть нове посилання на відео:")

async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Bot crashed: {str(e)}", exc_info=True)