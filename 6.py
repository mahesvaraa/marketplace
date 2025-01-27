import time
from datetime import datetime
from typing import Dict, List

import requests
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import base64

class UbisoftMarketClient:
    def __init__(self, email: str, password: str):
        """
        Инициализация клиента для работы с Ubisoft Market API

        Args:
            email (str): Email для авторизации
            password (str): Пароль для авторизации
        """
        self.email = email
        self.password = password
        self.auth_token = None
        self.session_id = None
        self.two_factor_code = None  # Код 2FA
        self.initialize_client()

    def get_auth_token(self) -> str:
        """
        Получает базовый токен авторизации с использованием email и пароля.

        Returns:
            str: Базовый токен авторизации
        """
        return base64.b64encode(f"{self.email}:{self.password}".encode("utf-8")).decode("utf-8")

    def authenticate_with_2fa(self, two_factor_code: str):
        """
        Выполняет авторизацию с использованием 2FA.

        Args:
            two_factor_code (str): Код двухфакторной аутентификации.
        """
        self.two_factor_code = two_factor_code
        self.refresh_token()

    def refresh_token(self):
        """
        Обновляет токен авторизации, включая 2FA.
        """
        headers = {
            'User-Agent': 'UbiServices_SDK_2020.Release.58_PC64_ansi_static',
            'Content-Type': 'application/json; charset=UTF-8',
            'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
            'Authorization': f'Basic {self.get_auth_token()}'
        }

        data = {
            "rememberMe": True
        }

        if self.two_factor_code:
            data["twoFactorAuthenticationTicket"] = self.two_factor_code

        try:
            response = requests.post(
                url='https://public-ubiservices.ubi.com/v3/profiles/sessions',
                headers=headers,
                json=data
            )

            if response.status_code == 200:
                result = response.json()
                if "ticket" in result:
                    self.auth_token = f"Ubi_v1 t={result['ticket']}"
                    self.session_id = result.get("sessionId")
                    print("Токен успешно обновлен.")
                else:
                    print("Ошибка: токен не найден в ответе.")
            else:
                print(f"Ошибка при обновлении токена: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Ошибка при обновлении токена: {str(e)}")
            raise

    def initialize_client(self):
        """
        Инициализирует клиент для работы с Ubisoft Market API.
        """
        transport = RequestsHTTPTransport(
            url='https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql',
            headers={
                'content-type': 'application/json',
                'Authorization': f'{self.auth_token}',
                'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
                'Ubi-SessionId': self.session_id or '88c422ca-73c4-437f-92e3-25f03b08cc2b',
                'User-Agent': 'UbiServices_SDK_2020.Release.58_PC64_ansi_static'
            },
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
            print(f"Параметры запроса: space_id={space_id}, item_id={item_id}, quantity={quantity}, price={price}")
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
            sort_direction: str = "DESC",
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
                        })

            # Обновление текущего состояния
            self.previous_data[item_id] = market_info

        return significant_changes


if __name__ == '__main__':
    email = 'danilashkirdow@mail.ru'
    password = 'Dd170296dD!'
    client = UbisoftMarketClient(email=email, password=password)

    # Первая попытка авторизации
    try:
        client.refresh_token()
    except Exception as e:
        if "twoFactorAuthenticationTicket" in str(e):
            print("Требуется двухфакторная аутентификация.")
            two_factor_code = input("Введите код 2FA: ")
            client.authenticate_with_2fa(two_factor_code)
        else:
            raise
    analyzer = MarketAnalyzer()
    selling_list = []
    while True:
        all_items = []
        for i in range(5):
            response = client.get_sellable_items(
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
                    result = client.create_sell_order(
                        space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                        item_id=change['item_id'],
                        quantity=1,
                        price=5000
                    )
                    print(f"Ордера создан: {result}")
                    selling_list.append(change['item_id'])
                except Exception as e:
                    print(f"Ошибка при создании ордера: {e}")

            print(f"Резкое изменение у предмета {change['name']} (ID: {change['item_id']})")
            print(f"Изменение цены: {change['price_change']}")
            print(f"Изменение активных предложений: {change['active_count_change']}")
            print("---")

        time.sleep(5)