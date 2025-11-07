import pytest
import streamlit as st
from unittest.mock import MagicMock, patch
from app.modes.operating_hours_mode import run_weekly_report_logic
import pandas as pd
import datetime

@pytest.fixture
def mock_session_state(monkeypatch):
    """Fixture to mock streamlit's session_state."""
    mock_state = MagicMock()
    mock_state.selected_region = 'Test Region'
    mock_state.selected_market = 'Test Market'
    mock_state.theaters = [{'name': 'Test Theater 1'}]
    mock_state.selected_theaters = ['Test Theater 1']
    mock_state.all_showings = {
        'Test Theater 1': [
            {'film_title': 'Test Movie 1', 'showtime': '10:00am', 'daypart': 'Matinee', 'market': 'Test Market'},
            {'film_title': 'Test Movie 1', 'showtime': '8:00pm', 'daypart': 'Prime', 'market': 'Test Market'},
        ]
    }
    mock_state.market_date = pd.to_datetime('2025-09-08').date()
    mock_state.daypart_selections = set()
    mock_state.selected_showtimes = {}
    mock_state.report_running = False
    monkeypatch.setattr(st, "session_state", mock_state)
    return mock_state

@patch('app.utils.process_and_save_operating_hours')
def test_save_op_hours_after_partial_scrape(mock_process_and_save, mock_session_state, monkeypatch):
    """
    Integration test to simulate the workflow of saving operating hours
    after a partial scrape.
    """
    # 1. Simulate a partial scrape by selecting only one showtime
    mock_session_state['selected_showtimes'] = {
        'Test Theater 1': {
            'Test Movie 1': {
                '10:00am': [{'film_title': 'Test Movie 1', 'showtime': '10:00am', 'daypart': 'Matinee'}]
            }
        }
    }

    # 2. Mock the function that would be called
    from app.utils import save_operating_hours_from_all_showings

    # 3. Simulate the user selecting "All" dayparts to trigger the save
    mock_session_state['daypart_selections'] = {"All"}

    # 4. Call the function that saves the operating hours
    save_operating_hours_from_all_showings(
        mock_session_state.all_showings,
        ['Test Theater 1'],
        mock_session_state.market_date,
        'Test Market'
    )

    # 5. Assert that the processing function was called with the correct data
    mock_process_and_save.assert_called_once()
    call_args = mock_process_and_save.call_args[0]
    results_by_date = call_args[0]

    date_key = mock_session_state.market_date.strftime('%Y-%m-%d')
    assert date_key in results_by_date
    assert 'Test Theater 1' in results_by_date[date_key]
    assert results_by_date[date_key]['Test Theater 1'][0]['market'] == 'Test Market'


@patch('app.modes.operating_hours_mode.run_async_in_thread')
@patch('app.modes.operating_hours_mode.database')
@patch('app.modes.operating_hours_mode.datetime')
def test_weekly_operating_hours_report_logic(mock_datetime, mock_database, mock_run_async, monkeypatch):
    """Tests the weekly report logic, including data saving and row consolidation."""
    # 1. Setup
    # Keep the original date and timedelta classes, only mock the 'today' method.
    mock_datetime.date = MagicMock()
    mock_datetime.date.today.return_value = datetime.date(2025, 9, 15)  # A Monday
    mock_datetime.timedelta = datetime.timedelta
    mock_datetime.datetime.strptime = datetime.datetime.strptime  # Keep strptime working

    monkeypatch.setattr('app.config.REPORTS_DIR', 'dummy_reports_dir')
    monkeypatch.setattr('app.config.RUNTIME_LOG_FILE', 'dummy_runtime_log.csv')

    mock_session = MagicMock()
    mock_session.selected_company = 'TestCompany'
    mock_session.run_weekly_op_hours_report = True
    monkeypatch.setattr(st, "session_state", mock_session)

    mock_scout = MagicMock()
    mock_cache_data = {
        "markets": {"Market1": {"theaters": [
            {"name": "Theater A", "company": "TestCompany"},
            {"name": "Theater B", "company": "TestCompany"},
            {"name": "Theater C", "company": "OtherCompany"}
        ]}}
    }

    # Mock the scrape to return consistent hours for the whole week
    current_week_scrape_result = {
        'Theater A': [{'showtime': '10:00am', 'film_title': 'Film A'}, {'showtime': '10:00pm', 'film_title': 'Film A'}],
        'Theater B': [{'showtime': '11:00am', 'film_title': 'Film B'}, {'showtime': '11:00pm', 'film_title': 'Film B'}]
    }
    mock_run_async.return_value = (MagicMock(), lambda: ('success', current_week_scrape_result, "", 0.1))

    previous_week_hours = pd.DataFrame({
        'scrape_date': ['2025-09-11', '2025-09-11'],
        'theater_name': ['Theater A', 'Theater B'],
        'open_time': ['10:00 AM', '12:00 PM'], # A is same, B is different
        'close_time': ['10:00 PM', '11:00 PM'] # B is same
    })
    mock_database.get_operating_hours_for_theaters_and_dates.return_value = previous_week_hours

    # Mock the saving function that is passed into the logic
    mock_process_and_save_func = MagicMock()

    # 2. Execution
    run_weekly_report_logic(mock_scout, mock_cache_data, mock_process_and_save_func, all_theaters=[t for t in mock_cache_data['markets']['Market1']['theaters'] if t['company'] == 'TestCompany'])

    # 3. Assertions
    assert mock_run_async.call_count == 7 # Thu to Wed
    mock_database.get_operating_hours_for_theaters_and_dates.assert_called_once()
    db_call_args = mock_database.get_operating_hours_for_theaters_and_dates.call_args[0]
    assert set(db_call_args[0]) == {'Theater A', 'Theater B'}
    assert db_call_args[1] == datetime.date(2025, 9, 11)
    assert db_call_args[2] == datetime.date(2025, 9, 18)

    # Assert that the silent save function was called correctly
    mock_process_and_save_func.assert_called_once()
    save_call_args, save_call_kwargs = mock_process_and_save_func.call_args
    assert "Weekly Operating Hours Report for TestCompany (Thu-Thu)" in save_call_args[1]
    assert save_call_kwargs == {'silent': True}
    assert '2025-09-18' in save_call_args[0] # Check if results were passed

    report_df = st.session_state.weekly_op_hours_report_data
    assert report_df is not None
    
    theater_a_df = report_df[report_df['Theater'] == 'Theater A']
    assert len(theater_a_df) == 2 # One row for 'No' change, one for 'New'
    no_change_row_a = theater_a_df[theater_a_df['Changed'] == '✅ No Change'].iloc[0]
    assert no_change_row_a['Day'] == 'Thursday'
    assert no_change_row_a['Current Week Hours'] == '10:00 AM - 10:00 PM'
    assert no_change_row_a['Previous Week Hours'] == '10:00 AM - 10:00 PM'

    theater_b_df = report_df[report_df['Theater'] == 'Theater B']
    assert len(theater_b_df) == 2 # One row for 'Yes' change, one for 'New'
    yes_change_row_b = theater_b_df[theater_b_df['Changed'] == '🔄 Changed'].iloc[0]
    assert yes_change_row_b['Day'] == 'Thursday'
    assert yes_change_row_b['Current Week Hours'] == '11:00 AM - 11:00 PM'
    assert yes_change_row_b['Previous Week Hours'] == '12:00 PM - 11:00 PM'

    assert st.session_state.run_weekly_op_hours_report is False
