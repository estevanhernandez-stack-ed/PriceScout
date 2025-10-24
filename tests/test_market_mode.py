
import pytest
from unittest.mock import MagicMock, patch
import streamlit as st
import datetime
from app.modes.market_mode import render_market_mode

@pytest.fixture
def mock_market_mode_session_state(monkeypatch):
    mock_state = MagicMock()
    mock_state.selected_region = 'Test Region'
    mock_state.selected_market = 'Test Market'
    mock_state.theaters = [{'name': 'Test Theater 1'}]
    mock_state.selected_theaters = ['Test Theater 1']
    mock_state.all_showings = {
        'Test Theater 1': [
            {'film_title': 'Test Movie 1', 'showtime': '10:00am', 'daypart': 'Matinee'},
            {'film_title': 'Test Movie 1', 'showtime': '8:00pm', 'daypart': 'Prime'},
        ]
    }
    mock_state.market_date = '2025-09-08'
    mock_state.daypart_selections = set()
    mock_state.selected_showtimes = {}
    mock_state.report_running = False
    mock_state.confirm_scrape = False

    monkeypatch.setattr(st, "session_state", mock_state)
    return mock_state

def test_market_mode_full_workflow(mock_market_mode_session_state, monkeypatch):
    mock_scraper = MagicMock()
    mock_markets_data = {
        "Test Parent": {
            "Test Region": {
                "Test Market": {
                    "theaters": [{"name": "Test Theater 1"}]
                }
            }
        }
    }
    mock_cache_data = {
        "markets": {
            "Test Market": {
                "theaters": [{"name": "Test Theater 1", "url": "http://example.com/theater1"}]
            }
        }
    }

    with patch('app.modes.market_mode.st') as mock_st:
        def columns_side_effect(num_cols):
            if isinstance(num_cols, int):
                return [MagicMock() for _ in range(num_cols)]
            return [MagicMock() for _ in num_cols]
        mock_st.columns.side_effect = columns_side_effect
        mock_st.date_input.return_value = (datetime.date(2025, 9, 8), datetime.date(2025, 9, 8))
        render_market_mode(mock_scraper, mock_markets_data, mock_cache_data, False, "Test Parent")

        # Simulate user selecting a market
        mock_st.session_state.selected_market = 'Test Market'

        # Simulate user selecting a theater
        mock_st.session_state.selected_theaters = ['Test Theater 1']

        # Simulate user selecting all dayparts
        mock_st.session_state.daypart_selections = {'All'}

        # Simulate user clicking the "Confirm Selections and Scrape" button
        mock_st.session_state.confirm_scrape = True

        render_market_mode(mock_scraper, mock_markets_data, mock_cache_data, False, "Test Parent")

        assert mock_st.session_state.confirm_scrape == True
