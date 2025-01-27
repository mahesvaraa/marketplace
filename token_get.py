import time
import requests
import json
import subprocess
from websocket import create_connection

def get_auth_token():
    # Запускаем Chrome с необходимыми параметрами
    subprocess.Popen([
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "--remote-debugging-port=9222",
        "--user-data-dir=C:\\ChromeDebug",
        "--remote-allow-origins=http://127.0.0.1:9222",
        "https://www.ubisoft.com/ru-ru/game/rainbow-six/siege/marketplace?route=transactions",
    ])

    # Ждём, чтобы браузер успел загрузиться
    time.sleep(10)

    # Подключаемся к DevTools Protocol
    DEBUGGER_URL = "http://127.0.0.1:9222/json"
    tabs = requests.get(DEBUGGER_URL).json()

    # Берём первую вкладку
    tab = tabs[0]['webSocketDebuggerUrl']
    ws = create_connection(tab)

    # Выполняем JavaScript для получения токена
    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": "localStorage.getItem('PRODOverlayConnectLoginData')"
        }
    }))

    # Обрабатываем ответ
    response = json.loads(ws.recv())
    ws.close()

    # Извлекаем токен из результата
    token_data = json.loads(response['result']['result']['value'])
    token = f"ubi_v1 t={token_data['ticket']}"
    return token

# Пример использования
if __name__ == "__main__":
    auth_token = get_auth_token()
    print(f"Auth Token: {auth_token}")