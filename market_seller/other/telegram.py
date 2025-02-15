import asyncio
import io
import threading
from datetime import datetime, timezone
from functools import partial

import aiohttp
import requests
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

from market_seller import config
from market_seller.config import SPACE_ID
from market_seller.other.utils import update_reserved_ids


class MarketTelegramBot:
    _is_running = False  # Флаг для отслеживания состояния бота

    def __init__(self, token: str, market_client, logger, admin_chat_id):
        telebot.logger.handlers = []
        self.bot = telebot.TeleBot(token)
        self.client = market_client
        self.admin_chat_id = admin_chat_id
        self.loop = None
        self.logger = logger
        self._thread = None  # Поток бота
        self._stop_event = threading.Event()  # Флаг остановки
        self._setup_handlers()

    def _setup_handlers(self):
        """Настройка обработчиков сообщений"""

        @self.bot.message_handler(commands=["start"])
        def start_command(message):
            keyboard = self._create_main_keyboard()
            self.bot.send_message(
                message.chat.id,
                "Бот Market Seller запущен. Выберите действие:",
                reply_markup=keyboard,
            )

        @self.bot.message_handler(content_types=["text"])
        def handle_text(message):
            if not self.loop:
                return
            if not self.admin_chat_id or not self.bot:
                       return  # Если бот остановлен, не отправлять уведомления
            if message.text == "Отменить старые заказы":
                asyncio.run_coroutine_threadsafe(self._cancel_old_trades(message.chat.id), self.loop)
            elif message.text == "Активные заказы":
                asyncio.run_coroutine_threadsafe(self._get_pending_trades(message.chat.id), self.loop)
            elif message.text == "Добавить предмет в игнор":
                asyncio.run_coroutine_threadsafe(self._get_pending_trades_for_ignore(message.chat.id), self.loop)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith(("cancel_trade_", "ignore_item_")))
        def handle_callback(call):
            if not self.admin_chat_id or not self.bot:
                return  # Если бот остановлен, не отправлять уведомления
            if call.data.startswith("cancel_trade_"):
                trade_id = call.data.replace("cancel_trade_", "")
                asyncio.run_coroutine_threadsafe(self._cancel_specific_trade(call.message.chat.id, trade_id), self.loop)
            elif call.data.startswith("ignore_item_"):
                item_id = call.data.replace("ignore_item_", "")
                asyncio.run_coroutine_threadsafe(self._add_item_to_ignore(call.message.chat.id, item_id), self.loop)

    @staticmethod
    def _create_main_keyboard():
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton("Отменить старые заказы"))
        keyboard.add(KeyboardButton("Активные заказы"))
        keyboard.add(KeyboardButton("Добавить предмет в игнор"))
        return keyboard

    async def _cancel_old_trades(self, chat_id):
        """Отмена старых заказов"""
        if not self.admin_chat_id or not self.bot:
            return  # Если бот остановлен, не отправлять уведомления
        try:
            result = await self.client.monitor_and_cancel_old_trades(SPACE_ID, reserve_item_ids=config.RESERVE_ITEM_IDS)
            await self.send_message(chat_id, f"Старые заказы отменены\nРезультат: {len(result)}\n" + '\n'.join([f"{trade['name']} (срок: {int(trade['age_minutes'])})" for trade in result]))
        except Exception as e:
            await self.send_message(chat_id, f"Ошибка при отмене заказов: {str(e)}")

    async def _cancel_specific_trade(self, chat_id, trade_id):
        """Отмена конкретного заказа"""
        if not self.admin_chat_id or not self.bot:
                   return  # Если бот остановлен, не отправлять уведомления
        try:
            await self.client.cancel_old_trade(SPACE_ID, trade_id)
            await self.send_message(chat_id, f"Заказ {trade_id} успешно отменен")
            # Обновляем список активных заказов
            await self._get_pending_trades(chat_id)
        except Exception as e:
            await self.send_message(chat_id, f"Ошибка при отмене заказа {trade_id}: {str(e)}")

    async def _get_pending_trades(self, chat_id):
        """Получение списка активных заказов с кнопками отмены"""
        if not self.admin_chat_id or not self.bot:
                   return  # Если бот остановлен, не отправлять уведомления
        try:
            response = await self.client.get_pending_trades(SPACE_ID)
            data = response

            trades = data.get("game", {}).get("viewer", {}).get("meta", {}).get("trades", {}).get("nodes", [])

            if trades:
                message = "Активные заказы:\n\n"
                # Создаем клавиатуру с инлайн-кнопками
                keyboard = InlineKeyboardMarkup()

                for index, trade in enumerate(trades, 1):
                    trade_id = trade.get("tradeId", "Неизвестно")
                    item_info = trade.get("tradeItems", [{}])[0].get("item", {})
                    item_name = item_info.get("name", "Неизвестно")
                    price_info = trade.get("paymentProposal") or trade.get("paymentOptions", [{}])[0]
                    price = price_info.get("price", "Не указано")

                    message += f"{self.convert_expires_data(trade['expiresAt'])}\n" f"Предмет: {item_name}\n" f"Цена: {price}\n" f"ID: {trade_id}\n" "\n"

                    # Добавляем кнопку отмены для каждого заказа
                    keyboard.add(InlineKeyboardButton(f"Отменить заказ {item_name}", callback_data=f"cancel_trade_{trade_id}"))
            else:
                message = "Активных заказов нет"
                keyboard = None

            # Отправляем сообщение с клавиатурой
            await asyncio.get_event_loop().run_in_executor(None, partial(self.bot.send_message, chat_id, message, reply_markup=keyboard))
        except Exception as e:
            await self.send_message(chat_id, f"Ошибка при получении заказов: {str(e)}")

    async def _get_pending_trades_for_ignore(self, chat_id):
        """Получение списка активных заказов с кнопками добавления в игнор"""
        if not self.admin_chat_id or not self.bot:
                   return  # Если бот остановлен, не отправлять уведомления
        try:
            response = await self.client.get_pending_trades(SPACE_ID)
            data = response

            trades = data.get("game", {}).get("viewer", {}).get("meta", {}).get("trades", {}).get("nodes", [])

            if trades:
                message = "Активные заказы (для добавления в игнор):\n\n"
                keyboard = InlineKeyboardMarkup()

                for index, trade in enumerate(trades, 1):
                    item_info = trade.get("tradeItems", [{}])[0].get("item", {})
                    item_name = item_info.get("name", "Неизвестно")
                    item_id = item_info.get("itemId")
                    price_info = trade.get("paymentProposal") or trade.get("paymentOptions", [{}])[0]
                    price = price_info.get("price", "Не указано")

                    message += f"{self.convert_expires_data(trade['expiresAt'])}\n" f"Предмет: {item_name}\n" f"Цена: {price}\n" f"Item ID: {item_id}\n" "\n"

                    # Добавляем кнопку игнорирования для каждого предмета
                    keyboard.add(InlineKeyboardButton(f"Добавить в игнор {item_name}", callback_data=f"ignore_item_{item_id}"))
            else:
                message = "Активных заказов нет"
                keyboard = None

            await asyncio.get_event_loop().run_in_executor(None, partial(self.bot.send_message, chat_id, message, reply_markup=keyboard))
        except Exception as e:
            await self.send_message(chat_id, f"Ошибка при получении заказов: {str(e)}")

    async def _add_item_to_ignore(self, chat_id, item_id):
        """Добавление предмета в игнор-лист"""
        if not self.admin_chat_id or not self.bot:
                   return  # Если бот остановлен, не отправлять уведомления
        try:
            update_reserved_ids(item_id)
            await self.send_message(chat_id, f"Предмет {item_id} добавлен в игнор-лист")
            # Обновляем список активных заказов для игнора
            await self._get_pending_trades_for_ignore(chat_id)
        except Exception as e:
            await self.send_message(chat_id, f"Ошибка при добавлении предмета {item_id} в игнор: {str(e)}")

    async def send_message(self, chat_id, text):
        """Асинхронная отправка сообщения"""
        if not self.admin_chat_id or not self.bot:
                   return  # Если бот остановлен, не отправлять уведомления
        await asyncio.get_event_loop().run_in_executor(None, partial(self.bot.send_message, chat_id, text))

    @staticmethod
    async def _download_image(url):
        """Загрузка изображения по URL"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                return None

    async def notify_order_created(self, order_data):
        """Уведомление о создании нового заказа с изображением"""
        if not self.admin_chat_id or not self.bot:
            return  # Если бот остановлен, не отправлять уведомления

        message = (
            "🔔 Создан новый заказ:\n\n"
            f"Предмет: {order_data.get('name')}\n"
            f"Цена: {order_data.get('new_price')}\n"
            f"Изменение цены: {order_data.get('price_change')}\n"
            f"Активных предложений: {order_data.get('active_listings')}\n"
            f"Изменение активных предложений: {order_data.get('active_count_change')}\n"
            f"Тип: {order_data.get('type')}\n"
            f"Владелец: {order_data.get('owner')}"
        )

        asset_url = order_data.get("asset_url")
        if asset_url:
            try:
                image_data = await self._download_image(asset_url)
                if image_data:
                    photo = io.BytesIO(image_data)
                    photo.name = "item.png"

                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        partial(
                            self.bot.send_photo,
                            self.admin_chat_id,
                            photo,
                            caption=message,
                        ),
                    )
                    return
            except Exception as e:
                self.logger.error(f"Ошибка при отправке изображения: {e}")

        await self.send_message(self.admin_chat_id, message)

    def _run_polling(self):
        """Запускает бота в потоке и проверяет флаг остановки"""
        while not self._stop_event.is_set():
            try:
                self.bot.infinity_polling(timeout=30, long_polling_timeout=25)
            except requests.exceptions.ReadTimeout:
                self.logger.warning("Telegram API не ответил вовремя. Пропускаем...")
            except Exception as e:
                self.logger.error(f"Ошибка в боте: {e}")

    def run(self, loop):
        """Запуск бота в отдельном потоке с указанным event loop"""
        self.loop = loop
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_polling, daemon=True)
        self._thread.start()

    def stop(self):
        self.logger.info("Остановка бота...")
        self._stop_event.set()

        try:
            self.bot.stop_polling()
            if hasattr(self.bot, "session"):
                self.bot.session.close()  # Закрываем сессию если она есть
        except Exception as e:
            self.logger.error(f"Ошибка при остановке бота: {e}")

        if self._thread:
            self._thread.join(timeout=5)  # Увеличиваем таймаут
            if self._thread.is_alive():
                self.logger.warning("Поток бота не завершился корректно")
                # Можно добавить более агрессивную остановку
                import ctypes

                ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(self._thread.ident), ctypes.py_object(SystemExit))

        self.bot = None
        self.logger.info("Бот остановлен")

    @staticmethod
    def convert_expires_data(expires_at):
        # Формат даты
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"

        # Текущее время

        now = datetime.now(tz=timezone.utc)
        now = now.replace(tzinfo=timezone.utc)

        # Время истечения
        expires_dt = datetime.strptime(expires_at, fmt).replace(tzinfo=timezone.utc)

        # Вычисляем разницу
        time_left = expires_dt - now

        # Извлекаем дни, часы и минуты
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        # Формируем строку
        return f"Осталось {days} д. {hours} ч. {minutes} мин."
