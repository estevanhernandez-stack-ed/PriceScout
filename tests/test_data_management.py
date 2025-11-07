import pytest
import asyncio
from app import data_management_v2
from unittest.mock import MagicMock, patch
import json
import pandas as pd
import sqlite3, datetime
from app import config, database as app_database

@pytest.fixture
def dm_temp_db(tmp_path, monkeypatch):
    """Fixture to create a temporary database for data management tests."""
    db_path = tmp_path / "dm_test.db"
    # Patch the config module
    monkeypatch.setattr(config, 'DB_FILE', str(db_path))
    # Let the tests initialize the schema as needed
    return str(db_path)

def test_import_data_management():
    assert data_management_v2 is not None, "data_management_v2 module should be importable"


def test_extract_company_name():
    from app.utils import _extract_company_name
    assert _extract_company_name("Marcus Wehrenberg Cape West 14 Cine") == "Marcus Theatres"
    assert _extract_company_name("Some Indie Theater") == "Unknown"


def test_strip_common_terms():
    assert data_management_v2._strip_common_terms("AMC DINE-IN South Barrington 24 with IMAX, Dolby, Prime") == "south barrington 24 with prime"
    assert data_management_v2._strip_common_terms("Regal City North Stadium 14 & RPX") == "city north stadium 14 rpx"


def test_extract_zip_from_market_name():
    assert data_management_v2._extract_zip_from_market_name("My Market 12345") == "12345"
    assert data_management_v2._extract_zip_from_market_name("Market Name Without Zip") is None


def test_find_duplicate_theaters():
    sample_data = {
        "CompanyA": {
            "Region1": {
                "Market1": {
                    "theaters": [
                        {"name": "Theater A"},
                        {"name": "Theater B"},
                        {"name": "Theater A"} # Duplicate
                    ]
                },
                "Market2": {
                    "theaters": [
                        {"name": "Theater C"},
                        {"name": "Theater D"}
                    ]
                }
            }
        }
    }
    duplicates = data_management_v2.find_duplicate_theaters(sample_data)
    assert "Market1" in duplicates
    assert duplicates["Market1"] == ["Theater A"]
    assert "Market2" not in duplicates


@pytest.mark.asyncio
async def test_process_market_success(mocker):
    # Mock the scraper methods
    mocker.patch.object(data_management_v2.scraper, 'live_search_by_zip', new_callable=mocker.AsyncMock, return_value={})
    mocker.patch.object(data_management_v2.scraper, 'live_search_by_name', new_callable=mocker.AsyncMock, side_effect=[
        {
            "Fandango Palace 12": {"name": "Fandango Palace 12", "url": "http://fandango.com/palace"}
        },
        {
            "Fandango Majestic Cinema": {"name": "Fandango Majestic Cinema", "url": "http://fandango.com/majestic"}
        }
    ])

    market_theaters = [
        {"name": "Fandango Palace", "zip": "12345"},
        {"name": "Fandango Majestic", "zip": "12345"}
    ]

    results = await data_management_v2.process_market("Test Market 12345", market_theaters)

    assert len(results) == 2
    assert results[0]['Original Name'] == "Fandango Palace"
    assert results[0]['Matched Fandango Name'] == "Fandango Palace 12"
    assert results[1]['Original Name'] == "Fandango Majestic"
    assert results[1]['Matched Fandango Name'] == "Fandango Majestic Cinema"


@pytest.mark.asyncio
async def test_process_all_markets_company_prioritization(mocker):
    # Mock scraper methods to return predictable results
    mocker.patch.object(data_management_v2.scraper, 'live_search_by_zip', new_callable=mocker.AsyncMock, return_value={})
    mocker.patch.object(data_management_v2.scraper, 'live_search_by_name', new_callable=mocker.AsyncMock, side_effect=[
        {
            "Fandango AMC Theater": {"name": "Fandango AMC Theater", "url": "http://fandango.com/amc"}
        },
        {
            "Fandango Indie Cinema": {"name": "Fandango Indie Cinema", "url": "http://fandango.com/indie"}
        }
    ])

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

    theater_cache, updated_markets, all_results = await data_management_v2.process_all_markets(sample_markets_data)

    # Assertions for theater_cache
    assert "Market1 12345" in theater_cache["markets"]
    market1_theaters = theater_cache["markets"]["Market1 12345"]["theaters"]
    assert len(market1_theaters) == 2

    # Check AMC Theatre
    amc_theater_cache = next(t for t in market1_theaters if t["name"] == "Fandango AMC Theater")
    assert amc_theater_cache["company"] == "AMC Theatres"

    # Check Indie Cinema (should fall back to ParentCompanyA)
    indie_theater_cache = next(t for t in market1_theaters if t["name"] == "Fandango Indie Cinema")
    assert indie_theater_cache["company"] == "ParentCompanyA"

    # Assertions for all_results
    assert len(all_results) == 2

    # Check AMC Theatre in all_results
    amc_theater_result = next(r for r in all_results if r["Original Name"] == "AMC Theatre")
    assert amc_theater_result["Company"] == "AMC Theatres"

    # Check Indie Cinema in all_results
    indie_theater_result = next(r for r in all_results if r["Original Name"] == "Indie Cinema")
    assert indie_theater_result["Company"] == "ParentCompanyA"


@pytest.mark.asyncio
async def test_rebuild_theater_cache(mocker):
    # Mock scraper.check_url_status
    mock_check_url_status = mocker.patch.object(data_management_v2.scraper, 'check_url_status', new_callable=mocker.AsyncMock)
    
    # Mock rematch_single_theater
    mock_rematch_single_theater = mocker.patch('app.data_management_v2.rematch_single_theater', new_callable=mocker.AsyncMock)

    # Dummy markets_data for zip lookup in rebuild_theater_cache
    markets_data = {
        "ParentCompanyA": {
            "Region1": {
                "Market1": {
                    "theaters": [
                        {"name": "Theater with Broken URL", "zip": "12345", "company": "CompanyX"},
                        {"name": "Theater to be Rematched", "zip": "54321", "company": "CompanyB"},
                    ]
                }
            }
        }
    }

    # Define side effects for mocks
    # First call to check_url_status (for "Theater with Broken URL") should be False
    # Second call to check_url_status (for "Theater to be Rematched") should be False
    mock_check_url_status.side_effect = [False, False] 

    # First call to rematch_single_theater (for "Theater with Broken URL") should be "No match found"
    # Second call to rematch_single_theater (for "Theater to be Rematched") should be a successful rematch
    mock_rematch_single_theater.side_effect = [
        {"Original Name": "Theater with Broken URL", "Matched Fandango Name": "No match found", "Matched Fandango URL": "", "Company": "CompanyX"},
        {"Original Name": "Theater to be Rematched", "Matched Fandango Name": "New Fandango Name", "Matched Fandango URL": "http://new.fandango.com", "Company": "CompanyB"}
    ]

    initial_cache = {
        "markets": {
            "Market1": {
                "theaters": [
                    {"name": "Theater with Broken URL", "url": "http://broken.com", "company": "CompanyX"},
                    {"name": "Theater to be Rematched", "url": "http://old.com", "company": "CompanyB"},
                    {"name": "Permanently Closed Theater", "url": "N/A", "company": "CompanyC"},
                    {"name": "Not on Fandango Theater", "url": "http://external.com", "not_on_fandango": True, "company": "CompanyD"}
                ]
            }
        }
    }

    updated_cache, stats, failed_theaters = await data_management_v2.rebuild_theater_cache(initial_cache, markets_data)

    # Assertions
    assert stats["re_matched"] == 1
    assert stats["skipped"] == 2 # Permanently Closed and Not on Fandango
    assert stats["failed"] == 1 # Theater with Broken URL (first one)
    
    # Verify failed_theaters list contains the broken theater
    assert len(failed_theaters) == 1
    assert failed_theaters[0]['original_name'] == "Theater with Broken URL"

    # Verify "Theater with Broken URL" is marked as no match found
    broken_theater = next(t for t in updated_cache["markets"]["Market1"]["theaters"] if t["name"] == "Theater with Broken URL")
    assert broken_theater["url"] == ""
    assert broken_theater["not_on_fandango"] is True

    

    # Verify "Permanently Closed Theater" remains unchanged
    closed_theater = next(t for t in updated_cache["markets"]["Market1"]["theaters"] if t["name"] == "Permanently Closed Theater")
    assert closed_theater["url"] == "N/A"

    # Verify "Not on Fandango Theater" remains unchanged
    not_fandango_theater = next(t for t in updated_cache["markets"]["Market1"]["theaters"] if t["name"] == "Not on Fandango Theater")
    assert not_fandango_theater["url"] == "http://external.com"
    assert not_fandango_theater["not_on_fandango"] is True

    # Verify "Theater to be Rematched" is updated
    rematched_theater = next(t for t in updated_cache["markets"]["Market1"]["theaters"] if t["name"] == "New Fandango Name")
    assert rematched_theater["url"] == "http://new.fandango.com"
    assert rematched_theater["company"] == "CompanyB"
    assert "not_on_fandango" not in rematched_theater


def test_get_markets_data_null_company(tmp_path, monkeypatch):
    # Create a dummy markets.json with a null company
    dummy_markets_json_content = {
        "TestParentCompany": {
            "TestRegion": {
                "TestMarket": {
                    "theaters": [
                        {"name": "Theater A", "zip": "11111", "company": None},
                        {"name": "Theater B", "zip": "22222"}, # Missing company
                        {"name": "Theater C", "zip": "33333", "company": "ExplicitCompany"}
                    ]
                }
            }
        }
    }
    dummy_file_path = tmp_path / "dummy_markets.json"
    with open(dummy_file_path, 'w') as f:
        json.dump(dummy_markets_json_content, f)

    # Mock uploaded_file
    mock_uploaded_file = MagicMock()
    mock_uploaded_file.getvalue.return_value = json.dumps(dummy_markets_json_content).encode('utf-8')

    # Mock st.session_state
    mock_session_state = {}
    monkeypatch.setattr('streamlit.session_state', mock_session_state)

    # Call the function
    result_markets_data = data_management_v2.get_markets_data(mock_uploaded_file)

    # Assertions
    assert result_markets_data["TestParentCompany"]["TestRegion"]["TestMarket"]["theaters"][0]["company"] == "TestParentCompany"
    assert result_markets_data["TestParentCompany"]["TestRegion"]["TestMarket"]["theaters"][1]["company"] == "TestParentCompany"
    assert result_markets_data["TestParentCompany"]["TestRegion"]["TestMarket"]["theaters"][2]["company"] == "ExplicitCompany"
    assert mock_session_state['markets_data'] == result_markets_data
    assert mock_session_state['file_uploaded'] is True

@pytest.fixture
def mock_dm_session_state(monkeypatch):
    """Mocks session state for data management form tests."""
    df = pd.DataFrame({
        'Original Name': ['Theater A', 'Theater B'],
        'Matched Fandango Name': ['No match found', 'Permanently Closed'],
        'Match Score': ['0%', 'N/A'],
        'Matched Fandango URL': ['', 'N/A'],
        'Zip Code': ['12345', '54321'],
        'Company': ['CompanyX', 'CompanyY']
    })
    mock_state = {'all_results_df': df}
    
    # Patch st.session_state to use our dictionary for this test's scope
    monkeypatch.setattr(data_management_v2.st, 'session_state', mock_state)
    return mock_state

@patch('app.data_management_v2.st')
@patch('app.data_management_v2.asyncio.run')
def test_render_attention_theater_form_rematch_action(mock_async_run, mock_st, mock_dm_session_state):
    """Tests the 'Re-run Match' action within the refactored form."""
    # --- Setup ---
    mock_st.form_submit_button.return_value = True
    mock_st.radio.return_value = "Re-run Match"
    mock_async_run.return_value = {
        'Original Name': 'Theater A', 
        'Matched Fandango Name': 'New Matched Name', 
        'Match Score': '95%', 
        'Matched Fandango URL': 'http://new.url',
        'Company': 'CompanyX'
    }
    # Link the mock session state to the mocked st object
    mock_st.session_state = mock_dm_session_state

    index = 0
    row = mock_dm_session_state['all_results_df'].iloc[index]

    # --- Execution ---
    data_management_v2.render_attention_theater_form(index, row, 'rematch')

    # --- Assertions ---
    mock_st.form.assert_called_with(key='form_rematch_0')
    mock_async_run.assert_called_once()
    
    updated_df = mock_dm_session_state['all_results_df']
    updated_row = updated_df.iloc[index]
    assert updated_row['Matched Fandango Name'] == 'New Matched Name'
    assert updated_row['Match Score'] == '95%'
    assert updated_row['Matched Fandango URL'] == 'http://new.url'
    
    mock_st.success.assert_called_once()
    mock_st.rerun.assert_called_once()

@patch('app.data_management_v2.st')
@patch('app.data_management_v2.asyncio.run') # Patch asyncio to prevent RuntimeWarning
def test_render_attention_theater_form_mark_closed_action(mock_async_run, mock_st, mock_dm_session_state):
    """Tests the 'Mark as Closed' action within the refactored form."""
    mock_st.form_submit_button.return_value = True
    mock_st.radio.return_value = "Mark as Closed"
    mock_st.session_state = mock_dm_session_state
    data_management_v2.render_attention_theater_form(0, mock_dm_session_state['all_results_df'].iloc[0], 'rematch')
    assert mock_dm_session_state['all_results_df'].iloc[0]['Matched Fandango Name'] == 'Confirmed Closed'
    mock_st.rerun.assert_called_once()

@patch('app.data_management_v2.st')
def test_render_attention_theater_form_mark_not_fandango_action(mock_st, mock_dm_session_state):
    """Tests the 'Mark as Not on Fandango' action within the refactored form."""
    mock_st.form_submit_button.return_value = True
    mock_st.radio.return_value = "Mark as Not on Fandango"
    mock_st.text_input.return_value = "http://theater.website"
    mock_st.session_state = mock_dm_session_state
    data_management_v2.render_attention_theater_form(0, mock_dm_session_state['all_results_df'].iloc[0], 'rematch')
    updated_row = mock_dm_session_state['all_results_df'].iloc[0]
    assert updated_row['Matched Fandango Name'] == 'Not on Fandango'
    assert updated_row['Matched Fandango URL'] == 'http://theater.website'
    mock_st.rerun.assert_called_once()

@patch('app.data_management_v2.st')
def test_merge_external_db(mock_st, tmp_path, monkeypatch, dm_temp_db):
    """Tests the database merge functionality."""
    # --- 1. Setup Master Database ---
    master_db_path = dm_temp_db # Use the fixture
    monkeypatch.setattr(config, 'DB_FILE', master_db_path) # <<< IMPORTANT: Ensure context uses master
    with sqlite3.connect(master_db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        app_database.init_database() # Use the app's own init function
        app_database.update_database_schema() # ENSURE SCHEMA IS UP-TO-DATE

        # Add an existing run
        cursor.execute("INSERT INTO scrape_runs (run_id, run_timestamp, mode, run_context) VALUES (?, ?, ?, ?)", (1, '2025-01-01 12:00:00', 'Market Mode', 'Existing Run'))
        cursor.execute("INSERT INTO showings (showing_id, play_date, theater_name, film_title, showtime) VALUES (1, '2025-01-01', 'Master Theater', 'Master Film', '10:00am')")
        cursor.execute("INSERT INTO prices (run_id, showing_id, ticket_type, price) VALUES (?, ?, ?, ?)", (1, 1, 'Adult', 10.0))
        conn.commit()

    # --- 2. Setup Source Database ---
    source_db_path = tmp_path / "source.db"
    monkeypatch.setattr(config, 'DB_FILE', source_db_path) # <<< IMPORTANT: Switch context to source
    with sqlite3.connect(source_db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        # Use the app's own init to create a correct, modern schema
        app_database.init_database()
        app_database.update_database_schema()

        # Add the same existing run to test duplicate skipping
        cursor.execute("INSERT INTO scrape_runs (run_id, run_timestamp, mode, run_context) VALUES (?, ?, ?, ?)", (1, '2025-01-01 12:00:00', 'Market Mode', 'Existing Run'))
        cursor.execute("INSERT INTO showings (showing_id, play_date, theater_name, film_title, showtime) VALUES (100, '2025-01-01', 'Duplicate Theater', 'Duplicate Film', '10:00am')")
        cursor.execute("INSERT INTO prices (run_id, showing_id, ticket_type, price) VALUES (?, ?, ?, ?)", (1, 100, 'Adult', 99.0))

        # Add a new run to be merged
        cursor.execute("INSERT INTO scrape_runs (run_id, run_timestamp, mode, run_context) VALUES (?, ?, ?, ?)", (2, '2025-01-02 12:00:00', 'CompSnipe Mode', 'New Run'))
        cursor.execute("INSERT INTO showings (showing_id, play_date, theater_name, film_title, showtime) VALUES (101, '2025-01-02', 'Source Theater', 'Source Film', '11:00am')")
        cursor.execute("INSERT INTO prices (run_id, showing_id, ticket_type, price) VALUES (?, ?, ?, ?)", (2, 101, 'Adult', 20.0))
        conn.commit()
    
    # <<< IMPORTANT: Restore context to master DB for the merge operation
    monkeypatch.setattr(config, 'DB_FILE', master_db_path)

    # --- 3. Simulate File Upload ---
    with open(source_db_path, 'rb') as f:
        source_db_bytes = f.read()
    
    mock_uploaded_file = MagicMock()
    mock_uploaded_file.getvalue.return_value = source_db_bytes

    # --- 4. Call the function to be tested ---
    data_management_v2.merge_external_db(mock_uploaded_file)

    # --- 5. Assertions ---
    with sqlite3.connect(master_db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        # DEBUG: Check source DB before assertions
        with sqlite3.connect(source_db_path, detect_types=sqlite3.PARSE_DECLTYPES) as src_conn:
            src_runs = pd.read_sql("SELECT * FROM scrape_runs", src_conn)
            assert len(src_runs) == 2, f"Source should have 2 runs, found {len(src_runs)}"
            print(f"\n[DEBUG] Source DB runs:\n{src_runs}")
        
            # Check that only one new run was merged
            runs_df = pd.read_sql("SELECT * FROM scrape_runs", conn)
            print(f"\n[DEBUG] Master DB runs after merge:\n{runs_df}")
            assert len(runs_df) == 2, f"Should have the original run and one new run, but found {len(runs_df)}: {runs_df['run_id'].tolist()}"
            assert 'New Run' in runs_df['run_context'].values
            assert 'Existing Run' in runs_df['run_context'].values
            
            # DEBUG: Check showings
            showings_df = pd.read_sql("SELECT * FROM showings", conn)
            print(f"\n[DEBUG] Master DB showings:\n{showings_df}")
            # The source has 3 showings total (one master, one duplicate for run 1, one new for run 2)
            # INSERT OR IGNORE should result in 2 showings in master (original + new, duplicate ignored)
            assert len(showings_df) >= 2, f"Expected at least 2 showings, got {len(showings_df)}: {showings_df['film_title'].tolist()}"

            # --- FIX: Join prices with showings to check film titles ---
            prices_df = pd.read_sql("SELECT p.*, s.film_title FROM prices p JOIN showings s ON p.showing_id = s.showing_id", conn)
            print(f"\n[DEBUG] Master DB prices:\n{prices_df}")
            assert len(prices_df) == 2, f"Should have prices from the original and the new run, got {len(prices_df)}"        # Check that the original price record is untouched
        assert 'Master Film' in prices_df['film_title'].values
        
        # Check that the new price record was added
        assert 'Source Film' in prices_df['film_title'].values

        # Check that the duplicate price record was NOT added
        assert 'Duplicate Film' not in prices_df['film_title'].values

        # Check that the new price record is associated with the new run_id (which will be 2)
        new_run_id = runs_df[runs_df['run_context'] == 'New Run']['run_id'].iloc[0]
        assert prices_df[prices_df['run_id'] == new_run_id].iloc[0]['film_title'] == 'Source Film'


    mock_st.success.assert_called_with("✅ Successfully merged 1 new scrape runs and their associated data.")


@patch('app.database.print') # Mock print to avoid clutter
def test_upsert_showings(mock_print, dm_temp_db):
    """Tests that showings are correctly inserted or ignored."""
    data_management_v2.database.init_database()

    play_date = datetime.date(2025, 9, 15)
    all_showings = {
        "Theater A": [
            {'film_title': 'Film 1', 'showtime': '10:00am', 'format': '2D', 'daypart': 'Matinee', 'ticket_url': 'url1'},
            {'film_title': 'Film 1', 'showtime': '10:00am', 'format': 'IMAX', 'daypart': 'Matinee', 'ticket_url': 'url2'}, # Same time, different format
        ],
        "Theater B": [
            {'film_title': 'Film 2', 'showtime': '8:00pm', 'format': '2D', 'daypart': 'Prime', 'ticket_url': 'url3'},
        ]
    }

    # First upsert
    data_management_v2.database.upsert_showings(all_showings, play_date)

    with sqlite3.connect(dm_temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        df = pd.read_sql("SELECT * FROM showings", conn)
        assert len(df) == 3
        assert 'Film 1' in df['film_title'].values
        assert 'IMAX' in df['format'].values

    # Second upsert with same data, should add no new rows
    data_management_v2.database.upsert_showings(all_showings, play_date)
    
    with sqlite3.connect(dm_temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        df = pd.read_sql("SELECT * FROM showings", conn)
        assert len(df) == 3 # Length should be unchanged

@patch('app.database.print')
def test_migrate_schema(mock_print, dm_temp_db):
    """Tests the database schema migration from old to new format."""

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
    assert "Successfully migrated" in message

    # 3. Verify new schema and data
    with sqlite3.connect(dm_temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        # Check old table is gone
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices_old'")
        assert cursor.fetchone() is None
        
        showings_df = pd.read_sql("SELECT * FROM showings", conn)
        prices_df = pd.read_sql("SELECT * FROM prices", conn)

        assert len(showings_df) == 1
        assert showings_df.iloc[0]['play_date'] == datetime.date(2025, 9, 15)
        assert len(prices_df) == 2
        assert prices_df['showing_id'].nunique() == 1
        assert prices_df.iloc[0]['showing_id'] == showings_df.iloc[0]['showing_id']

def test_upsert_film_details_with_box_office(dm_temp_db):
    """Tests that film details, including box office gross, are correctly saved."""
    data_management_v2.database.init_database()

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
        "last_omdb_update": datetime.datetime.now()
    }

    # Call the upsert function
    data_management_v2.database.upsert_film_details(film_data)

    # Verify the data was saved correctly
    with sqlite3.connect(dm_temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT domestic_gross FROM films WHERE film_title = ?", ("Test Film",))
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 100000000

@pytest.mark.asyncio
async def test_rematch_single_theater_success(mocker):
    """Test rematch_single_theater with successful name match."""
    mocker.patch.object(
        data_management_v2.scraper, 
        'live_search_by_name', 
        new_callable=mocker.AsyncMock, 
        return_value={
            "Fandango AMC Theater 24": {
                "name": "Fandango AMC Theater 24",
                "url": "http://fandango.com/amc24"
            }
        }
    )
    
    result = await data_management_v2.rematch_single_theater("AMC Theater 24", "12345")
    
    assert result['Original Name'] == "AMC Theater 24"
    assert result['Matched Fandango Name'] == "Fandango AMC Theater 24"
    assert result['Matched Fandango URL'] == "http://fandango.com/amc24"
    assert int(result['Match Score'].rstrip('%')) >= 50

@pytest.mark.asyncio
async def test_rematch_single_theater_zip_fallback(mocker):
    """Test rematch_single_theater falling back to zip search when name search fails."""
    mocker.patch.object(
        data_management_v2.scraper, 
        'live_search_by_name', 
        new_callable=mocker.AsyncMock, 
        return_value={}
    )
    mocker.patch.object(
        data_management_v2.scraper, 
        'live_search_by_zip', 
        new_callable=mocker.AsyncMock, 
        return_value={
            "Cinema 16 at Main Street": {
                "name": "Cinema 16 at Main Street",
                "url": "http://fandango.com/cinema16"
            }
        }
    )
    
    result = await data_management_v2.rematch_single_theater("Cinema Main Street 16", "54321")
    
    assert result['Original Name'] == "Cinema Main Street 16"
    assert result['Matched Fandango Name'] == "Cinema 16 at Main Street"
    assert result['Matched Fandango URL'] == "http://fandango.com/cinema16"

@pytest.mark.asyncio
async def test_rematch_single_theater_no_match(mocker):
    """Test rematch_single_theater when no match is found."""
    mocker.patch.object(
        data_management_v2.scraper, 
        'live_search_by_name', 
        new_callable=mocker.AsyncMock, 
        return_value={}
    )
    mocker.patch.object(
        data_management_v2.scraper, 
        'live_search_by_zip', 
        new_callable=mocker.AsyncMock, 
        return_value={}
    )
    
    result = await data_management_v2.rematch_single_theater("Nonexistent Theater", "99999")
    
    assert result['Original Name'] == "Nonexistent Theater"
    assert result['Matched Fandango Name'] == "No match found"
    assert result['Match Score'] == "0%"
    assert result['Matched Fandango URL'] == ""

def test_add_unmatched_ticket_type_local(dm_temp_db, mocker):
    """Test _add_unmatched_ticket_type_local adds unmatched ticket type to database."""
    # Initialize database with schema
    data_management_v2.database.init_database()
    
    # Call the function
    data_management_v2._add_unmatched_ticket_type_local("IMAX 3D", "IMAX 3D Premium")
    
    # Verify the unmatched type was added
    with sqlite3.connect(dm_temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT unmatched_part, original_description FROM unmatched_ticket_types WHERE unmatched_part = ?",
            ("IMAX 3D",)
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "IMAX 3D"
        assert result[1] == "IMAX 3D Premium"

def test_discover_and_add_new_films_from_bom_new_films(dm_temp_db, mocker):
    """Test discover_and_add_new_films_from_bom with new films."""
    # Initialize database
    data_management_v2.database.init_database()
    
    # Mock BoxOfficeMojoScraper
    mock_bom = mocker.MagicMock()
    mock_bom.discover_films_by_year.return_value = [
        {"title": "New Film 1"},
        {"title": "New Film 2"}
    ]
    mocker.patch('app.data_management_v2.BoxOfficeMojoScraper', return_value=mock_bom)
    
    # Mock OMDbClient
    mock_omdb = mocker.MagicMock()
    mock_omdb.get_film_details.side_effect = [
        {
            "film_title": "New Film 1",
            "genre": "Action",
            "mpaa_rating": "PG-13",
            "imdb_id": "tt111",
            "runtime": "120 min",
            "director": "Director 1",
            "actors": "Actor 1",
            "plot": "Plot 1",
            "poster_url": "http://example.com/poster1.jpg",
            "metascore": 80,
            "imdb_rating": 8.0,
            "release_date": "2025-01-01",
            "domestic_gross": None,
            "opening_weekend_domestic": None,
            "last_omdb_update": datetime.datetime.now()
        },
        {
            "film_title": "New Film 2",
            "genre": "Comedy",
            "mpaa_rating": "R",
            "imdb_id": "tt222",
            "runtime": "90 min",
            "director": "Director 2",
            "actors": "Actor 2",
            "plot": "Plot 2",
            "poster_url": "http://example.com/poster2.jpg",
            "metascore": 70,
            "imdb_rating": 7.5,
            "release_date": "2025-02-01",
            "domestic_gross": None,
            "opening_weekend_domestic": None,
            "last_omdb_update": datetime.datetime.now()
        }
    ]
    mocker.patch('app.data_management_v2.OMDbClient', return_value=mock_omdb)
    
    # Run the function
    new_films, existing_films, failed_films = data_management_v2.discover_and_add_new_films_from_bom(2025)
    
    # Verify results
    assert len(new_films) == 2
    assert "New Film 1" in new_films
    assert "New Film 2" in new_films
    assert len(existing_films) == 0
    assert len(failed_films) == 0

def test_discover_and_add_new_films_from_bom_existing_films(dm_temp_db, mocker):
    """Test discover_and_add_new_films_from_bom with existing films."""
    # Initialize database and add a film
    data_management_v2.database.init_database()
    with sqlite3.connect(dm_temp_db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO films (film_title, genre, mpaa_rating, last_omdb_update) VALUES (?, ?, ?, ?)",
            ("Existing Film", "Drama", "PG", datetime.datetime.now())
        )
        conn.commit()
    
    # Mock BoxOfficeMojoScraper
    mock_bom = mocker.MagicMock()
    mock_bom.discover_films_by_year.return_value = [
        {"title": "Existing Film"}
    ]
    mocker.patch('app.data_management_v2.BoxOfficeMojoScraper', return_value=mock_bom)
    
    # Mock OMDbClient (shouldn't be called for existing films)
    mock_omdb = mocker.MagicMock()
    mocker.patch('app.data_management_v2.OMDbClient', return_value=mock_omdb)
    
    # Run the function
    new_films, existing_films, failed_films = data_management_v2.discover_and_add_new_films_from_bom(2025)
    
    # Verify results
    assert len(new_films) == 0
    assert len(existing_films) == 1
    assert "Existing Film" in existing_films
    assert len(failed_films) == 0
    assert mock_omdb.get_film_details.call_count == 0  # Should not fetch details for existing films

def test_discover_and_add_new_films_from_bom_failed_films(dm_temp_db, mocker):
    """Test discover_and_add_new_films_from_bom with films that fail OMDb lookup."""
    # Initialize database
    data_management_v2.database.init_database()
    
    # Mock BoxOfficeMojoScraper
    mock_bom = mocker.MagicMock()
    mock_bom.discover_films_by_year.return_value = [
        {"title": "Unknown Film"}
    ]
    mocker.patch('app.data_management_v2.BoxOfficeMojoScraper', return_value=mock_bom)
    
    # Mock OMDbClient to return None (film not found)
    mock_omdb = mocker.MagicMock()
    mock_omdb.get_film_details.return_value = None
    mocker.patch('app.data_management_v2.OMDbClient', return_value=mock_omdb)
    
    # Run the function
    new_films, existing_films, failed_films = data_management_v2.discover_and_add_new_films_from_bom(2025)
    
    # Verify results
    assert len(new_films) == 0
    assert len(existing_films) == 0
    assert len(failed_films) == 1
    assert failed_films[0]['Title'] == "Unknown Film"
    assert "Could not find match" in failed_films[0]['Error']
