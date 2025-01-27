import json
import time
from datetime import datetime

import requests


class UbisoftMarketWatcher:
    def __init__(self, auth_token):
        """
        Инициализация клиента для отслеживания товаров на Ubisoft Market

        Args:
            auth_token (str): Токен авторизации
        """
        self.url = "https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql"
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': auth_token,
            'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
            'Ubi-SessionId': '88c422ca-73c4-437f-92e3-25f03b08cc2b',
            'User-Agent': 'UbiServices_SDK_2020.Release.58_PC64_ansi_static'
        }

    def fetch_items(self, offset=0, limit=10):
        """
        Отправляет запрос на получение списка товаров

        Args:
            offset (int): Смещение для пагинации
            limit (int): Количество товаров

        Returns:
            list: Список товаров
        """

        payload = [
            {
                "operationName": "GetSellableItems",
                "variables": {
                    "withOwnership": False,
                    "spaceId": "0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                    "limit": limit,
                    "offset": offset,
                    "filterBy": {
                        "types": [],
                        "tags": []
                    },
                    "sortBy": {
                        "field": "LAST_TRANSACTION_PRICE",
                        "direction": "DESC",
                        "paymentItemId": "9ef71262-515b-46e8-b9a8-b6b6ad456c67"
                    }
                },
                "query": """GetSellableItems($spaceId: String!, $limit: Int!, $offset: Int, $filterBy: MarketableItemFilter, $sortBy: MarketableItemSort) {
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
                                            }"""}
        ]

        response = requests.post(self.url, headers=self.headers, data=json.dumps(payload))

        if response.status_code == 200:
            try:
                data = response.json()
                nodes = data[0].get('data', {}).get('game', {}).get('viewer', {}).get('meta', {}).get('marketableItems',
                                                                                                      {}).get('nodes',
                                                                                                              [])
                return nodes
            except Exception as e:
                print(f"Ошибка парсинга ответа: {e}")
                print("Полный ответ:", response.text)  # Логируем полный ответ
                return []
        else:
            print(f"Ошибка HTTP {response.status_code}: {response.text}")
            return []

    def track_items(self):
        """
        Отслеживает товары и выводит те, чья цена последней продажи > 1500.
        """
        while True:
            items = self.fetch_items()
            for item in items:
                name = item['item']['name']
                last_sold_data = item['marketData'].get('lastSoldAt')
                if last_sold_data:
                    price = last_sold_data[0]['price']
                    if price > 1100:
                        performed_at = last_sold_data[0]['performedAt']
                        timestamp = datetime.fromisoformat(performed_at.replace('Z', '+00:00'))
                        print(
                            f"Товар: {name}, Цена: {price}, Дата продажи: {timestamp}, \nURL: https://www.ubisoft.com/ru-ru/game/rainbow-six/siege/marketplace?route=sell%2Fitem-details&itemId={item['item']['id']})")
            print("--- Пауза на 5 секунд ---")
            time.sleep(5)


if __name__ == "__main__":
    token = "ubi_v1 "  # Ваш токен авторизации
    watcher = UbisoftMarketWatcher(auth_token=token)
    watcher.track_items()
