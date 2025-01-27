import asyncio
from datetime import datetime, timedelta

from market_seller.analyzer import MarketAnalyzer
from market_seller.auth2 import UbisoftAuth
from market_seller.market_changer import MarketChangesTracker
from market_seller.market_client import AsyncUbisoftMarketClient


async def run_main_logic(auth: UbisoftAuth):
    client = AsyncUbisoftMarketClient(auth=auth)
    await client.init_session()

    last_token_refresh = datetime.now()
    refresh_interval = timedelta(minutes=15)

    try:
        analyzer = MarketAnalyzer(client)
        tracker = MarketChangesTracker(history_size=10)

        while True:
            # Проверяем необходимость обновления токена
            if datetime.now() - last_token_refresh > refresh_interval:
                print("Refreshing token...", end=' ')
                client.auth.refresh_token()
                last_token_refresh = datetime.now()

            all_items = []
            try:
                tasks = [
                    client.get_sellable_items(
                        space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                        limit=40,
                        offset=i * 40,
                    )
                    for i in range(10)
                ]

                responses = await asyncio.gather(*tasks)

                for response in responses:
                    items = client.parse_market_data(response)
                    all_items.extend(items)

                changes = await analyzer.analyze(all_items)
                if changes:
                    now = datetime.now()
                    current_time = now.strftime("%H:%M:%S")
                    frequent_changes = tracker.add_changes(changes)
                    if frequent_changes:
                        print("\nFrequent changes detected:")
                        for change in frequent_changes:
                            if change.get("item_id") not in analyzer.selling_list:
                                result = await client.create_sell_order(
                                    space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                                    item_id=change.get("item_id"),
                                    quantity=1,
                                    price=9900,
                                )
                                print(f"Order created: {result}")
                                analyzer.selling_list.append(change.get("item_id"))
                                analyzer.print_change_info(change)

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
                if "{'code': 1895}" in str(e):
                    print("Ошибка при создании ордера. Товар пока нельзя продавать")
                    analyzer.selling_list.append(change.get("item_id"))
                elif "{'code': 1821}" in str(e):
                    print("Ошибка при создании ордера. Товар уже продается")
                    analyzer.selling_list.append(change.get("item_id"))
                elif "Invalid Ticket".lower() in str(e).lower():
                    analyzer.client.auth.refresh_token()
                print(f"Error in main loop: {e}")

                # await client.close_session()

    except Exception as e:
        print(f"Error: {e}")
        # await client.close_session()
    # finally:
    #     await client.close_session()


async def main(email, password):
    restart_interval = timedelta(minutes=60)

    while True:
        start_time = datetime.now()
        auth = UbisoftAuth(email, password)

        if auth.is_token_expired():
            print("Token is expired or invalid. Attempting to refresh session...")
            if not auth.ensure_valid_token():
                print("Session refresh failed. Manual authentication required.")
                auth.basic_auth(auth.email, auth.password)
                if auth.two_factor_ticket:
                    code = input("Enter 2FA code: ")
                    auth.complete_2fa(code)
        else:
            print("Successfully authenticated using saved tokens")

        try:
            await run_main_logic(auth)
        except Exception as e:
            print(f"Error during execution: {e}")

        if datetime.now() - start_time > restart_interval:
            print("Restarting due to token refresh requirement...")
            continue  # Перезапускаем функцию с нуля


if __name__ == "__main__":
    asyncio.run(main("email@mail.ru", "password!"))
