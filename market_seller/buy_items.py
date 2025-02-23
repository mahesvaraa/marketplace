import asyncio
import os

from dotenv import load_dotenv

from config import SPACE_ID, ITEMS_LIMIT, LIMIT_MASS_BUY_PRICE, PAGES_TO_FETCH_BUY
from market_seller.market_client import AsyncUbisoftMarketClient
from market_seller.other.auth import UbisoftAuth
from market_seller.other.utils import setup_logger
from other.requests_params import RequestsParams

load_dotenv()
logger = setup_logger(name="market_buyer", log_file="market_buyer.log")


async def fetch_market_items(client, space_id: str, items_limit: int, pages_to_fetch: int) -> list:
    """Получение всех доступных предметов с ретраями."""
    tasks = [
        client.get_marketable_items(
            space_id=space_id,
            limit=items_limit,
            offset=i * items_limit,
            query=RequestsParams.GET_MARKETABLE_ITEMS_QUERY,
        )
        for i in range(pages_to_fetch)
    ]

    responses = await asyncio.gather(*tasks)
    return [item for response in responses for item in client.parse_market_data(response)]


async def buy_cheap_items(
    auth: UbisoftAuth, space_id: str, max_price: int = 30, items_limit: int = 100, pages_to_fetch: int = 5
):
    """Основная логика покупки дешевых предметов."""
    client = AsyncUbisoftMarketClient(auth=auth, logger=logger)
    await client.init_session()

    try:
        # Получаем все предметы
        all_items = await fetch_market_items(client, space_id, items_limit, pages_to_fetch)
        logger.info(f"Найдено {len(all_items)} предметов")

        # Фильтруем предметы по цене
        cheap_items = [
            item
            for item in all_items
            if item.market_info.lowest_price <= max_price and item.market_info.active_listings > 0
        ]

        if not cheap_items:
            logger.info(f"Не найдено предметов дешевле {max_price}")
            return

        logger.info(f"Найдено {len(cheap_items)} предметов дешевле {max_price}")

        # Покупаем каждый дешевый предмет
        for item in cheap_items[:20]:
            try:
                response = await client.create_buy_order(
                    space_id=space_id,
                    item_id=item.item_id,
                    quantity=1,
                    price=item.market_info.lowest_price,
                    payment_item_id="9ef71262-515b-46e8-b9a8-b6b6ad456c67",
                )

                logger.info(
                    f"Куплен предмет: {item.name} " f"(ID: {item.item_id}) " f"за {item.market_info.lowest_price}"
                )

            except Exception as e:
                logger.error(f"Ошибка при покупке {item.name}: {e}")
                continue

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await client.close_session()


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


async def main():
    """Точка входа."""
    auth = await authenticate(os.getenv("EMAIL"), os.getenv("PASSWORD"))

    await buy_cheap_items(
        auth=auth,
        space_id=SPACE_ID,
        max_price=LIMIT_MASS_BUY_PRICE,
        items_limit=ITEMS_LIMIT,
        pages_to_fetch=PAGES_TO_FETCH_BUY,
    )


if __name__ == "__main__":
    asyncio.run(main())
