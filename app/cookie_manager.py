"""
Cookie Manager for PriceScout Persistent Sessions

Handles cookie-based session persistence using extra-streamlit-components.
"""

import streamlit as st
import extra_streamlit_components as stx

# Cookie settings
COOKIE_NAME_USERNAME = "pricescout_username"
COOKIE_NAME_TOKEN = "pricescout_session_token"
COOKIE_EXPIRY_DAYS = 30

def get_cookie_manager():
    """
    Get or create the cookie manager instance.

    Returns:
        CookieManager instance
    """
    try:
        # Create cookie manager - this library doesn't need manual ready() checks
        return stx.CookieManager()
    except Exception as e:
        print(f"Cookie manager initialization failed: {e}")
        return None

def save_login_cookie(username, session_token):
    """
    Save login credentials to cookies for persistent session.

    Args:
        username: Username to save
        session_token: Session token to save
    """
    try:
        cookie_manager = get_cookie_manager()
        if cookie_manager is None:
            print("DEBUG cookie_manager: Failed to get cookie manager")
            return

        # Set cookies with expiry
        import datetime
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=COOKIE_EXPIRY_DAYS)

        cookie_manager.set(COOKIE_NAME_USERNAME, username, expires_at=expiry_date)
        cookie_manager.set(COOKIE_NAME_TOKEN, session_token, expires_at=expiry_date)

        print(f"DEBUG cookie_manager: Saved cookies for user: {username}")
    except Exception as e:
        # Cookie errors shouldn't break login, just log them
        print(f"Warning: Failed to save login cookie: {e}")

def get_saved_login():
    """
    Get saved login credentials from cookies.

    Returns:
        Tuple of (username, token) or (None, None) if not found
    """
    try:
        cookie_manager = get_cookie_manager()
        if cookie_manager is None:
            print("DEBUG cookie_manager: Failed to get cookie manager")
            return None, None

        # Get all cookies
        all_cookies = cookie_manager.get_all()

        username = all_cookies.get(COOKIE_NAME_USERNAME)
        token = all_cookies.get(COOKIE_NAME_TOKEN)

        if username and token:
            print(f"DEBUG cookie_manager: Found saved login for user: {username}")
            return username, token
        else:
            print(f"DEBUG cookie_manager: No saved login found (username={username}, token={'set' if token else 'not set'})")
    except Exception as e:
        print(f"Warning: Failed to read login cookie: {e}")

    return None, None

def clear_login_cookie():
    """
    Clear saved login credentials from cookies.
    """
    try:
        cookie_manager = get_cookie_manager()
        if cookie_manager is None:
            return

        cookie_manager.delete(COOKIE_NAME_USERNAME)
        cookie_manager.delete(COOKIE_NAME_TOKEN)

        print("DEBUG cookie_manager: Cleared login cookies")
    except Exception as e:
        print(f"Warning: Failed to clear login cookie: {e}")
