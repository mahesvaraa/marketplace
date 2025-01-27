import os
import requests
import json
import base64
from typing import Dict, Any

TOKEN_FILE = "auth_token.json"

class UbisoftAuth:
    def __init__(self):
        self.base_url = "https://public-ubiservices.ubi.com/v3"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Ubi-AppId": "685a3038-2b04-47ee-9c5a-6403381a46aa",  # Используем AppID из HAR-файла
            "Ubi-RequestedPlatformType": "uplay",
            "Accept": "*/*",
            "Origin": "https://connect.ubisoft.com",
            "Referer": "https://connect.ubisoft.com/"
        }
        self.session = requests.Session()
        self.two_factor_ticket = None
        self.token = None

    def load_token(self):
        """Load token from file if it exists."""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                self.token = data.get("token")
                if self.token:
                    self.headers["Authorization"] = f"Ubi_v1 t={self.token}"

    def save_token(self, token: str):
        """Save token to file."""
        with open(TOKEN_FILE, "w") as f:
            json.dump({"token": token}, f)

    def validate_token(self) -> bool:
        """Check if the current token is still valid."""
        if not self.token:
            return False
        url = f"{self.base_url}/profiles/me"
        response = self.session.get(url, headers=self.headers)
        return response.status_code == 200

    def basic_auth(self, email: str, password: str) -> Dict[str, Any]:
        """Initial authentication with email and password."""
        url = f"{self.base_url}/profiles/sessions"

        # Create Basic Authentication header
        auth_string = f"{email}:{password}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()

        headers = self.headers.copy()
        headers["Authorization"] = f"Basic {auth_base64}"

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                print(f"Authentication failed with status {response.status_code}")
                print(f"Response: {response_data}")
                return response_data

            self.two_factor_ticket = response_data.get("twoFactorAuthenticationTicket")
            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error: {str(e)}")
            return {"error": str(e)}

    def complete_2fa(self, code: str) -> Dict[str, Any]:
        """Complete authentication with 2FA code."""
        if not self.two_factor_ticket:
            raise Exception("No two-factor authentication ticket found. Run basic_auth first.")

        url = f"{self.base_url}/profiles/sessions"

        headers = self.headers.copy()
        headers["Ubi-2FACode"] = str(code)
        headers["Authorization"] = f"ubi_2fa_v1 t={self.two_factor_ticket}"

        data = {"rememberMe": True}

        try:
            response = self.session.post(url, headers=headers, json=data)
            response_data = response.json()

            if response.status_code != 200:
                print(f"2FA failed with status {response.status_code}")
                print(f"Response: {response_data}")
                return response_data

            if "ticket" in response_data:
                self.token = response_data["ticket"]
                self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                self.save_token(self.token)

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error during 2FA: {str(e)}")
            return {"error": str(e)}

def main():
    auth = UbisoftAuth()

    # Load saved token and validate it
    auth.load_token()
    if auth.token and auth.validate_token():
        print("Using saved token. Authentication successful.")
        return auth.token

    # If token is invalid or missing, authenticate again
    email = input("Enter your Ubisoft email: ")
    password = input("Enter your password: ")

    print("\nAttempting initial authentication...")
    basic_response = auth.basic_auth(email, password)

    print("\nInitial authentication response:")
    print(json.dumps(basic_response, indent=2))

    if auth.two_factor_ticket:
        print("\n2FA required. Check your authentication device.")
        print(f"Phone number: {basic_response.get('maskedPhone', 'Unknown')}")

        # Complete 2FA
        code = input("\nEnter 2FA code: ")
        print("\nCompleting 2FA authentication...")
        auth_response = auth.complete_2fa(code)

        print("\n2FA response:")
        print(json.dumps(auth_response, indent=2))

        return auth.token

    return basic_response.get("ticket")

if __name__ == "__main__":
    token = main()
    if token:
        print(f"\nFinal authentication token: {token}")
