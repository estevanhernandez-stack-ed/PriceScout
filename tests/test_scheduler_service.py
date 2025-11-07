import pytest
import os
import sys
import json
from datetime import datetime, time
import pytz
from unittest.mock import patch, AsyncMock, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module to be tested
from scheduler_service import execute_scheduled_scrape, execute_op_hours_report_task, check_and_run_tasks
from app import config, database

# --- Fixtures ---

@pytest.fixture
def temp_company_dir(tmp_path):
    """Creates a temporary company directory structure for testing."""
    company_name = "TestCompany"
    company_path = tmp_path / "data" / company_name
    tasks_path = company_path / "scheduled_tasks"
    reports_path = company_path / "reports"
    os.makedirs(tasks_path)
    os.makedirs(reports_path)
    return {
        "company_name": company_name,
        "company_path": company_path,
        "tasks_path": tasks_path,
        "reports_path": reports_path
    }

@pytest.fixture
def mock_cache_file(tmp_path):
    """Creates a mock theater_cache.json file."""
    cache_content = {
        "markets": {
            "TestMarket1": {
                "theaters": [
                    {"name": "Theater A", "url": "http://a.com", "company": "TestCompany"},
                    {"name": "Theater B", "url": "http://b.com", "company": "TestCompany"}
                ]
            },
            "TestMarket2": {
                 "theaters": [
                    {"name": "Theater C", "url": "http://c.com", "company": "OtherCompany"}
                ]
            }
        }
    }
    cache_path = tmp_path / "theater_cache.json"
    with open(cache_path, 'w') as f:
        json.dump(cache_content, f)
    return str(cache_path)

@pytest.fixture
def mock_db(tmp_path):
    """Creates a temporary database path."""
    db_path = tmp_path / "test_scheduler.db"
    return str(db_path)

# --- Mocks for the entire module ---

@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch, mock_cache_file, mock_db, tmp_path):
    """Auto-patches dependencies for all tests in this module."""
    monkeypatch.setattr(config, 'DATA_DIR', str(tmp_path / "data"))
    monkeypatch.setattr(config, 'CACHE_FILE', mock_cache_file)
    monkeypatch.setattr(config, 'DB_FILE', mock_db)


# --- Tests ---

@pytest.mark.asyncio
@patch('scheduler_service.Scraper')
@patch('scheduler_service.database')
async def test_execute_scheduled_scrape(mock_db_mod, mock_scraper_cls, temp_company_dir):
    """
    Tests the main scheduled scrape execution logic.
    """
    # --- Setup ---
    mock_scraper_instance = mock_scraper_cls.return_value
    mock_scraper_instance.get_all_showings_for_theaters = AsyncMock(return_value={
        "Theater A": [{"film_title": "Film 1", "showtime": "10:00"}]
    })
    mock_scraper_instance.scrape_details = AsyncMock(return_value=([{"Price": "$10"}], []))

    mock_db_mod.create_scrape_run.return_value = 123
    mock_db_mod.save_prices = MagicMock()
    mock_db_mod.upsert_showings = MagicMock()

    task_config = {
        "task_name": "Daily Scrape",
        "markets": ["TestMarket1"]
    }
    company_name = temp_company_dir["company_name"]

    # --- Execution ---
    await execute_scheduled_scrape(task_config, company_name)

    # --- Assertions ---
    mock_scraper_instance.get_all_showings_for_theaters.assert_called_once()
    mock_scraper_instance.scrape_details.assert_called_once()
    mock_db_mod.upsert_showings.assert_called_once()
    mock_db_mod.create_scrape_run.assert_called_once_with("Scheduled", "Scheduled Task: Daily Scrape")
    mock_db_mod.save_prices.assert_called_once()
    assert config.DB_FILE == str(temp_company_dir["company_path"] / 'price_scout.db')

@pytest.mark.asyncio
@patch('scheduler_service.generate_weekly_report_data', return_value=[{"theater_name": "Theater A", "report": MagicMock()}])
@patch('scheduler_service.pd.ExcelWriter')
async def test_execute_op_hours_report_task(mock_excel_writer, mock_generate_report, temp_company_dir):
    """
    Tests the operating hours report generation task.
    """
    task_config = {"task_name": "Weekly Op Hours"}
    company_name = temp_company_dir["company_name"]

    await execute_op_hours_report_task(task_config, company_name)

    mock_generate_report.assert_called_once()
    mock_excel_writer.assert_called_once()
    saved_path = mock_excel_writer.call_args[0][0]
    assert temp_company_dir["reports_path"].name in saved_path
    assert company_name in saved_path
    assert "OpHours_Weekly_Op_Hours" in saved_path

@patch('scheduler_service.asyncio.run')
@patch('scheduler_service.datetime')
def test_check_and_run_tasks_runs_due_task(mock_datetime, mock_async_run, temp_company_dir):
    """
    Tests that check_and_run_tasks correctly identifies and runs a task
    that is enabled and scheduled for the current time.
    """
    schedule_time = time(10, 30)
    mock_now = datetime(2025, 9, 17, 10, 30, 5, tzinfo=pytz.utc)
    mock_datetime.now.return_value = mock_now
    mock_datetime.fromisoformat.side_effect = lambda ts: datetime.fromisoformat(ts)

    task_config = {
        "task_name": "Due Task", "enabled": True, "schedule_time_utc": schedule_time.strftime("%H:%M"),
        "last_run": None, "markets": ["TestMarket1"]
    }
    task_file = temp_company_dir["tasks_path"] / "due_task.json"
    with open(task_file, 'w') as f: json.dump(task_config, f)

    check_and_run_tasks()

    mock_async_run.assert_called_once()
    called_func = mock_async_run.call_args[0][0]
    assert called_func.__name__ == 'execute_scheduled_scrape'
    
    with open(task_file, 'r') as f: updated_config = json.load(f)
    assert updated_config['last_run'] == mock_now.isoformat()

@patch('scheduler_service.asyncio.run')
@patch('scheduler_service.datetime')
def test_check_and_run_tasks_skips_disabled_task(mock_datetime, mock_async_run, temp_company_dir):
    """Tests that a disabled task is correctly skipped."""
    mock_datetime.now.return_value = datetime(2025, 9, 17, 10, 30, 5, tzinfo=pytz.utc)
    task_config = {"task_name": "Disabled", "enabled": False, "schedule_time_utc": "10:30", "last_run": None}
    task_file = temp_company_dir["tasks_path"] / "disabled.json"
    with open(task_file, 'w') as f: json.dump(task_config, f)
    check_and_run_tasks()
    mock_async_run.assert_not_called()

@patch('scheduler_service.asyncio.run')
@patch('scheduler_service.datetime')
def test_check_and_run_tasks_skips_wrong_time_task(mock_datetime, mock_async_run, temp_company_dir):
    """Tests that a task scheduled for a different time is skipped."""
    mock_datetime.now.return_value = datetime(2025, 9, 17, 10, 30, 5, tzinfo=pytz.utc)
    task_config = {"task_name": "Wrong Time", "enabled": True, "schedule_time_utc": "11:00", "last_run": None}
    task_file = temp_company_dir["tasks_path"] / "wrong_time.json"
    with open(task_file, 'w') as f: json.dump(task_config, f)
    check_and_run_tasks()
    mock_async_run.assert_not_called()

@patch('scheduler_service.asyncio.run')
@patch('scheduler_service.datetime')
def test_check_and_run_tasks_skips_recently_run_task(mock_datetime, mock_async_run, temp_company_dir):
    """Tests that a task that has run in the last minute is skipped."""
    mock_now = datetime(2025, 9, 17, 10, 30, 30, tzinfo=pytz.utc)
    last_run_time = datetime(2025, 9, 17, 10, 30, 5, tzinfo=pytz.utc)
    mock_datetime.now.return_value = mock_now
    mock_datetime.fromisoformat.side_effect = lambda ts: datetime.fromisoformat(ts)

    task_config = {"task_name": "Recent", "enabled": True, "schedule_time_utc": "10:30", "last_run": last_run_time.isoformat()}
    task_file = temp_company_dir["tasks_path"] / "recent.json"
    with open(task_file, 'w') as f: json.dump(task_config, f)
    check_and_run_tasks()
    mock_async_run.assert_not_called()