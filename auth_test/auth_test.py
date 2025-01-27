import requests
import json
import base64
from datetime import datetime, timedelta
from typing import Dict, Any

class UbisoftAuth:
    def __init__(self):
        self.base_url = "https://public-ubiservices.ubi.com/v3"
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Ubi-AppId": "685a3038-2b04-47ee-9c5a-6403381a46aa",
            "Ubi-RequestedPlatformType": "uplay",
            "GenomeId": "29f82202-95c0-4410-8d46-08525fc3ebc9"
        }
        self.token = None
        self.session_id = None
        self.two_factor_ticket = None
        self.token_expiry = None
        self.load_saved_data()

    def load_saved_data(self):
        """Load saved authentication data"""
        try:
            with open('auth_data.json', 'r') as f:
                data = json.load(f)
                self.token = data.get('token')
                self.session_id = data.get('session_id')
                self.two_factor_ticket = data.get('two_factor_ticket')
                self.remember_me_ticket = data.get('rememberMeTicket')
                expiry_str = data.get('token_expiry')
                if expiry_str:
                    self.token_expiry = datetime.fromisoformat(expiry_str)
                if self.token:
                    self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                if self.remember_me_ticket:
                    self.headers["ubi-rememberdeviceticket"] = self.remember_me_ticket
        except FileNotFoundError:
            pass

    def save_token(self, token: str = None, session_id: str = None, two_factor_ticket: str = None):
        """Save authentication data to file"""
        data = {
            'token': token or self.token,
            'session_id': session_id or self.session_id,
            'two_factor_ticket': two_factor_ticket or self.two_factor_ticket,
            'rememberMeTicket': self.remember_me_ticket,
            'token_expiry': self.token_expiry.isoformat() if self.token_expiry else None
        }
        with open('auth_data.json', 'w') as f:
            json.dump(data, f)

    def clear_saved_data(self):
        """Clear all saved authentication data"""
        self.token = None
        self.session_id = None
        self.two_factor_ticket = None
        self.token_expiry = None
        try:
            with open('auth_data.json', 'w') as f:
                json.dump({}, f)
        except:
            pass

    def basic_auth(self, email: str, password: str) -> Dict[str, Any]:
        """Perform basic authentication to get 2FA ticket"""
        url = f"{self.base_url}/profiles/sessions"

        auth_string = f"{email}:{password}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()

        headers = self.headers.copy()
        headers["Authorization"] = f"Basic {auth_base64}"

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                print(f"Authentication failed with status {response.status_code}")
                self.clear_saved_data()
                return response_data

            self.two_factor_ticket = response_data.get("twoFactorAuthenticationTicket")
            self.session_id = response_data.get("sessionId")
            self.save_token(None, self.session_id, self.two_factor_ticket)

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error: {str(e)}")
            self.clear_saved_data()
            return {"error": str(e)}

    def complete_2fa(self, code: str) -> Dict[str, Any]:
        """Complete the 2FA process using the provided code"""
        if not self.two_factor_ticket:
            raise Exception("No two-factor authentication ticket found. Run basic_auth first.")

        url = f"{self.base_url}/profiles/sessions"

        headers = self.headers.copy()
        headers["Ubi-2FACode"] = str(code)
        headers["Authorization"] = f"ubi_2fa_v1 t={self.two_factor_ticket}"

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                print(f"2FA failed with status {response.status_code}")
                self.clear_saved_data()
                return response_data

            if "ticket" in response_data:
                self.token = response_data["ticket"]
                self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                self.token_expiry = datetime.now() + timedelta(hours=24)  # Предполагаемое время жизни токена

            # Сохраняем rememberMeTicket, если он есть
            self.remember_me_ticket = response_data.get("rememberMeTicket")
            if self.remember_me_ticket:
                self.headers["ubi-rememberdeviceticket"] = self.remember_me_ticket

            # Сохраняем все данные
            self.save_token(
                token=self.token,
                session_id=self.session_id,
                two_factor_ticket=self.two_factor_ticket
            )

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error during 2FA: {str(e)}")
            self.clear_saved_data()
            return {"error": str(e)}


    def is_token_valid(self) -> bool:
        """Check if the current token is valid and not expired"""
        if not self.token or not self.token_expiry:
            return False
        return datetime.now() < self.token_expiry

def main():
    auth = UbisoftAuth()

    email = "danilashkirdow@mail.ru"
    password = "Dd170296dD!"

    try:
        # Проверяем, есть ли действующий токен
        if auth.is_token_valid():
            print("Using existing valid token...")
            return

        # Выполняем базовую авторизацию
        print("Performing basic authentication...")
        auth_result = auth.basic_auth(email, password)

        if "twoFactorAuthenticationTicket" in auth_result:
            # Если требуется 2FA, запрашиваем код
            two_fa_code = input("Enter 2FA code: ")
            print("Completing 2FA...")
            auth.complete_2fa(two_fa_code)
            print("Authentication successful!")
        else:
            print("Authentication completed without 2FA!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()