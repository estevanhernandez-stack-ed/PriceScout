
import pytest
import sys
import streamlit as st
from unittest.mock import patch

def test_app_import(monkeypatch):
    # Create a mock for the 'tools.tool_code' module
    # --- FIX: The app doesn't use 'tools.tool_code'. Mock the OMDb API key instead. ---
    mock_secrets = {
        "omdb_api_key": "fake_key",
        "users": {"test_user": "hashed_password"}
    }
    monkeypatch.setattr(st, 'secrets', mock_secrets)

    with patch('app.price_scout_app.login', return_value=True): # Mock the login function
        try:
            # Import main to ensure the app loads without login issues
            from app.price_scout_app import main
            assert callable(main) # Check if main is callable
        except ImportError as e:
            pytest.fail(f"Failed to import price_scout_app: {e}")
