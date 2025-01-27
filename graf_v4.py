import asyncio
import base64
import json
import os
from datetime import datetime
from typing import Dict, List, Any

import aiohttp
import requests

TOKEN_FILE = "auth_token.json"


class UbisoftAuth:
    def __init__(self):
        self.base_url = "https://public-ubiservices.ubi.com/v3"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Ubi-AppId": "685a3038-2b04-47ee-9c5a-6403381a46aa",
            "Ubi-RequestedPlatformType": "uplay",
            "Accept": "*/*",
            "Origin": "https://connect.ubisoft.com",
            "Referer": "https://connect.ubisoft.com/"
        }
        self.session = requests.Session()
        self.two_factor_ticket = None
        self.token = None

    def load_token(self):
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                self.token = data.get("token")
                if self.token:
                    self.headers["Authorization"] = f"Ubi_v1 t={self.token}"

    def save_token(self, token: str):
        with open(TOKEN_FILE, "w") as f:
            json.dump({"token": token}, f)

    def validate_token(self) -> bool:
        if not self.token:
            return False
        url = f"{self.base_url}/profiles/me"
        response = self.session.get(url, headers=self.headers)
        return response.status_code == 200

    def basic_auth(self, email: str, password: str) -> Dict[str, Any]:
        url = f"{self.base_url}/profiles/sessions"

        auth_string = f"{email}:{password}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()

        headers = self.headers.copy()
        headers["Authorization"] = f"Basic {auth_base64}"

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                print(f"Authentication failed with status {response.status_code}")
                return response_data

            self.two_factor_ticket = response_data.get("twoFactorAuthenticationTicket")
            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error: {str(e)}")
            return {"error": str(e)}

    def complete_2fa(self, code: str) -> Dict[str, Any]:
        if not self.two_factor_ticket:
            raise Exception("No two-factor authentication ticket found. Run basic_auth first.")

        url = f"{self.base_url}/profiles/sessions"

        headers = self.headers.copy()
        headers["Ubi-2FACode"] = str(code)
        headers["Authorization"] = f"ubi_2fa_v1 t={self.two_factor_ticket}"

        data = {"rememberMe": True}

        try:
            response = self.session.post(url, headers=headers, json=data)
            response_data = response.json()

            if response.status_code != 200:
                print(f"2FA failed with status {response.status_code}")
                return response_data

            if "ticket" in response_data:
                self.token = response_data["ticket"]
                self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                self.save_token(self.token)

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error during 2FA: {str(e)}")
            return {"error": str(e)}


class AsyncUbisoftMarketClient:
    def __init__(self, auth: UbisoftAuth):
        self.url = 'https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql'
        self.headers = {
            'content-type': 'application/json',
            'Authorization': f'ubi_v1 t={auth.token}',
            'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
            'Ubi-SessionId': '88c422ca-73c4-437f-92e3-25f03b08cc2b',
            'User-Agent': 'UbiServices_SDK_2020.Release.58_PC64_ansi_static',
            'Ubi-Localecode': 'ru-RU',
            'Ubi-Countryid': 'RU'
        }
        self.auth = auth
        self.session = None

    async def init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def refresh_token_if_needed(self):
        if not self.auth.validate_token():
            print("Token expired, refreshing token...")
            self.auth.load_token()
            if not self.auth.validate_token():
                print("Re-authenticating...")
                email = input("Enter your Ubisoft email: ")
                password = input("Enter your Ubisoft password: ")
                self.auth.basic_auth(email, password)
                if self.auth.two_factor_ticket:
                    code = input("Enter 2FA code: ")
                    self.auth.complete_2fa(code)

            self.headers['Authorization'] = f'Ubi_v1 t={self.auth.token}'

    async def execute_query(self, query: str, variables: dict) -> Dict:
        await self.refresh_token_if_needed()

        payload = {
            'query': query,
            'variables': variables
        }

        if not self.session:
            await self.init_session()

        async with self.session.post(self.url, json=payload, headers=self.headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Query failed with status {response.status}: {error_text}")

            result = await response.json()
            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")

            return result['data']

    async def create_sell_order(self, space_id: str, item_id: str, quantity: int, price: int) -> Dict:
        mutation = """
                mutation CreateSellOrder($spaceId: String!, $tradeItems: [TradeOrderItem!]!, $paymentOptions: [PaymentItem!]!) {
                    createSellOrder(
                        spaceId: $spaceId
                        tradeItems: $tradeItems
                        paymentOptions: $paymentOptions
                    ) {
                        trade {
                            id
                            state
                            tradeId
                        }
                    }
                }
            """

        variables = {
            "spaceId": space_id,
            "tradeItems": [{"itemId": item_id, "quantity": quantity}],
            "paymentOptions": [{"paymentItemId": "9ef71262-515b-46e8-b9a8-b6b6ad456c67", "price": price}]
        }

        try:
            result = await self.execute_query(mutation, variables)
            return result
        except Exception as e:
            print(f"Ошибка при создании ордера на продажу: {str(e)}")
            raise

    async def update_sell_order(self, space_id: str, trade_id: str, price: int) -> Dict:
        mutation = """
            mutation UpdateSellOrder($spaceId: String!, $tradeId: String!, $paymentOptions: [PaymentItem!]!) {
                updateSellOrder(
                    spaceId: $spaceId
                    tradeId: $tradeId
                    paymentOptions: $paymentOptions
                ) {
                    trade {
                        id
                        tradeId
                        state
                        category
                        createdAt
                        expiresAt
                        lastModifiedAt
                    }
                }
            }
        """

        variables = {
            "spaceId": space_id,
            "tradeId": trade_id,
            "paymentOptions": [{"paymentItemId": "9ef71262-515b-46e8-b9a8-b6b6ad456c67", "price": price}]
        }

        try:
            result = await self.execute_query(mutation, variables)
            return result
        except Exception as e:
            print(f"Ошибка при обновлении ордера на продажу: {str(e)}")
            raise

    async def get_sellable_items(
            self,
            space_id: str,
            limit: int = 100,
            offset: int = 0,
            item_types: List[str] = None,
            tags: List[str] = None,
            with_ownership: bool = False,
            sort_field: str = "ACTIVE_COUNT",
            sort_direction: str = "ASC",
            payment_item_id: str = "9ef71262-515b-46e8-b9a8-b6b6ad456c67"
    ) -> Dict:
        query = """
            query GetSellableItems($spaceId: String!, $limit: Int!, $offset: Int, $filterBy: MarketableItemFilter, $sortBy: MarketableItemSort) {
                game(spaceId: $spaceId) {
                    id
                    viewer {
                        meta {
                            id
                            marketableItems(
                                limit: $limit
                                offset: $offset
                                filterBy: $filterBy
                                sortBy: $sortBy
                                withMarketData: true
                            ) {
                                nodes {
                                    item {
                                        id
                                        assetUrl
                                        itemId
                                        name
                                        tags
                                        type
                                    }
                                    marketData {
                                        id
                                        sellStats {
                                            paymentItemId
                                            lowestPrice
                                            highestPrice
                                            activeCount
                                        }
                                        lastSoldAt {
                                            paymentItemId
                                            price
                                            performedAt
                                        }
                                    }
                                }
                                totalCount
                            }
                        }
                    }
                }
            }
        """

        variables = {
            "spaceId": space_id,
            "limit": limit,
            "offset": offset,
            "withOwnership": with_ownership,
            "filterBy": {
                "types": item_types or [],
                "tags": tags or []
            },
            "sortBy": {
                "field": sort_field,
                "orderType": "Sell",
                "direction": sort_direction,
                "paymentItemId": payment_item_id
            }
        }

        try:
            return await self.execute_query(query, variables)
        except Exception as e:
            print(f"Ошибка при выполнении запроса: {str(e)}")
            raise

    @staticmethod
    def parse_market_data(response: Dict) -> List[Dict]:
        items = []
        try:
            nodes = response['game']['viewer']['meta']['marketableItems']['nodes']
            for node in nodes:
                item_data = node['item']
                market_data = node['marketData']
                sell_stats = market_data['sellStats'][0] if market_data['sellStats'] else None
                last_sold = market_data['lastSoldAt'][0] if market_data['lastSoldAt'] else None

                if sell_stats and last_sold:
                    parsed_item = {
                        'name': item_data['name'],
                        'type': item_data['type'],
                        'item_id': item_data['itemId'],
                        'tags': item_data['tags'],
                        'asset_url': item_data['assetUrl'],
                        'market_info': {
                            'lowest_price': sell_stats['lowestPrice'],
                            'highest_price': sell_stats['highestPrice'],
                            'active_listings': sell_stats['activeCount'],
                            'last_sold_price': last_sold['price'],
                            'last_sold_at': datetime.fromisoformat(last_sold['performedAt'].replace('Z', '+00:00'))
                        }
                    }
                    items.append(parsed_item)

            return items
        except Exception as e:
            print(f"Ошибка при парсинге данных: {str(e)}")
            raise


class MarketAnalyzer:
    def __init__(self, client: AsyncUbisoftMarketClient):
        self.previous_data = {}
        self.client = client
        self.selling_list = []

    async def create_sell_order(self, item_data):
        if (item_data['price_change'] > 100 or item_data['active_count_change'] > 1) and \
                item_data['item_id'] not in self.selling_list:

            print(f"Создание ордера на продажу для предмета {item_data['name']} (ID: {item_data['item_id']})")
            try:
                price = 9995
                result = await self.client.create_sell_order(
                    space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                    item_id=item_data['item_id'],
                    quantity=1,
                    price=price
                )
                print(f"Ордер создан: {result}")
                trade_id = result['createSellOrder']['trade']['id']  # Получаем правильный trade_id
                self.selling_list.append(item_data['item_id'])
                #
                # # Понижение цены каждые 3 секунды
                # for i in range(1, 4):
                #     await asyncio.sleep(2)
                #     price -= 5000  # Или можно настроить шаг
                #     result = await self.client.update_sell_order(
                #         space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                #         trade_id=trade_id,  # Используем полученный trade_id
                #         price=price
                #     )
                #     print(f"Ордер обновлен: {result}")

                self.print_change_info(item_data)
            except Exception as e:
                if "{'code': 1895}" in str(e):
                    print('Ошибка при создании ордера. Товар пока нельзя продавать')
                    self.selling_list.append(item_data['item_id'])
                else:
                    print(f"Ошибка при создании ордера: {e}")

    def print_change_info(self, item_data):
        print(
            f"Резкое изменение у предмета {item_data['name']} \n"
            f"(ID: https://www.ubisoft.com/ru-ru/game/rainbow-six/siege/marketplace?"
            f"route=sell%2Fitem-details&itemId={item_data['item_id']})"
        )
        if item_data['price_change']:
            print(f"Изменение цены: {item_data['price_change']}")
        print(
            f"Изменение активных предложений: {item_data['active_count_change']} "
            f"(Всего: {item_data['active_listings']})"
        )
        print("---")

    async def analyze(self, items: List[Dict]):
        significant_changes = []
        tasks = []

        for item in items:
            item_id = item['item_id']
            market_info = item['market_info']

            if item_id in self.previous_data:
                previous_market_info = self.previous_data[item_id]

                if market_info['last_sold_price'] and previous_market_info['last_sold_price']:
                    price_change = market_info['last_sold_price'] - previous_market_info['last_sold_price']
                    active_count_change = previous_market_info['active_listings'] - market_info['active_listings']

                    if abs(price_change) > 0 or active_count_change > 0:
                        change_data = {
                            'item_id': item_id,
                            'name': item['name'],
                            'price_change': price_change,
                            'active_count_change': active_count_change,
                            'new_price': market_info['last_sold_price'],
                            'old_price': previous_market_info['last_sold_price'],
                            'active_listings': market_info['active_listings'],
                            'type': item['type'],
                            'owner': item['tags'][0].split('.')[-1]
                        }
                        significant_changes.append(change_data)
                        tasks.append(self.create_sell_order(change_data))

            self.previous_data[item_id] = market_info

        if tasks:
            await asyncio.gather(*tasks)
        return significant_changes


async def main():
    auth = UbisoftAuth()
    auth.load_token()

    if not auth.token or not auth.validate_token():
        print("Token is missing or invalid. Authenticating...")
        email = input("Enter your Ubisoft email: ")
        password = input("Enter your password: ")
        auth.basic_auth(email, password)
        if auth.two_factor_ticket:
            code = input("Enter 2FA code: ")
            auth.complete_2fa(code)

    client = AsyncUbisoftMarketClient(auth=auth)

    try:
        analyzer = MarketAnalyzer(client)

        while True:
            now = datetime.now()

            current_time = now.strftime("%H:%M:%S")
            all_items = []
            try:
                tasks = []
                for i in range(10):
                    tasks.append(client.get_sellable_items(
                        space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                        limit=40,
                        offset=i * 40
                    ))

                responses = await asyncio.gather(*tasks)

                for response in responses:
                    items = client.parse_market_data(response)
                    all_items.extend(items)

                changes = await analyzer.analyze(all_items)
                if changes:
                    print('=========', current_time, '=========')
                for change in changes:
                    print(
                        f"{change['name']:<30} | {change['price_change']:>7} | "
                        f"{change['active_count_change']:>3} | ({change['active_listings']:>3}) | {change['type']} | {change['owner']}"
                    )

                await asyncio.sleep(5)

            except Exception as e:
                print(f"Ошибка в основном цикле: {e}")
                auth = UbisoftAuth()
                auth.load_token()

                if not auth.token or not auth.validate_token():
                    print("Token is missing or invalid. Authenticating...")
                    email = input("Enter your Ubisoft email: ")
                    password = input("Enter your password: ")
                    auth.basic_auth(email, password)
                    if auth.two_factor_ticket:
                        code = input("Enter 2FA code: ")
                        auth.complete_2fa(code)

                client = AsyncUbisoftMarketClient(auth=auth)
    finally:
        await client.close_session()


if __name__ == '__main__':
    asyncio.run(main())
