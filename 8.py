import time
from datetime import datetime
from typing import Dict, List

from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport


class UbisoftMarketClient:
    def __init__(self, auth_token: str):
        """
        Инициализация клиента для работы с Ubisoft Market API

        Args:
            auth_token (str): Токен авторизации
        """

        transport = RequestsHTTPTransport(
            url='https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql',
            headers={'content-type': 'application/json',
                     'Authorization': f'{auth_token}',
                     'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
                     'Ubi-SessionId': '88c422ca-73c4-437f-92e3-25f03b08cc2b',
                     'User-Agent': 'UbiServices_SDK_2020.Release.58_PC64_ansi_static'},
            use_json=True,
        )
        self.client = Client(
            transport=transport,
            fetch_schema_from_transport=False
        )

    def create_sell_order(self, space_id: str, item_id: str, quantity: int, price: int) -> Dict:
        """
        Создает ордер на продажу предмета.

        Args:
            space_id (str): ID пространства.
            item_id (str): ID предмета.
            quantity (int): Количество предметов для продажи.
            price (int): Цена за единицу предмета.

        Returns:
            Dict: Ответ от API.
        """
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
            raise

    def get_sellable_items(
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
                    'item_id': item_data['itemId'],
                    'tags': item_data['tags'],
                    'asset_url': item_data['assetUrl'],
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

    def create_buy_order(self, space_id: str, item_id: str, quantity: int, price: int) -> Dict:
        """
        Создает ордер на покупку предмета.

        Args:
            space_id (str): ID пространства.
            item_id (str): ID предмета.
            quantity (int): Количество предметов для покупки.
            price (int): Цена за единицу предмета.

        Returns:
            Dict: Ответ от API.
        """
        variables = {
            "spaceId": space_id,
            "tradeItems": [{"itemId": item_id, "quantity": quantity}],
            "paymentProposal": {"paymentItemId": "9ef71262-515b-46e8-b9a8-b6b6ad456c67", "price": price}
        }

        mutation = gql("""
               mutation CreateBuyOrder($spaceId: String!, $tradeItems: [TradeOrderItem!]!, $paymentProposal: PaymentItem!) {
                   createBuyOrder(
                       spaceId: $spaceId
                       tradeItems: $tradeItems
                       paymentProposal: $paymentProposal
                   ) {
                       trade {
                           id
                           tradeId
                           state
                       }
                   }
               }
           """)

        try:
            result = self.client.execute(mutation, variable_values=variables)
            return result
        except Exception as e:
            print(f"Ошибка при создании ордера на покупку: {str(e)}")
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

                # Проверка изменений
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
                            'active_listings': market_info['active_listings']
                        })

            # Обновление текущего состояния
            self.previous_data[item_id] = market_info

        return significant_changes


if __name__ == '__main__':
    token = input("token")
    client = UbisoftMarketClient(auth_token=token)
    analyzer = MarketAnalyzer()
    selling_list = []
    result = client.create_buy_order(
        space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
        item_id="ea43dc95-8762-4f5f-a0d0-9dbd9777ae08",
        quantity=5,
        price=300  # Цена для покупки
    )