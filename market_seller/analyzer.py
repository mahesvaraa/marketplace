from typing import Dict, List, Optional

from config import *
from market_seller.other.utils import play_notification_sound


class MarketAnalyzer:
    def __init__(self, client, logger, bot=None):
        self.previous_data = {}
        self.client = client
        self.selling_list = []
        self.bot = bot
        self.logger = logger

    @staticmethod
    def _is_token_invalid(error: Exception) -> bool:
        """Проверка, является ли ошибка связанной с невалидным токеном."""
        return "Invalid Ticket".lower() in str(error).lower()

    async def create_sell_order(self, item_data: Dict, price: int = DEFAULT_SELL_PRICE):
        """Создание ордера на продажу с обработкой различных сценариев."""
        self.logger.info(self._format_order_creation_message(item_data))

        try:
            await self._execute_sell_order(item_data, price)
            self._handle_successful_order(item_data, price)
            await self.bot.notify_order_created(item_data)
            play_notification_sound()
        except Exception as e:
            self._handle_order_creation_error(e, item_data)

    @staticmethod
    def _format_order_creation_message(item_data: Dict) -> str:
        """Форматирование сообщения о создании ордера."""
        return f"\nСоздание ордера на продажу для {item_data.get('name')} " f"(ID: {item_data.get('item_id')})"

    async def _execute_sell_order(self, item_data: Dict, price: int):
        """Выполнение операции создания ордера."""
        return await self.client.create_sell_order(
            space_id=SPACE_ID,
            item_id=item_data.get("item_id"),
            quantity=1,
            price=price,
        )

    def _handle_successful_order(self, item_data: Dict, price: int):
        """Обработка успешного создания ордера."""
        self.logger.info(f"Ордер создан: {item_data.get('name')} за {price}")
        self.selling_list.append(item_data.get("item_id"))
        self.print_change_info(item_data)

    def _handle_order_creation_error(self, error: Exception, item_data: Dict):
        """Обработка ошибок при создании ордера."""
        error_message = str(error)

        for error_code, message in ERROR_MAPPING.items():
            if error_code in error_message:
                self.logger.warning(message)
                self.selling_list.append(item_data.get("item_id"))
                return

        if self._is_token_invalid(error):
            self.logger.warning("Невалидный токен, обновляем...")
            self.client.auth.refresh_token()
        else:
            self.logger.error(f"Ошибка при создании ордера: {error}")
            play_notification_sound()

    def print_change_info(self, item_data: Dict):
        """Вывод детальной информации об изменении предмета."""
        change_info = (
            f"\n---\n"
            f"Резкое изменение у {item_data.get('name')}\n"
            f"(ID: {MARKETPLACE_URL_TEMPLATE.format(item_data.get('item_id'))})\n"
            f"Изменение цены: {item_data.get('price_change')}\n"
            f"Изменение активных предложений: {item_data.get('active_count_change')} "
            f"(Всего: {item_data.get('active_listings')})\n"
            "---"
        )
        self.logger.info(change_info)

    @staticmethod
    def _calculate_market_changes(current_market_info: Dict, previous_market_info: Dict) -> Optional[Dict]:
        """Расчет изменений на рынке для конкретного предмета."""
        if not (current_market_info.get("last_sold_price") and previous_market_info.get("last_sold_price")):
            return None

        price_change = current_market_info.get("last_sold_price") - previous_market_info.get("last_sold_price")
        active_count_change = previous_market_info.get("active_listings") - current_market_info.get("active_listings")

        last_sold_date = current_market_info.get("last_sold_at")
        prev_last_sold_date = previous_market_info.get("last_sold_at")

        return (abs(price_change) > 0 or active_count_change > 0) and last_sold_date != prev_last_sold_date

    @staticmethod
    def _prepare_change_data(item: Dict, market_info: Dict, previous_market_info: Dict) -> Dict:
        """Подготовка данных об изменениях."""
        return {
            "item_id": item.get("item_id"),
            "name": item.get("name"),
            "asset_url": item.get("asset_url"),
            "price_change": market_info.get("last_sold_price") - previous_market_info.get("last_sold_price"),
            "active_count_change": previous_market_info.get("active_listings") - market_info.get("active_listings"),
            "new_price": market_info.get("last_sold_price"),
            "old_price": previous_market_info.get("last_sold_price"),
            "active_listings": market_info.get("active_listings"),
            "type": item.get("type"),
            "owner": item.get("tags", [""])[0].split(".")[-1],
            "active_buy_count": market_info.get("active_buy_count", 0),
            "sell_range": f'{market_info.get("lowest_price")} - {market_info.get("highest_price")}',
            "highest_price": market_info.get("highest_price"),
            "buy_range": f'{market_info.get("lowest_buy_price")} - {market_info.get("highest_buy_price")}',
            "highest_buy_price": market_info.get("highest_buy_price"),
        }

    async def analyze(self, items: List[Dict], sell_price: int = DEFAULT_SELL_PRICE):
        """Основной метод анализа рыночных данных."""
        significant_changes = []

        for item in items:
            item_id = item.get("item_id")
            market_info = item.get("market_info")

            if item_id in self.previous_data:
                previous_market_info = self.previous_data[item_id]

                if self._calculate_market_changes(market_info, previous_market_info):
                    change_data = self._prepare_change_data(item, market_info, previous_market_info)
                    significant_changes.append(change_data)

                    if self._should_create_sell_order(change_data):
                        await self._process_sell_order(change_data, sell_price)

                if previous_market_info.get('highest_price') / market_info.get("highest_price") <= DIFFERENCE_SELL_PRICE:

                    change_data = self._prepare_change_data(item, market_info, previous_market_info)
                    await self._process_sell_order(change_data, market_info.get("highest_price") - 10)

            self.previous_data[item_id] = market_info

        return significant_changes

    def _should_create_sell_order(self, change_data: Dict) -> bool:
        """Определение необходимости создания ордера на продажу."""
        is_significant_change = change_data.get("price_change", 0) > SIGNIFICANT_PRICE_CHANGE or change_data.get("active_count_change", 0) > SIGNIFICANT_ACTIVE_COUNT_CHANGE
        is_not_selling = change_data.get("item_id") not in self.selling_list
        return is_significant_change and is_not_selling

    async def _process_sell_order(self, change_data: Dict, sell_price: int):
        """Обработка создания ордера на продажу."""
        if change_data.get("price_change", 0) > EXTREME_PRICE_CHANGE:
            self.selling_list.append(change_data)
            await self.create_sell_order(change_data, EXTREME_SELL_PRICE)
        else:
            await self.create_sell_order(change_data, sell_price)
