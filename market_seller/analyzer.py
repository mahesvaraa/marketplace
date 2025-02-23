from typing import List, Optional, Dict

from config import *
from market_seller.other.utils import play_notification_sound, DotDict
from other.market_changer import MarketChangesTracker


class MarketAnalyzer:
    def __init__(self, client, logger, bot=None):
        self.previous_data = {}
        self.client = client
        self.selling_list = []
        self.bot = bot
        self.logger = logger
        self.tracker = MarketChangesTracker(history_size=HISTORY_FREQUENT_SIZE)
        self.price_drop_orders: Dict[str, Dict] = {}  # item_id -> {trade_id, price}

    @staticmethod
    def _is_token_invalid(error: Exception) -> bool:
        """Проверка, является ли ошибка связанной с невалидным токеном."""
        return "Invalid Ticket".lower() in str(error).lower()

    async def create_sell_order(self, item_data: DotDict, price: int = DEFAULT_SELL_PRICE):
        """Создание ордера на продажу с обработкой различных сценариев."""
        self.logger.info(self._format_order_creation_message(item_data))

        try:
            response = await self._execute_sell_order(item_data, price)
            self._handle_successful_order(item_data, price, response)
            await self.bot.notify_order_created(item_data)
            play_notification_sound()
        except Exception as e:
            self._handle_order_creation_error(e, item_data)

    @staticmethod
    def _format_order_creation_message(item_data: DotDict) -> str:
        """Форматирование сообщения о создании ордера."""
        return f"\nСоздание ордера на продажу для {item_data.name} " f"(ID: {item_data.item_id})"

    async def _execute_sell_order(self, item_data: DotDict, price: int):
        """Выполнение операции создания ордера."""
        return await self.client.create_sell_order(
            space_id=SPACE_ID,
            item_id=item_data.item_id,
            quantity=1,
            price=price,
        )

    def _handle_successful_order(self, item_data: DotDict, price: int, response: dict):
        """Обработка успешного создания ордера."""
        self.logger.info(f"Ордер создан: {item_data.name} за {price}")
        self.selling_list.append(item_data.item_id)

        # Если ордер создан из-за падения цены, сохраняем его
        if item_data.item_id in self.previous_data:
            prev_info = self.previous_data[item_data.item_id]
            if prev_info.highest_price / price <= DIFFERENCE_SELL_PRICE:
                trade_id = response["createSellOrder"]["trade"]["tradeId"]
                self.price_drop_orders[item_data.item_id] = {"trade_id": trade_id, "price": price}
                self.logger.info(f"Сохранен ордер на падении цены: {item_data.name} (ID: {trade_id})")

        self.print_change_info(item_data)

    def _handle_order_creation_error(self, error: Exception, item_data: DotDict):
        """Обработка ошибок при создании ордера."""
        error_message = str(error)

        for error_code, message in ERROR_MAPPING.items():
            if error_code in error_message:
                self.logger.warning(message)
                self.selling_list.append(item_data.item_id)
                return

        if self._is_token_invalid(error):
            self.logger.warning("Невалидный токен, обновляем...")
            self.client.auth.refresh_token()
        else:
            play_notification_sound()

    def print_change_info(self, item_data: DotDict):
        """Вывод детальной информации об изменении предмета."""
        change_info = (
            f"\n---\n"
            f"Резкое изменение у {item_data.name}\n"
            f"(ID: {MARKETPLACE_URL_TEMPLATE.format(item_data.item_id)})\n"
            f"Изменение цены: {item_data.price_change}\n"
            f"Изменение активных предложений: {item_data.active_count_change} "
            f"(Всего: {item_data.active_listings})\n"
            "---"
        )
        self.logger.info(change_info)

    @staticmethod
    def _calculate_market_changes(current_market_info: DotDict, previous_market_info: DotDict) -> Optional[DotDict]:
        """Расчет изменений на рынке для конкретного предмета."""
        if not (current_market_info.last_sold_price and previous_market_info.last_sold_price):
            return None

        price_change = current_market_info.last_sold_price - previous_market_info.last_sold_price
        active_count_change = previous_market_info.active_listings - current_market_info.active_listings

        last_sold_date = current_market_info.last_sold_at
        prev_last_sold_date = previous_market_info.last_sold_at

        return (abs(price_change) > 0 or active_count_change > 0) and last_sold_date != prev_last_sold_date

    @staticmethod
    def _prepare_change_data(item: DotDict, market_info: DotDict, previous_market_info: DotDict) -> DotDict:
        """Подготовка данных об изменениях."""
        return DotDict(
            {
                "item_id": item.item_id,
                "name": item.name,
                "asset_url": item.asset_url,
                "price_change": market_info.last_sold_price - previous_market_info.last_sold_price,
                "active_count_change": previous_market_info.active_listings - market_info.active_listings,
                "new_price": market_info.last_sold_price,
                "old_price": previous_market_info.last_sold_price,
                "active_listings": market_info.active_listings,
                "type": item.type,
                "owner": item.get("tags", [""])[0].split(".")[-1],
                "active_buy_count": market_info.get("active_buy_count", 0),
                "sell_range": f"{market_info.lowest_price} - {market_info.highest_price}",
                "highest_price": market_info.highest_price,
                "buy_range": f"{market_info.lowest_buy_price} - {market_info.highest_buy_price}",
                "highest_buy_price": market_info.highest_buy_price,
            }
        )

    async def check_and_cancel_price_drop_orders(self, item_data: DotDict, market_info: DotDict):
        """Проверка и отмена ордеров, созданных при падении цены."""
        item_id = item_data.item_id
        if item_id in self.price_drop_orders:
            order_info = self.price_drop_orders[item_id]
            if market_info.data["highest_price"] == order_info["price"]:
                try:
                    await self.client.cancel_old_trade(space_id=SPACE_ID, trade_id=order_info["trade_id"])
                    self.logger.info(
                        f"Отменен ордер {order_info['trade_id']} для {item_data.name} "
                        f"так как последняя цена совпадает с нашей ({order_info['price']})"
                    )
                    del self.price_drop_orders[item_id]
                except Exception as e:
                    self.logger.error(f"Ошибка при отмене ордера: {e}")

    async def analyze(self, items: List[DotDict], sell_price: int = DEFAULT_SELL_PRICE):
        """Основной метод анализа рыночных данных."""
        significant_changes = []

        for item in items:
            item_id = item.item_id
            market_info = item.market_info
            # Проверяем и отменяем ордера при необходимости
            await self.check_and_cancel_price_drop_orders(item, market_info)

            if item_id in self.previous_data:
                previous_market_info = self.previous_data[item_id]

                if self._calculate_market_changes(market_info, previous_market_info):
                    change_data = self._prepare_change_data(item, market_info, previous_market_info)
                    significant_changes.append(change_data)

                    if self._should_create_sell_order(change_data):
                        await self._process_sell_order(change_data, sell_price)

                if previous_market_info.highest_price / market_info.highest_price <= DIFFERENCE_SELL_PRICE:
                    change_data = self._prepare_change_data(item, market_info, previous_market_info)
                    await self._process_sell_order(change_data, int(market_info.highest_price * 0.9))

            self.previous_data[item_id] = market_info

        if significant_changes:
            frequent_changes = self.tracker.add_changes(significant_changes, FREQUENCY)
            for change in significant_changes:
                self.logger.info(self.format_log_change_message(change))

            if frequent_changes:
                for change in frequent_changes:
                    await self.create_sell_order(change, FREQ_SELL_PRICE)
        return significant_changes

    def _should_create_sell_order(self, change_data: DotDict) -> bool:
        """Определение необходимости создания ордера на продажу."""
        is_significant_change = (
            change_data.get("price_change", 0) > SIGNIFICANT_PRICE_CHANGE
            or change_data.get("active_count_change", 0) > SIGNIFICANT_ACTIVE_COUNT_CHANGE
        )
        is_not_selling = change_data.item_id not in self.selling_list
        return is_significant_change and is_not_selling

    async def _process_sell_order(self, change_data: DotDict, sell_price: int):
        """Обработка создания ордера на продажу."""
        if change_data.get("price_change", 0) > EXTREME_PRICE_CHANGE:
            self.selling_list.append(change_data)
            await self.create_sell_order(change_data, EXTREME_SELL_PRICE)
        else:
            await self.create_sell_order(change_data, sell_price)

    @staticmethod
    def format_log_change_message(change: DotDict) -> str:
        """Форматирование лога с информацией об изменении."""
        ru_ru = {
            "CharacterUniform": "ФОРМА",
            "WeaponSkin": "СКИН НА ОРУЖИЕ",
            "CharacterHeadgear": "ШЛЕМ",
            "Charm": "ЗНАЧОК",
            "OperatorCardBackground": "ФОН",
            "OperatorCardPortrait": "ПОРТРЕТ",
            "WeaponAttachmentSkinSet": "СКИН НА МОДУЛИ",
        }
        return (
            f"{change.name:<29} | "
            f"{change.new_price:>7} | "
            f"{change.price_change:>7} | "
            f"{change.active_count_change:>3} | "
            f"{change.active_listings:>3} | "
            f"{ru_ru.get(change.type, change.type):<15} | "
            f"{change.owner:<18} | "
            f"{change.sell_range: <15} | "
            f"{change.active_buy_count:>3} | "
            f"{change.buy_range}"
        )
