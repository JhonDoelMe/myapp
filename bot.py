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

# Конфигурация логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Константы
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB лимит Telegram

load_dotenv()

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

def log_event(event: str, user_id: int = None, details: str = None):
    """Улучшенное логирование событий"""
    log_msg = f"[EVENT] {event}"
    if user_id:
        log_msg += f" | User: {user_id}"
    if details:
        log_msg += f" | Details: {details[:100]}..." if len(details) > 100 else f" | Details: {details}"
    logger.info(log_msg)

async def async_remove_file(path: str):
    """Асинхронное удаление файла с логированием"""
    try:
        os.remove(path)
        logger.info(f"Удален временный файл: {path}")
    except Exception as e:
        logger.error(f"Ошибка удаления файла {path}: {str(e)}")

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
        
        file_size = os.path.getsize(file_path)
        log_event("Video downloaded", user_id, 
                f"Path: {file_path}, Size: {file_size/1024/1024:.2f}MB, "
                f"Time: {download_time:.2f}s")
        
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"Файл слишком большой ({file_size/1024/1024:.2f}MB)")

        video = FSInputFile(file_path)
        await message.answer_video(
            video,
            caption="Ось ваше відео без водяного знаку! ✅",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Скачати ще", callback_data="download_more")]
            ]) # Removed extra parenthesis here
        )

        log_event("Video sent successfully", user_id)

    except subprocess.TimeoutExpired as e:
        logger.error(f"Timeout error for user {user_id}: {str(e)}")
        await message.answer("🔴 Час завантаження вийшов. Спробуйте ще раз.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Download failed for user {user_id}. URL: {url}. Error: {str(e)}")
        await message.answer("🔴 Помилка завантаження відео. Перевірте посилання.")
    except Exception as e:
        logger.error(f"Unexpected error for user {user_id}: {str(e)}", exc_info=True)
        await message.answer("🔴 Сталася неочікувана помилка. Спробуйте інше посилання.")
    finally:
        if wait_msg:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
            except Exception as e:
                logger.warning(f"Failed to delete wait message: {str(e)}")
        if file_path and os.path.exists(file_path):
            await async_remove_file(file_path)

def extract_url(text: str) -> str | None:
    import re
    url_pattern = (
        r'https?://(?:vm\.tiktok\.com|'
        r'www\.tiktok\.com|'
        r'www\.instagram\.com/reel|'
        r'youtu\.be|'
        r'youtube\.com/shorts)\S+'
    )
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
        raise