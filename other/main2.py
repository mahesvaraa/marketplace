import asyncio
from datetime import datetime

from market_seller.analyzer import MarketAnalyzer
from market_seller.auth2 import UbisoftAuth
from market_seller.market_client import AsyncUbisoftMarketClient


async def main():
    auth = UbisoftAuth()
    # Пробуем загрузить существующий токен и переиспользовать его
    if auth.is_token_expired():
        print("Token is expired or invalid. Attempting to refresh session...")
        # If automatic refresh fails, proceed with manual authentication
        if not auth.ensure_valid_token():
            print("Session refresh failed. Manual authentication required.")
            auth.basic_auth(auth.email, auth.password)
            if auth.two_factor_ticket:
                code = input("Enter 2FA code: ")
                auth.complete_2fa(code)
    else:
        print("Successfully authenticated using saved tokens")

    client = AsyncUbisoftMarketClient(auth=auth)
    await client.init_session()

    try:
        analyzer = MarketAnalyzer(client)

        while True:
            all_items = []

            try:
                tasks = []
                for i in range(10):
                    tasks.append(client.get_marketable_items(
                        space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                        limit=40,
                        offset=i * 40
                    ))

                responses = await asyncio.gather(*tasks)

                for response in responses:
                    items = client.parse_market_data_extended(response)
                    all_items.extend(items)

                changes = await analyzer.analyze(all_items)
                if changes:
                    now = datetime.now()
                    current_time = now.strftime("%H:%M:%S")
                    for change in changes:
                        print(f'[{current_time}]   ',
                              f"{change['name']:<30} | "
                              f"{change['price_change']:>7} | "
                              f"{change['active_count_change']:>3} | "
                              f"({change['active_listings']:>3}) | "
                              f"{change['type']:<25} | {change['owner']}",
                              )

                await asyncio.sleep(5)

            except Exception as e:
                print(f"Error in main loop: {e}")

                await client.close_session()

                if auth.is_token_expired():  # Заменили validate_token на is_token_expired
                    print("Re-authenticating...")
                    auth.basic_auth(auth.email, auth.password)
                    if auth.two_factor_ticket:
                        code = input("Enter 2FA code: ")
                        auth.complete_2fa(code)

                client = AsyncUbisoftMarketClient(auth=auth)
                await client.init_session()
                continue

    finally:
        await client.close_session()


if __name__ == '__main__':
    asyncio.run(main())
