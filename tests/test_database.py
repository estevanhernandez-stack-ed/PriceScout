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
    with sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
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
    with sqlite3.connect(temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
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
    with sqlite3.connect(temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
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
    with sqlite3.connect(temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
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

def test_get_dates_for_theaters(temp_db):
    """Tests getting unique dates for selected theaters."""
    import datetime
    # Get dates for Theater A
    dates = database.get_dates_for_theaters(['Theater A'])
    assert len(dates) >= 1
    assert datetime.date(2025, 9, 15) in dates
    
    # Get dates for multiple theaters
    dates = database.get_dates_for_theaters(['Theater A', 'Theater B'])
    assert datetime.date(2025, 9, 15) in dates
    
    # Empty theater list
    dates = database.get_dates_for_theaters([])
    assert dates == []

def test_get_common_films_for_theaters_dates(temp_db):
    """Tests getting films available for all selected theaters on at least one date."""
    # Add more test data to make this meaningful
    with sqlite3.connect(temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        # Add showings for Theater B with Film 1 (common with Theater A)
        cursor.execute("INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart) VALUES (?, ?, ?, ?, ?, ?)", 
                      ('2025-09-15', 'Theater B', 'Film 1', '2:00pm', '2D', 'Evening'))
        conn.commit()
    
    # Get common films between Theater A and Theater B on 2025-09-15
    films = database.get_common_films_for_theaters_dates(['Theater A', 'Theater B'], ['2025-09-15'])
    assert 'Film 1' in films  # Film 1 is shown at both theaters
    assert 'Film 2' not in films  # Film 2 is only at Theater A
    
    # Empty inputs
    films = database.get_common_films_for_theaters_dates([], ['2025-09-15'])
    assert films == []
    
    films = database.get_common_films_for_theaters_dates(['Theater A'], [])
    assert films == []

def test_get_dates_for_theater(temp_db):
    """Tests getting dates for a single theater."""
    import datetime
    dates = database.get_dates_for_theater('Theater A')
    assert len(dates) >= 1
    assert datetime.date(2025, 9, 15) in dates

def test_get_films_for_theater_date(temp_db):
    """Tests getting films for a specific theater and date."""
    films = database.get_films_for_theater_date('Theater A', '2025-09-15')
    assert len(films) >= 2
    assert 'Film 1' in films
    assert 'Film 2' in films

def test_get_final_prices(temp_db):
    """Tests getting final prices for a specific theater, date, film combination."""
    prices_df = database.get_final_prices('Theater A', '2025-09-15', 'Film 1')
    assert not prices_df.empty
    assert 'Adult' in prices_df['ticket_type'].values
    
    # Test with daypart filter (use 'Matinee' which exists in test data)
    prices_filtered = database.get_final_prices('Theater A', '2025-09-15', 'Film 1', daypart='Matinee')
    assert not prices_filtered.empty
    assert all(prices_filtered['daypart'] == 'Matinee')

def test_get_unique_column_values(temp_db):
    """Tests getting unique values from various columns in the prices table."""
    # Get unique ticket types (prices table column)
    ticket_types = database.get_unique_column_values('ticket_type')
    assert 'Adult' in ticket_types
    assert len(ticket_types) > 0

def test_get_available_films(temp_db):
    """Tests getting available films for selected theaters."""
    # Get films for Theater A
    films_a = database.get_available_films(['Theater A'])
    assert 'Film 1' in films_a
    assert 'Film 2' in films_a
    
    # Get films for Theater B
    films_b = database.get_available_films(['Theater B'])
    assert 'Film 3 (No Metadata)' in films_b
    
    # Empty list should return empty
    films_empty = database.get_available_films([])
    assert films_empty == []

def test_get_available_dates(temp_db):
    """Tests getting min/max dates for theaters and films."""
    # Get date range for Theater A and Film 1
    min_date, max_date = database.get_available_dates(['Theater A'], ['Film 1'])
    assert min_date is not None
    assert max_date is not None
    
    # Empty inputs should return None, None
    min_date, max_date = database.get_available_dates([], ['Film 1'])
    assert min_date is None
    assert max_date is None

def test_upsert_film_details(temp_db):
    """Tests inserting and updating film metadata."""
    # Insert new film
    film_data = {
        'film_title': 'New Film',
        'imdb_id': 'tt1234567',
        'genre': 'Action',
        'mpaa_rating': 'PG-13',
        'runtime': '120 min',
        'director': 'Test Director',
        'actors': 'Actor A, Actor B',
        'plot': 'A test plot',
        'poster_url': 'http://example.com/poster.jpg',
        'metascore': 75,
        'imdb_rating': 7.5,
        'release_date': '2025-01-01',
        'domestic_gross': 100000000,
        'opening_weekend_domestic': 25000000,
        'last_omdb_update': datetime.datetime.now()
    }
    database.upsert_film_details(film_data)
    
    # Verify film was inserted
    assert database.check_film_exists('New Film')
    
    # Update the film
    film_data['genre'] = 'Action, Thriller'
    film_data['metascore'] = 80
    database.upsert_film_details(film_data)
    
    # Verify update worked
    updated_film = database.get_film_details('New Film')
    assert updated_film['genre'] == 'Action, Thriller'
    assert updated_film['metascore'] == 80

def test_check_film_exists(temp_db):
    """Tests checking if a film exists in the database."""
    # Film 1 exists (added in fixture)
    assert database.check_film_exists('Film 1')
    
    # Non-existent film
    assert not database.check_film_exists('Nonexistent Film')

def test_get_film_details(temp_db):
    """Tests retrieving film details."""
    # Get existing film
    film = database.get_film_details('Film 1')
    assert film is not None
    assert film['film_title'] == 'Film 1'
    assert film['genre'] == 'Action, Adventure'
    assert film['mpaa_rating'] == 'PG-13'
    
    # Get non-existent film
    film = database.get_film_details('Nonexistent')
    assert film is None

def test_get_all_unique_genres(temp_db):
    """Tests getting unique genres from films table."""
    genres = database.get_all_unique_genres()
    assert 'Action' in genres
    assert 'Adventure' in genres  # Split from 'Action, Adventure'
    assert 'Comedy' in genres
    assert 'Family' in genres
    assert len(genres) > 0

def test_get_all_unique_ratings(temp_db):
    """Tests getting unique MPAA ratings, excluding non-ratings."""
    ratings = database.get_all_unique_ratings()
    assert 'PG-13' in ratings
    assert 'R' in ratings
    assert 'PG' in ratings
    # Should exclude 'Not Rated', 'N/A', etc.
    assert 'Not Rated' not in ratings
    assert 'N/A' not in ratings

def test_save_operating_hours(temp_db):
    """Tests saving operating hours data."""
    with database._get_db_connection() as conn:
        cursor = conn.cursor()
        # Create a scrape run
        cursor.execute("INSERT INTO scrape_runs (run_timestamp, mode, run_context) VALUES (?, ?, ?)", 
                      (datetime.datetime.now(), 'Operating Hours', 'Test'))
        run_id = cursor.lastrowid
        
        # Operating hours data
        hours_data = [
            {
                'Market': 'Test Market',
                'Theater': 'Theater A',
                'Date': '2025-09-20',
                'Showtime Range': '10:00 AM - 11:00 PM',
                'Duration (hrs)': 13.0
            },
            {
                'Market': 'Test Market',
                'Theater': 'Theater B',
                'Date': '2025-09-20',
                'Showtime Range': 'No showtimes found',
                'Duration (hrs)': 0
            }
        ]
        
        database.save_operating_hours(run_id, hours_data, conn)
        conn.commit()
        
        # Verify data was saved
        cursor.execute("SELECT * FROM operating_hours WHERE run_id = ?", (run_id,))
        saved_hours = cursor.fetchall()
        assert len(saved_hours) == 2
        
        # Check Theater A has times
        cursor.execute("SELECT open_time, close_time FROM operating_hours WHERE theater_name = 'Theater A' AND run_id = ?", (run_id,))
        theater_a = cursor.fetchone()
        assert theater_a[0] == '10:00 AM'
        assert theater_a[1] == '11:00 PM'
        
        # Check Theater B has no times
        cursor.execute("SELECT open_time, close_time FROM operating_hours WHERE theater_name = 'Theater B' AND run_id = ?", (run_id,))
        theater_b = cursor.fetchone()
        assert theater_b[0] is None
        assert theater_b[1] is None

def test_get_all_films_for_enrichment(temp_db):
    """Tests getting all films for enrichment."""
    # Get as list of dicts
    films_list = database.get_all_films_for_enrichment(as_df=False)
    assert len(films_list) >= 4  # At least Film 1, 2, 4, 5 from fixture
    assert isinstance(films_list[0], dict)
    assert 'film_title' in films_list[0]
    
    # Get as DataFrame
    films_df = database.get_all_films_for_enrichment(as_df=True)
    assert not films_df.empty
    assert 'film_title' in films_df.columns
    assert len(films_df) >= 4

def test_add_film_to_ignore_list(temp_db):
    """Tests adding films to the ignore list."""
    # Add a film to ignore list
    database.add_film_to_ignore_list('Annoying Film')
    
    # Verify it was added
    with database._get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT film_title FROM ignored_films WHERE film_title = ?", ('Annoying Film',))
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 'Annoying Film'
    
    # Adding same film again should not cause error (INSERT OR IGNORE)
    database.add_film_to_ignore_list('Annoying Film')

def test_calculate_operating_hours_from_showings(temp_db):
    """Tests deriving operating hours from showings when operating_hours table is empty."""
    start_date = datetime.datetime(2025, 9, 15)
    end_date = datetime.datetime(2025, 9, 15)
    
    # Get operating hours derived from showings
    hours_df = database.calculate_operating_hours_from_showings(['Theater A'], start_date, end_date)
    
    assert not hours_df.empty
    assert 'theater_name' in hours_df.columns
    assert 'open_time' in hours_df.columns
    assert 'close_time' in hours_df.columns
    assert 'Theater A' in hours_df['theater_name'].values
    
    # Empty theater list should return empty DataFrame
    hours_empty = database.calculate_operating_hours_from_showings([], start_date, end_date)
    assert hours_empty.empty

def test_save_full_operating_hours_run(temp_db):
    """Tests the full operating hours save workflow."""
    hours_data = [
        {
            'Market': 'Test Market',
            'Theater': 'Theater C',
            'Date': '2025-09-25',
            'Showtime Range': '9:00 AM - 10:00 PM',
            'Duration (hrs)': 13.0
        }
    ]
    
    database.save_full_operating_hours_run(hours_data, 'Test Context')
    
    # Verify scrape run was created
    with database._get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scrape_runs WHERE mode = 'Operating Hours' AND run_context = 'Test Context'")
        run = cursor.fetchone()
        assert run is not None
        
        run_id = run[0]
        
        # Verify operating hours were saved
        cursor.execute("SELECT * FROM operating_hours WHERE run_id = ?", (run_id,))
        hours = cursor.fetchall()
        assert len(hours) == 1
        assert hours[0][3] == 'Theater C'  # theater_name column

def test_delete_operating_hours(temp_db):
    """Tests deleting operating hours for specific theaters and dates."""
    # First add some operating hours
    with database._get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO scrape_runs (run_timestamp, mode, run_context) VALUES (?, ?, ?)", 
                      (datetime.datetime.now(), 'Operating Hours', 'Test'))
        run_id = cursor.lastrowid
        
        cursor.execute(
            "INSERT INTO operating_hours (run_id, theater_name, scrape_date, open_time, close_time) VALUES (?, ?, ?, ?, ?)",
            (run_id, 'Theater A', '2025-09-30', '10:00 AM', '11:00 PM')
        )
        cursor.execute(
            "INSERT INTO operating_hours (run_id, theater_name, scrape_date, open_time, close_time) VALUES (?, ?, ?, ?, ?)",
            (run_id, 'Theater B', '2025-09-30', '11:00 AM', '10:00 PM')
        )
        conn.commit()
        
        # Delete operating hours for Theater A on that date
        delete_date = datetime.datetime(2025, 9, 30)
        database.delete_operating_hours(['Theater A'], delete_date, conn)
        conn.commit()
        
        # Verify Theater A was deleted
        cursor.execute("SELECT * FROM operating_hours WHERE theater_name = 'Theater A' AND scrape_date = '2025-09-30'")
        assert cursor.fetchone() is None
        
        # Verify Theater B still exists
        cursor.execute("SELECT * FROM operating_hours WHERE theater_name = 'Theater B' AND scrape_date = '2025-09-30'")
        assert cursor.fetchone() is not None

def test_log_and_get_unmatched_films(temp_db):
    """Tests logging and retrieving unmatched films."""
    # Log an unmatched film
    database.log_unmatched_film('Strange Unknown Movie')
    
    # Retrieve unmatched films
    unmatched = database.get_unmatched_films()
    assert not unmatched.empty
    assert 'Strange Unknown Movie' in unmatched['film_title'].values
    
    # Logging same film again shouldn't duplicate (INSERT OR IGNORE)
    database.log_unmatched_film('Strange Unknown Movie')
    unmatched = database.get_unmatched_films()
    film_count = len(unmatched[unmatched['film_title'] == 'Strange Unknown Movie'])
    assert film_count == 1

def test_delete_unmatched_film(temp_db):
    """Tests deleting an unmatched film."""
    # Add an unmatched film
    database.log_unmatched_film('Film To Delete')
    
    # Verify it exists
    unmatched = database.get_unmatched_films()
    assert 'Film To Delete' in unmatched['film_title'].values
    
    # Delete it
    database.delete_unmatched_film('Film To Delete')
    
    # Verify it's gone
    unmatched = database.get_unmatched_films()
    assert 'Film To Delete' not in unmatched['film_title'].values

def test_log_and_get_unmatched_ticket_types(temp_db):
    """Tests logging and retrieving unmatched ticket types."""
    # Log without context
    database.log_unmatched_ticket_type('Senior Discount (65+)', 'Senior', None)
    
    # Log with context
    showing_details = {
        'theater_name': 'Theater A',
        'film_title': 'Film 1',
        'showtime': '7:00pm',
        'format': '2D',
        'play_date': '2025-09-15'
    }
    database.log_unmatched_ticket_type('Student Price', 'Student', showing_details)
    
    # Retrieve unmatched ticket types
    unmatched = database.get_unmatched_ticket_types()
    assert not unmatched.empty
    assert 'Senior' in unmatched['unmatched_part'].values
    assert 'Student' in unmatched['unmatched_part'].values
    
    # Check context was saved
    student_row = unmatched[unmatched['unmatched_part'] == 'Student'].iloc[0]
    assert student_row['theater_name'] == 'Theater A'
    assert student_row['film_title'] == 'Film 1'

def test_delete_unmatched_ticket_type(temp_db):
    """Tests deleting an unmatched ticket type."""
    # Add an unmatched ticket type
    database.log_unmatched_ticket_type('VIP Pass', 'VIP', None)
    
    # Get its ID
    unmatched_before = database.get_unmatched_ticket_types()
    vip_row = unmatched_before[unmatched_before['unmatched_part'] == 'VIP'].iloc[0]
    vip_id = int(vip_row['id'])
    
    # Verify it exists before deletion
    assert 'VIP' in unmatched_before['unmatched_part'].values
    
    # Delete it
    database.delete_unmatched_ticket_type(vip_id)
    
    # Verify it's gone
    unmatched_after = database.get_unmatched_ticket_types()
    if not unmatched_after.empty:
        assert 'VIP' not in unmatched_after['unmatched_part'].values

def test_get_films_missing_release_date(temp_db):
    """Tests getting films with missing release dates."""
    # Add a film without release date
    film_data = {
        'film_title': 'Mystery Film',
        'imdb_id': 'tt9999999',
        'genre': 'Mystery',
        'mpaa_rating': 'PG',
        'runtime': '90 min',
        'director': 'Unknown',
        'actors': 'TBD',
        'plot': 'Unknown plot',
        'poster_url': None,
        'metascore': None,
        'imdb_rating': None,
        'release_date': None,  # No release date
        'domestic_gross': None,
        'opening_weekend_domestic': None,
        'last_omdb_update': datetime.datetime.now()
    }
    database.upsert_film_details(film_data)
    
    # Get films missing release date
    missing = database.get_films_missing_release_date()
    assert 'Mystery Film' in missing

def test_get_films_missing_metadata(temp_db):
    """Tests getting films in showings but not in films table."""
    # Film 3 (No Metadata) is in showings but was not added to films table in fixture
    missing = database.get_films_missing_metadata()
    assert 'Film 3 (No Metadata)' in missing
    
    # Films 1 and 2 have metadata, so they shouldn't be in the list
    assert 'Film 1' not in missing
    assert 'Film 2' not in missing

def test_get_films_missing_metadata_for_dates(temp_db):
    """Tests getting films missing metadata for a specific date range."""
    # Check for films missing metadata on 2025-09-15
    missing = database.get_films_missing_metadata_for_dates('2025-09-15', '2025-09-15')
    assert 'Film 3 (No Metadata)' in missing
    
    # Date range with no showings should return empty list
    missing = database.get_films_missing_metadata_for_dates('2099-01-01', '2099-01-02')
    assert len(missing) == 0

def test_get_ticket_type_usage_counts(temp_db):
    """Tests getting ticket type usage counts from prices table."""
    usage = database.get_ticket_type_usage_counts()
    
    # Should have Adult ticket type (from fixture)
    assert not usage.empty
    assert 'Adult' in usage['ticket_type'].values or 'adult' in usage['ticket_type'].str.lower().values
    
    # Should have count column
    assert 'count' in usage.columns

def test_get_comparable_films(temp_db):
    """Tests finding comparable films by genre."""
    # Get comparable films to Film 1 (Action, Adventure)
    comparable = database.get_comparable_films('Film 1', ['Action', 'Adventure'])
    
    # If there are no other films with matching genres, it should return empty
    # Our test data has Film 1 as Action, Adventure but no other Action films
    # So this should be empty or have very few results
    assert isinstance(comparable, pd.DataFrame)
    
    # Test with empty genres
    empty_result = database.get_comparable_films('Film 1', [])
    assert empty_result.empty

