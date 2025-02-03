from typing import Dict, List

import winsound


class MarketAnalyzer:
    def __init__(self, client):
        self.previous_data = {}
        self.client = client
        self.selling_list = []

    async def create_sell_order(self, item_data, price=9900):
        if (item_data.get("price_change") > 100 or item_data.get("active_count_change") > 1) and item_data.get("item_id") not in self.selling_list:
            if item_data.get("price_change") > 7000:
                self.selling_list.append(item_data)
                return
            winsound.PlaySound(
                "C:\Windows\Media\Windows Logon.wav", winsound.SND_FILENAME
            )
            print(
                f"Создание ордера на продажу для предмета {item_data.get('name')} (ID: {item_data.get('item_id')})"
            )
            try:
                result = await self.client.create_sell_order(
                    space_id="0d2ae42d-4c27-4cb7-af6c-2099062302bb",
                    item_id=item_data.get("item_id"),
                    quantity=1,
                    price=price,
                )
                print(f"Ордер создан: {result}")
                trade_id = result.get("createSellOrder").get("trade")[
                    "id"
                ]  # Получаем правильный trade_id
                self.selling_list.append(item_data.get("item_id"))
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
                    print("Ошибка при создании ордера. Товар пока нельзя продавать")
                    self.selling_list.append(item_data.get("item_id"))
                elif "{'code': 1821}" in str(e):
                    print("Ошибка при создании ордера. Товар уже продается")
                    self.selling_list.append(item_data.get("item_id"))
                elif "Invalid Ticket".lower() in str(e).lower():
                    self.client.auth.refresh_token()
                else:
                    print(f"Ошибка при создании ордера: {e}")

    @staticmethod
    def print_change_info(item_data):
        print(
            f"Резкое изменение у предмета {item_data.get('name')} \n"
            f"(ID: https://www.ubisoft.com/ru-ru/game/rainbow-six/siege/marketplace?"
            f"route=sell%2Fitem-details&itemId={item_data.get('item_id')})"
        )
        if item_data.get("price_change"):
            print(f"Изменение цены: {item_data.get('price_change')}")
        print(
            f"Изменение активных предложений: {item_data.get('active_count_change')} "
            f"(Всего: {item_data.get('active_listings')})"
        )
        print("---")

    async def analyze(self, items: List[Dict], sell_price=9900):
        significant_changes = []

        for item in items:
            item_id = item.get("item_id")
            market_info = item.get("market_info")

            if item_id in self.previous_data:
                previous_market_info = self.previous_data[item_id]

                if market_info.get("last_sold_price") and previous_market_info.get(
                    "last_sold_price"
                ):
                    price_change = market_info.get(
                        "last_sold_price"
                    ) - previous_market_info.get("last_sold_price")
                    active_count_change = previous_market_info.get(
                        "active_listings"
                    ) - market_info.get("active_listings")

                    if abs(price_change) > 0 or active_count_change > 0:
                        change_data = {
                            "item_id": item_id,
                            "name": item.get("name"),
                            "price_change": price_change,
                            "active_count_change": active_count_change,
                            "new_price": market_info.get("last_sold_price"),
                            "old_price": previous_market_info.get("last_sold_price"),
                            "active_listings": market_info.get("active_listings"),
                            "type": item.get("type"),
                            "owner": item.get("tags")[0].split(".")[-1],
                            "active_buy_count": market_info.get("active_buy_count", 0),
                            "buy_range": f'{market_info.get("lowest_buy_price")} - {market_info.get("highest_buy_price")}',
                            "highest_buy_price": market_info.get("highest_buy_price"),
                        }
                        significant_changes.append(change_data)

                        # Немедленный вызов create_sell_order
                        await self.create_sell_order(change_data, sell_price)

            self.previous_data[item_id] = market_info

        return significant_changes
