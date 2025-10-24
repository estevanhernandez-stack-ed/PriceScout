import pytest
from unittest.mock import MagicMock, patch
import streamlit as st
import sys
import os
import json
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def mock_session_state_e2e(monkeypatch):
    mock_state = MagicMock()
    mock_state.logged_in = True # Explicitly set login state to bypass the login form UI
    mock_state.is_admin = True
    mock_state.company = None
    mock_state.selected_company = "Test Parent"
    mock_state.selected_region = None
    mock_state.selected_market = None
    mock_state.theaters = []
    mock_state.selected_theaters = []
    mock_state.all_showings = {}
    mock_state.market_date = datetime.date(2025, 9, 8)
    mock_state.daypart_selections = set()
    mock_state.selected_showtimes = {}
    mock_state.report_running = True  # Set to True to directly test the scraping block
    mock_state.confirm_scrape = False # This should be False when report_running is True
    mock_state.stage = 'data_fetched' # Start at a stage where scraping is possible
    mock_state.search_mode = 'Market Mode'
    mock_state.last_run_log = ''
    monkeypatch.setattr(st, "session_state", mock_state)
    return mock_state

@patch('app.price_scout_app.run_async_in_thread')
@patch('app.price_scout_app.save_operating_hours_from_all_showings') # Mock this to prevent DB writes
@patch('app.modes.market_mode.st')
def test_end_to_end_market_mode_workflow(mock_st_market, mock_save_op_hours, mock_run_async, mock_session_state_e2e, monkeypatch, tmp_path):
    # Mock DB_FILE in app.config
    monkeypatch.setattr('app.config.DB_FILE', str(tmp_path / "test_price_scout.db"))
    # Mock REPORTS_DIR in app.config
    monkeypatch.setattr('app.config.REPORTS_DIR', str(tmp_path / "test_reports"))
    # Mock CACHE_FILE in app.config
    monkeypatch.setattr('app.config.CACHE_FILE', str(tmp_path / "test_theater_cache.json"))
    # --- FIX: Also patch RUNTIME_LOG_FILE to prevent PermissionError ---
    reports_dir = tmp_path / "test_reports"
    monkeypatch.setattr('app.config.REPORTS_DIR', str(reports_dir))
    monkeypatch.setattr('app.config.RUNTIME_LOG_FILE', str(reports_dir / "runtime_log.csv"))
    monkeypatch.setattr('app.config.SCHEDULED_TASKS_DIR', str(tmp_path / "tasks"))

    # Create a dummy cache file
    dummy_cache_data = {"metadata": {"last_updated": "2025-09-10T00:00:00"}, "markets": {}}
    with open(str(tmp_path / "test_theater_cache.json"), 'w') as f:
        json.dump(dummy_cache_data, f)

    # Use the app's own init function to ensure schema is correct
    from app import database
    database.init_database()

    # Manually insert a showing so save_to_database can find it
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "test_price_scout.db"))
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart, ticket_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('2025-09-08', 'Test Theater 1', 'Test Movie 1', '10:00am', 'Standard', 'Matinee', 'http://example.com/ticket1'))
    conn.commit()
    conn.close()

    from app.price_scout_app import main as price_scout_main
    from app.modes.market_mode import render_market_mode
    from app.scraper import Scraper

    # 1. Initialize the app and scraper
    scraper = Scraper()
    markets_data = {
        "Test Parent": {
            "Test Region": {
                "Test Market": {
                    "theaters": [{"name": "Test Theater 1"}]
                }
            }
        }
    }
    cache_data = {
        "markets": {
            "Test Market": {
                "theaters": [{"name": "Test Theater 1", "url": "http://example.com/theater1"}]
            }
        }
    }

    # 2. Mock streamlit functions that are not relevant to the workflow
    mock_st_market.session_state = mock_session_state_e2e
    mock_st_market.columns.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock())
    mock_st_market.text_input.return_value = "Test Task"
    mock_st_market.multiselect.return_value = ["Test Market"]
    mock_st_market.time_input.return_value = datetime.time(8, 0)

    # 3. Set session state to the desired state
    mock_session_state_e2e.selected_region = 'Test Region'
    mock_session_state_e2e.selected_market = 'Test Market'
    mock_session_state_e2e.theaters = cache_data["markets"]["Test Market"]["theaters"]
    mock_session_state_e2e.all_showings = {
        'Test Theater 1': [
            {'film_title': 'Test Movie 1', 'showtime': '10:00am', 'daypart': 'Matinee', 'ticket_url': 'http://example.com/ticket1'}
        ]
    }
    mock_session_state_e2e.selected_theaters = ['Test Theater 1']
    mock_session_state_e2e.selected_showtimes = {
        'Test Theater 1': {
            'Test Movie 1': {
                '10:00am': [{'film_title': 'Test Movie 1', 'showtime': '10:00am', 'format': 'Standard', 'daypart': 'Matinee', 'ticket_url': 'http://example.com/ticket1'}]
            }
        }
    }

    # Mock the return value for the scrape itself to simulate a successful run with data
    mock_scrape_result = ([{
        'Theater Name': 'Test Theater 1', 
        'Film Title': 'Test Movie 1', 
        'Showtime': '10:00am',
        'Format': 'Standard',
        'Ticket Type': 'Adult',
        'Price': '$10.00',
        'Capacity': 'Available'
    }], [{'film_title': 'Test Movie 1'}])
    mock_run_async.return_value = (MagicMock(), lambda: ('success', mock_scrape_result, "log message", 0.5))

    # Mock st.rerun to prevent it from stopping the test and to assert it's called
    mock_st_market.rerun = MagicMock()

    # 4. Call the main function
    # We patch users.init_database to prevent it from creating a real users.db file during the test run.
    with patch('app.price_scout_app.st', mock_st_market), patch('app.users.init_database'):
        price_scout_main() # Initial call to start the process
        price_scout_main() # Second call to process the scrape result
        price_scout_main() # Third call to finalize the report

    # 5. Verify that the scrape was triggered and the state was updated correctly
    mock_run_async.assert_called_once()
    mock_st_market.write.assert_any_call("DEBUG: current_index=0, len(queue)=1")
    # The app should set report_running to False after the scrape
    assert mock_st_market.session_state.report_running == False
    # The stage should be updated to show the report
    assert mock_st_market.session_state.stage == 'report_generated'
    # The final dataframe should be populated
    assert not mock_st_market.session_state.final_df.empty
    # The app should rerun to display the new state
    mock_st_market.rerun.assert_called_once()