import asyncio
import logging
import os
import threading
from functools import wraps

import winsound

from market_seller import config

DEFAULT_SOUND_PATH = r"C:\Windows\Media\Windows Logon.wav"


def play_notification_sound(sound_path=DEFAULT_SOUND_PATH):
    """Универсальное воспроизведение звука уведомления в отдельном потоке"""
    if os.path.exists(sound_path) and config.USE_SOUND:
        threading.Thread(target=winsound.PlaySound, args=(sound_path, winsound.SND_FILENAME)).start()


def setup_logger(name="market_logger", log_file=None):
    """Настройка логера с возможностью вывода в файл и консоль"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    # Форматер с timestamp
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Консольный вывод
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Опциональный вывод в файл
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def async_retry(max_retries=3, delay=1, exceptions=(Exception,)):
    """Декоратор для асинхронных ретраев"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    # logging.warning(f"Retry {attempt + 1}: {e}")
                    await asyncio.sleep(delay)

        return wrapper

    return decorator

def update_reserved_ids(item_id):
    config.RESERVE_ITEM_IDS.append(item_id)