"""
Cookie Manager for PriceScout Persistent Sessions

Handles cookie-based session persistence using streamlit-cookies-manager.
"""

import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
import os

# Cookie settings
COOKIE_NAME_USERNAME = "pricescout_username"
COOKIE_NAME_TOKEN = "pricescout_session_token"
COOKIE_EXPIRY_DAYS = 30

def get_cookie_manager():
    """
    Get or create the cookie manager instance.

    Returns:
        EncryptedCookieManager instance
    """
    # Use a secret key from environment or generate a default one
    # In production, this should be set via environment variable
    password = os.getenv('COOKIE_PASSWORD', 'pricescout_default_cookie_secret_change_in_production')

    if 'cookie_manager' not in st.session_state:
        st.session_state.cookie_manager = EncryptedCookieManager(
            prefix="pricescout_",
            password=password
        )

    # Ensure cookies are ready
    if not st.session_state.cookie_manager.ready():
        st.stop()

    return st.session_state.cookie_manager

def save_login_cookie(username, session_token):
    """
    Save login credentials to cookies for persistent session.

    Args:
        username: Username to save
        session_token: Session token to save
    """
    try:
        cookies = get_cookie_manager()
        cookies[COOKIE_NAME_USERNAME] = username
        cookies[COOKIE_NAME_TOKEN] = session_token
        cookies.save()
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
        username = cookies.get(COOKIE_NAME_USERNAME)
        token = cookies.get(COOKIE_NAME_TOKEN)

        if username and token:
            return username, token
    except Exception as e:
        print(f"Warning: Failed to read login cookie: {e}")

    return None, None

def clear_login_cookie():
    """
    Clear saved login credentials from cookies.
    """
    try:
        cookies = get_cookie_manager()
        if COOKIE_NAME_USERNAME in cookies:
            del cookies[COOKIE_NAME_USERNAME]
        if COOKIE_NAME_TOKEN in cookies:
            del cookies[COOKIE_NAME_TOKEN]
        cookies.save()
    except Exception as e:
        print(f"Warning: Failed to clear login cookie: {e}")
