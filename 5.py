import asyncio
import base64
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List

import aiohttp
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport


class FailedToConnect(Exception):
    pass


class UbisoftMarketClient:
    def __init__(self, email: str = None, password: str = None, creds_path: str = None):
        """
        Инициализация клиента для работы с Ubisoft Market API

        Args:
            email (str): Email для авторизации
            password (str): Пароль для авторизации
            creds_path (str): Путь к файлу с учетными данными
        """
        self.email = email
        self.password = password
        self.token = self.get_basic_token(email, password) if email and password else None
        self.creds_path = creds_path or f"{os.getcwd()}/creds/{self.token}.json" if self.token else None

        # Authentication data
        self.sessionid: str = ""
        self.key: str = ""
        self.new_key: str = ""
        self.expiration: str = ""
        self.new_expiration: str = ""
        self.profileid: str = ""
        self.userid: str = ""

        self.client = None
        self._last_auth_time = 0
        self.auth_refresh_interval = 180  # 3 minutes

    @staticmethod
    def get_basic_token(email: str, password: str) -> str:
        return base64.b64encode(f"{email}:{password}".encode("utf-8")).decode("utf-8")

    def save_creds(self) -> None:
        if not self.creds_path:
            return

        if not os.path.exists(os.path.dirname(self.creds_path)):
            os.makedirs(os.path.dirname(self.creds_path))

        with open(self.creds_path, 'w') as f:
            json.dump({
                "sessionid": self.sessionid,
                "key": self.key,
                "new_key": self.new_key,
                "profileid": self.profileid,
                "userid": self.userid,
                "expiration": self.expiration,
                "new_expiration": self.new_expiration,
            }, f, indent=4)

    def load_creds(self) -> None:
        if not self.creds_path or not os.path.exists(self.creds_path):
            return

        with open(self.creds_path, "r") as f:
            data = json.load(f)

        self.sessionid = data.get("sessionid", "")
        self.key = data.get("key", "")
        self.new_key = data.get("new_key", "")
        self.profileid = data.get("profileid", "")
        self.userid = data.get("userid", "")
        self.expiration = data.get("expiration", "")
        self.new_expiration = data.get("new_expiration", "")

    async def authenticate(self) -> None:
        self.load_creds()

        # Check if current token is still valid
        if self.key and self.expiration:
            expiration_time = datetime.fromisoformat(self.expiration[:26] + "+00:00")
            if expiration_time > datetime.now(timezone.utc):
                self._update_client()
                return

        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "UbiServices_SDK_2020.Release.58_PC64_ansi_static",
                "Content-Type": "application/json; charset=UTF-8",
                "Ubi-AppId": "e3d5ea9e-50bd-43b7-88bf-39794f4e3d40",
                "Authorization": f"Basic {self.token}"
            }

            resp = await session.post(
                url="https://public-ubiservices.ubi.com/v3/profiles/sessions",
                headers=headers,
                json={"rememberMe": True}
            )

            data = await resp.json()

            if "ticket" in data:
                self.key = data.get("ticket")
                self.expiration = data.get("expiration")
                self.profileid = data.get('profileId')
                self.sessionid = data.get("sessionId")
                self.userid = data.get("userId")
                self._update_client()
            else:
                message = data.get("message", "Unknown Error")
                if "httpCode" in data:
                    message = f"HTTP {data['httpCode']}: {message}"
                raise FailedToConnect(message)

            self.save_creds()
            self._last_auth_time = time.time()

    def _update_client(self):
        """Обновляет GQL клиент с новым токеном авторизации"""
        transport = RequestsHTTPTransport(
            url='https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql',
            headers={
                'content-type': 'application/json',
                'Authorization': f'Ubi_v1 t={self.key}',
                'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
                'Ubi-SessionId': self.sessionid,
                'User-Agent': 'UbiServices_SDK_2020.Release.58_PC64_ansi_static'
            },
            use_json=True,
        )
        self.client = Client(
            transport=transport,
            fetch_schema_from_transport=False
        )

    async def ensure_authenticated(self):
        """Проверяет необходимость обновления токена"""
        if self.client is None or time.time() - self._last_auth_time > self.auth_refresh_interval:
            await self.authenticate()

    async def create_sell_order(self, space_id: str, item_id: str, quantity: int, price: int) -> Dict:
        await self.ensure_authenticated()

        variables = {
            "spaceId": space_id,
            "tradeItems": [{"itemId": item_id, "quantity": quantity}],
            "paymentOptions": [{"paymentItemId": "9ef71262-515b-46e8-b9a8-b6b6ad456c67", "price": price}]
        }

        mutation = gql("""
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
        """)

        try:
            result = self.client.execute(mutation, variable_values=variables)
            return result
        except Exception as e:
            print(f"Ошибка при создании ордера на продажу: {str(e)}")
            if "401: Unauthorized" in str(e) or "Ticket is expired" in str(e):
                await self.authenticate()
                self._update_client()
                try:
                    result = self.client.execute(mutation, variable_values=variables)
                    return result
                except Exception as retry_error:
                    print(f"Ошибка после повторной авторизации: {str(retry_error)}")
                    raise
            raise

    async def get_sellable_items(
            self,
            space_id: str,
            limit: int = 40,
            offset: int = 0,
            item_types: List[str] = None,
            tags: List[str] = None,
            with_ownership: bool = False,
            sort_field: str = "ACTIVE_COUNT",
            sort_direction: str = "ASC",
            payment_item_id: str = "9ef71262-515b-46e8-b9a8-b6b6ad456c67"
    ) -> Dict:
        await self.ensure_authenticated()

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

        query = gql("""
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
        """)

        try:
            result = self.client.execute(query, variable_values=variables)
            return result
        except Exception as e:
            print(f"Ошибка при выполнении запроса: {str(e)}")
            raise

    def parse_market_data(self, response: Dict) -> List[Dict]:
        items = []
        try:
            nodes = response['game']['viewer']['meta']['marketableItems']['nodes']
            for node in nodes:
                item_data = node['item']
                market_data = node['marketData']
                sell_stats = market_data['sellStats'][0] if market_data['sellStats'] else None
                last_sold = market_data['lastSoldAt'][0] if market_data['lastSoldAt'] else None
                parsed_item = {
                    'name': item_data['name'],
                    'type': item_data['type'],
                    'item_id': item_data['id'],
                    'tags': item_data['tags'],
                    'market_info': {
                        'lowest_price': sell_stats['lowestPrice'] if sell_stats else None,
                        'highest_price': sell_stats['highestPrice'] if sell_stats else None,
                        'active_listings': sell_stats['activeCount'] if sell_stats else None,
                        'last_sold_price': last_sold['price'] if last_sold else None,
                        'last_sold_at': datetime.fromisoformat(
                            last_sold['performedAt'].replace('Z', '+00:00')) if last_sold else None
                    }
                }
                items.append(parsed_item)

            return items
        except Exception as e:
            print(f"Ошибка при парсинге данных: {str(e)}")
            raise


class MarketAnalyzer:
    def __init__(self):
        self.previous_data = {}

    def analyze(self, items: List[Dict]):
        significant_changes = []

        for item in items:
            item_id = item['item_id']
            market_info = item['market_info']

            if item_id in self.previous_data:
                previous_market_info = self.previous_data[item_id]

                if market_info['last_sold_price'] and previous_market_info['last_sold_price']:
                    price_change = market_info['last_sold_price'] - previous_market_info['last_sold_price']
                    active_count_change = previous_market_info['active_listings'] - market_info['active_listings']

                    if abs(price_change) > 0 or active_count_change > 0:
                        significant_changes.append({
                            'item_id': item_id,
                            'name': item['name'],
                            'price_change': price_change,
                            'active_count_change': active_count_change,
                            'new_price': market_info['last_sold_price'],
                            'old_price': previous_market_info['last_sold_price'],
                        })

            # Обновляем предыдущие данные
            self.previous_data[item_id] = market_info

        return significant_changes

    def report_changes(self, changes: List[Dict]) -> None:
        if not changes:
            print("Нет значительных изменений на рынке.")
            return

        print("Значительные изменения на рынке:")
        for change in changes:
            print(f"Предмет: {change['name']} (ID: {change['item_id']})")
            print(f"  Старая цена: {change['old_price']}")
            print(f"  Новая цена: {change['new_price']}")
            print(f"  Изменение цены: {change['price_change']}")
            print("-" * 30)


async def main():
    client = UbisoftMarketClient(
        email="danilashkirdow@mail.ru",
        password="Dd170296dD!"
    )

    await client.authenticate()
    analyzer = MarketAnalyzer()
    selling_list = []

    while True:
        all_items = []
        for i in range(0, 6):
            response = await client.get_sellable_items(
                space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                limit=40,
                offset=i * 40
            )
            items = client.parse_market_data(response)
            all_items.extend(items)

        changes = analyzer.analyze(all_items)

        for change in changes:
            print('price_change = ', change['price_change'], 'new_price = ', change['new_price'])
            if (change['price_change'] > 1 or change['new_price'] > 1) and change['item_id'] not in selling_list:
                print(f"Создание ордера на продажу для предмета {change['name']} (ID: {change['item_id']})")
                try:
                    result = await client.create_sell_order(
                        space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                        item_id=change['item_id'],
                        quantity=1,
                        price=5000
                    )
                    print(f"Ордер создан: {result}")
                    selling_list.append(change['item_id'])
                except Exception as e:
                    print(f"Ошибка при создании ордера: {e}")

            print(f"Резкое изменение у предмета {change['name']} (ID: {change['item_id']})")
            print(f"Изменение цены: {change['price_change']}")
            print(f"Изменение активных предложений: {change['active_count_change']}")
            print("---")

        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
