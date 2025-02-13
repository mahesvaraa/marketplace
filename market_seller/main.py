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
from market_seller.other.market_changer import MarketChangesTracker
from market_seller.other.telegram import MarketTelegramBot
# Импорт утилит
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


def format_log_change_message(change: dict) -> str:
    """Форматирование лога с информацией об изменении."""
    ru_ru = {
        "CharacterUniform": "ФОРМА",
        "WeaponSkin": "СКИН НА ОРУЖИЕ",
        "CharacterHeadgear": "ШЛЕМ",
        "Charm": "ЗНАЧОК",
        "OperatorCardBackground": "ФОН",
        "OperatorCardPortrait": "ПОРТРЕТ",
        "WeaponAttachmentSkinSet": "СКИН НА МОДУЛИ",
    }
    return (
        f"{change.get('name'):<25} | "
        f"{change.get('new_price'):>7} | "
        f"{change.get('price_change'):>7} | "
        f"{change.get('active_count_change'):>3} | "
        f"{change.get('active_listings'):>3} | "
        f"{ru_ru.get(change.get('type'), change.get('type')):<15} | "
        f"{change.get('owner'):<18} | "
        f"{change.get('sell_range'): <15} | "
        f"{change.get('active_buy_count'):>3} | "
        f"{change.get('buy_range')}"
    )


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
    frequent_changes = []
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
    analyzer = MarketAnalyzer(client, logger, bot=telegram_bot)
    tracker = MarketChangesTracker(history_size=HISTORY_FREQUENT_SIZE)
    start_time = datetime.now()
    changes = []
    await client.monitor_and_cancel_old_trades(SPACE_ID, reserve_item_ids=config.RESERVE_ITEM_IDS)
    db_items = []
    try:
        while datetime.now() - start_time < RESTART_INTERVAL:
            if datetime.now() - last_token_refresh > TOKEN_REFRESH_INTERVAL:
                client.auth.refresh_token()
                last_token_refresh = datetime.now()
                await client.monitor_and_cancel_old_trades(SPACE_ID, reserve_item_ids=config.RESERVE_ITEM_IDS)

            try:
                all_items = await fetch_market_items(client, SPACE_ID)
                db_items.extend(all_items)
                changes = await analyzer.analyze(all_items, sell_price=sell_price)
                if changes:
                    frequent_changes = tracker.add_changes(changes, FREQUENCY)
                    for change in changes:
                        logger.info(format_log_change_message(change))

                if frequent_changes:
                    for change in frequent_changes:
                        item_id = change.get("item_id")
                        if item_id not in analyzer.selling_list:
                            await client.create_sell_order(
                                space_id=SPACE_ID,
                                item_id=item_id,
                                quantity=1,
                                price=FREQ_SELL_PRICE,
                            )
                            play_notification_sound()
                            analyzer.selling_list.append(item_id)
                            analyzer.print_change_info(change)
                            await telegram_bot.notify_order_created(change)
                await asyncio.sleep(SLEEP_INTERVAL)

            except Exception as e:
                if changes:
                    await handle_exception(e, analyzer, changes[0])
                else:
                    logger.critical(f"Ошибка: {e}")
                    play_notification_sound()

    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        play_notification_sound()
    finally:
        seens_items = []
        for item in db_items:
            if item in seens_items:
                continue
            else:
                db.insert_item(item)
                seens_items.append(item)
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
