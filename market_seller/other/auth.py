import base64
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional

import requests

from market_seller.config import *
from market_seller.other.utils import play_notification_sound


# Импортируем утилиты


class UbisoftAuth:
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None, logger=None):
        self.base_url = BASE_URL
        self.headers = DEFAULT_HEADERS.copy()
        self.session = requests.Session()

        # Настройка логирования с использованием новой утилиты
        self.logger = logger

        self._reset_authentication_state()

        self.email = email
        self.password = password
        self._refresh_thread = None
        self._stop_refresh = False

        # Загрузка сохранённого токена при инициализации
        self.load_token()

    def _reset_authentication_state(self):
        """Сброс состояния аутентификации."""
        self.two_factor_ticket = None
        self.token = None
        self.session_id = None
        self.token_expiry = None
        self.remember_me_ticket = None

    def start_token_refresh(self):
        """Запуск фонового потока для обновления токена."""
        if self._refresh_thread is None:
            self._stop_refresh = False
            self._refresh_thread = threading.Thread(target=self._token_refresh_loop, daemon=True)
            self._refresh_thread.start()

    def stop_token_refresh(self):
        """Остановка фонового потока для обновления токена."""
        self._stop_refresh = True
        if self._refresh_thread:
            self._refresh_thread.join()
            self._refresh_thread = None

    def _token_refresh_loop(self):
        """Фоновый цикл для обновления токена."""
        while not self._stop_refresh:
            time.sleep(REFRESH_INTERVAL_MINUTES * 60)
            if not self._stop_refresh:
                try:
                    self.refresh_token()
                except Exception as e:
                    self.logger.error(f"Ошибка в цикле обновления токена: {e}")

    def _prepare_auth_headers(self, token: Optional[str] = None, remember_me: Optional[str] = None) -> Dict[str, str]:
        """Подготовка заголовков для аутентификации."""
        headers = self.headers.copy()
        if token:
            headers["Authorization"] = f"Ubi_v1 t={token}"
        if remember_me:
            headers["ubi-rememberdeviceticket"] = remember_me
        return headers

    def _update_tokens_and_headers(self, response_data: Dict[str, Any]):
        """Обновление токенов и заголовков на основе ответа."""
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

    def _handle_authentication_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка ответа от сервера аутентификации."""
        if response_data.get("error"):
            self.logger.error(f"Ошибка аутентификации: {response_data['error']}")
            self.clear_saved_data()
            play_notification_sound()
        return response_data

    def refresh_token(self) -> Dict[str, Any]:
        """Обновление токена с использованием текущего токена."""
        if not self.token:
            return {"error": "Нет доступного токена"}

        url = f"{self.base_url}/profiles/sessions"
        headers = self._prepare_auth_headers(self.token)

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                return self._handle_authentication_response(response_data)

            self._update_tokens_and_headers(response_data)
            # self.logger.info("Токен успешно обновлён")
            return response_data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка запроса при обновлении токена: {str(e)}")
            play_notification_sound()
            return {"error": str(e)}

    def clear_saved_data(self):
        """Очистка всех сохранённых данных аутентификации."""
        self._reset_authentication_state()
        if "Authorization" in self.headers:
            del self.headers["Authorization"]
        self.save_token(None, None, None, None)

    def load_token(self):
        """Загрузка токена из файла."""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r") as f:
                    data = json.load(f)
                    self.token = data.get("token")
                    self.session_id = data.get("session_id")
                    self.two_factor_ticket = data.get("two_factor_ticket")
                    self.remember_me_ticket = data.get("remember_me_ticket")

                    expiry_str = data.get("expiry", "2000-01-01T00:00:00")
                    self.token_expiry = datetime.fromisoformat(expiry_str)

                    if self.token:
                        self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                    if self.remember_me_ticket:
                        self.headers["ubi-rememberdeviceticket"] = self.remember_me_ticket

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке токена: {e}")
                self.clear_saved_data()

    def save_token(
        self,
        token: Optional[str],
        session_id: Optional[str] = None,
        two_factor_ticket: Optional[str] = None,
        remember_me_ticket: Optional[str] = None,
    ):
        """Сохранение токена в файл."""
        try:
            data = {
                "token": token,
                "session_id": session_id,
                "two_factor_ticket": two_factor_ticket,
                "remember_me_ticket": remember_me_ticket,
                "expiry": (datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)).isoformat(),
            }

            with open(TOKEN_FILE, "w") as f:
                json.dump(data, f)

        except Exception as e:
            self.logger.error(f"Ошибка при сохранении токена: {e}")

    def is_token_expired(self) -> bool:
        """Проверка, истёк ли текущий токен."""
        if not self.token or not self.token_expiry:
            return True

        if datetime.now() > self.token_expiry:
            return True

        try:
            response = self.session.get(f"{self.base_url}/profiles/me", headers=self.headers)
            return response.status_code != 200
        except Exception as e:
            self.logger.error(f"Ошибка при проверке токена: {e}")
            return True

    def ensure_valid_token(self) -> bool:
        """Проверка и обновление токена, если это необходимо."""
        if self.is_token_expired():
            try:
                if self.token and "ticket" in self.refresh_token():
                    return True
            except Exception as e:
                self.logger.error(f"Ошибка при обновлении токена: {e}")
                play_notification_sound()

            try:
                if self.remember_me_ticket and "ticket" in self.refresh_session_with_remember_me():
                    return True
            except Exception as e:
                self.logger.error(f"Ошибка при обновлении с помощью remember_me_ticket: {e}")
                play_notification_sound()

            self.clear_saved_data()
            return False
        return True

    def basic_auth(self, email: str, password: str) -> Dict[str, Any]:
        """Выполнение базовой аутентификации."""
        url = f"{self.base_url}/profiles/sessions"

        auth_string = f"{email}:{password}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()

        headers = self._prepare_auth_headers()
        headers["Authorization"] = f"Basic {auth_base64}"

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                return self._handle_authentication_response(response_data)

            self.two_factor_ticket = response_data.get("twoFactorAuthenticationTicket")
            self.session_id = response_data.get("sessionId")
            self.save_token(None, self.session_id, self.two_factor_ticket, None)

            return response_data

        except requests.exceptions.RequestException as e:
            return self._handle_authentication_response({"error": str(e)})

    def complete_2fa(self, code: str) -> Dict[str, Any]:
        """Завершение двухфакторной аутентификации."""
        if not self.two_factor_ticket:
            raise Exception("Двухфакторный тикет отсутствует")

        url = f"{self.base_url}/profiles/sessions"

        headers = self._prepare_auth_headers()
        headers["Ubi-2FACode"] = str(code)
        headers["Authorization"] = f"ubi_2fa_v1 t={self.two_factor_ticket}"

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                return self._handle_authentication_response(response_data)

            self._update_tokens_and_headers(response_data)
            self.start_token_refresh()  # Запуск обновления токена

            return response_data

        except requests.exceptions.RequestException as e:
            return self._handle_authentication_response({"error": str(e)})

    def refresh_session_with_remember_me(self) -> Dict[str, Any]:
        """Обновление сессии с помощью remember_me_ticket."""
        if not self.remember_me_ticket:
            return {"error": "Отсутствует remember_me_ticket"}

        url = f"{self.base_url}/profiles/sessions"
        headers = self._prepare_auth_headers(remember_me=self.remember_me_ticket)

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                return self._handle_authentication_response(response_data)

            self._update_tokens_and_headers(response_data)
            return response_data

        except requests.exceptions.RequestException as e:
            return self._handle_authentication_response({"error": str(e)})
