import pytest
import streamlit as st
from unittest.mock import MagicMock, patch
import pandas as pd
import datetime
import sqlite3

# Add path for imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.modes.analysis_mode import render_theater_analysis, render_film_analysis, render_analysis_mode
from app import database, config

@pytest.fixture
def mock_db_with_new_schema(tmp_path, monkeypatch):
    """Sets up an in-memory SQLite database with the NEW schema and sample data."""
    db_path = tmp_path / "test_analysis_new.db"
    monkeypatch.setattr('app.config.DB_FILE', str(db_path))
    database.init_database() # Use the official init to create the new schema

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # Insert data
        d1 = '2025-09-15'
        d2 = '2025-09-16'
        cursor.execute("INSERT INTO scrape_runs (run_id, run_timestamp, mode) VALUES (1, ?, 'Market')", (f'{d1} 12:00:00',))
        cursor.execute("INSERT INTO scrape_runs (run_id, run_timestamp, mode) VALUES (2, ?, 'Market')", (f'{d2} 12:00:00',))
        
        # Showings
        cursor.execute("INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart) VALUES (?, 'Theater A', 'Film 1', '10:00am', '2D', 'Matinee')", (d1,))
        s1_id = cursor.lastrowid
        cursor.execute("INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart) VALUES (?, 'Theater B', 'Film 1', '11:00am', '2D', 'Matinee')", (d1,))
        s2_id = cursor.lastrowid
        cursor.execute("INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart) VALUES (?, 'Theater A', 'Film 2', '8:00pm', 'IMAX', 'Prime')", (d2,))
        s3_id = cursor.lastrowid

        # Prices
        cursor.execute("INSERT INTO prices (run_id, showing_id, ticket_type, price) VALUES (1, ?, 'Adult', 15.00)", (s1_id,))
        cursor.execute("INSERT INTO prices (run_id, showing_id, ticket_type, price) VALUES (1, ?, 'Adult', 16.00)", (s2_id,))
        cursor.execute("INSERT INTO prices (run_id, showing_id, ticket_type, price) VALUES (2, ?, 'Adult', 20.00)", (s3_id,))

        # Op Hours
        cursor.execute("INSERT INTO operating_hours (theater_name, scrape_date, open_time, close_time) VALUES ('Theater A', ?, '10:00 AM', '10:00 PM')", (d1,))
        conn.commit()
    return str(db_path)


@pytest.fixture
def mock_analysis_session_state(monkeypatch):
    """Mocks streamlit's session_state object with a MagicMock."""
    mock_session = MagicMock()
    # Pre-initialize attributes that the app expects to exist
    mock_session.analysis_report_df = pd.DataFrame()
    mock_session.film_summary_df = pd.DataFrame()
    mock_session.film_detail_data = pd.DataFrame()
    return mock_session

# Tests for the Theater-first workflow
@patch('app.modes.analysis_mode.st')
def test_theater_analysis_generate_prices_report(mock_st, mock_db_with_new_schema, mock_analysis_session_state):
    """Tests generating a 'Prices' report in the theater-centric analysis."""
    # Setup the mock session state
    mock_st.session_state = mock_analysis_session_state
    mock_st.session_state.analysis_data_type = "Prices"
    mock_st.session_state.analysis_theaters = ["Theater A"]
    mock_st.session_state.analysis_date_range = (datetime.date(2025, 9, 15), datetime.date(2025, 9, 16))
    mock_st.button.return_value = True
    mock_st.spinner.return_value.__enter__.return_value = None
    
    markets_data = {"Test Company": {"Test Director": {"Test Market": {}}}}
    cache_data = {"markets": {"Test Market": {"theaters": [{"name": "Theater A"}]}}}
    mock_st.session_state.selected_company = "Test Company"
    mock_st.session_state.analysis_market_select = "Test Market"
    mock_st.columns.return_value = (MagicMock(), MagicMock())

    render_theater_analysis(markets_data, cache_data)

    mock_st.spinner.assert_called_with("Querying historical data...")
    # Assert against the mock object, which has been updated by the function
    report_df = mock_st.session_state.analysis_report_df
    assert not report_df.empty
    assert 'film_title' in report_df.columns
    assert 'Film 1' in report_df['film_title'].values
    assert 'Film 2' in report_df['film_title'].values

@patch('app.modes.analysis_mode.st')
def test_theater_analysis_no_data_found(mock_st, mock_db_with_new_schema, mock_analysis_session_state):
    """Tests the warning message when no data is found in theater-centric analysis."""
    mock_st.session_state = mock_analysis_session_state
    mock_st.session_state.analysis_data_type = "Prices"
    mock_st.session_state.analysis_theaters = ["Theater C"] # A theater with no data
    mock_st.session_state.analysis_date_range = (datetime.date(2025, 9, 15), datetime.date(2025, 9, 15))
    mock_st.button.return_value = True
    mock_st.spinner.return_value.__enter__.return_value = None
    
    markets_data = {"Test Company": {"Test Director": {"Test Market": {}}}}
    cache_data = {"markets": {"Test Market": {"theaters": [{"name": "Theater C"}]}}}
    mock_st.session_state.selected_company = "Test Company"
    mock_st.session_state.analysis_director_select = "Test Director"
    mock_st.session_state.analysis_market_select = "Test Market"
    mock_st.columns.return_value = (MagicMock(), MagicMock())

    render_theater_analysis(markets_data, cache_data)
    
    assert mock_st.session_state.analysis_report_df.empty
    mock_st.warning.assert_called_with("No data found for the selected criteria.")

# Tests for the Film-first workflow
@patch('app.modes.analysis_mode.st')
def test_film_analysis_workflow(mock_st, mock_db_with_new_schema, mock_analysis_session_state):
    """Tests the full workflow of the 'Film' analysis mode."""
    # --- Setup ---
    mock_st.session_state = mock_analysis_session_state
    mock_st.session_state.analysis_data_type = "Film"
    mock_st.session_state.film_analysis_date_range_start = datetime.date(2025, 9, 15)
    mock_st.session_state.film_analysis_date_range_end = datetime.date(2025, 9, 16)
    mock_st.button.return_value = True # Simulate clicking "Generate Film Report"
    mock_st.spinner.return_value.__enter__.return_value = None
    
    # --- Execution 1: Generate Summary Report ---
    render_film_analysis({})

    mock_st.button.return_value = False

    # --- Assertions 1 ---
    mock_st.spinner.assert_called_with("Querying and analyzing film data...")
    summary_df = mock_st.session_state.film_summary_df
    
    assert not summary_df.empty
    assert len(summary_df) == 2
    assert 'Film Title' in summary_df.columns
    assert 'Total Showings' in summary_df.columns
    assert 'Theaters Playing' in summary_df.columns
    assert 'Average Price' in summary_df.columns

    film1_row = summary_df[summary_df['Film Title'] == 'Film 1'].iloc[0]
    assert film1_row['Total Showings'] == 2
    assert film1_row['Theaters Playing'] == 2
    assert film1_row['Average Price'] == '$15.50'

    mock_st.dataframe.assert_any_call(summary_df, use_container_width=True, hide_index=True)

@patch('app.modes.analysis_mode.render_film_analysis')
@patch('app.modes.analysis_mode.render_theater_analysis')
@patch('app.modes.analysis_mode.st')
def test_render_analysis_mode_selection(mock_st, mock_render_theater, mock_render_film, mock_analysis_session_state):
    """Test that the correct render function is called based on data type selection."""
    
    # --- Test 1: No data type selected ---
    mock_st.session_state = mock_analysis_session_state
    mock_st.session_state.analysis_data_type = None
    render_analysis_mode({}, {})

    # --- Test 2: 'Film' data type selected ---
    mock_st.session_state.analysis_data_type = 'Film'
    render_analysis_mode({}, {})
    
    # Reset mocks
    mock_render_film.reset_mock()
    mock_render_theater.reset_mock()

    # --- Test 3: Other data type ('Prices') selected ---
    mock_st.session_state.analysis_data_type = 'Prices'
    render_analysis_mode({'data': 1}, {'cache': 2})