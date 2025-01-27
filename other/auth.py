import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import base64
import requests

TOKEN_FILE = "auth_token1.json"
TOKEN_LIFETIME_HOURS = 3

class UbisoftAuth:
    def __init__(self):
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

        # Load saved tokens on initialization
        self.load_token()
        self.ensure_valid_token()

    def clear_saved_data(self):
        """Clear all saved authentication data"""
        self.token = None
        self.session_id = None
        self.two_factor_ticket = None
        self.token_expiry = None
        self.remember_me_ticket = None
        if "Authorization" in self.headers:
            del self.headers["Authorization"]
        self.save_token(None, None, None, None)

    def load_token(self):
        """Load token data from file"""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r") as f:
                    data = json.load(f)
                    self.token = data.get("token")
                    self.session_id = data.get("session_id")
                    self.two_factor_ticket = data.get("two_factor_ticket")
                    self.remember_me_ticket = data.get("remember_me_ticket")
                    self.token_expiry = datetime.fromisoformat(data.get("expiry", "2000-01-01T00:00:00"))

                    if self.token:
                        self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                    if self.remember_me_ticket:
                        self.headers["ubi-rememberdeviceticket"] = self.remember_me_ticket

            except Exception as e:
                print(f"Error loading token file: {e}")
                self.clear_saved_data()

    def save_token(self, token: Optional[str], session_id: Optional[str] = None,
                  two_factor_ticket: Optional[str] = None, remember_me_ticket: Optional[str] = None):
        """Save token data to file"""
        try:
            data = {
                "token": token,
                "session_id": session_id,
                "two_factor_ticket": two_factor_ticket,
                "remember_me_ticket": remember_me_ticket,
                "expiry": (datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)).isoformat()
            }

            with open(TOKEN_FILE, "w") as f:
                json.dump(data, f)

        except Exception as e:
            print(f"Error saving token file: {e}")

    def is_token_expired(self) -> bool:
        """Check if the current token has expired"""
        if not self.token or not self.token_expiry:
            return True

        # Check token expiration time
        if datetime.now() > self.token_expiry:
            return True

        # Validate token with API
        try:
            response = self.session.get(f"{self.base_url}/profiles/me", headers=self.headers)
            return response.status_code != 200
        except Exception as e:
            print(f"Error checking token: {e}")
            return True

    def ensure_valid_token(self) -> bool:
        """Check and refresh token if needed using remember_me_ticket if available"""
        if self.is_token_expired():
            if self.remember_me_ticket:
                try:
                    response = self.refresh_session_with_remember_me()
                    if "ticket" in response:
                        return True
                except Exception as e:
                    print(f"Failed to refresh session: {e}")
            
            # If remember_me failed or not available, try 2FA ticket
            if self.two_factor_ticket:
                try:
                    response = self.reuse_two_factor_ticket()
                    return "ticket" in response
                except Exception as e:
                    print(f"Failed to reuse 2FA ticket: {e}")
            
            self.clear_saved_data()
            return False
        return True

    def refresh_session_with_remember_me(self) -> Dict[str, Any]:
        """Refresh session using remember_me_ticket"""
        if not self.remember_me_ticket:
            return {"error": "No remember_me_ticket available"}

        url = f"{self.base_url}/profiles/sessions"
        headers = self.headers.copy()
        headers["ubi-rememberdeviceticket"] = self.remember_me_ticket

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                print(f"Session refresh failed with status {response.status_code}")
                return response_data

            if "ticket" in response_data:
                self.token = response_data["ticket"]
                self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                self.token_expiry = datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)
                
                # Update remember_me_ticket if a new one is provided
                new_remember_me = response_data.get("rememberMeTicket")
                if new_remember_me:
                    self.remember_me_ticket = new_remember_me
                    self.headers["ubi-rememberdeviceticket"] = new_remember_me

                self.save_token(self.token, self.session_id, self.two_factor_ticket, self.remember_me_ticket)

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error during session refresh: {str(e)}")
            return {"error": str(e)}

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
            self.save_token(None, self.session_id, self.two_factor_ticket, None)

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
                self.token_expiry = datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)

                # Save rememberMeTicket if provided
                remember_me_ticket = response_data.get("rememberMeTicket")
                if remember_me_ticket:
                    self.remember_me_ticket = remember_me_ticket
                    self.headers["ubi-rememberdeviceticket"] = remember_me_ticket

                self.save_token(self.token, self.session_id, self.two_factor_ticket, remember_me_ticket)

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error during 2FA: {str(e)}")
            self.clear_saved_data()
            return {"error": str(e)}

    def reuse_two_factor_ticket(self) -> Dict[str, Any]:
        """Try to reuse the saved 2FA ticket and session"""
        if not self.two_factor_ticket or not self.session_id:
            print("No saved 2FA ticket or session to reuse.")
            self.clear_saved_data()
            return {"error": "No saved ticket"}

        url = f"{self.base_url}/profiles/sessions"
        headers = self.headers.copy()
        headers["Authorization"] = f"ubi_2fa_v1 t={self.two_factor_ticket}"

        try:
            response = self.session.post(url, headers=headers, json={"rememberMe": True})
            response_data = response.json()

            if response.status_code != 200:
                print(f"Reusing 2FA ticket failed with status {response.status_code}")
                self.clear_saved_data()
                return response_data

            if "ticket" in response_data:
                self.token = response_data["ticket"]
                self.headers["Authorization"] = f"Ubi_v1 t={self.token}"
                self.token_expiry = datetime.now() + timedelta(hours=TOKEN_LIFETIME_HOURS)
                
                # Save rememberMeTicket if provided
                remember_me_ticket = response_data.get("rememberMeTicket")
                if remember_me_ticket:
                    self.remember_me_ticket = remember_me_ticket
                    self.headers["ubi-rememberdeviceticket"] = remember_me_ticket
                
                self.save_token(self.token, self.session_id, self.two_factor_ticket, self.remember_me_ticket)

            return response_data

        except requests.exceptions.RequestException as e:
            print(f"Request error during 2FA reuse: {str(e)}")
            self.clear_saved_data()
            return {"error": str(e)}

    def make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with automatic token refresh if needed"""
        method_map = {
            'GET': self.session.get,
            'POST': self.session.post,
            'PUT': self.session.put,
            'DELETE': self.session.delete,
        }

        if method.upper() not in method_map:
            raise ValueError(f"Unsupported HTTP method: {method}")

        kwargs['headers'] = kwargs.get('headers', self.headers)
        try:
            response = method_map[method.upper()](url, **kwargs)
            if response.status_code == 401:  # Unauthorized
                if self.ensure_valid_token():
                    kwargs['headers'] = self.headers  # Update headers with new token
                    response = method_map[method.upper()](url, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            print(f"Request error: {str(e)}")
            raise

def main():
    auth = UbisoftAuth()

    # Try to use existing tokens (remember_me or 2FA)
    if auth.is_token_expired():
        print("Token is expired or invalid. Attempting to refresh session...")
        # If automatic refresh fails, proceed with manual authentication
        if not auth.ensure_valid_token():
            print("Session refresh failed. Manual authentication required.")
            email = input("Enter your Ubisoft email: ")
            password = input("Enter your password: ")
            auth.basic_auth(email, password)
            if auth.two_factor_ticket:
                code = input("Enter 2FA code: ")
                auth.complete_2fa(code)
    else:
        print("Successfully authenticated using saved tokens")

    # Example usage:
    try:
        response = auth.make_request('GET', f"{auth.base_url}/profiles/me")
        if response.status_code == 200:
            print("Successfully fetched profile data")
            print(response.json())
        else:
            print(f"Failed to fetch profile data: {response.status_code}")
    except Exception as e:
        print(f"Error making request: {e}")

if __name__ == "__main__":
    main()