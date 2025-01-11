from playwright.sync_api import sync_playwright
import time
from typing import Dict, Any, List
import logging
from collections import deque

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class MarketplaceMonitor:
    def __init__(self):
        self.tracked_items: Dict[str, Any] = {}
        self.price_history: Dict[str, deque] = {}
        self.min_orders = float('inf')
        self.history_size = 3
        self.previous_items = set()
        self.processed_items = set()  # Множество для хранения ID обработанных товаров

    def get_average_price(self, item_id: str) -> float:
        if item_id not in self.price_history:
            return 0
        return sum(self.price_history[item_id]) / len(self.price_history[item_id])

    def update_item(self, item_id: str, price: int, orders: int, is_new_scan: bool) -> bool:
        current_time = time.time()

        # Если товар уже был обработан, не открываем его снова
        if item_id in self.processed_items:
            return False

        if is_new_scan and self.min_orders != float('inf'):
            if item_id not in self.tracked_items:
                should_click = orders < self.min_orders
                if should_click:
                    logging.info(f"New item found with lower orders: ID={item_id}, Orders={orders}, Min Orders={self.min_orders}")
            else:
                avg_price = self.get_average_price(item_id)
                price_diff = abs(price - avg_price)
                should_click = price_diff > 100 and price_diff != avg_price
                if should_click:
                    logging.info(f"Price change detected: ID={item_id}, Avg={avg_price}, New={price}")

            if item_id not in self.price_history:
                self.price_history[item_id] = deque(maxlen=self.history_size)
            self.price_history[item_id].append(price)

            self.tracked_items[item_id] = {
                'price': price,
                'orders': orders,
                'last_updated': current_time
            }
            return should_click

        self.min_orders = min(self.min_orders, orders)
        return False

def wait_and_click_button(iframe, button_text: str):
    button = iframe.wait_for_selector(f"button:has-text('{button_text}')")
    if button:
        button.click()
        time.sleep(2)

def get_price_range(iframe) -> tuple:
    try:
        price_range_text = iframe.locator('[data-testid="price-tag-value"]').all()[1].text_content()

        if not price_range_text or ' - ' not in price_range_text:
            logging.warning("Invalid price range format")
            return None, None

        min_price, max_price = map(
            lambda x: int(x.replace('\xa0', '').strip()),
            price_range_text.split(' - ')
        )
        return min_price, max_price
    except Exception as e:
        logging.error(f"Error getting price range: {e}")
        return None, None

def process_item_card(iframe, monitor: MarketplaceMonitor, item_id: str):  # Добавлен параметр item_id
    try:
        # Get price range with retry
        for attempt in range(3):
            min_price, max_price = get_price_range(iframe)
            if min_price is not None and max_price is not None:
                break
            time.sleep(1)
        else:
            logging.error("Could not get price range after multiple attempts")
            return

        # Calculate average price
        avg_price = min_price // 2
        logging.info(f"Setting price to {avg_price} (range: {min_price}-{max_price})")

        # Find price input and enter average price
        price_input = iframe.wait_for_selector("input[type='text']", timeout=5000)
        if price_input:
            price_input.fill(str(avg_price))
            time.sleep(1)

        # Click "Place sell order" button
        sell_button = iframe.wait_for_selector("button:has-text('Разместить заказ на продажу')", timeout=5000)
        if sell_button:
            sell_button.click()
            time.sleep(1)

        # Wait for modal and click "Confirm"
        confirm_button = iframe.wait_for_selector("button:has-text('Подтвердить')", timeout=5000)
        if confirm_button:
            confirm_button.click()
            time.sleep(1)

            # Добавляем товар в список обработанных только после успешного подтверждения
            monitor.processed_items.add(item_id)
            logging.info(f"Item {item_id} successfully processed and added to processed items")

    except Exception as e:
        logging.error(f"Error processing item card: {e}")

def scan_items(iframe, monitor: MarketplaceMonitor, is_new_scan: bool):
    iframe.wait_for_selector("div[role='button']")
    items = iframe.query_selector_all("div[role='button']")

    logging.info(f"Scanning {len(items)} items...")

    current_items = set()

    for item in items:
        try:
            item_id = item.get_attribute("data-focusable-id")
            if not item_id:
                continue

            current_items.add(item_id)

            price = iframe.evaluate("""
                (el) => {
                    const priceContainer = Array.from(el.querySelectorAll('span')).find(span => span.textContent === 'Последняя цена');
                    if (priceContainer) {
                        const priceParent = priceContainer.parentElement;
                        const priceElement = priceParent.querySelector('[data-testid="price-tag-value"]');
                        return priceElement ? parseInt(priceElement.textContent.replace(/\s+/g, '')) : null;
                    }
                    return null;
                }
            """, item)

            if price is None:
                continue

            orders = iframe.evaluate("""
                (el) => {
                    const ordersContainer = Array.from(el.querySelectorAll('span')).find(span => span.textContent === 'Заказы: продажа');
                    if (ordersContainer) {
                        const ordersParent = ordersContainer.parentElement;
                        const ordersElement = ordersParent.querySelector('p');
                        return ordersElement ? parseInt(ordersElement.textContent.trim()) : null;
                    }
                    return null;
                }
            """, item)

            if orders is None:
                continue

            if monitor.update_item(item_id, price, orders, is_new_scan):
                logging.info(f"Clicking item: ID={item_id}, Price={price}, Orders={orders}")
                item.click()
                time.sleep(1)
                process_item_card(iframe, monitor, item_id)  # Передаем monitor и item_id

        except Exception as e:
            logging.error(f"Error processing item: {e}")

    if is_new_scan and monitor.previous_items:
        disappeared_items = monitor.previous_items - current_items
        if disappeared_items:
            logging.info(f"Items disappeared: {', '.join(list(disappeared_items)[:5])}...")

    monitor.previous_items = current_items

def main():
    monitor = MarketplaceMonitor()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.ubisoft.com/ru-ru/game/rainbow-six/siege/marketplace?route=sell")
        time.sleep(10)
        page.reload()
        time.sleep(30)
        input('Залогинься')

        while True:
            try:
                shadow_host = page.wait_for_selector("ubisoft-connect")
                if not shadow_host:
                    continue

                shadow_root = shadow_host.evaluate_handle("host => host.shadowRoot")
                iframe_element = shadow_root.evaluate_handle(
                    "root => root.querySelector('iframe')"
                )
                iframe = iframe_element.content_frame()

                wait_and_click_button(iframe, "История транзакций")
                wait_and_click_button(iframe, "Продать")

                scan_items(iframe, monitor, True)

                logging.info("Waiting 15 seconds before next scan...")
                time.sleep(15)

            except Exception as e:
                logging.error(f"Error in main loop: {e}")
                time.sleep(5)

        browser.close()

if __name__ == "__main__":
    main()