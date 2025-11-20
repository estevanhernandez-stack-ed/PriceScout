"""
Session Manager for PriceScout Persistent Sessions

Uses URL query parameters for reliable session persistence across page refreshes.
This is the standard approach for Streamlit authentication.
"""

import streamlit as st

# Session parameter name
SESSION_PARAM = "session"

def save_login_cookie(username, session_token):
    """
    Save login session by adding token to URL query parameters.

    Args:
        username: Username (for logging only)
        session_token: Session token to save
    """
    try:
        # Set the session token in query params
        st.query_params[SESSION_PARAM] = session_token
        print(f"DEBUG cookie_manager: Saved session token to URL for user: {username}")
    except Exception as e:
        print(f"Warning: Failed to save session token to URL: {e}")

def get_saved_login():
    """
    Get saved session token from URL query parameters.

    Returns:
        Session token string or None if not found
    """
    try:
        # Get session token from query params
        token = st.query_params.get(SESSION_PARAM)

        if token:
            print(f"DEBUG cookie_manager: Found session token in URL")
            return token
        else:
            print(f"DEBUG cookie_manager: No session token found in URL")
            return None
    except Exception as e:
        print(f"Warning: Failed to read session token from URL: {e}")
        return None

def clear_login_cookie():
    """
    Clear saved session token from URL query parameters.
    """
    try:
        # Remove session param from URL
        if SESSION_PARAM in st.query_params:
            del st.query_params[SESSION_PARAM]
        print("DEBUG cookie_manager: Cleared session token from URL")
    except Exception as e:
        print(f"Warning: Failed to clear session token from URL: {e}")
