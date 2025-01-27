import sqlite3
from datetime import datetime
from typing import Dict


class DatabaseManager:
    def __init__(self, db_name: str = "ubisoft_market.db"):
        self.db_name = db_name
        self.connection = None
        self.init_database()

    def init_database(self):
        """Создание таблиц базы данных, если они отсутствуют."""
        self.connection = sqlite3.connect(self.db_name)
        cursor = self.connection.cursor()

        # Создание таблицы для предметов
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            type TEXT,
            item_id TEXT UNIQUE,
            tags TEXT,
            asset_url TEXT,
            lowest_price INTEGER,
            highest_price INTEGER,
            active_listings INTEGER,
            last_sold_price INTEGER,
            last_sold_at TEXT
        )
        """
        )

        # Создание таблицы для ордеров
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS sell_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            space_id TEXT,
            trade_id TEXT UNIQUE,
            item_id TEXT,
            quantity INTEGER,
            price INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
        """
        )

        self.connection.commit()

    def insert_item(self, item: Dict):
        """Добавление предмета в базу данных."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
            INSERT OR REPLACE INTO items (
                name, type, item_id, tags, asset_url, lowest_price,
                highest_price, active_listings, last_sold_price, last_sold_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item["name"],
                    item["type"],
                    item["item_id"],
                    ",".join(item["tags"]),
                    item["asset_url"],
                    item["market_info"]["lowest_price"],
                    item["market_info"]["highest_price"],
                    item["market_info"]["active_listings"],
                    item["market_info"]["last_sold_price"],
                    (
                        item["market_info"]["last_sold_at"].isoformat()
                        if item["market_info"]["last_sold_at"]
                        else None
                    ),
                ),
            )
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при вставке предмета: {e}")

    def insert_sell_order(self, order: Dict):
        """Добавление ордера на продажу в базу данных."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
            INSERT OR REPLACE INTO sell_orders (
                space_id, trade_id, item_id, quantity, price, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    order["space_id"],
                    order["trade_id"],
                    order["item_id"],
                    order["quantity"],
                    order["price"],
                    order.get("created_at", datetime.utcnow().isoformat()),
                    order.get("updated_at", datetime.utcnow().isoformat()),
                ),
            )
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при вставке ордера: {e}")

    def close_connection(self):
        """Закрытие соединения с базой данных."""
        if self.connection:
            self.connection.close()
