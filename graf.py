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

        # Настройка транспорта
        transport = RequestsHTTPTransport(
            url='https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql',
            headers={'content-type': 'application/json',
                     'Authorization': f'{auth_token}',
                     'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
                     'Ubi-SessionId': '88c422ca-73c4-437f-92e3-25f03b08cc2b',
                     'User-Agent': 'UbiServices_SDK_2020.Release.58_PC64_ansi_static'},
            use_json=True,
        )

        # Создание клиента
        self.client = Client(
            transport=transport,
            fetch_schema_from_transport=False
        )

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
        """
        Получение списка предметов для продажи

        Args:
            space_id (str): ID игрового пространства
            limit (int): Количество предметов на странице
            offset (int): Смещение для пагинации
            item_types (List[str]): Фильтр по типам предметов
            tags (List[str]): Фильтр по тегам
            with_ownership (bool): Включать ли информацию о владении
            sort_field (str): Поле для сортировки
            sort_direction (str): Направление сортировки (ASC/DESC)
            payment_item_id (str): ID валюты для оплаты

        Returns:
            Dict: Результат запроса
        """
        # Формирование переменных запроса
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

        # Запрос
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
        """
        Парсинг ответа API в удобный формат

        Args:
            response (Dict): Ответ API

        Returns:
            List[Dict]: Список предметов с рыночной информацией
        """
        items = []

        try:
            nodes = response['game']['viewer']['meta']['marketableItems']['nodes']

            for node in nodes:
                item_data = node['item']
                market_data = node['marketData']

                # Получение статистики продаж
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


if __name__ == '__main__':
    token='ubi...'
    client = UbisoftMarketClient(auth_token=token)

    for i in range(10):
        # Получение предметов
        response = client.get_sellable_items(
            space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
            limit=40,
            offset=i * 40
        )

        # Парсинг и вывод данных
        items = client.parse_market_data(response)
        for item in items:
            print(f"Предмет: {item['name']}")
            print(f"Минимальная цена: {item['market_info']['lowest_price']}")
            print(f"Последняя цена: {item['market_info']['last_sold_price']}")
            print("---")
