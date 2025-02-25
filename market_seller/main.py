import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from config import *
from market_seller import config
from market_seller.analyzer import MarketAnalyzer
from market_seller.market_client import AsyncUbisoftMarketClient
from market_seller.other.auth import UbisoftAuth
from market_seller.other.database import DatabaseManager
from market_seller.other.telegram import MarketTelegramBot
from market_seller.other.utils import setup_logger, play_notification_sound

load_dotenv()
logger = setup_logger(name="market_script", log_file="market_script.log")
telegram_bot = None


def is_token_invalid_error(error_message: str) -> bool:
    """Проверка, является ли ошибка связанной с невалидным токеном."""
    return "Invalid Ticket".lower() in error_message.lower()


async def handle_exception(exception, analyzer, change):
    """Обработка различных исключений при работе с маркетом."""
    error_message = str(exception)

    for error_code, message in ERROR_MAPPING.items():
        if error_code in error_message:
            logger.warning(message)
            # play_notification_sound()
            analyzer.selling_list.append(change.get("item_id"))
            return

    if is_token_invalid_error(error_message):
        logger.warning("Ошибка: Невалидный токен, обновляем...")
        analyzer.client.auth.refresh_token()
    else:
        logger.error(f"Неожиданная ошибка: {exception}")
        play_notification_sound()


async def fetch_market_items(client, space_id: str) -> list:
    """Получение всех доступных для продажи предметов с ретраями."""
    tasks = [
        client.get_sellable_items(
            space_id=space_id,
            limit=ITEMS_LIMIT,
            offset=i * ITEMS_LIMIT,
        )
        for i in range(PAGES_TO_FETCH)
    ]

    responses = await asyncio.gather(*tasks)
    return [item for response in responses for item in client.parse_market_data(response)]


async def run_main_logic(auth: UbisoftAuth, sell_price: int = DEFAULT_SELL_PRICE):
    """Основная логика работы скрипта."""
    global telegram_bot
    db = DatabaseManager("ubisoft_market.db")
    client = AsyncUbisoftMarketClient(auth=auth, logger=logger)
    await client.init_session()
    loop = asyncio.get_running_loop()
    telegram_bot = MarketTelegramBot(
        os.getenv("TELEGRAM_TOKEN"),
        client,
        logger,
        os.getenv("ADMIN_CHAT_ID"),
    )
    telegram_bot.run(loop)

    last_token_refresh = datetime.now()
    last_trades_refresh = datetime.now()
    analyzer = MarketAnalyzer(client, logger, bot=telegram_bot)
    start_time = datetime.now()
    await client.monitor_and_cancel_old_trades(SPACE_ID, reserve_item_ids=config.RESERVE_ITEM_IDS)
    db_items = []
    try:
        while datetime.now() - start_time < RESTART_INTERVAL:
            if datetime.now() - last_token_refresh > TOKEN_REFRESH_INTERVAL:
                client.auth.refresh_token()
                last_token_refresh = datetime.now()

            if datetime.now() - last_trades_refresh > TRADES_CANCEL_CHECK_INTERVAL:
                last_trades_refresh = datetime.now()
                canceled_trades = await client.monitor_and_cancel_old_trades(
                    SPACE_ID, reserve_item_ids=config.RESERVE_ITEM_IDS
                )
                if canceled_trades:
                    item_ids = [
                        key
                        for key, values in analyzer.price_drop_orders.items()
                        if values["trade_id"] in [v.values() for v in canceled_trades]
                    ]
                    for item_id in item_ids:
                        del analyzer.price_drop_orders[item_id]

            try:
                all_items = await fetch_market_items(client, SPACE_ID)
                db_items.extend(all_items)
                await analyzer.analyze(all_items, sell_price=sell_price)
                await asyncio.sleep(SLEEP_INTERVAL)

            except Exception as e:
                logger.critical(f"Ошибка: {e}")
                play_notification_sound()

    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        play_notification_sound()
    finally:
        seen_items = []
        items_to_insert = []

        for item in db_items:
            item_copy = item.copy()
            if "market_info" in item_copy:
                item_copy["market_info"] = item_copy["market_info"].copy()
                item_copy["market_info"].pop("recorded_at", None)

            if item_copy not in seen_items:
                items_to_insert.append(item)
                seen_items.append(item_copy)

        db.insert_items_batch(items_to_insert)
        db.close_connection()
        await client.close_session()
        telegram_bot.stop()


async def authenticate(email: str, password: str) -> UbisoftAuth:
    """Аутентификация пользователя."""
    auth = UbisoftAuth(email, password, logger)

    if auth.is_token_expired():
        logger.warning("Токен истек или недействителен. Пытаемся обновить сессию...")
        if not auth.ensure_valid_token():
            logger.warning("Не удалось обновить сессию. Требуется ручная аутентификация.")
            auth.basic_auth(auth.email, auth.password)
            if auth.two_factor_ticket:
                code = input("Введите код двухфакторной аутентификации: ")
                auth.complete_2fa(code)
    else:
        logger.info("Успешная аутентификация с использованием сохраненных токенов")

    return auth


async def main(email: str, password: str, sell_price: int = DEFAULT_SELL_PRICE):
    """Основная точка входа."""
    auth = await authenticate(email, password)

    try:
        await run_main_logic(auth, sell_price=sell_price)
    except Exception as e:
        logger.error(f"Ошибка во время выполнения: {e}")
        asyncio.timeout(30)
        play_notification_sound()


if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main(os.getenv("EMAIL"), os.getenv("PASSWORD"), sell_price=SELL_PRICE))
        except Exception as e:
            logger.error(f"Ошибка в главном цикле: {e}")
            play_notification_sound()

        logger.info(f"Перезапуск main() через {RESTART_DELAY} секунд...")
        time.sleep(RESTART_DELAY)
