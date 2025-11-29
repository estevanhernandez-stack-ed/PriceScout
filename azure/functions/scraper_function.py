import logging
import json
import os
import sys
import azure.functions as func

# Add project root to path to allow imports from the 'app' package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.scraper import Scraper
from app import config
from app import db_adapter as database
import pandas as pd
from datetime import datetime
import pytz

async def main(msg: func.ServiceBusMessage):
    logging.info('Python ServiceBus queue trigger function processed a message: %s',
                 msg.get_body().decode('utf-8'))

    try:
        message_body = json.loads(msg.get_body().decode('utf-8'))
        task_config = message_body['task_config']
        company_name = message_body['company_name']

        logging.info(f"EXECUTING task '{task_config['task_name']}' for company '{company_name}'...")

        # --- Dynamically configure paths for this company ---
        company_path = os.path.join(config.DATA_DIR, company_name)
        database.DB_FILE = os.path.join(company_path, 'price_scout.db')
        config.DB_FILE = database.DB_FILE  # Ensure config module is also updated

        scout = Scraper()

        with open(config.CACHE_FILE, 'r') as f:
            cache_data = json.load(f)

        theaters_to_scrape = []
        for market_name in task_config['markets']:
            theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
            theaters_to_scrape.extend(theaters_in_market)

        if not theaters_to_scrape:
            logging.warning(f"No theaters found in cache for markets: {', '.join(task_config['markets'])}. Skipping scrape.")
            return

        scrape_date = datetime.now(pytz.utc).astimezone(pytz.timezone("America/Chicago")).date()

        all_showings = await scout.get_all_showings_for_theaters(theaters_to_scrape, scrape_date.strftime('%Y-%m-%d'))
        database.upsert_showings(all_showings, scrape_date)

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

        price_results, _ = await scout.scrape_details(theaters_to_scrape, selected_showtimes)

        if price_results:
            df_prices = pd.DataFrame(price_results)
            run_context = f"Scheduled Task: {task_config['task_name']}"
            run_id = database.create_scrape_run("Scheduled", run_context)
            if run_id:
                database.save_prices(run_id, df_prices, scrape_date)
            logging.info(f"SUCCESS: Saved {len(df_prices)} price points for '{task_config['task_name']}' to run_id {run_id}.")
        else:
            logging.info(f"Scrape for '{task_config['task_name']}' completed but found no price data.")

    except Exception as e:
        logging.error(f"An error occurred during scheduled scrape: {e}", exc_info=True)
