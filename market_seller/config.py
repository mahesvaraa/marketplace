# config.py
from datetime import timedelta

# Основные настройки
SELL_PRICE = 15432  # Цена продажи при больших изменениях
FREQ_SELL_PRICE = 2498  # Цена продажи при частых изменениях
EXTREME_SELL_PRICE = 498  # Цена продажи если уже прошла продажа свыше EXTREME_PRICE_CHANGE
RESERVE_ITEM_IDS = []  # Список айдишников предметов , которые не будут сняты автоснятием
MAX_AGE_MINUTES_TRADE = 15  # Время после которого товар будет снят
USE_SOUND = False  # Пиликать или нет на всякие действия
DIFFERENCE_SELL_PRICE = 0.2  # Изменение максимальной цены продаж, при котором попытаться оформить заказ

# Скрипт для выкупа предметов
LIMIT_MASS_BUY_PRICE = 30  # Макс цена по которой выкупится предмет
PAGES_TO_FETCH_BUY = 8  # Количество страниц которые парсит (по необходимости увеличивать)

# Настройки лимитов и интервалов
DEFAULT_SELL_PRICE = 9900  # Дефолтная цена. Не трогать, смысла нет
ITEMS_LIMIT = 40  # Кол-во предметов для парсинга одной страницы (40 макс)
PAGES_TO_FETCH = 8  # Кол-во страниц для парсинга
TOKEN_REFRESH_INTERVAL = timedelta(minutes=15)  # Интервал обновления токена
TRADES_CANCEL_CHECK_INTERVAL = timedelta(minutes=5)  # Интервал проверок отмены заказов
RESTART_INTERVAL = timedelta(minutes=60)  # Интервал обновления для перезапуска
SLEEP_INTERVAL = 2.5  # Время между проверками
RESTART_DELAY = 2  # Таймаут между перезапусками (те которые 60 минут)
HISTORY_FREQUENT_SIZE = 5  # Сколько изменений хранить для "частых" изменений (ПОКА ВЫКЛЮЧЕНО)
FREQUENCY = 6  # на какое число совпадений реагировать (ПОКА ВЫКЛЮЧЕНО)

# Параметры маркета
SIGNIFICANT_PRICE_CHANGE = 500  # Изменение цены на которое будет срабатывать продажа
SIGNIFICANT_ACTIVE_COUNT_CHANGE = 1  # Если больше N продаж было
EXTREME_PRICE_CHANGE = 7000  # Выше этого изменения цены будет игнор


# Пути и токены
SPACE_ID = "0d2ae42d-4c27-4cb7-af6c-2099062302bb"
SOUND_PATH = r"C:\Windows\Media\Windows Logon.wav"
MARKETPLACE_URL_TEMPLATE = (
    "https://www.ubisoft.com/ru-ru/game/rainbow-six/siege/marketplace?route=sell%2Fitem-details&itemId={}"
)

# Ошибки
ERROR_MAPPING = {
    "{'code': 1895}": "Ошибка: Товар пока нельзя продавать",
    "{'code': 1898}": "Ошибка: НЕТ СВОБОДНЫХ СЛОТОВ ДЛЯ ПРОДАЖИ",
    "{'code': 1821}": "Ошибка: Товар уже продается",
}


# market_client
API_URL = "https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql"
DEFAULT_PAYMENT_ITEM_ID = "9ef71262-515b-46e8-b9a8-b6b6ad456c67"
DEFAULT_LIMIT = 100
DEFAULT_SORT_FIELD = "ACTIVE_COUNT"
DEFAULT_SORT_DIRECTION = "ASC"
DEFAULT_MARKETABLE_LIMIT = 40
DEFAULT_MARKETABLE_SORT_FIELD = "LAST_TRANSACTION_PRICE"
DEFAULT_MARKETABLE_SORT_DIRECTION = "DESC"


# auth

# Константы
TOKEN_FILE = "auth_token.json"
TOKEN_LIFETIME_HOURS = 1
REFRESH_INTERVAL_MINUTES = 20

# URL и заголовки
BASE_URL = "https://public-ubiservices.ubi.com/v3"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Ubi-AppId": "685a3038-2b04-47ee-9c5a-6403381a46aa",
    "Ubi-RequestedPlatformType": "uplay",
    "Accept": "*/*",
    "Origin": "https://connect.ubisoft.com",
    "Referer": "https://connect.ubisoft.com/",
    "accept-language": "ru-RU,ru;q=0.9",
}
