import base64
import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import requests
import winsound

TOKEN_FILE = "auth_token1.json"
TOKEN_LIFETIME_HOURS = 1
REFRESH_INTERVAL_MINUTES = 20


class UbisoftAuth:
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        self.base_url = "https://public-ubiservices.ubi.com/v3"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Ubi-AppId": "685a3038-2b04-47ee-9c5a-6403381a46aa",
            "Ubi-RequestedPlatformType": "uplay",
            "Accept": "*/*",
            "Origin": "https://connect.ubisoft.com",
            "Referer": "https://connect.ubisoft.com/",
        }
        self.session = requests.Session()
        self.two_factor_ticket = None
        self.token = None
        self.session_id = None
        self.token_expiry = None
        self.remember_me_ticket = None
        self._refresh_thread = None
        self._stop_refresh = False
        self.email = email
        self.password = password

        # Загрузка сохранённого токена при инициализации
        self.load_token()

    def start_token_refresh(self):
        """Запуск фонового потока для обновления токена"""
        if self._refresh_thread is None:
            self._stop_refresh = False
            self._refresh_thread = threading.Thread(
                target=self._token_refresh_loop, daemon=True
            )
            self._refresh_thread.start()

    def stop_token_refresh(self):
        """Остановка фонового потока для обновления токена"""
        self._stop_refresh = True
        if self._refresh_thread:
            self._refresh_thread.join()
            self._refresh_thread = None

    def _token_refresh_loop(self):
        """Фоновый цикл для обновления токена"""
        while not self._stop_refresh:
            time.sleep(REFRESH_INTERVAL_MINUTES * 60)
            if not self._stop_refresh:
                try:
                    self.refresh_token()
                except Exception as e:
                    print(f"Ошибка в цикле обновления токена: {e}")

    def refresh_token(self) -> Dict[str, Any]:
        """Обновление токена с использованием текущего токена"""
        if not self.token:
            return {"error": "Нет доступного токена"}

        url = f"{self.base_url}/profiles/sessions"
        headers = self.headers.copy()
        headers["Authorization"] = f"Ubi_v1 t={self.token}"

        try:
            response = self.session.post(
                url, headers=headers, json={"rememberMe": True}
            )
            response_data = response.json()

            if response.status_code != 200:
                print(f"Не удалось обновить токен. Статус: {response.status_code}")
                return response_data

            if "ticket" in response_data:
                self.token = response_data["ticket"]
                self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                self.token_expiry = datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)

                remember_me_ticket = response_data.get("rememberMeTicket")
                if remember_me_ticket:
                    self.remember_me_ticket = remember_me_ticket
                    self.headers["ubi-rememberdeviceticket"] = remember_me_ticket

                self.save_token(
                    self.token,
                    self.session_id,
                    self.two_factor_ticket,
                    self.remember_me_ticket,
                )
                print("Токен успешно обновлён")

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса при обновлении токена: {str(e)}")
            winsound.PlaySound("C:\\Windows\\Media\\Windows Logon.wav", winsound.SND_FILENAME)
            return {"error": str(e)}

    def clear_saved_data(self):
        """Очистка всех сохранённых данных аутентификации"""
        self.token = None
        self.session_id = None
        self.two_factor_ticket = None
        self.token_expiry = None
        self.remember_me_ticket = None
        if "Authorization" in self.headers:
            del self.headers["Authorization"]
        self.save_token(None, None, None, None)

    def load_token(self):
        """Загрузка токена из файла"""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r") as f:
                    data = json.load(f)
                    self.token = data.get("token")
                    self.session_id = data.get("session_id")
                    self.two_factor_ticket = data.get("two_factor_ticket")
                    self.remember_me_ticket = data.get("remember_me_ticket")
                    self.token_expiry = datetime.fromisoformat(
                        data.get("expiry", "2000-01-01T00:00:00")
                    )

                    if self.token:
                        self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                    if self.remember_me_ticket:
                        self.headers["ubi-rememberdeviceticket"] = self.remember_me_ticket

            except Exception as e:
                print(f"Ошибка при загрузке токена: {e}")
                self.clear_saved_data()

    @staticmethod
    def save_token(
        token: Optional[str],
        session_id: Optional[str] = None,
        two_factor_ticket: Optional[str] = None,
        remember_me_ticket: Optional[str] = None,
    ):
        """Сохранение токена в файл"""
        try:
            data = {
                "token": token,
                "session_id": session_id,
                "two_factor_ticket": two_factor_ticket,
                "remember_me_ticket": remember_me_ticket,
                "expiry": (
                    datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)
                ).isoformat(),
            }

            with open(TOKEN_FILE, "w") as f:
                json.dump(data, f)

        except Exception as e:
            print(f"Ошибка при сохранении токена: {e}")

    def is_token_expired(self) -> bool:
        """Проверка, истёк ли текущий токен"""
        if not self.token or not self.token_expiry:
            return True

        # Проверка времени истечения токена
        if datetime.now() > self.token_expiry:
            return True

        # Валидация токена через API
        try:
            response = self.session.get(
                f"{self.base_url}/profiles/me", headers=self.headers
            )
            return response.status_code != 200
        except Exception as e:
            print(f"Ошибка при проверке токена: {e}")
            return True

    def ensure_valid_token(self) -> bool:
        """Проверка и обновление токена, если это необходимо"""
        if self.is_token_expired():
            if self.token:
                try:
                    response = self.refresh_token()
                    if "ticket" in response:
                        return True
                except Exception as e:
                    print(f"Ошибка при обновлении токена: {e}")
                    winsound.PlaySound("C:\\Windows\\Media\\Windows Logon.wav", winsound.SND_FILENAME)

            if self.remember_me_ticket:
                try:
                    response = self.refresh_session_with_remember_me()
                    if "ticket" in response:
                        return True
                except Exception as e:
                    print(f"Ошибка при обновлении с помощью remember_me_ticket: {e}")
                    winsound.PlaySound("C:\\Windows\\Media\\Windows Logon.wav", winsound.SND_FILENAME)

            self.clear_saved_data()
            return False
        return True

    def basic_auth(self, email: str, password: str) -> Dict[str, Any]:
        """Выполнение базовой аутентификации"""
        url = f"{self.base_url}/profiles/sessions"

        auth_string = f"{email}:{password}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()

        headers = self.headers.copy()
        headers["Authorization"] = f"Basic {auth_base64}"

        try:
            response = self.session.post(
                url, headers=headers, json={"rememberMe": True}
            )
            response_data = response.json()

            if response.status_code != 200:
                print(f"Ошибка аутентификации. Статус: {response.status_code}")
                self.clear_saved_data()
                return response_data

            self.two_factor_ticket = response_data.get("twoFactorAuthenticationTicket")
            self.session_id = response_data.get("sessionId")
            self.save_token(None, self.session_id, self.two_factor_ticket, None)

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса: {str(e)}")
            self.clear_saved_data()
            return {"error": str(e)}

    def complete_2fa(self, code: str) -> Dict[str, Any]:
        """Завершение двухфакторной аутентификации"""
        if not self.two_factor_ticket:
            raise Exception("Двухфакторный билет отсутствует")

        url = f"{self.base_url}/profiles/sessions"

        headers = self.headers.copy()
        headers["Ubi-2FACode"] = str(code)
        headers["Authorization"] = f"ubi_2fa_v1 t={self.two_factor_ticket}"

        try:
            response = self.session.post(
                url, headers=headers, json={"rememberMe": True}
            )
            response_data = response.json()

            if response.status_code != 200:
                print(f"Ошибка двухфакторной аутентификации. Статус: {response.status_code}")
                self.clear_saved_data()
                return response_data

            if "ticket" in response_data:
                self.token = response_data["ticket"]
                self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                self.token_expiry = datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)

                remember_me_ticket = response_data.get("rememberMeTicket")
                if remember_me_ticket:
                    self.remember_me_ticket = remember_me_ticket
                    self.headers["ubi-rememberdeviceticket"] = remember_me_ticket

                self.save_token(
                    self.token,
                    self.session_id,
                    self.two_factor_ticket,
                    remember_me_ticket,
                )

                # Запуск обновления токена после успешной двухфакторной аутентификации
                self.start_token_refresh()

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса при двухфакторной аутентификации: {str(e)}")
            self.clear_saved_data()
            return {"error": str(e)}

    def refresh_session_with_remember_me(self) -> Dict[str, Any]:
        """Обновление сессии с помощью remember_me_ticket"""
        if not self.remember_me_ticket:
            return {"error": "Отсутствует remember_me_ticket"}

        url = f"{self.base_url}/profiles/sessions"
        headers = self.headers.copy()
        headers["ubi-rememberdeviceticket"] = self.remember_me_ticket

        try:
            response = self.session.post(
                url, headers=headers, json={"rememberMe": True}
            )
            response_data = response.json()

            if response.status_code != 200:
                print(f"Ошибка обновления сессии. Статус: {response.status_code}")
                return response_data

            if "ticket" in response_data:
                self.token = response_data["ticket"]
                self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                self.token_expiry = datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)

                new_remember_me = response_data.get("rememberMeTicket")
                if new_remember_me:
                    self.remember_me_ticket = new_remember_me
                    self.headers["ubi-rememberdeviceticket"] = new_remember_me

                self.save_token(
                    self.token,
                    self.session_id,
                    self.two_factor_ticket,
                    self.remember_me_ticket,
                )

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса при обновлении сессии: {str(e)}")
            return {"error": str(e)}
