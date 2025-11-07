import os
import sys
import json
import re
import glob
from datetime import datetime, time
import pytz
import asyncio
import pandas as pd
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

# Add project root to path to allow imports from the 'app' package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app import config
from app.scraper import Scraper
from app.modes.operating_hours_mode import generate_weekly_report_data
from app.utils import _extract_company_name
from app import database

logger = logging.getLogger(__name__)


async def execute_scheduled_scrape(task_config: dict, company_name: str):
    """
    Configures the environment for a specific company and executes a scrape task.

    Args:
        task_config (dict): The configuration dictionary for the task.
        company_name (str): The name of the company this task belongs to.
    """
    logger.info(f"EXECUTING task '{task_config['task_name']}' for company '{company_name}'...")

    # --- Dynamically configure paths for this company ---
    company_path = os.path.join(config.DATA_DIR, company_name)
    database.DB_FILE = os.path.join(company_path, 'price_scout.db')
    config.DB_FILE = database.DB_FILE  # Ensure config module is also updated

    try:
        scout = Scraper()

        # Load the shared theater cache to get theater URLs
        with open(config.CACHE_FILE, 'r') as f:
            cache_data = json.load(f)

        theaters_to_scrape = []
        for market_name in task_config['markets']:
            theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
            theaters_to_scrape.extend(theaters_in_market)

        if not theaters_to_scrape:
            logger.warning(f"No theaters found in cache for markets: {', '.join(task_config['markets'])}. Skipping scrape.")
            return

        # --- Perform the scrape for all showtimes ---
        # For an automated task, we assume we want all showtimes for the day.
        # Use a timezone-aware date for the scrape.
        scrape_date = datetime.now(pytz.utc).astimezone(pytz.timezone("America/Chicago")).date()

        # 1. Get all showings from Fandango
        all_showings = await scout.get_all_showings_for_theaters(theaters_to_scrape, scrape_date.strftime('%Y-%m-%d'))

        # 2. Save showings to DB (this also triggers OMDb enrichment)
        database.upsert_showings(all_showings, scrape_date)

        # 3. Prepare the structure needed for the price scrape
        selected_showtimes = {}
        for theater_name, showings_list in all_showings.items():
            selected_showtimes[theater_name] = {}
            for showing in showings_list:
                film_title = showing['film_title']
                showtime = showing['showtime']
                if film_title not in selected_showtimes[theater_name]:
                    selected_showtimes[theater_name][film_title] = {}
                if showtime not in selected_showtimes[theater_name][film_title]:
                    selected_showtimes[theater_name][film_title][showtime] = []
                selected_showtimes[theater_name][film_title][showtime].append(showing)

        # 4. Scrape prices for all discovered showtimes
        price_results, _ = await scout.scrape_details(theaters_to_scrape, selected_showtimes)

        # 5. Save prices to the database
        if price_results:
            df_prices = pd.DataFrame(price_results)
            run_context = f"Scheduled Task: {task_config['task_name']}"
            run_id = database.create_scrape_run("Scheduled", run_context)
            if run_id:
                database.save_prices(run_id, df_prices, scrape_date)
            logger.info(f"SUCCESS: Saved {len(df_prices)} price points for '{task_config['task_name']}' to run_id {run_id}.")
        else:
            logger.info(f"Scrape for '{task_config['task_name']}' completed but found no price data.")

    except Exception as e:
        logger.error(f"An error occurred during scheduled scrape for '{task_config['task_name']}': {e}", exc_info=True)

async def execute_op_hours_report_task(task_config: dict, company_name: str):
    """
    Configures the environment and executes a weekly operating hours report task.
    """
    logger.info(f"EXECUTING op hours report task '{task_config['task_name']}' for company '{company_name}'...")

    # --- Dynamically configure paths for this company ---
    company_path = os.path.join(config.DATA_DIR, company_name)
    database.DB_FILE = os.path.join(company_path, 'price_scout.db')
    config.DB_FILE = database.DB_FILE
    reports_dir = os.path.join(company_path, 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    try:
        scout = Scraper()
        with open(config.CACHE_FILE, 'r') as f:
            cache_data = json.load(f)

        # Get all theaters for the company
        normalized_company_name = _extract_company_name(company_name)
        all_company_theaters = []
        for market in cache_data.get("markets", {}).values():
            for theater in market.get("theaters", []):
                theater_company = _extract_company_name(theater.get("company", ""))
                if theater_company == normalized_company_name and "Permanently Closed" not in theater.get("name", ""):
                    all_company_theaters.append(theater)

        if not all_company_theaters:
            logger.warning(f"No theaters found for company '{company_name}' in cache. Skipping report.")
            return

        # Generate the report data
        report_data = generate_weekly_report_data(scout, cache_data, all_company_theaters, company_name)

        if not report_data:
            logger.info(f"Generated op hours report for '{task_config['task_name']}' but it was empty.")
            return

        # Save the report to an Excel file with one sheet per theater
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        sanitized_task_name = re.sub(r'[^a-zA-Z0-9_-]', '_', task_config['task_name'])
        report_path = os.path.join(reports_dir, f"OpHours_{sanitized_task_name}_{timestamp}.xlsx")
        with pd.ExcelWriter(report_path, engine='xlsxwriter') as writer:
            for theater_report in report_data:
                sheet_name = re.sub(r'[\[\]\*\/\\?\:]', '', theater_report['theater_name'])[:31]
                theater_report['report'].to_excel(writer, sheet_name=sheet_name, index=False)
        logger.info(f"SUCCESS: Saved operating hours report to {report_path}")
    except Exception as e:
        logger.error(f"An error occurred during op hours report task for '{task_config['task_name']}': {e}", exc_info=True)

def check_and_run_tasks():
    """Scans all company task directories and runs any due tasks."""
    logger.info("Checking for scheduled tasks...")

    # Find all company directories within the main data directory
    company_dirs = glob.glob(os.path.join(config.DATA_DIR, '*'))

    for company_dir in company_dirs:
        if not os.path.isdir(company_dir):
            continue

        company_name = os.path.basename(company_dir)
        tasks_dir = os.path.join(company_dir, 'scheduled_tasks')

        if not os.path.exists(tasks_dir):
            continue

        for task_file in glob.glob(os.path.join(tasks_dir, '*.json')):
            try:
                with open(task_file, 'r+') as f:
                    task_config = json.load(f)

                    if not task_config.get('enabled', False):
                        continue

                    task_type = task_config.get("task_type", "market_scrape")
                    now_utc = datetime.now(pytz.utc)
                    schedule_time = time.fromisoformat(task_config.get('schedule_time_utc', '00:00'))

                    # Check if it's the right day of the week for this task
                    is_correct_day = True
                    if 'day_of_week' in task_config:
                        day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
                        scheduled_day_name = task_config['day_of_week']
                        if day_map.get(scheduled_day_name) != now_utc.weekday():
                            is_correct_day = False

                    # Check if the current time matches the scheduled time
                    if is_correct_day and now_utc.hour == schedule_time.hour and now_utc.minute == schedule_time.minute:
                        last_run_dt = datetime.fromisoformat(task_config['last_run']) if task_config.get('last_run') else None

                        # Ensure it hasn't already run in the last few minutes
                        if not last_run_dt or (now_utc - last_run_dt).total_seconds() > 60:
                            if task_type == "weekly_op_hours_report":
                                asyncio.run(execute_op_hours_report_task(task_config, company_name))
                            else: # Default to market scrape
                                asyncio.run(execute_scheduled_scrape(task_config, company_name))

                            # Update the last_run timestamp in the JSON file
                            task_config['last_run'] = now_utc.isoformat()
                            f.seek(0)
                            json.dump(task_config, f, indent=4)
                            f.truncate()
            except Exception as e:
                logger.error(f"Failed to process task file {task_file}: {e}", exc_info=True)


if __name__ == "__main__":
    # --- Setup Logging ---
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler
    file_handler = logging.FileHandler('scheduler.log')
    file_handler.setFormatter(log_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    
    # Get root logger and add handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Clear existing handlers to avoid duplicates if script is reloaded
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    scheduler = BlockingScheduler(timezone=pytz.utc)
    scheduler.add_job(check_and_run_tasks, 'interval', minutes=1, next_run_time=datetime.now(pytz.utc))

    logger.info("Scheduler service started. Press Ctrl+C to exit.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler service stopped.")