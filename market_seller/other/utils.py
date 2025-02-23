import asyncio
import functools
import logging
import os
import sys
import threading
import time
from collections import UserDict
from functools import wraps
from typing import TypeVar

import winsound

from market_seller import config

T = TypeVar("T")
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


def timing_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        print(f"Функция {func.__name__} выполнялась {end_time - start_time:.6f} секунд")
        return result

    return wrapper


def async_timing_decorator(func):
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = await func(*args, **kwargs)
            end_time = time.perf_counter()
            print(f"Функция {func.__name__} выполнялась {end_time - start_time:.6f} секунд")
            return result

    else:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            print(f"Функция {func.__name__} выполнялась {end_time - start_time:.6f} секунд")
            return result

    return wrapper


def profile_calls(func):
    """Декоратор для замера времени выполнения всех вызовов функций внутри обёрнутой функции."""

    def tracer(frame, event, arg):
        if event == "call":
            func_name = frame.f_code.co_name
            start_time = time.perf_counter()

            def tracer_return(frame, event, arg):
                if event == "return":
                    elapsed_time = time.perf_counter() - start_time
                    print(f"Функция {func_name} выполнялась {elapsed_time:.6f} секунд")
                    sys.setprofile(tracer)  # Возвращаем основной обработчик

            sys.setprofile(tracer_return)  # Переключаемся на замер завершения функции

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        sys.setprofile(tracer)
        try:
            return func(*args, **kwargs)
        finally:
            sys.setprofile(None)  # Убираем профилирование после выполнения

    return wrapper


def async_profile_calls(func):
    """Декоратор, измеряющий время выполнения всех асинхронных вызовов внутри обёрнутой функции."""

    async def timing_wrapper(coro, func_name):
        start_time = time.perf_counter()
        result = await coro
        elapsed_time = time.perf_counter() - start_time
        print(f"Функция {func_name} выполнялась {elapsed_time:.6f} секунд")
        return result

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        """Оборачиваем все асинхронные вызовы внутри обёрнутой функции."""

        def wrap_coroutine(original_coro):
            """Оборачивает каждую асинхронную функцию перед выполнением."""

            @functools.wraps(original_coro)
            async def wrapped(*coro_args, **coro_kwargs):
                return await timing_wrapper(original_coro(*coro_args, **coro_kwargs), original_coro.__name__)

            return wrapped

        # Патчим все вложенные асинхронные функции
        for attr_name in dir(func):
            attr = getattr(func, attr_name)
            if asyncio.iscoroutinefunction(attr):
                setattr(func, attr_name, wrap_coroutine(attr))

        return await timing_wrapper(func(*args, **kwargs), func.__name__)

    return wrapper


class DotDict(UserDict):
    def __init__(self, data=None, **kwargs):
        initial_data = data if data is not None else {}
        super().__init__({k: self._convert(v) for k, v in {**initial_data, **kwargs}.items()})

    @classmethod
    def _convert(cls, value):
        """Рекурсивно конвертирует вложенные структуры"""
        if isinstance(value, dict):
            return cls(value)  # Конвертируем словари
        if isinstance(value, list):
            return [cls._convert(v) for v in value]  # Конвертируем списки словарей
        return value

    def __getattr__(self, key):
        try:
            return self.data[key]
        except KeyError:
            raise AttributeError(f"No attribute named '{key}'")

    def __setattr__(self, key, value):
        if key == "data":  # Избегаем рекурсии при установке self.data
            super().__setattr__(key, value)
        else:
            self.data[key] = self._convert(value)  # Автоконвертация новых вложенных структур

    def __delattr__(self, key):
        try:
            del self.data[key]
        except KeyError:
            raise AttributeError(f"No attribute named '{key}'")
