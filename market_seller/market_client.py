import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp

from config import *
from market_seller.other.auth import UbisoftAuth
from market_seller.other.database import DatabaseManager
from market_seller.other.requests_params import RequestsParams
from market_seller.other.utils import play_notification_sound, async_retry


class AsyncUbisoftMarketClient:
    def __init__(
        self,
        auth: UbisoftAuth,
        logger,
        db_name: str = "ubisoft_market.db",
    ):
        self.headers = self._build_headers(auth.token)
        self.auth = auth
        self.session = None
        self.db = DatabaseManager(db_name)
        self.logger = logger

    @staticmethod
    def _build_headers(token: str) -> Dict[str, str]:
        """Build headers for API requests"""
        return {
            "content-type": "application/json",
            "Authorization": f"ubi_v1 t={token}",
            "Ubi-AppId": "e3d5ea9e-50bd-43b7-88bf-39794f4e3d40",
            "Ubi-SessionId": "88c422ca-73c4-437f-92e3-25f03b08cc2b",
            "User-Agent": "UbiServices_SDK_2020.Release.58_PC64_ansi_static",
            "Ubi-Localecode": "ru-RU",
            "Ubi-Countryid": "RU",
        }

    @staticmethod
    def _build_payment_option(price: int) -> Dict:
        """Build payment option structure"""
        return {
            "paymentItemId": DEFAULT_PAYMENT_ITEM_ID,
            "price": price,
        }

    @staticmethod
    def _build_sort_params(field: str, direction: str, payment_item_id: str = DEFAULT_PAYMENT_ITEM_ID) -> Dict:
        """Build sorting parameters"""
        return {
            "field": field,
            "orderType": "Sell",
            "direction": direction,
            "paymentItemId": payment_item_id,
        }

    @staticmethod
    def _build_filter_params(
        item_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        hide_owned: bool = False,
    ) -> Dict:
        """Build filter parameters"""
        return {
            "types": item_types or [],
            "tags": tags or [],
            "hideOwned": hide_owned,
        }

    async def init_session(self):
        """Initialize aiohttp session if not exists"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Close aiohttp session and database connection"""
        if self.session:
            await self.session.close()
            self.session = None
            self.db.close_connection()

    async def _handle_response_errors(self, response: aiohttp.ClientResponse, result: Dict):
        """Handle various API response errors"""
        if response.status != 200:
            error_text = await response.text()
            self.logger.error(f"Query failed with status {response.status}: {error_text}")

        if "errors" in result and "cancelOrder" not in str(result):
            play_notification_sound()
            self.auth.refresh_session_with_remember_me()
            self.logger.error(f"GraphQL errors: {result.get('errors')[0].get('message')}")
            raise Exception(f"GraphQL errors: {result.get('errors')}")

    async def execute_query(self, query: str, variables: dict) -> Dict:
        """Execute GraphQL query with error handling and retries"""
        payload = {"query": query, "variables": variables}

        if not self.session:
            await self.init_session()

        async with self.session.post(API_URL, json=payload, headers=self.headers, timeout=10) as response:
            result = await response.json()
            await self._handle_response_errors(response, result)
            return result.get("data", [])

    @staticmethod
    def _create_trade_data(
        space_id: str,
        trade_id: str,
        item_id: Optional[str],
        quantity: Optional[int],
        price: int,
        is_update: bool = False,
    ) -> Dict:
        """Create trade data structure for database"""
        trade_data = {
            "space_id": space_id,
            "trade_id": trade_id,
            "item_id": item_id,
            "quantity": quantity,
            "price": price,
        }

        if is_update:
            trade_data["updated_at"] = datetime.utcnow().isoformat()
        else:
            trade_data["created_at"] = datetime.utcnow().isoformat()

        return trade_data

    async def create_sell_order(self, space_id: str, item_id: str, quantity: int, price: int) -> Dict:
        mutation = RequestsParams.CREATE_SELL_ORDER_REQUEST
        variables = {
            "spaceId": space_id,
            "tradeItems": [{"itemId": item_id, "quantity": quantity}],
            "paymentOptions": [self._build_payment_option(price)],
        }

        try:
            result = await self.execute_query(mutation, variables)
            trade_id = result.get("createSellOrder").get("trade").get("tradeId")

            trade_data = self._create_trade_data(space_id, trade_id, item_id, quantity, price)
            self.db.insert_sell_order(trade_data)
            # self.logger.info(f"Successfully created sell order: {trade_data}")
            return result
        except Exception as e:
            # self.logger.error(f"Error creating sell order: {str(e)}")
            raise e

    async def update_sell_order(self, space_id: str, trade_id: str, price: int) -> Dict:
        mutation = RequestsParams.UPDATE_SELL_ORDER_REQUEST
        variables = {
            "spaceId": space_id,
            "tradeId": trade_id,
            "paymentOptions": [self._build_payment_option(price)],
        }

        try:
            result = await self.execute_query(mutation, variables)
            trade_data = self._create_trade_data(space_id, trade_id, None, None, price, is_update=True)
            self.db.insert_sell_order(trade_data)
            self.logger.info(f"Successfully updated sell order: {trade_data}")
            return result
        except Exception as e:
            self.logger.error(f"Error updating sell order: {str(e)}")

    @staticmethod
    def _parse_stats(stats: Optional[List[Dict]], default: Dict = None) -> Dict:
        """Parse market statistics"""
        return stats[0] if stats else (default or {})

    @staticmethod
    def _parse_market_item(
        item_data: Dict,
        market_data: Dict,
        sell_stats: Dict,
        last_sold: Dict,
        buy_stats: Dict,
    ) -> Dict:
        """Parse individual market item data"""
        return {
            "name": item_data.get("name"),
            "type": item_data.get("type"),
            "item_id": item_data.get("itemId"),
            "tags": item_data.get("tags"),
            "asset_url": item_data.get("assetUrl"),
            "market_info": {
                "lowest_price": sell_stats.get("lowestPrice"),
                "highest_price": sell_stats.get("highestPrice"),
                "active_listings": sell_stats.get("activeCount"),
                "last_sold_price": last_sold.get("price"),
                "last_sold_at": datetime.fromisoformat(last_sold.get("performedAt").replace("Z", "+00:00")),
                "lowest_buy_price": buy_stats.get("lowest_price", 0),
                "highest_buy_price": buy_stats.get("highestPrice", 0),
                "active_buy_count": buy_stats.get("activeCount", 0),
            },
        }

    def parse_market_data(self, response: Dict) -> List[Dict]:
        """Parse market data with error handling"""
        items = []
        try:
            nodes = response["game"]["viewer"]["meta"]["marketableItems"]["nodes"]
            for node in nodes:
                item_data = node.get("item")
                market_data = node.get("marketData")

                sell_stats = self._parse_stats(market_data.get("sellStats"))
                last_sold = self._parse_stats(market_data.get("lastSoldAt"))
                buy_stats = self._parse_stats(market_data.get("buyStats"))

                if sell_stats and last_sold:
                    parsed_item = self._parse_market_item(item_data, market_data, sell_stats, last_sold, buy_stats)
                    items.append(parsed_item)
                    # self.db.insert_item(parsed_item)
                    self.logger.debug(f"Parsed and stored item: {parsed_item['name']}")

            return items
        except Exception as e:
            self.logger.error(f"Error parsing market data: {str(e)}")

    @async_retry(max_retries=3, delay=1)
    async def get_sellable_items(
        self,
        space_id: str,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        item_types: List[str] = None,
        tags: List[str] = None,
        with_ownership: bool = False,
        sort_field: str = DEFAULT_SORT_FIELD,
        sort_direction: str = DEFAULT_SORT_DIRECTION,
        payment_item_id: str = DEFAULT_PAYMENT_ITEM_ID,
    ) -> Dict:
        query = RequestsParams.GET_SELLABLE_ITEMS_REQUEST
        variables = {
            "spaceId": space_id,
            "limit": limit,
            "offset": offset,
            "withOwnership": with_ownership,
            "filterBy": self._build_filter_params(item_types, tags),
            "sortBy": self._build_sort_params(sort_field, sort_direction, payment_item_id),
        }

        return await self.execute_query(query, variables)

    async def refresh_token_if_needed(self):
        """Refresh authentication token if expired"""
        if self.auth.is_token_expired():
            self.logger.info("Token expired, refreshing authentication...")
            self.auth.basic_auth(self.auth.email, self.auth.password)
            if self.auth.two_factor_ticket:
                code = input("Enter 2FA code: ")
                self.auth.complete_2fa(code)
                self.logger.info("2FA authentication completed")

    async def get_marketable_items(
        self,
        space_id: str,
        limit: int = DEFAULT_MARKETABLE_LIMIT,
        offset: int = 0,
        item_types: List[str] = None,
        tags: List[str] = None,
        hide_owned: bool = True,
        with_ownership: bool = True,
        sort_field: str = DEFAULT_MARKETABLE_SORT_FIELD,
        sort_direction: str = DEFAULT_MARKETABLE_SORT_DIRECTION,
        payment_item_id: str = DEFAULT_PAYMENT_ITEM_ID,
    ) -> Dict:
        query = RequestsParams.GET_MARKETABLE_ITEMS_QUERY
        variables = {
            "spaceId": space_id,
            "limit": limit,
            "offset": offset,
            "withOwnership": with_ownership,
            "filterBy": self._build_filter_params(item_types, tags, hide_owned),
            "sortBy": self._build_sort_params(sort_field, sort_direction, payment_item_id),
        }

        try:
            return await self.execute_query(query, variables)
        except Exception as e:
            self.logger.error(f"Error fetching marketable items: {str(e)}")
            await asyncio.sleep(5)
            raise

    async def get_pending_trades(
        self,
        space_id: str,
        limit: int = 40,
        offset: int = 0,
    ) -> Dict:
        """
        Get information about pending trade orders.

        Parameters:
        space_id (str): The space ID to query trades for
        limit (int): Maximum number of trades to return (default: 40)
        offset (int): Number of trades to skip (default: 0)

        Returns:
        Dict: Response containing pending trades information
        """
        query = RequestsParams.GET_PENDING_TRADES_QUERY

        variables = {"spaceId": space_id, "limit": limit, "offset": offset}

        try:
            return await self.execute_query(query, variables)
        except Exception as e:
            print(f"Error executing query: {str(e)}")
            asyncio.timeout(5)
            raise

    async def cancel_old_trade(self, space_id: str, trade_id: str) -> Dict:
        """
        Cancel a specific trade order.

        Parameters:
        space_id (str): The space ID
        trade_id (str): The ID of the trade to cancel

        Returns:
        Dict: Response containing cancel operation result
        """
        query = RequestsParams.CANCEL_OLD_TRADE_QUERY

        variables = {"spaceId": space_id, "tradeId": trade_id}

        try:
            return await self.execute_query(query, variables)
        except Exception as e:
            print(f"Error canceling trade {trade_id}: {str(e)}")
            raise

    async def monitor_and_cancel_old_trades(
        self,
        space_id: str,
        reserve_item_ids,
        max_age_minutes: int = MAX_AGE_MINUTES_TRADE,
    ) -> List[Dict]:
        """
        Monitor pending trades and cancel those older than specified time.

        Parameters:
        space_id (str): The space ID to monitor trades for
        max_age_minutes (int): Maximum age of trades in minutes before cancellation (default: 30)

        Returns:
        List[Dict]: List of cancelled trade responses
        """
        cancelled_trades = []

        try:
            # Get pending trades
            pending_trades = await self.get_pending_trades(space_id)

            if not pending_trades.get("game", {}).get("viewer", {}).get("meta", {}).get("trades", {}).get("nodes"):
                self.logger.info("Нет подходящих заказов для снятия")
                return cancelled_trades

            current_time = datetime.now(timezone.utc)

            # Process each trade
            for trade in pending_trades["game"]["viewer"]["meta"]["trades"]["nodes"]:
                if trade["category"] != "Sell" or trade["tradeItems"][0]["item"]["itemId"] in reserve_item_ids:
                    continue

                created_at = datetime.fromisoformat(trade["createdAt"].replace("Z", "+00:00"))
                age_minutes = (current_time - created_at).total_seconds() / 60
                name = trade["tradeItems"][0]["item"]["name"]

                if age_minutes > max_age_minutes:
                    self.logger.info(f"Заказ отменён {name} (Срок: {age_minutes:.1f} минут)")
                    try:
                        cancel_result = await self.cancel_old_trade(space_id, trade["tradeId"])
                        cancelled_trades.append(
                            {
                                "name": name,
                                "age_minutes": age_minutes,
                                "result": cancel_result,
                            }
                        )
                    except Exception as e:
                        self.logger.error(f"Ошибка при отмене заказа {trade['tradeId']}: {str(e)}")

                    # Add small delay between cancellations
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"Ошибка в авто-отмене заказов: {str(e)}")
            raise

        return cancelled_trades
