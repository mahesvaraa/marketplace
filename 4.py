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
                        tradeId
                        state
                        __typename
                    }
                    __typename
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
                                        name
                                        tags
                                        type
                                    }
                                    marketData {
                                        sellStats {
                                            paymentItemId
                                            lowestPrice
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

                parsed_item = {
                    'name': item_data['name'],
                    'type': item_data['type'],
                    'item_id': item_data['id'],
                    'tags': item_data['tags'],
                    'market_info': {
                        'lowest_price': sell_stats['lowestPrice'] if sell_stats else None
                    }
                }
                items.append(parsed_item)

            return items
        except Exception as e:
            print(f"Ошибка при парсинге данных: {str(e)}")
            raise