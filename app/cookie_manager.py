"""
Cookie Manager for PriceScout Persistent Sessions

Handles cookie-based session persistence using streamlit-cookies-manager.
"""

import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
import os

# Cookie settings
# NOTE: The EncryptedCookieManager adds the "pricescout_" prefix automatically,
# so these keys should NOT include the prefix
COOKIE_NAME_USERNAME = "username"
COOKIE_NAME_TOKEN = "session_token"
COOKIE_EXPIRY_DAYS = 30

def get_cookie_manager():
    """
    Get or create the cookie manager instance.

    Returns:
        EncryptedCookieManager instance or None if not ready
    """
    try:
        # Use a secret key from environment or generate a default one
        # In production, this should be set via environment variable
        password = os.getenv('COOKIE_PASSWORD', 'pricescout_default_cookie_secret_change_in_production')

        if 'cookie_manager' not in st.session_state:
            st.session_state.cookie_manager = EncryptedCookieManager(
                prefix="pricescout_",
                password=password
            )

        # Check if cookies are ready - if not, return None gracefully
        if not st.session_state.cookie_manager.ready():
            return None

        return st.session_state.cookie_manager
    except Exception as e:
        # If cookie manager fails, log and return None (app will work without persistence)
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
        cookies = get_cookie_manager()
        if cookies is None:
            # Cookies not ready yet, skip silently
            print("DEBUG cookie_manager: Cookie manager not ready, cannot save")
            return

        cookies[COOKIE_NAME_USERNAME] = username
        cookies[COOKIE_NAME_TOKEN] = session_token
        cookies.save()
        print(f"DEBUG cookie_manager: Saved cookie for user: {username}")
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
        cookies = get_cookie_manager()
        if cookies is None:
            # Cookies not ready yet
            print("DEBUG cookie_manager: Cookie manager not ready, cannot read")
            return None, None

        username = cookies.get(COOKIE_NAME_USERNAME)
        token = cookies.get(COOKIE_NAME_TOKEN)

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
        cookies = get_cookie_manager()
        if cookies is None:
            # Cookies not ready yet, skip silently
            return

        if COOKIE_NAME_USERNAME in cookies:
            del cookies[COOKIE_NAME_USERNAME]
        if COOKIE_NAME_TOKEN in cookies:
            del cookies[COOKIE_NAME_TOKEN]
        cookies.save()
    except Exception as e:
        print(f"Warning: Failed to clear login cookie: {e}")
