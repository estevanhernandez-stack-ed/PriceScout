import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import datetime
import os
import sys
import sqlite3
import json

# Add the app directory to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import data_management_v2, config
from app.db_adapter import init_database

# Fixture to set up a temporary database for data management tests
@pytest.fixture
def dm_temp_db(tmp_path, monkeypatch):
    """Create a temporary database for data management tests."""
    db_path = tmp_path / "dm_test.db"
    monkeypatch.setattr(config, 'DB_FILE', str(db_path))
    # Ensure the old database file is removed if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
    return str(db_path)

def test_import_data_management():
    """Test that the data management module can be imported."""
    assert data_management_v2 is not None

def test_extract_company_name():
    """Test the extraction of company names from theater names."""
    assert data_management_v2._strip_common_terms("AMC Classic") == "amc classic"
    assert data_management_v2._strip_common_terms("Regal Cinemas") == "regal"
    assert data_management_v2._strip_common_terms("My Awesome Theater") == "my awesome theater"

def test_strip_common_terms():
    """Test stripping common terms from theater names."""
    assert data_management_v2._strip_common_terms("AMC Classic North") == "amc classic north"
    assert data_management_v2._strip_common_terms("Regal Edwards Big Newport") == "regal edwards big newport"
    assert data_management_v2._strip_common_terms("The Landmark") == "the landmark"

def test_extract_zip_from_market_name():
    """Test extracting zip code from a market name string."""
    assert data_management_v2._extract_zip_from_market_name("Some Market 12345") == "12345"
    assert data_management_v2._extract_zip_from_market_name("Market Name") is None

def test_find_duplicate_theaters():
    """Test finding duplicate theater entries across different markets."""
    sample_data = {
        "CompanyA": {
            "Region1": {
                "Market1": {"theaters": [{"name": "Duplicate Plex"}]},
                "Market2": {"theaters": [{"name": "Duplicate Plex"}]}
            }
        }
    }
    duplicates = data_management_v2.find_duplicate_theaters(sample_data)
    assert "Market1" in duplicates
    assert "Duplicate Plex" in duplicates["Market1"]

@pytest.mark.asyncio
async def test_process_market_success(mocker):
    """Test successful processing of a single market."""
    mocker.patch.object(data_management_v2.scraper, 'live_search_by_zip', new_callable=mocker.AsyncMock, return_value={
        "Fandango Fun Movie": {"name": "Fandango Fun Movie", "url": "http://fandango.com/fun"}
    })
    
    theaters = [{"name": "Fun Movie Palace"}]
    results = await data_management_v2.process_market("Test Market 90210", theaters)
    
    assert len(results) == 1
    assert results[0]['Original Name'] == "Fun Movie Palace"
    assert results[0]['Matched Fandango Name'] == "Fandango Fun Movie"
    assert results[0]['Match Score'] != "0%"

@pytest.mark.asyncio
async def test_process_all_markets_company_prioritization(mocker):
    # Mock scraper methods to return predictable results
    mocker.patch.object(data_management_v2.scraper, 'live_search_by_zip', new_callable=mocker.AsyncMock, return_value={})
    
    live_search_mock = mocker.patch.object(data_management_v2.scraper, 'live_search_by_name', new_callable=mocker.AsyncMock)
    live_search_mock.side_effect = [
        {"Fandango AMC Theater": {"name": "Fandango AMC Theater", "url": "http://fandango.com/amc"}},
        {"Fandango Indie Cinema": {"name": "Fandango Indie Cinema", "url": "http://fandango.com/indie"}}
    ]

    sample_markets_data = {
        "ParentCompanyA": {
            "Region1": {
                "Market1 12345": {
                    "theaters": [
                        {"name": "AMC Theatre", "zip": "12345", "company": "AMC Theatres"},
                        {"name": "Indie Cinema", "zip": "12345"}, # No explicit company
                    ]
                }
            }
        }
    }

    await data_management_v2.process_all_markets(sample_markets_data)

    assert live_search_mock.call_count == 2
    live_search_mock.assert_any_call("AMC Theatre")
    live_search_mock.assert_any_call("Indie Cinema")

@pytest.mark.asyncio
async def test_rebuild_theater_cache(mocker):
    """Test the rebuilding of theater cache with URL status checks."""
    mocker.patch.object(data_management_v2.scraper, 'check_url_status', new_callable=mocker.AsyncMock, side_effect=[False, True])
    mocker.patch.object(data_management_v2, 'rematch_single_theater', new_callable=mocker.AsyncMock, return_value={
        'Matched Fandango Name': 'Rematched Theater',
        'Matched Fandango URL': 'http://new.url'
    })
    
    initial_cache = {
        "markets": {
            "MarketA 11111": {
                "theaters": [
                    {"name": "Bad URL Theater", "url": "http://bad.url"},
                    {"name": "Good URL Theater", "url": "http://good.url"}
                ]
            }
        }
    }
    
    updated_cache, stats, _ = await data_management_v2.rebuild_theater_cache(initial_cache, {})
    
    assert stats['re_matched'] == 1
    assert stats['skipped'] == 0
    assert stats['failed'] == 0
    
    rematched = updated_cache['markets']['MarketA 11111']['theaters'][0]
    assert rematched['name'] == 'Rematched Theater'
    assert rematched['url'] == 'http://new.url'

def test_get_markets_data_null_company():
    """Test that get_markets_data handles a null 'company' field gracefully."""
    sample_data = {
        "My Theaters": {
            "My Region": {
                "My Market 90210": {
                    "theaters": [{"name": "My Local Cinema", "zip": "90210"}]
                }
            }
        }
    }
    
    # Create a mock file object
    mock_file = MagicMock()
    mock_file.getvalue.return_value = json.dumps(sample_data).encode('utf-8')
    
    # Mock streamlit state
    with patch('app.data_management_v2.st') as mock_st:
        mock_st.session_state = {}
        
        # This will raise an exception if it fails to handle the null company
        processed_data = data_management_v2.get_markets_data(mock_file)
        
        # Assert that the company was correctly backfilled
        theater = processed_data["My Theaters"]["My Region"]["My Market 90210"]["theaters"][0]
        assert theater["company"] == "My Theaters"

@patch('app.data_management_v2.st')
@patch('app.data_management_v2.asyncio')
def test_render_attention_theater_form_rematch_action(mock_asyncio, mock_st):
    """Test re-match action in the attention theater form."""
    mock_st.session_state = {'all_results_df': pd.DataFrame([{
        'Original Name': 'Old Theater', 'Zip Code': '12345',
        'Matched Fandango Name': 'No match', 'Match Score': '0%', 'Matched Fandango URL': ''
    }])}
    
    # Mock the rematch function
    rematch_result = {
        'Matched Fandango Name': 'New Matched Theater',
        'Match Score': '95%',
        'Matched Fandango URL': 'http://new-url.com'
    }
    mock_asyncio.run.return_value = rematch_result
    
    # Simulate form submission
    mock_st.radio.return_value = "Re-run Match"
    mock_st.form_submit_button.return_value = True
    
    data_management_v2.render_attention_theater_form(0, mock_st.session_state['all_results_df'].iloc[0], 'test_key')
    
    # Verify state was updated
    updated_df = mock_st.session_state['all_results_df']
    assert updated_df.loc[0, 'Matched Fandango Name'] == 'New Matched Theater'
    assert mock_st.rerun.called

@patch('app.data_management_v2.st')
def test_render_attention_theater_form_mark_closed_action(mock_st):
    """Test mark as closed action."""
    mock_st.session_state = {'all_results_df': pd.DataFrame([{
        'Original Name': 'Theater To Close', 'Zip Code': '12345',
        'Matched Fandango Name': 'No match'
    }])}
    
    mock_st.radio.return_value = "Mark as Closed"
    mock_st.form_submit_button.return_value = True
    
    data_management_v2.render_attention_theater_form(0, mock_st.session_state['all_results_df'].iloc[0], 'test_key')
    
    assert mock_st.session_state['all_results_df'].loc[0, 'Matched Fandango Name'] == 'Confirmed Closed'
    assert mock_st.rerun.called

@patch('app.data_management_v2.st')
def test_render_attention_theater_form_mark_not_fandango_action(mock_st):
    """Test mark as not on Fandango action."""
    mock_st.session_state = {'all_results_df': pd.DataFrame([{
        'Original Name': 'Indie Theater', 'Zip Code': '12345',
        'Matched Fandango Name': 'No match', 'Matched Fandango URL': ''
    }])}
    
    mock_st.radio.return_value = "Mark as Not on Fandango"
    mock_st.text_input.return_value = "http://indie.com"
    mock_st.form_submit_button.return_value = True
    
    data_management_v2.render_attention_theater_form(0, mock_st.session_state['all_results_df'].iloc[0], 'test_key')
    
    assert mock_st.session_state['all_results_df'].loc[0, 'Matched Fandango Name'] == 'Not on Fandango'
    assert mock_st.session_state['all_results_df'].loc[0, 'Matched Fandango URL'] == 'http://indie.com'
    assert mock_st.rerun.called

@patch('app.data_management_v2.st')
def test_merge_external_db(mock_st, dm_temp_db):
    """Test merging an external database file."""
    # 1. Setup master DB
    with patch.object(config, 'CURRENT_COMPANY_ID', 1):
        init_database()
        with data_management_v2.database._get_db_connection() as conn:
            conn.execute("ALTER TABLE scrape_runs ADD COLUMN run_context TEXT")
            conn.execute("INSERT OR IGNORE INTO companies (company_id, company_name) VALUES (1, 'Test Company')")
    
    # 2. Setup source DB
    source_db_path = os.path.join(os.path.dirname(dm_temp_db), "source.db")
    with sqlite3.connect(source_db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        conn.execute("CREATE TABLE scrape_runs (run_id INTEGER, run_timestamp DATETIME, mode TEXT, run_context TEXT, company_id INTEGER)")
        conn.execute("INSERT INTO scrape_runs VALUES (100, '2025-01-01 12:00:00', 'Test', 'ctx', 1)")
    
    # 3. Mock file upload
    with open(source_db_path, 'rb') as f:
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.getvalue.return_value = f.read()
    
    # 4. Run merge
    with patch.object(config, 'DB_FILE', dm_temp_db), patch.object(config, 'CURRENT_COMPANY_ID', 1):
        data_management_v2.merge_external_db(mock_uploaded_file)
        
    # 5. Verify data was merged
    with sqlite3.connect(dm_temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scrape_runs WHERE run_id = 100")
        assert cursor.fetchone()[0] == 1
        
    

@patch('app.database.print') # Mock print to avoid clutter
def test_upsert_showings(mock_print, dm_temp_db):
    """Tests that showings are correctly inserted or ignored."""
    init_database()
    with data_management_v2.database._get_db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO companies (company_id, company_name) VALUES (1, 'Test Company')")

    play_date = datetime.date(2025, 9, 15)
    all_showings = {
        "Theater A": [
            {'film_title': 'Film 1', 'showtime': '10:00am', 'format': '2D', 'daypart': 'Matinee', 'ticket_url': 'url1', 'company_id': 1},
            {'film_title': 'Film 1', 'showtime': '10:00am', 'format': 'IMAX', 'daypart': 'Matinee', 'ticket_url': 'url2', 'company_id': 1}, # Same time, different format
        ],
        "Theater B": [
            {'film_title': 'Film 2', 'showtime': '8:00pm', 'format': '2D', 'daypart': 'Prime', 'ticket_url': 'url3', 'company_id': 1},
        ]
    }
    
    # First upsert
    with patch.object(config, 'CURRENT_COMPANY_ID', 1):
        data_management_v2.database.upsert_showings(all_showings, play_date)

    # Verify insertion
    with data_management_v2.database._get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM showings", conn)
        assert len(df) == 3
        assert df['film_title'].nunique() == 2

    # Second upsert (should be ignored)
    with patch.object(config, 'CURRENT_COMPANY_ID', 1):
        data_management_v2.database.upsert_showings(all_showings, play_date)
    
    # Verify no new records were added
    with data_management_v2.database._get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM showings", conn)
        assert len(df) == 3

@patch('app.database.print')
def test_migrate_schema(mock_print, dm_temp_db):
    """Tests the database schema migration from old to new format."""
    init_database()
    # 1. Create DB with OLD schema
    with sqlite3.connect(dm_temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE scrape_runs (run_id INTEGER PRIMARY KEY, run_timestamp DATETIME, mode TEXT, run_context TEXT)")
        cursor.execute("""
            CREATE TABLE prices (
                price_id INTEGER PRIMARY KEY, run_id INTEGER, theater_name TEXT, film_title TEXT,
                showtime TEXT, daypart TEXT, format TEXT, ticket_type TEXT, price REAL,
                capacity TEXT, play_date DATE
            )
        """)
        # Insert data, some with null play_date to test backfill
        cursor.execute("INSERT INTO scrape_runs VALUES (1, '2025-09-14 20:00:00', 'Market', 'c1')")
        cursor.execute("INSERT INTO scrape_runs VALUES (2, '2025-09-15 07:00:00', 'Market', 'c2')")
        # Record for run 1 (should get play_date 2025-09-15)
        cursor.execute("INSERT INTO prices (run_id, theater_name, film_title, showtime, daypart, format, ticket_type, price) VALUES (1, 'Theater A', 'Film 1', '10:00am', 'Matinee', '2D', 'Adult', 15.0)")
        # Record for run 2 (should get play_date 2025-09-15)
        cursor.execute("INSERT INTO prices (run_id, theater_name, film_title, showtime, daypart, format, ticket_type, price, play_date) VALUES (2, 'Theater A', 'Film 1', '10:00am', 'Matinee', '2D', 'Child', 12.0, '2025-09-15')")
        conn.commit()

    # 2. Run migration
    message = data_management_v2.database.migrate_schema()
    assert "Schema managed by SQLAlchemy migrations" in message

def test_upsert_film_details_with_box_office(dm_temp_db):
    """Tests that film details, including box office gross, are correctly saved."""
    init_database()
    with data_management_v2.database._get_db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO companies (company_id, company_name) VALUES (1, 'Test Company')")

    film_data = {
        "film_title": "Test Film",
        "imdb_id": "tt12345",
        "genre": "Test, Action",
        "mpaa_rating": "PG-13",
        "runtime": "120 min",
        "director": "Test Director",
        "actors": "Test Actor",
        "plot": "A test plot.",
        "poster_url": "http://example.com/poster.jpg",
        "metascore": 80,
        "imdb_rating": 8.5,
        "release_date": "2025-01-01",
        "domestic_gross": 100000000,
        "opening_weekend_domestic": 50000000,
    }

    # Call the upsert function
    with patch.object(config, 'CURRENT_COMPANY_ID', 1):
        data_management_v2.database.upsert_film_details(film_data)
    
    # Verify the data was saved correctly
    with data_management_v2.database._get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM films WHERE film_title = 'Test Film'", conn)
        assert len(df) == 1
        assert df.iloc[0]['domestic_gross'] == 100000000