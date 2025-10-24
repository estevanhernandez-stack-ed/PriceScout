import pytest
import pandas as pd
import io
import openpyxl
import datetime
import json
import os
import pytz
import streamlit as st
from unittest.mock import patch

from app.utils import style_price_change, to_excel, to_csv, check_cache_status, log_runtime, format_price_change, style_price_change_v2, get_error_message, normalize_time_string, format_theater_name_for_display, is_run_allowed, estimate_scrape_time, clear_workflow_state

def test_style_price_change():
    assert style_price_change("▲$5.00") == 'background-color: #e6ffe6' # Light green
    assert style_price_change("▼$5.00") == 'background-color: #ffe6e6' # Light red
    assert style_price_change("$0.00") == ''
    assert style_price_change("No Change") == ''

def test_format_price_change():
    """Tests the format_price_change function."""
    assert format_price_change('$10.00', '$15.00') == '▲5.00'
    assert format_price_change('$15.00', '$10.00') == '▼5.00'
    assert format_price_change('$10.00', '$10.00') == '—'
    assert format_price_change(None, '$10.00') == 'N/A'
    assert format_price_change('$10.00', None) == 'N/A'

def test_style_price_change_v2():
    """Tests the style_price_change_v2 function."""
    assert style_price_change_v2('▲$5.00') == 'color: green'
    assert style_price_change_v2('▼$5.00') == 'color: red'
    assert style_price_change_v2('—') == ''
    assert style_price_change_v2('Some other string') == ''

def test_get_error_message():
    """Tests the get_error_message utility."""
    assert get_error_message(ValueError("Test error")) == "Test error"
    assert get_error_message("a string") == "An unknown error occurred."
    assert get_error_message(123) == "An unknown error occurred."

def test_normalize_time_string():
    """Tests the normalization of various time string formats."""
    assert normalize_time_string('4:15p') == '04:15PM'
    assert normalize_time_string('10:30 AM') == '10:30AM'
    assert normalize_time_string('12:00pm') == '12:00PM'
    assert normalize_time_string('1:00 a.m.') == '01:00AM'
    assert normalize_time_string(None) == ""

def test_format_theater_name_for_display():
    """Tests the cleaning of theater names for display."""
    assert format_theater_name_for_display('My Cinema Theatre') == 'My Cinema'
    assert format_theater_name_for_display('My Cinema Theater') == 'My Cinema'
    assert format_theater_name_for_display('My Cinema') == 'My Cinema'
    assert format_theater_name_for_display('My Cinema Theatre ') == 'My Cinema'

def test_to_excel():
    df = pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})
    excel_data = to_excel(df)
    assert isinstance(excel_data, bytes)
    # check if it's a valid excel file
    workbook = openpyxl.load_workbook(io.BytesIO(excel_data))
    assert workbook.sheetnames == ['Sheet1']

def test_to_csv():
    df = pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})
    csv_data = to_csv(df)
    assert isinstance(csv_data, bytes)
    expected = 'col1,col2\n1,3\n2,4\n'
    assert csv_data.decode('utf-8').replace('\r\n', '\n') == expected

def test_check_cache_status_missing(monkeypatch):
    monkeypatch.setattr('app.config.CACHE_FILE', 'non_existent_file.json')
    status, last_updated = check_cache_status()
    assert status == "missing"
    assert last_updated is None

def test_check_cache_status_invalid(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("invalid json")
    monkeypatch.setattr('app.config.CACHE_FILE', str(cache_file))
    status, last_updated = check_cache_status()
    assert status == "stale"
    assert last_updated == "Error reading cache"

def test_check_cache_status_stale(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    stale_date = datetime.datetime.now() - datetime.timedelta(days=4)
    cache_data = {"metadata": {"last_updated": stale_date.isoformat()}}
    cache_file.write_text(json.dumps(cache_data))
    monkeypatch.setattr('app.config.CACHE_FILE', str(cache_file))
    monkeypatch.setattr('app.config.CACHE_EXPIRATION_DAYS', 3)
    status, last_updated = check_cache_status()
    assert status == "stale"
    assert last_updated == stale_date.strftime('%Y-%m-%d %H:%M:%S')

def test_check_cache_status_fresh(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    fresh_date = datetime.datetime.now() - datetime.timedelta(days=2)
    cache_data = {"metadata": {"last_updated": fresh_date.isoformat()}}
    cache_file.write_text(json.dumps(cache_data))
    monkeypatch.setattr('app.config.CACHE_FILE', str(cache_file))
    monkeypatch.setattr('app.config.CACHE_EXPIRATION_DAYS', 3)
    status, last_updated = check_cache_status()
    assert status == "fresh"
    assert last_updated == fresh_date.strftime('%Y-%m-%d %H:%M:%S')

def test_log_runtime(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    log_file = reports_dir / "runtime.csv"
    monkeypatch.setattr('app.config.REPORTS_DIR', str(reports_dir)) # Mock REPORTS_DIR
    monkeypatch.setattr('app.config.RUNTIME_LOG_FILE', str(log_file))
    log_runtime("Test Mode", 10, 100, 123.456)
    assert os.path.exists(log_file)
    with open(log_file, 'r') as f:
        content = f.read()
        assert "Test Mode" in content
        assert "10" in content
        assert "100" in content
        assert "123.456" in content

@patch('app.utils.datetime')
def test_is_run_allowed(mock_datetime):
    """Tests the is_run_allowed function with mocked time."""
    # Mock 'now' to be 7 AM in Chicago (13:00 UTC on a non-DST day)
    mock_now_utc_early = datetime.datetime(2025, 1, 1, 13, 0, 0, tzinfo=pytz.utc)
    mock_datetime.datetime.now.return_value = mock_now_utc_early
    
    # It's before 8 AM, so it should be allowed
    assert is_run_allowed("America/Chicago") is True

    # Mock 'now' to be 9 AM in Chicago (15:00 UTC on a non-DST day)
    mock_now_utc_late = datetime.datetime(2025, 1, 1, 15, 0, 0, tzinfo=pytz.utc)
    mock_datetime.datetime.now.return_value = mock_now_utc_late

    # It's after 8 AM, so it should not be allowed
    assert is_run_allowed("America/Chicago") is False

def test_estimate_scrape_time(tmp_path, monkeypatch):
    """Tests the scrape time estimation based on historical log data."""
    log_file = tmp_path / "runtime.csv"
    monkeypatch.setattr('app.config.RUNTIME_LOG_FILE', str(log_file))

    # Case 1: No log file
    assert estimate_scrape_time(10) == -1

    # Case 2: Log file exists but is empty
    log_file.write_text("timestamp,mode,num_theaters,num_showings,duration_seconds\n")
    assert estimate_scrape_time(10) == -1

    # Case 3: Valid log file
    log_content = (
        "timestamp,mode,num_theaters,num_showings,duration_seconds\n"
        "2025-01-01,Market Mode,5,50,100\n"  # 2s per showing
        "2025-01-02,CompSnipe Mode,10,100,400\n" # 4s per showing
    )
    log_file.write_text(log_content)
    # Average time per showing is (2+4)/2 = 3s.
    # Estimated time for 10 showings should be 10 * 3 = 30s.
    assert estimate_scrape_time(10) == pytest.approx(30.0)



def test_clear_workflow_state(monkeypatch):
    """Tests that clear_workflow_state correctly removes only workflow-specific keys."""
    # 1. Setup a mock session state with a mix of workflow and persistent keys
    mock_state_dict = {
        # Workflow keys that should be cleared
        'selected_market': 'Test Market',
        'final_df': pd.DataFrame(),
        'stage': 'report_generated',
        'report_running': True,
        'cs_date': datetime.date(2025, 1, 1),
        # Persistent keys that should NOT be cleared
        'logged_in': True,
        'user_name': 'testuser',
        'search_mode': 'Market Mode',
        'dev_mode': True
    }
    
    # Use a class to allow attribute deletion, mimicking st.session_state
    class MockSessionState:
        def __init__(self, state_dict):
            self.__dict__.update(state_dict)
        def __contains__(self, key):
            return key in self.__dict__
        def __delitem__(self, key):
            del self.__dict__[key]

    mock_session_object = MockSessionState(mock_state_dict)
    monkeypatch.setattr(st, "session_state", mock_session_object)

    # 2. Call the function
    clear_workflow_state()

    # 3. Assertions
    # Check that workflow keys are gone
    assert 'selected_market' not in st.session_state.__dict__
    assert 'stage' not in st.session_state.__dict__
    # Check that persistent keys remain
    assert 'logged_in' in st.session_state.__dict__
    assert st.session_state.logged_in is True
