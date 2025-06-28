import os
import subprocess
import asyncio
import logging
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
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
CACHE_DIR = Path("video_cache")
CACHE_EXPIRE_DAYS = 7
MAX_CACHE_SIZE_GB = 1  # Лимит размера кеша в гигабайтах
STATS_FILE = Path("bot_stats.json")

# Создаем директорию для кеша
CACHE_DIR.mkdir(exist_ok=True)

# Инициализация статистики
bot_stats = {
    "total_requests": 0,
    "successful_downloads": 0,
    "failed_downloads": 0,
    "cache_hits": 0,
    "platform_stats": defaultdict(int),
    "user_stats": defaultdict(int),
    "last_activity": datetime.now().isoformat()
}

# Загрузка статистики из файла
if STATS_FILE.exists():
    try:
        with open(STATS_FILE, "r") as f:
            loaded_stats = json.load(f)
            bot_stats.update(loaded_stats)
            bot_stats["platform_stats"] = defaultdict(int, loaded_stats.get("platform_stats", {}))
            bot_stats["user_stats"] = defaultdict(int, loaded_stats.get("user_stats", {}))
    except Exception as e:
        logger.error(f"Ошибка загрузки статистики: {str(e)}")

load_dotenv()

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

def save_stats():
    """Сохраняет статистику в файл"""
    try:
        stats_to_save = bot_stats.copy()
        stats_to_save["platform_stats"] = dict(bot_stats["platform_stats"])
        stats_to_save["user_stats"] = dict(bot_stats["user_stats"])
        
        with open(STATS_FILE, "w") as f:
            json.dump(stats_to_save, f, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения статистики: {str(e)}")

def log_event(event: str, user_id: int = None, details: str = None):
    """Логирование событий"""
    log_msg = f"[EVENT] {event}"
    if user_id:
        log_msg += f" | User: {user_id}"
    if details:
        log_msg += f" | Details: {details[:100]}..." if len(details) > 100 else f" | Details: {details}"
    logger.info(log_msg)

def get_url_hash(url: str) -> str:
    """Генерирует хеш для URL"""
    return hashlib.md5(url.encode()).hexdigest()

def get_platform(url: str) -> str:
    """Определяет платформу по URL"""
    if "tiktok.com" in url:
        return "tiktok"
    elif "instagram.com" in url:
        return "instagram"
    elif "youtube.com/shorts" in url or "youtu.be" in url:
        return "youtube"
    return "other"

async def async_remove_file(path: str):
    """Асинхронное удаление файла с логированием"""
    try:
        os.remove(path)
        logger.info(f"Удален временный файл: {path}")
    except Exception as e:
        logger.error(f"Ошибка удаления файла {path}: {str(e)}")

def clean_old_cache():
    """Очищает старые файлы из кеша"""
    now = datetime.now()
    for file in CACHE_DIR.glob("*"):
        if (now - datetime.fromtimestamp(file.stat().st_mtime)) > timedelta(days=CACHE_EXPIRE_DAYS):
            try:
                file.unlink()
                logger.info(f"Удален устаревший кеш: {file.name}")
            except Exception as e:
                logger.error(f"Ошибка удаления кеша {file.name}: {str(e)}")

def clean_cache_by_size():
    """Очищает кеш при превышении максимального размера"""
    try:
        files = sorted(CACHE_DIR.glob("*"), key=lambda f: f.stat().st_mtime)
        total_size = sum(f.stat().st_size for f in files)
        
        deleted_count = 0
        while total_size > MAX_CACHE_SIZE_GB * 1024**3 and files:
            oldest = files.pop(0)
            total_size -= oldest.stat().st_size
            oldest.unlink()
            deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"Очистка кеша по размеру: удалено {deleted_count} файлов, освобождено {total_size/1024**3:.2f}GB")
    except Exception as e:
        logger.error(f"Ошибка очистки кеша по размеру: {str(e)}")

@dp.message(Command("start"))
async def start(message: Message):
    bot_stats["user_stats"][str(message.from_user.id)] += 1
    save_stats()
    
    log_event("Command received", message.from_user.id, "/start")
    await message.answer(
        "Привіт! Надішли мені посилання на відео з Instagram Reels, TikTok або YouTube Shorts, "
        "і я завантажу його без водяного знаку! 🚀\n\n"
        "Працюю з форматами:\n"
        "• TikTok: vm.tiktok.com, www.tiktok.com\n"
        "• Instagram: www.instagram.com/reel\n"
        "• YouTube: youtu.be, youtube.com/shorts\n\n"
        "📊 Статистика бота:\n"
        f"• Оброблено запитів: {bot_stats['total_requests']}\n"
        f"• Вдалих завантажень: {bot_stats['successful_downloads']}\n"
        f"• Використано кешу: {bot_stats['cache_hits']}")

@dp.message(Command("stats"))
async def show_stats(message: Message):
    stats_msg = (
        "📊 Детальна статистика:\n"
        f"• Всього запитів: {bot_stats['total_requests']}\n"
        f"• Вдалих завантажень: {bot_stats['successful_downloads']}\n"
        f"• Невдалих спроб: {bot_stats['failed_downloads']}\n"
        f"• Звернень до кешу: {bot_stats['cache_hits']}\n"
        "📈 За платформами:\n"
    )
    
    for platform, count in sorted(bot_stats["platform_stats"].items()):
        platform_name = {
            "tiktok": "TikTok",
            "instagram": "Instagram", 
            "youtube": "YouTube",
            "other": "Інші"
        }.get(platform, platform.capitalize())
        
        stats_msg += f"• {platform_name}: {count}\n"
    
    await message.answer(stats_msg)

@dp.message(F.text | F.caption)
async def handle_links(message: Message):
    text = message.text or message.caption
    url = extract_url(text)
    user_id = message.from_user.id
    
    if not url:
        log_event("No URL found", user_id)
        await message.answer("🔴 Не знайдено посилання. Спробуй ще раз!")
        return

    # Обновляем статистику
    bot_stats["total_requests"] += 1
    bot_stats["user_stats"][str(user_id)] += 1
    platform = get_platform(url)
    bot_stats["platform_stats"][platform] += 1
    save_stats()
    
    log_event("Message received", user_id, f"Text: {text[:50]}...")

    wait_msg = None
    file_path = None
    
    try:
        # Проверка кеша
        url_hash = get_url_hash(url)
        cached_file = CACHE_DIR / f"{url_hash}.mp4"
        
        if cached_file.exists():
            bot_stats["cache_hits"] += 1
            save_stats()
            log_event("Cache hit", user_id, f"URL: {url}")
            file_path = str(cached_file)
        else:
            log_event("Video processing started", user_id, f"URL: {url}")
            wait_msg = await message.answer("⏳ Обробляю ваше відео...")
            
            start_time = datetime.now()
            file_path = await download_video(url, url_hash)
            download_time = (datetime.now() - start_time).total_seconds()
            
            log_event("Video downloaded", user_id, 
                     f"Path: {file_path}, Size: {os.path.getsize(file_path)/1024/1024:.2f}MB, "
                     f"Time: {download_time:.2f}s")

        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"Файл слишком большой ({file_size/1024/1024:.2f}MB)")

        video = FSInputFile(file_path)
        await message.answer_video(
            video,
            caption="Ось ваше відео без водяного знаку! ✅",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Скачати ще", callback_data="download_more")]
            ])
        )

        bot_stats["successful_downloads"] += 1
        save_stats()
        log_event("Video sent successfully", user_id)

    except subprocess.TimeoutExpired as e:
        bot_stats["failed_downloads"] += 1
        save_stats()
        logger.error(f"Timeout error for user {user_id}: {str(e)}")
        await message.answer("🔴 Час завантаження вийшов. Спробуйте ще раз.")
    except subprocess.CalledProcessError as e:
        bot_stats["failed_downloads"] += 1
        save_stats()
        logger.error(f"Download failed for user {user_id}. URL: {url}. Error: {str(e)}")
        await message.answer("🔴 Помилка завантаження відео. Перевірте посилання.")
    except Exception as e:
        bot_stats["failed_downloads"] += 1
        save_stats()
        logger.error(f"Unexpected error for user {user_id}: {str(e)}", exc_info=True)
        await message.answer("🔴 Сталася неочікувана помилка. Спробуйте інше посилання.")
    finally:
        if wait_msg:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
            except Exception as e:
                logger.warning(f"Failed to delete wait message: {str(e)}")
        if file_path and not file_path.startswith(str(CACHE_DIR)):
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

async def download_video(url: str, url_hash: str) -> str:
    """Скачивает видео и сохраняет в кеш"""
    clean_cache_by_size()  # Проверка размера перед скачиванием
    
    output_path = str(CACHE_DIR / f"{url_hash}.mp4")
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

async def on_startup():
    """Действия при запуске бота"""
    logger.info("Cleaning old cache...")
    clean_old_cache()  # Сначала по времени
    clean_cache_by_size()  # Затем по размеру
    logger.info("Bot starting...")

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Bot crashed: {str(e)}", exc_info=True)
        raise