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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                type TEXT,
                item_id TEXT UNIQUE,
                tags TEXT,
                asset_url TEXT
            )
        """)

        # Создание таблицы для истории цен
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT,
                lowest_price INTEGER,
                highest_price INTEGER,
                active_listings INTEGER,
                last_sold_price INTEGER,
                last_sold_at TEXT,
                lowest_buy_price INTEGER,
                highest_buy_price INTEGER,
                active_buy_count INTEGER,
                FOREIGN KEY (item_id) REFERENCES items (item_id)
            )
        """)

        self.connection.commit()

    def has_identical_previous_record(self, cursor, item_id: str, market_info: Dict) -> bool:
        """Проверяет, есть ли идентичная предыдущая запись для данного предмета."""
        cursor.execute("""
            SELECT 
                lowest_price, highest_price, active_listings,
                last_sold_price, last_sold_at, lowest_buy_price,
                highest_buy_price, active_buy_count
            FROM price_history 
            WHERE item_id = ? 
            ORDER BY id DESC 
            LIMIT 1
        """, (item_id,))

        last_record = cursor.fetchone()
        if not last_record:
            return False

        # Преобразуем last_sold_at в строку ISO формата для сравнения
        current_last_sold_at = (market_info["last_sold_at"].isoformat()
                              if market_info["last_sold_at"] else None)

        # Сравниваем все значения
        current_values = (
            market_info["lowest_price"],
            market_info["highest_price"],
            market_info["active_listings"],
            market_info["last_sold_price"],
            current_last_sold_at,
            market_info["lowest_buy_price"],
            market_info["highest_buy_price"],
            market_info["active_buy_count"]
        )

        return current_values == last_record

    def insert_item(self, item: Dict):
        """Добавление или обновление предмета в базе данных и запись истории цен."""
        try:
            cursor = self.connection.cursor()

            # Вставка или обновление основной информации о предмете
            cursor.execute("""
                INSERT OR REPLACE INTO items (
                    name, type, item_id, tags, asset_url
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                item["name"],
                item["type"],
                item["item_id"],
                ",".join(item["tags"]),
                item["asset_url"]
            ))

            # Проверяем, есть ли идентичная предыдущая запись
            if not self.has_identical_previous_record(cursor, item["item_id"], item["market_info"]):
                # Записываем новые данные только если они отличаются
                cursor.execute("""
                    INSERT INTO price_history (
                        item_id, lowest_price, highest_price, active_listings,
                        last_sold_price, last_sold_at, lowest_buy_price,
                        highest_buy_price, active_buy_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item["item_id"],
                    item["market_info"]["lowest_price"],
                    item["market_info"]["highest_price"],
                    item["market_info"]["active_listings"],
                    item["market_info"]["last_sold_price"],
                    item["market_info"]["last_sold_at"].isoformat() if item["market_info"]["last_sold_at"] else None,
                    item["market_info"]["lowest_buy_price"],
                    item["market_info"]["highest_buy_price"],
                    item["market_info"]["active_buy_count"]
                ))

            self.connection.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при вставке предмета: {e}")

    def get_price_history(self, item_id: str, limit: int = 100):
        """Получение истории цен для конкретного предмета."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM price_history 
                WHERE item_id = ? 
                ORDER BY id DESC 
                LIMIT ?
            """, (item_id, limit))
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении истории цен: {e}")
            return []

    def close_connection(self):
        """Закрытие соединения с базой данных."""
        if self.connection:
            self.connection.close()