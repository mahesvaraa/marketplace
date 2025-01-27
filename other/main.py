from datetime import datetime
from typing import Dict, List

import aiohttp

from market_seller.auth import UbisoftAuth


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
