import requests
import pandas as pd
import os
from app import config

# Determine API base URL based on environment
if config.is_azure_deployment() and config.APIM_GATEWAY_URL:
    # Use APIM gateway in Azure production
    BASE_URL = f"{config.APIM_GATEWAY_URL}/api/v1"
elif config.is_azure_deployment():
    # Fallback to direct App Service URL if APIM not configured
    app_service_name = os.getenv('WEBSITE_SITE_NAME', 'pricescout-app')
    BASE_URL = f"https://{app_service_name}.azurewebsites.net/api/v1"
else:
    # Local development - direct API connection
    BASE_URL = os.getenv('API_BASE_URL', 'http://127.0.0.1:8000/api/v1')

# Optional: Add APIM subscription key if required
DEFAULT_HEADERS = {}
if config.APIM_SUBSCRIPTION_KEY:
    DEFAULT_HEADERS['Ocp-Apim-Subscription-Key'] = config.APIM_SUBSCRIPTION_KEY

def get_health():
    """Checks the health of the API."""
    try:
        response = requests.get(f"{BASE_URL}/healthz")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"status": "error", "detail": str(e)}

def login(username, password):
    """Authenticates a user and returns a token."""
    try:
        response = requests.post(f"{BASE_URL}/login/token", data={"username": username, "password": password})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_all_markets(token: str):
    """Fetches all market data from the API."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/markets", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_markets_by_company(token: str, company: str):
    """Fetches all markets for a given company."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/markets", headers=headers, params={"company": company})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_theaters_by_market(company: str, market: str):
    """Fetches all theaters for a given market."""
    try:
        response = requests.get(f"{BASE_URL}/theaters", params={"company": company, "market": market})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_historical_prices(market: str, start_date: str, end_date: str):
    """Fetches historical price data."""
    try:
        response = requests.get(
            f"{BASE_URL}/reports/historical_prices",
            params={"market": market, "start_date": start_date, "end_date": end_date},
        )
        response.raise_for_status()
        return pd.DataFrame(response.json())
    except requests.exceptions.RequestException as e:
        return pd.DataFrame() # Return empty dataframe on error

def create_scrape_run(token: str, mode: str, context: str):
    """Creates a new scrape run record."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(f"{BASE_URL}/scrape_runs", headers=headers, json={"mode": mode, "context": context})
        response.raise_for_status()
        return response.json().get("run_id")
    except requests.exceptions.RequestException as e:
        print(f"Error creating scrape run: {e}")
        return None

def change_password(token: str, old_password: str, new_password: str):
    """Changes the current user's password."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        data = {"old_password": old_password, "new_password": new_password}
        response = requests.post(f"{BASE_URL}/users/change-password", headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def reset_password_request(username: str):
    """Requests a password reset code for a user."""
    try:
        data = {"username": username}
        response = requests.post(f"{BASE_URL}/users/reset-password-request", json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def reset_password_with_code(username: str, code: str, new_password: str):
    """Resets a user's password using a reset code."""
    try:
        data = {"username": username, "code": code, "new_password": new_password}
        response = requests.post(f"{BASE_URL}/users/reset-password-with-code", json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
