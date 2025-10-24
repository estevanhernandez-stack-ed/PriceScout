import pytest
import sqlite3
import pandas as pd
import datetime
import os
import sys

# Add project root to path to allow imports from the 'app' package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import database
from app import config

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Fixture to create a temporary database for testing."""
    db_path = tmp_path / "test_db.db"
    monkeypatch.setattr(config, 'DB_FILE', str(db_path))
    
    # --- FIX: Also patch other file paths to use the temp directory ---
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(config, 'REPORTS_DIR', str(reports_dir))
    monkeypatch.setattr(config, 'RUNTIME_LOG_FILE', str(reports_dir / "runtime_log.csv"))
    
    # Initialize the database with the current schema
    database.init_database()
    database.update_database_schema() # Ensure all columns exist
    
    # Pre-populate with some data
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # Run 1
        cursor.execute("INSERT INTO scrape_runs (run_timestamp, mode, run_context) VALUES (?, ?, ?)", ('2025-09-15 10:00:00', 'Market', 'Test Run 1'))
        run1_id = cursor.lastrowid
        # Run 2
        cursor.execute("INSERT INTO scrape_runs (run_timestamp, mode, run_context) VALUES (?, ?, ?)", ('2025-09-16 11:00:00', 'CompSnipe', 'Test Run 2'))
        run2_id = cursor.lastrowid

        # Showings
        cursor.execute("INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart) VALUES (?, ?, ?, ?, ?, ?)", ('2025-09-15', 'Theater A', 'Film 1', '10:00am', '2D', 'Matinee'))
        showing1_id = cursor.lastrowid
        cursor.execute("INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart) VALUES (?, ?, ?, ?, ?, ?)", ('2025-09-15', 'Theater A', 'Film 2', '11:00am', 'IMAX', 'Matinee'))
        showing2_id = cursor.lastrowid
        # A showing for a film that won't have metadata
        cursor.execute("INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart) VALUES (?, ?, ?, ?, ?, ?)", ('2025-09-15', 'Theater B', 'Film 3 (No Metadata)', '12:00pm', '2D', 'Matinee'))
        showing3_id = cursor.lastrowid

        # Prices
        cursor.execute("INSERT INTO prices (run_id, showing_id, ticket_type, price) VALUES (?, ?, ?, ?)", (run1_id, showing1_id, 'Adult', 15.0))
        cursor.execute("INSERT INTO prices (run_id, showing_id, ticket_type, price) VALUES (?, ?, ?, ?)", (run1_id, showing2_id, 'Adult', 20.0))

        # Operating Hours
        cursor.execute("INSERT INTO operating_hours (run_id, theater_name, scrape_date, open_time, close_time) VALUES (?, ?, ?, ?, ?)", (run1_id, 'Theater A', '2025-09-15', '10:00 AM', '11:00 PM'))
        cursor.execute("INSERT INTO operating_hours (run_id, theater_name, scrape_date, open_time, close_time) VALUES (?, ?, ?, ?, ?)", (run1_id, 'Theater A', '2025-09-16', '10:30 AM', '10:30 PM'))
        cursor.execute("INSERT INTO operating_hours (run_id, theater_name, scrape_date, open_time, close_time) VALUES (?, ?, ?, ?, ?)", (run2_id, 'Theater B', '2025-09-15', '12:00 PM', '11:00 PM'))

        # Films (Metadata)
        cursor.execute("INSERT INTO films (film_title, genre, mpaa_rating, last_omdb_update) VALUES (?, ?, ?, ?)", ('Film 1', 'Action, Adventure', 'PG-13', datetime.datetime.now()))
        cursor.execute("INSERT INTO films (film_title, genre, mpaa_rating, last_omdb_update) VALUES (?, ?, ?, ?)", ('Film 2', 'Comedy', 'R', datetime.datetime.now()))
        cursor.execute("INSERT INTO films (film_title, genre, mpaa_rating, last_omdb_update) VALUES (?, ?, ?, ?)", ('Film 4', 'Family', 'PG', datetime.datetime.now()))
        cursor.execute("INSERT INTO films (film_title, genre, mpaa_rating, last_omdb_update) VALUES (?, ?, ?, ?)", ('Film 5', 'Horror', 'R', datetime.datetime.now())) # Duplicate R
        cursor.execute("INSERT INTO films (film_title, genre, mpaa_rating, last_omdb_update) VALUES (?, ?, ?, ?)", ('Film 6', 'Doc', 'Not Rated', datetime.datetime.now())) # Should be excluded
        cursor.execute("INSERT INTO films (film_title, genre, mpaa_rating, last_omdb_update) VALUES (?, ?, ?, ?)", ('Film 7', 'Indie', 'N/A', datetime.datetime.now())) # Should be excluded
        cursor.execute("INSERT INTO films (film_title, genre, mpaa_rating, last_omdb_update) VALUES (?, ?, ?, ?)", ('Film 8', 'Foreign', None, datetime.datetime.now())) # Should be excluded

        conn.commit()
    
    return str(db_path)

def test_save_prices_with_missing_date_column(temp_db, capsys):
    """
    Tests that save_prices handles a DataFrame missing the 'play_date' column.
    """
    # Create a DataFrame *without* the 'play_date' column
    df = pd.DataFrame([{'Theater Name': 'Theater A', 'Film Title': 'Film 1', 'Showtime': '10:00am', 'Format': '2D', 'Ticket Type': 'Adult', 'Price': '$15.00', 'Capacity': 'Available'}])
    
    # Call the function
    database.save_prices(run_id=1, df=df)
    
    # Check that the correct error was printed
    captured = capsys.readouterr()
    assert "save_prices was called with a DataFrame missing 'play_date' data" in captured.out
    
    # Verify no new prices were added
    with sqlite3.connect(temp_db) as conn:
        prices_df = pd.read_sql("SELECT * FROM prices", conn)
        assert len(prices_df) == 2 # Should only contain the two prices from the fixture

def test_create_and_get_scrape_runs(temp_db):
    """
    Tests creating a new scrape run and then fetching all runs.
    """
    # Create a new run
    new_run_id = database.create_scrape_run(mode="Test Mode", context="A test context")
    assert new_run_id is not None
    
    # Fetch all runs
    runs_df = database.get_scrape_runs()
    
    # There should be 3 runs now (2 from fixture, 1 new)
    assert len(runs_df) == 3
    assert "Test Mode" in runs_df['mode'].values
    assert "A test context" in runs_df['run_context'].values

def test_get_prices_for_run(temp_db):
    """
    Tests fetching the price data associated with a specific run.
    """
    # Run 1 has 2 price points
    prices_df = database.get_prices_for_run(run_id=1)
    assert len(prices_df) == 2
    assert 'Film 1' in prices_df['film_title'].values
    assert 'Film 2' in prices_df['film_title'].values
    
    # Run 2 has 0 price points
    prices_df_empty = database.get_prices_for_run(run_id=2)
    assert prices_df_empty.empty

def test_delete_operating_hours(temp_db):
    """
    Tests that operating hours records can be deleted for a specific theater and date.
    """
    with sqlite3.connect(temp_db) as conn:
        # Verify initial state
        df_before = pd.read_sql("SELECT * FROM operating_hours WHERE theater_name = 'Theater A'", conn)
        assert len(df_before) == 2
        
        # Delete records for one date
        database.delete_operating_hours(theater_names=['Theater A'], scrape_date=datetime.date(2025, 9, 15), conn=conn)
        
        # Verify final state
        df_after = pd.read_sql("SELECT * FROM operating_hours WHERE theater_name = 'Theater A'", conn)
        assert len(df_after) == 1
        assert df_after.iloc[0]['scrape_date'] == '2025-09-16'

def test_get_films_missing_metadata(temp_db):
    """
    Tests the function that finds films in 'showings' that are not in 'films'.
    """
    missing_films = database.get_films_missing_metadata()
    
    assert isinstance(missing_films, list)
    assert len(missing_films) == 1
    assert missing_films[0] == 'Film 3 (No Metadata)'

def test_update_database_schema_idempotent(temp_db):
    """
    Tests that running update_database_schema multiple times doesn't cause errors.
    """
    try:
        # Run it once (already run in fixture, but this is explicit)
        database.update_database_schema()
        # Run it again
        database.update_database_schema()
    except Exception as e:
        pytest.fail(f"update_database_schema failed on second run: {e}")

    # Check that the column is still there
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(scrape_runs)")
        columns = [info[1] for info in cursor.fetchall()]
        assert 'run_context' in columns

def test_get_data_for_trend_report_success(temp_db):
    """
    Tests fetching data for the trend report with valid filters that match fixture data.
    """
    # Define filters that match the data in the fixture
    theater_list = ['Theater A']
    date_list = ['2025-09-15']
    film_list = ['Film 1', 'Film 2']
    daypart_list = ['Matinee']

    # Call the function
    df = database.get_data_for_trend_report(theater_list, date_list, film_list, daypart_list)

    # Assertions
    assert not df.empty
    assert len(df) == 2
    assert all(col in df.columns for col in ['scrape_date', 'theater_name', 'film_title', 'daypart', 'ticket_type', 'price'])
    assert df['theater_name'].unique().tolist() == ['Theater A']
    assert df['film_title'].isin(['Film 1', 'Film 2']).all()
    # The order is not guaranteed by SQL, so sort before comparing
    assert sorted(df['price'].tolist()) == [15.0, 20.0]

def test_get_all_unique_ratings(temp_db):
    """
    Tests that get_all_unique_ratings returns a sorted, unique list of ratings,
    excluding common non-rating values.
    """
    # The temp_db fixture is pre-populated with various ratings
    ratings = database.get_all_unique_ratings()

    assert isinstance(ratings, list)
    # The function should return a sorted list of unique, valid ratings
    assert ratings == ['PG', 'PG-13', 'R']
def test_get_data_for_trend_report_no_results(temp_db):
    """
    Tests the get_market_at_a_glance_data function.
    """
    # This test uses the data pre-populated by the temp_db fixture.
    # We expect to get data for 'Film 1' and 'Film 2' which were scraped recently.
    
    theater_list = ['Theater A', 'Theater B']
    
    # Call the function
    df, latest_date = database.get_market_at_a_glance_data(theater_list)

    # Assertions
    assert not df.empty
    assert isinstance(df, pd.DataFrame)
    assert isinstance(latest_date, datetime.date)

    # Check that the latest scrape date is correct (from run 2 in the fixture)
    assert latest_date == datetime.date(2025, 9, 16)

    # Check for expected columns, including the joined 'release_date'
    expected_cols = ['theater_name', 'film_title', 'daypart', 'release_date', 'ticket_type', 'price', 'run_timestamp']
    assert all(col in df.columns for col in expected_cols)

    # Check that the data is correct
    assert 'Film 1' in df['film_title'].values
    assert 'Film 2' in df['film_title'].values
    assert df[df['film_title'] == 'Film 1']['price'].iloc[0] == 15.0

def test_get_data_for_trend_report_no_results(temp_db):
    """
    Tests that an empty DataFrame is returned when no data matches the filters.
    """
    # Use filters that won't match any data (wrong daypart)
    df = database.get_data_for_trend_report(
        theater_list=['Theater A'],
        date_list=['2025-09-15'],
        film_list=['Film 1'],
        daypart_list=['Prime'] # Fixture data is 'Matinee'
    )
    assert df.empty

def test_get_data_for_trend_report_empty_input(temp_db):
    """
    Tests that an empty DataFrame is returned immediately if any input list is empty.
    """
    # Case: Empty film list
    df = database.get_data_for_trend_report(['Theater A'], ['2025-09-15'], [], ['Matinee'])
    assert df.empty