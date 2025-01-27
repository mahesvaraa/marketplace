from datetime import datetime
from typing import Dict, List

import aiohttp
import winsound

from database import DatabaseManager  # Импортируем класс базы данных
from market_seller.auth2 import UbisoftAuth


class AsyncUbisoftMarketClient:
    def __init__(self, auth: UbisoftAuth, db_name: str = "ubisoft_market.db"):
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
        self.db = DatabaseManager(db_name)  # Инициализируем менеджер базы данных

    async def init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None
        self.db.close_connection()  # Закрываем соединение с базой данных

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
                winsound.PlaySound("C:\Windows\Media\Windows Logon.wav", winsound.SND_FILENAME )
                self.auth.refresh_session_with_remember_me()
                raise Exception(f"GraphQL errors: {result.get('errors')}")

            return result.get('data')

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
            self.db.insert_sell_order({
                'space_id': space_id,
                'trade_id': result.get('createSellOrder').get('trade').get('tradeId'),
                'item_id': item_id,
                'quantity': quantity,
                'price': price,
                'created_at': datetime.utcnow().isoformat()
            })
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
            self.db.insert_sell_order({
                'space_id': space_id,
                'trade_id': trade_id,
                'item_id': None,  # Предполагаем, что item_id неизвестен при обновлении
                'quantity': None,  # Не обновляем количество
                'price': price,
                'updated_at': datetime.utcnow().isoformat()
            })
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
                                        buyStats {
                                            id
                                            paymentItemId
                                            lowestPrice
                                            highestPrice
                                            activeCount
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

    def parse_market_data(self, response: Dict) -> List[Dict]:
        items = []
        try:
            nodes = response['game']['viewer']['meta']['marketableItems']['nodes']
            for node in nodes:
                item_data = node.get('item')
                market_data = node.get('marketData')
                sell_stats = market_data.get('sellStats')[0] if market_data.get('sellStats') else None
                last_sold = market_data.get('lastSoldAt')[0] if market_data.get('lastSoldAt') else None

                if sell_stats and last_sold:
                    parsed_item = {
                        'name': item_data.get('name'),
                        'type': item_data.get('type'),
                        'item_id': item_data.get('itemId'),
                        'tags': item_data.get('tags'),
                        'asset_url': item_data.get('assetUrl'),
                        'market_info': {
                            'lowest_price': sell_stats.get('lowestPrice'),
                            'highest_price': sell_stats.get('highestPrice'),
                            'active_listings': sell_stats.get('activeCount'),
                            'last_sold_price': last_sold.get('price'),
                            'last_sold_at': datetime.fromisoformat(last_sold.get('performedAt').replace('Z', '+00:00'))
                        }
                    }
                    items.append(parsed_item)
                    self.db.insert_item(parsed_item)  # Сохраняем предмет в базу данных

            return items
        except Exception as e:
            print(f"Ошибка при парсинге данных: {str(e)}")
            raise

    async def refresh_token_if_needed(self):
        if self.auth.is_token_expired():  # Заменили validate_token на is_token_expired
            print("Token is missing or invalid. Authenticating...")

            self.auth.basic_auth(self.auth.email, self.auth.password)
            if self.auth.two_factor_ticket:
                code = input("Enter 2FA code: ")
                self.auth.complete_2fa(code)

    # ===========================

    async def get_marketable_items(
            self,
            space_id: str,
            limit: int = 40,
            offset: int = 0,
            item_types: List[str] = None,
            tags: List[str] = None,
            hide_owned: bool = True,
            with_ownership: bool = True,
            sort_field: str = "LAST_TRANSACTION_PRICE",
            sort_direction: str = "DESC",
            payment_item_id: str = "9ef71262-515b-46e8-b9a8-b6b6ad456c67"
    ) -> Dict:
        query = """
            query GetMarketableItems($spaceId: String!, $limit: Int!, $offset: Int, $filterBy: MarketableItemFilter, $withOwnership: Boolean = true, $sortBy: MarketableItemSort) {
                game(spaceId: $spaceId) {
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
                                viewer @include(if: $withOwnership) {
                                    meta {
                                        id
                                        isOwned
                                        quantity
                                    }
                                }
                            }
                            marketData {
                                id
                                sellStats {
                                    id
                                    paymentItemId
                                    lowestPrice
                                    highestPrice
                                    activeCount
                                }
                                buyStats {
                                    id
                                    paymentItemId
                                    lowestPrice
                                    highestPrice
                                    activeCount
                                }
                                lastSoldAt {
                                    id
                                    paymentItemId
                                    price
                                    performedAt
                                }
                            }
                            viewer {
                                meta {
                                    id
                                    activeTrade {
                                        id
                                        tradeId
                                        state
                                        category
                                        createdAt
                                        expiresAt
                                        lastModifiedAt
                                        failures
                                    }
                                }
                            }
                        }
                        totalCount
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
                "tags": tags or [],
                "hideOwned": hide_owned
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

    def parse_market_data_extended(self, response: Dict) -> List[Dict]:
        items = []
        try:
            nodes = response['game']['marketableItems']['nodes']
            for node in nodes:
                item_data = node.get('item', {})
                market_data = node.get('marketData', {})
                viewer_data = node.get('viewer', {}).get('meta', {})

                sell_stats = market_data.get('sellStats', [{}])[0] if market_data.get('sellStats') else {}
                buy_stats = market_data.get('buyStats', [{}])[0] if market_data.get('buyStats') else {}
                last_sold = market_data.get('lastSoldAt', [{}])[0] if market_data.get('lastSoldAt') else {}

                # Get ownership data if available
                viewer_meta = item_data.get('viewer', {}).get('meta', {})

                active_trade = viewer_data.get('activeTrade', {})

                parsed_item = {
                    'name': item_data.get('name'),
                    'type': item_data.get('type'),
                    'item_id': item_data.get('itemId'),
                    'tags': item_data.get('tags'),
                    'asset_url': item_data.get('assetUrl'),
                    'ownership': {
                        'is_owned': viewer_meta.get('isOwned', False),
                        'quantity': viewer_meta.get('quantity', 0)
                    },
                    'market_info': {
                        'sell': {
                            'lowest_price': sell_stats.get('lowestPrice'),
                            'highest_price': sell_stats.get('highestPrice'),
                            'active_count': sell_stats.get('activeCount')
                        },
                        'buy': {
                            'lowest_price': buy_stats.get('lowestPrice'),
                            'highest_price': buy_stats.get('highestPrice'),
                            'active_count': buy_stats.get('activeCount')
                        },
                        'last_sold': {
                            'price': last_sold.get('price'),
                            'performed_at': datetime.fromisoformat(last_sold.get('performedAt', '').replace('Z', '+00:00')) if last_sold.get('performedAt') else None
                        }
                    },
                    'active_trade': {
                        'trade_id': active_trade.get('tradeId'),
                        'state': active_trade.get('state'),
                        'category': active_trade.get('category'),
                        'created_at': datetime.fromisoformat(active_trade.get('createdAt', '').replace('Z', '+00:00')) if active_trade.get('createdAt') else None,
                        'expires_at': datetime.fromisoformat(active_trade.get('expiresAt', '').replace('Z', '+00:00')) if active_trade.get('expiresAt') else None,
                        'failures': active_trade.get('failures', [])
                    } if active_trade else None
                }

                items.append(parsed_item)
              #   self.db.insert_item(parsed_item)  # Сохраняем предмет в базу данных

            return items
        except Exception as e:
            print(f"Ошибка при парсинге данных: {str(e)}")
            raise