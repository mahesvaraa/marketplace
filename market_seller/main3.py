import asyncio
from datetime import datetime, timedelta

from market_seller.analyzer import MarketAnalyzer
from market_seller.auth2 import UbisoftAuth
from market_seller.market_changer import MarketChangesTracker
from market_seller.market_client import AsyncUbisoftMarketClient

async def run_main_logic(auth: UbisoftAuth, sell_price=9900):
    client = AsyncUbisoftMarketClient(auth=auth)
    await client.init_session()

    last_token_refresh = datetime.now()
    refresh_interval = timedelta(minutes=15)

    analyzer = MarketAnalyzer(client)
    tracker = MarketChangesTracker(history_size=10)

    try:
        while True:
            # Проверяем необходимость обновления токена
            if datetime.now() - last_token_refresh > refresh_interval:
                client.auth.refresh_token()
                last_token_refresh = datetime.now()

            try:
                # Получение всех доступных для продажи предметов
                tasks = [
                    client.get_sellable_items(
                        space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                        limit=40,
                        offset=i * 40,
                    )
                    for i in range(10)
                ]

                responses = await asyncio.gather(*tasks)

                all_items = []
                for response in responses:
                    items = client.parse_market_data(response)
                    all_items.extend(items)

                # Анализ изменений на рынке
                changes = await analyzer.analyze(all_items, sell_price=sell_price)
                if changes:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    frequent_changes = tracker.add_changes(changes)

                    # Обработка частых изменений
                    if frequent_changes:
                        print("\nОбнаружены частые изменения:")
                        for change in frequent_changes:
                            item_id = change.get("item_id")
                            if item_id not in analyzer.selling_list:
                                result = await client.create_sell_order(
                                    space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                                    item_id=item_id,
                                    quantity=1,
                                    price=sell_price,
                                )
                                print(f"Ордер создан: {result}")
                                analyzer.selling_list.append(item_id)
                                analyzer.print_change_info(change)

                    # Логирование изменений
                    for change in changes:
                        print(
                            f"[{current_time}]   ",
                            f"{change.get('name'):<30} | "
                            f"{change.get('price_change'):>7} | "
                            f"{change.get('active_count_change'):>3} | "
                            f"({change.get('active_listings'):>3}) | "
                            f"{change.get('type'):<25} | {change.get('owner')}",
                        )

                await asyncio.sleep(5)

            except Exception as e:
                await handle_exception(e, analyzer, change)

    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        await client.close_session()


async def handle_exception(exception, analyzer, change):
    error_message = str(exception)

    if "{'code': 1895}" in error_message:
        print("Ошибка: Товар пока нельзя продавать")
        analyzer.selling_list.append(change.get("item_id"))
    elif "{'code': 1821}" in error_message:
        print("Ошибка: Товар уже продается")
        analyzer.selling_list.append(change.get("item_id"))
    elif "Invalid Ticket".lower() in error_message.lower():
        print("Ошибка: Невалидный токен, обновляем...")
        analyzer.client.auth.refresh_token()
    else:
        print(f"Неожиданная ошибка: {exception}")


async def main(email, password, sell_price=9900):
    restart_interval = timedelta(minutes=60)

    while True:
        start_time = datetime.now()
        auth = UbisoftAuth(email, password)

        if auth.is_token_expired():
            print("Токен истек или недействителен. Пытаемся обновить сессию...")
            if not auth.ensure_valid_token():
                print("Не удалось обновить сессию. Требуется ручная аутентификация.")
                auth.basic_auth(auth.email, auth.password)
                if auth.two_factor_ticket:
                    code = input("Введите код двухфакторной аутентификации: ")
                    auth.complete_2fa(code)
        else:
            print("Успешная аутентификация с использованием сохраненных токенов")

        try:
            await run_main_logic(auth, sell_price=sell_price)
        except Exception as e:
            print(f"Ошибка во время выполнения: {e}")

        if datetime.now() - start_time > restart_interval:
            print("Перезапуск из-за необходимости обновления токена...")


if __name__ == "__main__":
    asyncio.run(main("email@mail.ru", "password!", sell_price=9900))
