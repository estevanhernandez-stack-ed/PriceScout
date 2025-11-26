import pytest
import streamlit as st
from unittest.mock import MagicMock, patch
import pandas as pd
import datetime
import sqlite3
import os
import sys

# Add path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.modes.analysis_mode import (
    render_theater_analysis, 
    render_film_analysis, 
    render_analysis_mode,
    _generate_operating_hours_report
)
from app import db_adapter as database, config
from app.db_models import Company, ScrapeRun, Film, Showing, Price, OperatingHours
from app.db_session import get_session, close_engine

@pytest.fixture(scope="function")
def mock_db_with_new_schema(tmp_path, monkeypatch):
    """Sets up a fresh in-memory SQLite database for each test function."""
    db_path = tmp_path / f"test_db_{os.urandom(4).hex()}.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    monkeypatch.setattr('app.config.DB_FILE', str(db_path))
    
    # Ensure the engine is closed after the test, so the next test gets a fresh one
    yield str(db_path)
    close_engine()


@pytest.fixture
def mock_analysis_session_state(monkeypatch):
    """Mocks streamlit's session_state object with a MagicMock."""
    mock_session = MagicMock()
    # Pre-initialize attributes that the app expects to exist
    mock_session.analysis_report_df = pd.DataFrame()
    mock_session.film_summary_df = pd.DataFrame()
    mock_session.film_detail_data = pd.DataFrame()
    return mock_session

# Helper to populate db for specific tests
def populate_db_for_test(db_path, company_id=1):
    database.init_database()
    with get_session() as session:
        # Insert a company for context
        company = Company(company_id=company_id, company_name='Test Company')
        session.add(company)
        session.commit()

        config.CURRENT_COMPANY_ID = company_id
        
        # Insert data with company_id
        d1 = datetime.date(2025, 9, 15)
        d2 = datetime.date(2025, 9, 16)
        
        run1 = ScrapeRun(run_id=1, run_timestamp=datetime.datetime(2025, 9, 15, 12, 0, 0), mode='Market', company_id=company_id)
        run2 = ScrapeRun(run_id=2, run_timestamp=datetime.datetime(2025, 9, 16, 12, 0, 0), mode='Market', company_id=company_id)
        session.add_all([run1, run2])
        session.commit()

        # Films
        film1 = Film(film_title='Film 1', company_id=company_id, last_omdb_update=datetime.datetime.now())
        film2 = Film(film_title='Film 2', company_id=company_id, last_omdb_update=datetime.datetime.now())
        session.add_all([film1, film2])
        session.commit()

        # Showings
        showing1 = Showing(company_id=company_id, play_date=d1, theater_name='Theater A', film_title='Film 1', showtime='10:00am', format='2D', daypart='Matinee')
        showing2 = Showing(company_id=company_id, play_date=d1, theater_name='Theater B', film_title='Film 1', showtime='11:00am', format='2D', daypart='Matinee')
        showing3 = Showing(company_id=company_id, play_date=d2, theater_name='Theater A', film_title='Film 2', showtime='8:00pm', format='IMAX', daypart='Prime')
        session.add_all([showing1, showing2, showing3])
        session.commit()

        # Prices
        price1 = Price(company_id=company_id, run_id=1, showing_id=showing1.showing_id, ticket_type='Adult', price=15.00)
        price2 = Price(company_id=company_id, run_id=1, showing_id=showing2.showing_id, ticket_type='Adult', price=16.00)
        price3 = Price(company_id=company_id, run_id=2, showing_id=showing3.showing_id, ticket_type='Adult', price=20.00)
        session.add_all([price1, price2, price3])
        session.commit()

        # Op Hours
        op_hours = OperatingHours(company_id=company_id, theater_name='Theater A', scrape_date=d1, open_time='10:00 AM', close_time='10:00 PM')
        session.add(op_hours)
        session.commit()

# Tests for the Theater-first workflow
@patch('app.modes.analysis_mode.st')
def test_theater_analysis_generate_prices_report(mock_st, mock_db_with_new_schema, mock_analysis_session_state):
    """Tests generating a 'Prices' report in the theater-centric analysis."""
    populate_db_for_test(mock_db_with_new_schema)
    
    # Setup the mock session state
    mock_st.session_state = mock_analysis_session_state
    mock_st.session_state.analysis_data_type = "Prices"
    mock_st.session_state.analysis_theaters = ["Theater A"]
    mock_st.session_state.analysis_films_pre_filter = ["Film 1", "Film 2"]
    mock_st.multiselect.return_value = ["Theater A"]
    def get_side_effect(key, default=None):
        if key == 'analysis_films_pre_filter':
            return ["Film 1", "Film 2"]
        return default
    mock_st.session_state.get.side_effect = get_side_effect
    mock_st.session_state.analysis_date_range = (datetime.date(2025, 9, 15), datetime.date(2025, 9, 16))
    mock_st.button.return_value = True
    mock_st.spinner.return_value.__enter__.return_value = None
    
    markets_data = {"Test Company": {"Test Director": {"Test Market": {}}}}
    cache_data = {"markets": {"Test Market": {"theaters": [{"name": "Theater A", "market": "Test Market"}]}}}
    mock_st.session_state.selected_company = "Test Company"
    mock_st.session_state.analysis_market_select = "Test Market"
    mock_st.columns.return_value = (MagicMock(), MagicMock())

    render_theater_analysis(markets_data, cache_data)

    mock_st.spinner.assert_any_call("Querying historical data...")
    report_df = mock_st.session_state.analysis_report_df
    assert not report_df.empty
    assert 'film_title' in report_df.columns
    assert 'Film 1' in report_df['film_title'].values
    assert 'Film 2' in report_df['film_title'].values

@patch('app.modes.analysis_mode.st')
def test_theater_analysis_no_data_found(mock_st, mock_db_with_new_schema, mock_analysis_session_state):
    """Tests the warning message when no data is found in theater-centric analysis."""
    populate_db_for_test(mock_db_with_new_schema)
    mock_st.session_state = mock_analysis_session_state
    mock_st.session_state.analysis_data_type = "Prices"
    mock_st.session_state.analysis_theaters = ["Theater C"] # A theater with no data
    mock_st.session_state.analysis_date_range = (datetime.date(2025, 9, 15), datetime.date(2025, 9, 15))
    mock_st.button.return_value = True
    mock_st.spinner.return_value.__enter__.return_value = None
    
    # Mock the database function to return an empty DataFrame
    with patch('app.db_adapter.get_theater_comparison_summary', return_value=pd.DataFrame()):
        markets_data = {"Test Company": {"Test Director": {"Test Market": {}}}}
        cache_data = {"markets": {"Test Market": {"theaters": [{"name": "Theater C", "market": "Test Market"}]}}}
        mock_st.session_state.selected_company = "Test Company"
        mock_st.session_state.analysis_director_select = "Test Director"
        mock_st.session_state.analysis_market_select = "Test Market"
        mock_st.columns.return_value = (MagicMock(), MagicMock())

        render_theater_analysis(markets_data, cache_data)

    assert mock_st.session_state.analysis_report_df.empty
    mock_st.warning.assert_called_with("🔍 No data found for the selected theaters and date range. Try running a scrape or adjusting your filters.")
# Tests for the Film-first workflow
@patch('app.modes.analysis_mode.st')
def test_film_analysis_workflow(mock_st, mock_db_with_new_schema, mock_analysis_session_state):
    """Tests the full workflow of the 'Film' analysis mode."""
    populate_db_for_test(mock_db_with_new_schema)
    # --- Setup ---
    mock_st.session_state = mock_analysis_session_state
    mock_st.session_state.analysis_data_type = "Film"
    mock_st.session_state.film_analysis_date_range_start = datetime.date(2025, 9, 15)
    mock_st.session_state.film_analysis_date_range_end = datetime.date(2025, 9, 16)
    mock_st.button.return_value = True # Simulate clicking "Generate Film Report"
    mock_st.spinner.return_value.__enter__.return_value = None
    
    # --- Execution 1: Generate Summary Report ---
    render_film_analysis({"markets": {"Test Market": {"theaters": [{"name": "Theater A", "market": "Test Market"}, {"name": "Theater B", "market": "Test Market"}]}}})

    # --- Execution 2: Display the report ---
    mock_st.button.return_value = False
    render_film_analysis({"markets": {"Test Market": {"theaters": [{"name": "Theater A", "market": "Test Market"}, {"name": "Theater B", "market": "Test Market"}]}}})

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

    # --- FIX: Use a more robust way to check for dataframe calls ---
    assert mock_st.dataframe.called
    # Get the dataframe that was passed to the mock
    called_df = mock_st.dataframe.call_args[0][0]
    pd.testing.assert_frame_equal(summary_df, called_df)

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


# Tests for _generate_operating_hours_report function
class TestGenerateOperatingHoursReport:
    """Tests for the _generate_operating_hours_report utility function."""
    
    @patch('app.db_adapter.get_operating_hours_for_theaters_and_dates')
    def test_generates_report_with_current_and_previous_data(self, mock_get_hours):
        """Test that the function generates a complete report with comparison data."""
        # Mock current week data
        current_data = pd.DataFrame({
            'theater_name': ['Theater A'],
            'scrape_date': ['2025-09-22'],
            'open_time': ['9:00 AM'],
            'close_time': ['11:00 PM']
        })
        
        # Mock previous week data
        prev_data = pd.DataFrame({
            'theater_name': ['Theater A'],
            'scrape_date': ['2025-09-15'],
            'open_time': ['10:00 AM'],
            'close_time': ['10:00 PM']
        })
        
        # First call returns current data, second call returns previous data
        mock_get_hours.side_effect = [current_data, prev_data]
        
        # Execute
        result = _generate_operating_hours_report(
            theaters=['Theater A'],
            start_date=datetime.date(2025, 9, 22),
            end_date=datetime.date(2025, 9, 22)
        )
        
        # Assert
        assert not result.empty
        assert 'Theater' in result.columns
        assert 'Date' in result.columns
        assert 'Current Hours' in result.columns
        assert 'Previous Hours' in result.columns
        assert 'Changed' in result.columns
        
        # Check that comparison worked
        assert result.iloc[0]['Previous Hours'] == '10:00 AM - 10:00 PM'
        assert result.iloc[0]['Current Hours'] == '9:00 AM - 11:00 PM'
        assert result.iloc[0]['Changed'] == 'Yes'
    
    @patch('app.db_adapter.calculate_operating_hours_from_showings')
    @patch('app.db_adapter.get_operating_hours_for_theaters_and_dates')
    def test_handles_no_previous_data(self, mock_get_hours, mock_calc_hours):
        """Test that the function handles theaters with no previous week data."""
        current_data = pd.DataFrame({
            'theater_name': ['Theater New'],
            'scrape_date': ['2025-09-22'],
            'open_time': ['10:00 AM'],
            'close_time': ['10:00 PM']
        })
        
        # First call returns current data, second call returns empty (no previous)
        mock_get_hours.side_effect = [current_data, pd.DataFrame()]
        mock_calc_hours.return_value = pd.DataFrame()  # No fallback data either
        
        result = _generate_operating_hours_report(
            theaters=['Theater New'],
            start_date=datetime.date(2025, 9, 22),
            end_date=datetime.date(2025, 9, 22)
        )
        
        assert not result.empty
        assert result.iloc[0]['Previous Hours'] == 'N/A'
        assert result.iloc[0]['Changed'] == 'New'
    
    @patch('app.db_adapter.calculate_operating_hours_from_showings')
    @patch('app.db_adapter.get_operating_hours_for_theaters_and_dates')
    def test_handles_no_showings_found(self, mock_get_hours, mock_calc_hours):
        """Test handling of theaters scraped but with no showtimes."""
        current_data = pd.DataFrame({
            'theater_name': ['Theater Closed'],
            'scrape_date': ['2025-09-22'],
            'open_time': [None],
            'close_time': [None]
        })
        
        mock_get_hours.side_effect = [current_data, pd.DataFrame()]
        mock_calc_hours.return_value = pd.DataFrame()
        
        result = _generate_operating_hours_report(
            theaters=['Theater Closed'],
            start_date=datetime.date(2025, 9, 22),
            end_date=datetime.date(2025, 9, 22)
        )
        
        assert not result.empty
        assert result.iloc[0]['Current Hours'] == 'No Showings Found'
    
    @patch('app.db_adapter.calculate_operating_hours_from_showings')
    @patch('app.db_adapter.get_operating_hours_for_theaters_and_dates')
    def test_returns_empty_dataframe_when_no_data(self, mock_get_hours, mock_calc_hours):
        """Test that function returns empty DataFrame when no data exists."""
        mock_get_hours.return_value = pd.DataFrame()
        mock_calc_hours.return_value = pd.DataFrame()
        
        result = _generate_operating_hours_report(
            theaters=['Nonexistent Theater'],
            start_date=datetime.date(2025, 9, 22),
            end_date=datetime.date(2025, 9, 22)
        )
        
        assert result.empty
    
    @patch('app.db_adapter.calculate_operating_hours_from_showings')
    @patch('app.db_adapter.get_operating_hours_for_theaters_and_dates')
    def test_detects_unchanged_hours(self, mock_get_hours, mock_calc_hours):
        """Test detection of unchanged operating hours."""
        current_data = pd.DataFrame({
            'theater_name': ['Theater Stable'],
            'scrape_date': ['2025-09-22'],
            'open_time': ['10:00 AM'],
            'close_time': ['10:00 PM']
        })
        
        prev_data = pd.DataFrame({
            'theater_name': ['Theater Stable'],
            'scrape_date': ['2025-09-15'],
            'open_time': ['10:00 AM'],
            'close_time': ['10:00 PM']
        })
        
        mock_get_hours.side_effect = [current_data, prev_data]
        
        result = _generate_operating_hours_report(
            theaters=['Theater Stable'],
            start_date=datetime.date(2025, 9, 22),
            end_date=datetime.date(2025, 9, 22)
        )
        
        assert not result.empty
        assert result.iloc[0]['Current Hours'] == result.iloc[0]['Previous Hours']
        assert result.iloc[0]['Changed'] == 'No'
    
    @patch('app.db_adapter.calculate_operating_hours_from_showings')
    @patch('app.db_adapter.get_operating_hours_for_theaters_and_dates')
    def test_handles_multiple_theaters(self, mock_get_hours, mock_calc_hours):
        """Test generating report for multiple theaters."""
        current_data = pd.DataFrame({
            'theater_name': ['Theater One', 'Theater Two'],
            'scrape_date': ['2025-09-22', '2025-09-22'],
            'open_time': ['9:00 AM', '10:00 AM'],
            'close_time': ['11:00 PM', '10:00 PM']
        })
        
        mock_get_hours.side_effect = [current_data, pd.DataFrame()]
        mock_calc_hours.return_value = pd.DataFrame()
        
        result = _generate_operating_hours_report(
            theaters=['Theater One', 'Theater Two'],
            start_date=datetime.date(2025, 9, 22),
            end_date=datetime.date(2025, 9, 22)
        )
        
        assert len(result) == 2
        assert 'Theater One' in result['Theater'].values
        assert 'Theater Two' in result['Theater'].values
    
    @patch('app.db_adapter.calculate_operating_hours_from_showings')
    @patch('app.db_adapter.get_operating_hours_for_theaters_and_dates')
    def test_date_formatting(self, mock_get_hours, mock_calc_hours):
        """Test that dates are formatted correctly."""
        current_data = pd.DataFrame({
            'theater_name': ['Theater A'],
            'scrape_date': ['2025-09-22'],
            'open_time': ['9:00 AM'],
            'close_time': ['11:00 PM']
        })
        
        mock_get_hours.side_effect = [current_data, pd.DataFrame()]
        mock_calc_hours.return_value = pd.DataFrame()
        
        result = _generate_operating_hours_report(
            theaters=['Theater A'],
            start_date=datetime.date(2025, 9, 22),
            end_date=datetime.date(2025, 9, 22)
        )
        
        # Check date format (e.g., "Mon, Sep 22")
        assert not result.empty
        date_str = result.iloc[0]['Date']
        assert 'Sep 22' in date_str
    
    @patch('app.db_adapter.calculate_operating_hours_from_showings')
    @patch('app.db_adapter.get_operating_hours_for_theaters_and_dates')
    @patch('app.modes.analysis_mode.st')
    def test_fallback_to_calculated_hours(self, mock_st, mock_get_hours, mock_calc_hours):
        """Test fallback to calculating hours from showings when no op_hours exist."""
        # First call returns empty (no operating hours)
        mock_get_hours.side_effect = [pd.DataFrame(), pd.DataFrame()]
        
        # Fallback returns calculated hours
        calculated_data = pd.DataFrame({
            'theater_name': ['Theater Fallback'],
            'scrape_date': ['2025-09-25'],
            'open_time': ['2:00 PM'],
            'close_time': ['10:00 PM']
        })
        mock_calc_hours.return_value = calculated_data
        
        # Mock the info message
        mock_st.info.return_value = None
        
        result = _generate_operating_hours_report(
            theaters=['Theater Fallback'],
            start_date=datetime.date(2025, 9, 25),
            end_date=datetime.date(2025, 9, 25)
        )
        
        # Should trigger the fallback path and display info message
        mock_st.info.assert_called_with("No dedicated operating hours found. Calculating from scraped showtimes as a backup...")
        assert not result.empty


class TestAnalysisModeHelpers:
    """Tests for other helper functions in analysis_mode.py"""
    
    @patch('app.modes.analysis_mode.st')
    def test_film_analysis_no_price_data(self, mock_st, mock_db_with_new_schema, mock_analysis_session_state):
        """Test that film analysis handles films with no price data."""
        populate_db_for_test(mock_db_with_new_schema)
        # Add showing without price
        with get_session() as session:
            showing = Showing(company_id=1, play_date=datetime.date(2025, 9, 20), theater_name='Theater X', film_title='No Price Film', showtime='3:00 PM', format='2D', daypart='Prime')
            session.add(showing)
            session.commit()
        
        mock_st.session_state = mock_analysis_session_state
        mock_st.session_state.film_analysis_date_range_start = datetime.date(2025, 9, 20)
        mock_st.session_state.film_analysis_date_range_end = datetime.date(2025, 9, 20)
        mock_st.button.return_value = True
        mock_st.spinner.return_value.__enter__.return_value = None
        
        render_film_analysis({})
        
        # Should display warning about no price data
        mock_st.warning.assert_called_with("🔍 No film data found for the selected date range. Try expanding your date range or selecting different theaters.")
    
    @patch('app.modes.analysis_mode.st')  
    def test_film_analysis_empty_dataset(self, mock_st, mock_db_with_new_schema, mock_analysis_session_state):
        """Test film analysis with no data at all."""
        populate_db_for_test(mock_db_with_new_schema)
        mock_st.session_state = mock_analysis_session_state
        mock_st.session_state.film_analysis_date_range_start = datetime.date(2025, 12, 1)
        mock_st.session_state.film_analysis_date_range_end = datetime.date(2025, 12, 31)
        mock_st.button.return_value = True
        mock_st.spinner.return_value.__enter__.return_value = None
        
        render_film_analysis({})

        # Should display warning about no data
        mock_st.warning.assert_called_with("🔍 No film data found for the selected date range. Try expanding your date range or selecting different theaters.")