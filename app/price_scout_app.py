# price_scout_app.py - The Streamlit User Interface & Scraping Engine (v27.0 - Enhanced Data Management)

import streamlit as st
import pandas as pd
import os
import datetime
import time
import asyncio
import traceback
import sys
import threading
import urllib.parse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import json
from functools import reduce
import io
from contextlib import redirect_stdout
import requests # Using requests for fast static page scraping
import random
import sqlite3
from thefuzz import fuzz

from config import SCRIPT_DIR, PROJECT_DIR, DEBUG_DIR, DATA_DIR, CACHE_FILE, MARKETS_FILE, CACHE_EXPIRATION_DAYS, REPORTS_DIR, RUNTIME_LOG_FILE, DB_FILE, SCHEDULED_TASKS_DIR
import database
from utils import run_async_in_thread, format_price_change, style_price_change_v2, check_cache_status, get_report_path, log_runtime, clear_workflow_state, reset_session, style_price_change, to_excel, to_csv, get_error_message
from ui_components import render_daypart_selector

# --- Windows asyncio policy fix ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- Check for Developer Mode ---
query_params = st.query_params
DEV_MODE_ENABLED = query_params.get("dev") == "true"

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="PriceScout",
    page_icon=os.path.join(SCRIPT_DIR, 'PriceScoutLogo.png'),
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* --- Base Button Style --- */
    button {
        border-radius: 5px !important;
        font-weight: bold !important;
        transition: background-color 0.2s, color 0.2s, border-color 0.2s;
    }
    /* --- Unselected Button --- */
    button.st-emotion-cache-1anq8dj.e7nj0r42 {
        border: 2px solid #A21E25 !important;
        color: #A21E25 !important;
        background-color: transparent !important;
    }
    /* --- Selected Button --- */
    button.st-emotion-cache-1krtkoa.e7nj0r41 {
        background-color: #8B0F05 !important;
        color: white !important;
        border: 1px solid #8B0F05 !important;
    }
    /* --- Hover for All Buttons (Corrected) --- */
    button.st-emotion-cache-1anq8dj.e7nj0r42:hover,
    button.st-emotion-cache-1krtkoa.e7nj0r41:hover {
        background-color: #A21E25 !important;
        color: white !important;
        border-color: #A21E25 !important;
    }
    /* --- Focus Style (Corrected per Option 2) --- */
    button:focus {
        background-color: #8B0F05 !important; /* Dark Red */
        color: white !important;
        border-color: #8B0F05 !important;
        box-shadow: 0 0 0 0.2rem rgba(139, 15, 5, 0.5) !important;
    }

    /* --- Toggle Switch (Final) --- */
    /* Track of the toggle in the OFF state */
    label.st-emotion-cache-1t3w24c input[type="checkbox"] + div.st-emotion-cache-7oyrr6 {
        background-color: #f0f2f6 !important;
        border-color: #A21E25 !important;
    }
    /* Track of the toggle in the ON state */
    label.st-emotion-cache-1t3w24c input[type="checkbox"]:checked + div.st-emotion-cache-7oyrr6 {
        background-color: #A21E25 !important;
        border-color: #A21E25 !important;
    }
    /* Focus style for accessibility */
    label.st-emotion-cache-1t3w24c input[type="checkbox"]:focus + div.st-emotion-cache-7oyrr6 {
        box-shadow: 0 0 0 0.2rem rgba(139, 15, 5, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)


def check_password():
    """Returns `True` if the user has the correct password."""
    if "password" not in st.secrets:
        return True
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if st.session_state.get("password_correct", False):
        return True
    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False

# --- Main Application Logic ---
if check_password():
    st.title('📊 PriceScout: Competitive Pricing Tool')

    
        # --- Session State Initialization ---
    if 'stage' not in st.session_state: st.session_state.stage = 'initial'
    if 'search_mode' not in st.session_state: st.session_state.search_mode = "Market Mode"
    if 'last_run_log' not in st.session_state: st.session_state.last_run_log = ""
    if 'dev_mode' not in st.session_state: st.session_state.dev_mode = False
    if 'capture_html' not in st.session_state: st.session_state.capture_html = False
    if 'confirm_scrape' not in st.session_state: st.session_state.confirm_scrape = False
    if 'live_search_results' not in st.session_state: st.session_state.live_search_results = {}
    if 'report_running' not in st.session_state: st.session_state.report_running = False # <-- ADD THIS LINE
    if 'all_showings' not in st.session_state: st.session_state.all_showings = {}
    if 'selected_films' not in st.session_state: st.session_state.selected_films = []
    if 'selected_showtimes' not in st.session_state: st.session_state.selected_showtimes = {}
    if 'daypart_selections' not in st.session_state: st.session_state.daypart_selections = set()
    if 'dm_stage' not in st.session_state: st.session_state.dm_stage = 'initial'


    from scraper import Scraper
    scout = Scraper()

    

    # --- Load initial data & DB ---
    database.init_database()
    database.update_database_schema()
    try:
        with open(MARKETS_FILE, 'r') as f:
            markets_data = json.load(f)
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
    except FileNotFoundError:
        st.error(f"Error: `{MARKETS_FILE}` or `{CACHE_FILE}` not found. Please ensure they are in the same directory.")
        st.info("You may need to build the theater cache first if it's missing.")
        st.stop()

    IS_DISABLED = st.session_state.report_running

    # --- Main UI ---
    # Top-level sidebar controls that should always be visible
    st.sidebar.title("Controls")
    st.sidebar.image(os.path.join(SCRIPT_DIR, 'PriceScoutLogo.png'))
    if st.sidebar.button("🚀 Start New Report / Abort", use_container_width=True):
        if 'report_running' in st.session_state:
            st.session_state.report_running = False
        reset_session()

    st.sidebar.divider()

# --- CHANGE START ---: Moved Mode Selection to sidebar and converted to buttons
    st.sidebar.subheader("Select Mode")
    mode_options = ["Market Mode", "CompSnipe Mode", "Analysis Mode", "Data Management"]
    current_mode = st.session_state.get('search_mode', "Market Mode")

    # To stack buttons, we simply create them one after another in a loop.
    # No columns are needed.
    for mode in mode_options:
        # Create the button directly in the sidebar.
        # The 'type' changes to "primary" if it's the currently selected mode.
        if st.sidebar.button(mode, use_container_width=True, type="primary" if current_mode == mode else "secondary"):
            
            # If the button is clicked, update the search_mode in session_state
            if st.session_state.search_mode != mode:
                st.session_state.search_mode = mode
                
                # Clear any settings from the old mode to prevent conflicts
                clear_workflow_state() 
                
                # Rerun the app immediately to reflect the change
                st.rerun()

    st.sidebar.divider()
    # --- CHANGE END ---

    if DEV_MODE_ENABLED:
        st.sidebar.header("Developer Tools")
        st.session_state.dev_mode = True
        st.session_state.capture_html = st.sidebar.toggle("Capture HTML Snapshots", help="Save HTML files for analysis.", disabled=IS_DISABLED)
        if st.sidebar.button("Run Full System Diagnostic", use_container_width=True, disabled=IS_DISABLED):
            st.session_state.run_diagnostic = True
            st.rerun()
    else:
        st.session_state.dev_mode = False

    if st.session_state.get('run_diagnostic'):
        st.header("🛠️ Full System Diagnostic")
        st.warning("**Warning:** This will scrape every theater in the selected markets and may take a very long time to complete.")
        all_markets = []
        for director, markets in markets_data["Marcus Theatres"].items():
            all_markets.extend(markets.keys())
        all_markets = sorted(list(set(all_markets)))

        if 'markets_to_test' not in st.session_state:
            st.session_state.markets_to_test = []

        st.write("Select markets to test:")
        cols = st.columns(4)
        for i, market in enumerate(all_markets):
            is_selected = market in st.session_state.markets_to_test
            if cols[i % 4].button(market, key=f"diag_market_{market}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                if is_selected:
                    st.session_state.markets_to_test.remove(market)
                else:
                    st.session_state.markets_to_test.append(market)
                st.rerun()
        markets_to_test = st.session_state.markets_to_test
        if st.button("Start Full Diagnostic", type="primary", disabled=IS_DISABLED):
            st.session_state.report_running = True
            st.rerun()

    if st.session_state.report_running and st.session_state.get('run_diagnostic'):
        with st.spinner("Running diagnostic scan... This will take a long time."):
            diag_date_str = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            status, result, log, duration = run_async_in_thread(scout.run_diagnostic_scrape, markets_to_test, diag_date_str)
            st.session_state.last_run_log += log
            if status == 'success':
                st.success(f"Diagnostic Complete! (Took {duration:.2f} seconds)")
                df_diag = pd.DataFrame(result)
                st.dataframe(df_diag)
            else:
                st.error(f"The diagnostic tool encountered a critical error after {duration:.2f} seconds.")
            st.session_state.report_running = False
            st.session_state.run_diagnostic = False


    st.subheader("Theater Data Cache")
    cache_status, last_updated = check_cache_status()
    if cache_status == "fresh":
        st.success(f"Theater cache is up to date. Last refreshed: {last_updated}")
    elif cache_status == "stale":
        st.warning(f"Theater cache is stale (older than {CACHE_EXPIRATION_DAYS} days). Last refreshed: {last_updated}")
    else:
        st.error("Theater cache file is missing or invalid. Please build it.")

    
    st.divider()

    with st.expander("🗓️ Task Scheduler"):
        st.write("Create a new automated scraping task. The backend agent will run any due tasks every 15 minutes.")
        
        all_markets = []
        for parent, regions in markets_data.items():
            for region, markets in regions.items():
                all_markets.extend(markets.keys())
        all_markets = sorted(list(set(all_markets)))

        with st.form("scheduler_form", clear_on_submit=True):
            task_name = st.text_input("Task Name (e.g., 'DFW_Nightly_Audit')")
            markets_to_schedule = st.multiselect("Select Markets to Scrape", options=all_markets)
            schedule_time = st.time_input("Scheduled Time (UTC)", datetime.time(8, 0)) # Default to 8:00 UTC (3 AM CDT)
            notification_email = st.text_input("Notification Email (Optional)")
            
            submitted = st.form_submit_button("Save Scheduled Task")

            if submitted:
                if not task_name or not markets_to_schedule:
                    st.error("Task Name and at least one Market are required.")
                else:
                    sanitized_name = scout._sanitize_filename(task_name)
                    task_config = {
                        "task_name": task_name,
                        "markets": markets_to_schedule,
                        "schedule_time_utc": schedule_time.strftime("%H:%M"),
                        "notification_email": notification_email,
                        "enabled": True,
                        "last_run": None
                    }
                    os.makedirs(SCHEDULED_TASKS_DIR, exist_ok=True)
                    filepath = os.path.join(SCHEDULED_TASKS_DIR, f"{sanitized_name}.json")
                    with open(filepath, 'w') as f:
                        json.dump(task_config, f, indent=4)
                    st.success(f"Successfully saved task '{task_name}'!")
                    st.toast(f"Saved to {filepath}")
    st.divider()

    
    
    if st.session_state.search_mode == "Market Mode":
        if 'selected_region' not in st.session_state: st.session_state.selected_region = None
        if 'selected_market' not in st.session_state: st.session_state.selected_market = None

        parent_company = list(markets_data.keys())[0]
        regions = list(markets_data[parent_company].keys())
        st.subheader("Select Director")
        cols = st.columns(len(regions))
        for i, region in enumerate(regions):
            is_selected = st.session_state.selected_region == region
            if cols[i].button(region, key=f"region_{region}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                st.session_state.selected_region = region
                st.session_state.selected_market = None
                st.session_state.stage = 'region_selected'
                st.rerun()

        if st.session_state.selected_region:
            st.divider()
            markets = list(markets_data[parent_company][st.session_state.selected_region].keys())
            market_cols = st.columns(4)
            for i, market in enumerate(markets):
                is_selected = st.session_state.selected_market == market
                if market_cols[i % 4].button(market, key=f"market_{market}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                    st.session_state.selected_market = market
                    st.session_state.theaters = cache_data.get("markets", {}).get(market, {}).get("theaters", [])
                    st.session_state.selected_theaters = [t['name'] for t in st.session_state.theaters]
                    st.session_state.stage = 'theaters_listed'
                    st.rerun()

        if st.session_state.stage in ['theaters_listed', 'data_fetched', 'report_generated']:
            st.subheader("Step 2: Select Theaters")
            cols = st.columns(4)
            theaters = st.session_state.get('theaters', [])
            for i, theater in enumerate(theaters):
                is_selected = theater['name'] in st.session_state.get('selected_theaters', [])
                if cols[i % 4].button(theater['name'], key=f"theater_{i}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                    if 'selected_theaters' not in st.session_state: st.session_state.selected_theaters = []
                    if is_selected: st.session_state.selected_theaters.remove(theater['name'])
                    else: st.session_state.selected_theaters.append(theater['name'])
                    st.rerun()
            
            st.toggle("Only show films playing at ALL selected theaters", key="market_films_filter", disabled=IS_DISABLED, help="Filters the list in Step 2 to only show films common to every theater selected.")
            scrape_date = st.date_input("Select Date for Showtimes", datetime.date.today() + datetime.timedelta(days=1), key="market_date", disabled=IS_DISABLED)
            
            if st.button("Find Films for Selected Theaters", disabled=IS_DISABLED, use_container_width=True):
                theaters_to_scrape = [t for t in theaters if t['name'] in st.session_state.selected_theaters]
                with st.spinner("Finding all available films and showtimes..."):
                    thread, get_results = run_async_in_thread(scout.get_all_showings_for_theaters, theaters_to_scrape, scrape_date.strftime('%Y-%m-%d'))
                    thread.join()
                    status, result, log, duration = get_results()
                    st.session_state.last_run_log = log
                    if status == 'success':
                        st.info(f"Film search completed in {duration:.2f} seconds.")
                        st.session_state.all_showings = result
                        st.session_state.selected_films = []
                        st.session_state.selected_showtimes = {}
                        st.session_state.stage = 'data_fetched'
                    else:
                        st.error(f"Failed to fetch showings for theaters: {get_error_message(result)}")
                st.rerun()

        if st.session_state.stage in ['data_fetched', 'report_generated']:
            st.subheader("Step 3: Select Films & Showtimes")
            
            all_films_unfiltered = sorted(list(reduce(lambda a, b: a.union(b), [set(s['film_title'] for s in showings) for showings in st.session_state.all_showings.values() if showings], set())))
            
            if st.session_state.get('market_films_filter'):
                film_sets = [set(s['film_title'] for s in st.session_state.all_showings.get(theater, [])) for theater in st.session_state.selected_theaters]
                if film_sets:
                    common_films = set.intersection(*film_sets)
                    all_films_to_display = sorted(list(common_films))
                else:
                    all_films_to_display = []
            else:
                all_films_to_display = all_films_unfiltered

            st.write("Select Films:")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("Select All Films", key="market_select_all_films", use_container_width=True):
                    st.session_state.selected_films = all_films_to_display
                    st.rerun()
            with col2:
                if st.button("Deselect All Films", key="market_deselect_all_films", use_container_width=True):
                    st.session_state.selected_films = []
                    st.rerun()

            st.divider()

            cols = st.columns(4)
            for i, film in enumerate(all_films_to_display):
                is_selected = film in st.session_state.selected_films
                if cols[i % 4].button(film, key=f"film_{film}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                    if is_selected: st.session_state.selected_films.remove(film)
                    else: st.session_state.selected_films.append(film)
                    st.rerun()
            st.divider()

            if st.session_state.selected_films:
                render_daypart_selector(st.session_state.all_showings, st.session_state.selected_films, st.session_state.selected_theaters, IS_DISABLED, "market")

            for theater_name in st.session_state.get('selected_theaters', []):
                has_selections = any(st.session_state.selected_showtimes.get(theater_name, {}).values())
                expander_label = f"✅  {theater_name}" if has_selections else f"⚪️ {theater_name}"
                with st.expander(expander_label, expanded=True):
                    showings = st.session_state.all_showings.get(theater_name, [])
                    films_to_display = {f for f in st.session_state.selected_films if f in [s['film_title'] for s in showings]}
                    if not films_to_display: st.write("No selected films are showing at this theater.")
                    for film in sorted(list(films_to_display)):
                        st.markdown(f"**{film}**")
                        film_showings = sorted([s for s in showings if s['film_title'] == film], key=lambda x: datetime.datetime.strptime(x['showtime'].replace('p', 'PM').replace('a', 'AM'), "%I:%M%p").time())
                        showings_by_time = {}
                        for s in film_showings:
                            if s['showtime'] not in showings_by_time:
                                showings_by_time[s['showtime']] = []
                            showings_by_time[s['showtime']].append(s)

                        cols = st.columns(8)
                        for i, (time_str, showings_at_time) in enumerate(showings_by_time.items()):
                            is_selected = time_str in st.session_state.selected_showtimes.get(theater_name, {}).get(film, {})
                            if cols[i % 8].button(time_str, key=f"cs_time_{theater_name}_{film}_{time_str}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                                if theater_name not in st.session_state.selected_showtimes: st.session_state.selected_showtimes[theater_name] = {}
                                if film not in st.session_state.selected_showtimes[theater_name]: st.session_state.selected_showtimes[theater_name][film] = {}
                                
                                if is_selected:
                                    del st.session_state.selected_showtimes[theater_name][film][time_str]
                                else:
                                    st.session_state.selected_showtimes[theater_name][film][time_str] = showings_at_time
                                st.rerun()
        if any(any(film.values()) for film in st.session_state.get('selected_showtimes', {}).values()):
            st.subheader("Step 4: Generate Report")
            if st.button('📄 Generate Live Pricing Report', use_container_width=True, disabled=IS_DISABLED):
                st.session_state.confirm_scrape = True
                st.rerun()

    elif st.session_state.search_mode == "CompSnipe Mode":
        st.subheader("Step 1: Select Theaters")
        zip_col, zip_btn_col = st.columns([4, 1])
        with zip_col:
            zip_search_term = st.text_input("Enter 5-digit ZIP code to find theaters", max_chars=5, key="zip_search_input",
                                            on_change=lambda: st.session_state.update(live_search_results={}, compsnipe_theaters=[]), disabled=IS_DISABLED)
        with zip_btn_col:
            st.write("") 
            if st.button("Search by ZIP", key="search_by_zip_btn", disabled=IS_DISABLED):
                with st.spinner(f"Live searching Fandango for theaters near {zip_search_term}..."):
                    date_str = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
                    thread, result_func = run_async_in_thread(scout.live_search_by_zip, zip_search_term, date_str)
                    thread.join()
                    status, result, log, _ = result_func()
                    st.session_state.last_run_log = log
                    if status == 'success': 
                        st.session_state.live_search_results = result
                    else: 
                        st.error(f"Failed to perform live ZIP search: {get_error_message(result)}")
                st.rerun()

        if st.session_state.live_search_results:
            cols = st.columns(4)
            for i, name in enumerate(sorted(st.session_state.live_search_results.keys())):
                if 'compsnipe_theaters' not in st.session_state: st.session_state.compsnipe_theaters = []
                is_selected = name in [t['name'] for t in st.session_state.compsnipe_theaters]
                if cols[i % 4].button(name, key=f"cs_theater_{i}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                    theater_obj = st.session_state.live_search_results[name]
                    if is_selected:
                        st.session_state.compsnipe_theaters = [t for t in st.session_state.compsnipe_theaters if t['name'] != name]
                    else:
                        st.session_state.compsnipe_theaters.append(theater_obj)
                    st.rerun()

        if st.session_state.get('compsnipe_theaters'):
            scrape_date_cs = st.date_input("Select Date for Showtimes", datetime.date.today() + datetime.timedelta(days=1), key="cs_date", disabled=IS_DISABLED)
            
            if st.button("Find Available Films", use_container_width=True, disabled=IS_DISABLED):
                with st.spinner("Finding all available films and showtimes..."):
                    thread, result_func = run_async_in_thread(scout.get_all_showings_for_theaters, st.session_state.compsnipe_theaters, scrape_date_cs.strftime('%Y-%m-%d'))
                    thread.join()
                    status, result, log, duration = result_func()
                    st.session_state.last_run_log = log
                    if status == 'success':
                        st.info(f"Film search completed in {duration:.2f} seconds.")
                        st.session_state.all_showings = result
                        st.session_state.stage = 'cs_films_found'
                    else:
                        st.error(f"Failed to fetch showings: {get_error_message(result)}")
                st.rerun()

        if st.session_state.get('stage') == 'cs_films_found':
            st.subheader("Step 2: Choose Film Scope")
            
            film_sets = [set(s['film_title'] for s in st.session_state.all_showings.get(t['name'], [])) for t in st.session_state.compsnipe_theaters]
            all_films = sorted(list(set.union(*film_sets))) if film_sets else []
            common_films = sorted(list(set.intersection(*film_sets))) if film_sets else []
            
            c1, c2, c3 = st.columns(3)
            if c1.button(f"Scrape All {len(all_films)} Films", use_container_width=True, disabled=IS_DISABLED):
                st.session_state.selected_films = all_films
                st.session_state.compsnipe_film_filter_mode = 'all'
                st.session_state.stage = 'cs_showtimes'
                st.rerun()
            if c2.button(f"Scrape {len(common_films)} Common Films", use_container_width=True, disabled=IS_DISABLED):
                st.session_state.selected_films = common_films
                st.session_state.compsnipe_film_filter_mode = 'common'
                st.session_state.stage = 'cs_showtimes'
                st.rerun()
            if c3.button("Let Me Select Films...", use_container_width=True, disabled=IS_DISABLED):
                st.session_state.compsnipe_film_filter_mode = 'manual'
                st.session_state.stage = 'cs_showtimes'
                st.rerun()

        if st.session_state.get('stage') == 'cs_showtimes':
            st.subheader("Step 3: Select Films & Showtimes")

            if st.session_state.compsnipe_film_filter_mode == 'manual':
                film_sets = [set(s['film_title'] for s in st.session_state.all_showings.get(t['name'], [])) for t in st.session_state.compsnipe_theaters]
                all_films = sorted(list(set.union(*film_sets))) if film_sets else []
                st.write("Select Films:")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button("Select All Films", key="cs_select_all_films", use_container_width=True):
                        st.session_state.selected_films = all_films
                        st.rerun()
                with col2:
                    if st.button("Deselect All Films", key="cs_deselect_all_films", use_container_width=True):
                        st.session_state.selected_films = []
                        st.rerun()
                
                st.divider()

                cols = st.columns(4)
                for i, film in enumerate(all_films):
                    is_selected = film in st.session_state.selected_films
                    if cols[i % 4].button(film, key=f"cs_film_{film}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                        if is_selected: st.session_state.selected_films.remove(film)
                        else: st.session_state.selected_films.append(film)
                        st.rerun()
                st.divider()

            if st.session_state.selected_films:
                render_daypart_selector(st.session_state.all_showings, st.session_state.selected_films, [t['name'] for t in st.session_state.compsnipe_theaters], IS_DISABLED, "cs")

            for theater in st.session_state.get('compsnipe_theaters', []):
                theater_name = theater['name']
                has_selections = any(st.session_state.selected_showtimes.get(theater_name, {}).values())
                expander_label = f"✅  {theater_name}" if has_selections else f"⚪️ {theater_name}"
                with st.expander(expander_label, expanded=True):
                    showings = st.session_state.all_showings.get(theater_name, [])
                    films_to_display = {f for f in st.session_state.selected_films if f in [s['film_title'] for s in showings]}
                    if not films_to_display: st.write("No selected films are showing at this theater.")
                    for film in sorted(list(films_to_display)):
                        st.markdown(f"**{film}**")
                        film_showings = sorted([s for s in showings if s['film_title'] == film], key=lambda x: datetime.datetime.strptime(x['showtime'].replace('p', 'PM').replace('a', 'AM'), "%I:%M%p").time())
                        showings_by_time = {}
                        for s in film_showings:
                            if s['showtime'] not in showings_by_time:
                                showings_by_time[s['showtime']] = []
                            showings_by_time[s['showtime']].append(s)

                        cols = st.columns(8)
                        for i, (time_str, showings_at_time) in enumerate(showings_by_time.items()):
                            is_selected = time_str in st.session_state.selected_showtimes.get(theater_name, {}).get(film, {})
                            if cols[i % 8].button(time_str, key=f"cs_time_{theater_name}_{film}_{time_str}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                                if theater_name not in st.session_state.selected_showtimes: st.session_state.selected_showtimes[theater_name] = {}
                                if film not in st.session_state.selected_showtimes[theater_name]: st.session_state.selected_showtimes[theater_name][film] = {}
                                
                                if is_selected:
                                    del st.session_state.selected_showtimes[theater_name][film][time_str]
                                else:
                                    st.session_state.selected_showtimes[theater_name][film][time_str] = showings_at_time
                                st.rerun()

            if any(any(film.values()) for film in st.session_state.get('selected_showtimes', {}).values()):
                st.subheader("Step 4: Generate Report")
                if st.button('📄 Generate Sniper Report', use_container_width=True, disabled=IS_DISABLED):
                    st.session_state.confirm_scrape = True
                    st.rerun()

    if st.session_state.get('confirm_scrape'):
        st.info(f"You are about to scrape prices. This may take several minutes.")
        if st.button("✅ Yes, Proceed", use_container_width=True, type="primary"):
            st.session_state.report_running = True
            st.session_state.confirm_scrape = False
            st.rerun()

    if st.session_state.report_running and not st.session_state.get('run_diagnostic'):
        mode = st.session_state.search_mode
        
        with st.spinner(f"Executing {mode} scrape... This may take several minutes. UI is locked."):
            theaters_for_report = []
            if mode == "CompSnipe Mode":
                theaters_for_report = st.session_state.compsnipe_theaters
            elif mode == "Market Mode":
                theaters_for_report = [t for t in st.session_state.theaters if t['name'] in st.session_state.selected_theaters]
            run_context_str = "N/A"
            if mode == "Market Mode":
                market = st.session_state.get('selected_market', 'Unknown Market')
                theater_names = ", ".join([t['name'] for t in theaters_for_report])
                run_context_str = f"Market: {market} | Theaters: {theater_names}"
            elif mode == "CompSnipe Mode":
                zip_code = st.session_state.get('zip_search_input', 'N/A')
                theater_names = ", ".join([t['name'] for t in theaters_for_report])
                run_context_str = f"ZIP: {zip_code} | Theaters: {theater_names}"
            thread, get_results = run_async_in_thread(scout.scrape_details, theaters_for_report, st.session_state.selected_showtimes)
            thread.join()
            status, value, log, duration = get_results()
            st.session_state.last_run_log += log

            if status == 'success':
                result, showings_scraped = value
                if result:
                    st.session_state.last_run_duration = duration
                    df_current = pd.DataFrame(result)
                    
                    log_runtime(mode, len(theaters_for_report), len(showings_scraped), duration)
                    database.save_to_database(df_current, mode, run_context_str)
                    
                    st.session_state.final_df = df_current
                    st.session_state.stage = 'report_generated'
                else:
                    st.error(f"Scraper returned no data after {duration:.2f} seconds.")
            else:
                st.error(f"Scraper failed to produce a report after {duration:.2f} seconds. Error: {get_error_message(value)}")

            st.session_state.report_running = False
            st.rerun()
    elif st.session_state.search_mode == "Data Management":
        from data_management_v2 import main as data_management_main
        data_management_main()


    elif st.session_state.search_mode == "Analysis Mode":
        st.header("🗂️ Historical Analysis")

        try:
            with st.expander("📈 Advanced Trend Analysis", expanded=True):
                # Initialize session state variables
                if 'trend_theaters' not in st.session_state:
                    st.session_state.trend_theaters = []
                if 'trend_films' not in st.session_state:
                    st.session_state.trend_films = []
                if 'trend_dayparts' not in st.session_state:
                    st.session_state.trend_dayparts = []

                all_theaters = database.get_unique_column_values('theater_name')
                if not all_theaters:
                    st.info("No data available to analyze.")
                else:
                    # --- Step 1: Select Theaters ---
                    st.subheader("Step 1: Select Theaters")
                    cols = st.columns(4)
                    for i, theater in enumerate(all_theaters):
                        is_selected = theater in st.session_state.trend_theaters
                        if cols[i % 4].button(theater, key=f"trend_theater_{i}", type="primary" if is_selected else "secondary", use_container_width=True):
                            if is_selected: st.session_state.trend_theaters.remove(theater)
                            else: st.session_state.trend_theaters.append(theater)
                            # Clear dependent selections
                            st.session_state.trend_films = []
                            st.session_state.trend_dayparts = []
                            st.rerun()

                    if st.session_state.trend_theaters:
                        st.divider()
                        
                        # --- Step 2: Select Date Range ---
                        st.subheader("Step 2: Select a Date Range for Analysis")
                        today = datetime.date.today()
                        seven_days_ago = today - datetime.timedelta(days=7)
                        c1, c2 = st.columns(2)
                        start_date = c1.date_input("Start Date", seven_days_ago, key='trend_start_date')
                        end_date = c2.date_input("End Date", today, key='trend_end_date')

                        # --- Step 3: Select Films (using buttons) ---
                        if start_date and end_date and start_date <= end_date:
                            all_dates_in_range = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
                            
                            st.subheader("Step 3: Select Films")
                            available_films = database.get_common_films_for_theaters_dates(st.session_state.trend_theaters, all_dates_in_range)
                            
                            if not available_films:
                                st.warning("No films are common to all selected theaters in this date range.")
                            else:
                                film_cols = st.columns(4)
                                for i, film in enumerate(available_films):
                                    is_selected = film in st.session_state.trend_films
                                    if film_cols[i % 4].button(film, key=f"trend_film_{i}", type="primary" if is_selected else "secondary", use_container_width=True):
                                        if is_selected: st.session_state.trend_films.remove(film)
                                        else: st.session_state.trend_films.append(film)
                                        st.rerun()
                            
                            # --- Step 4: Select Dayparts (using buttons) ---
                            if st.session_state.trend_films:
                                st.subheader("Step 4: Select Dayparts")
                                dayparts_options = ["Matinee", "Twilight", "Prime", "Late Night"]
                                daypart_cols = st.columns(len(dayparts_options))
                                for i, dp in enumerate(dayparts_options):
                                    is_selected = dp in st.session_state.trend_dayparts
                                    if daypart_cols[i].button(dp, key=f"trend_dp_{i}", type="primary" if is_selected else "secondary", use_container_width=True):
                                        if is_selected: st.session_state.trend_dayparts.remove(dp)
                                        else: st.session_state.trend_dayparts.append(dp)
                                        st.rerun()

                        # --- Step 5: Generate the Advanced Report ---
                        if st.session_state.trend_theaters and st.session_state.trend_films and st.session_state.trend_dayparts:
                            st.divider()
                            if st.button("🚀 Generate Advanced Report", type="primary", use_container_width=True):
                                with st.spinner("Performing advanced analysis..."):
                                    raw_data = database.get_data_for_trend_report(
                                        st.session_state.trend_theaters,
                                        all_dates_in_range,
                                        st.session_state.trend_films,
                                        st.session_state.trend_dayparts
                                    )
                                    # (The rest of the logic remains the same)
                                    if raw_data.empty:
                                        st.warning("No price data found for the combination of your selections.")
                                        if 'advanced_report_df' in st.session_state: del st.session_state['advanced_report_df']
                                    else:
                                        raw_data['scrape_date'] = pd.to_datetime(raw_data['scrape_date'])
                                        raw_data['Day Type'] = raw_data['scrape_date'].dt.dayofweek.apply(lambda x: 'Weekend' if x >= 5 else 'Weekday')
                                        raw_data = raw_data.sort_values(by='scrape_date')
                                        raw_data['price_change'] = raw_data.groupby(['theater_name', 'film_title', 'ticket_type', 'daypart'])['price'].diff()
                                        def format_cell(row):
                                            price = f"${row['price']:.2f}"
                                            change = format_price_change(row['price_change'])
                                            if change == "$0.00" or change == "N/A": return price
                                            return f"{price} ({change})"
                                        raw_data['display_value'] = raw_data.apply(format_cell, axis=1)
                                        raw_data['scrape_date'] = raw_data['scrape_date'].dt.strftime('%Y-%m-%d')
                                        report_df = raw_data.pivot_table(index=['theater_name', 'film_title', 'Day Type', 'ticket_type', 'daypart'], columns='scrape_date', values='display_value', aggfunc='last').fillna('-')
                                        st.session_state.advanced_report_df = report_df.reset_index()


                                    if raw_data.empty:
                                        st.warning("No price data found for the combination of your selections.")
                                        if 'advanced_report_df' in st.session_state:
                                            del st.session_state['advanced_report_df']
                                    else:
                                        raw_data['scrape_date'] = pd.to_datetime(raw_data['scrape_date'])
                                        raw_data['Day Type'] = raw_data['scrape_date'].dt.dayofweek.apply(
                                            lambda x: 'Weekend' if x >= 5 else 'Weekday'  # Saturday=5, Sunday=6
                                        )
                                        raw_data = raw_data.sort_values(by='scrape_date')
                                        raw_data['price_change'] = raw_data.groupby(
                                            ['theater_name', 'film_title', 'ticket_type', 'daypart']
                                        )['price'].diff()
                                        
                                        def format_cell(row):
                                            price = f"${row['price']:.2f}"
                                            change = format_price_change(row['price_change'])
                                            if change == "$0.00" or change == "N/A":
                                                return price
                                            return f"{price} ({change})"

                                        raw_data['display_value'] = raw_data.apply(format_cell, axis=1)
                                        raw_data['scrape_date'] = raw_data['scrape_date'].dt.strftime('%Y-%m-%d')
                                        
                                        report_df = raw_data.pivot_table(
                                            index=['theater_name', 'film_title', 'Day Type', 'ticket_type', 'daypart'],
                                            columns='scrape_date',
                                            values='display_value',
                                            aggfunc='last'
                                        ).fillna('-')
                                        
                                        st.session_state.advanced_report_df = report_df.reset_index()

            # --- Display the final Advanced Report ---
            if 'advanced_report_df' in st.session_state:
                st.subheader("Advanced Trend Report")
                st.success("Report generated successfully!")
                df_to_show = st.session_state.advanced_report_df
                st.dataframe(df_to_show, use_container_width=True)
                st.download_button(
                    label="📄 Download Advanced Report as CSV",
                    data=to_csv(df_to_show),
                    file_name='PriceScout_Advanced_Report.csv',
                    mime='text/csv'
                )

        except Exception as e:
            st.error(f"An error occurred in the analysis tool: {e}")
            st.code(traceback.format_exc())
            
    if st.session_state.get('stage') == 'report_generated' and 'final_df' in st.session_state and not st.session_state.final_df.empty:
        st.header("Live Pricing Report")
        
        duration_str = f"(Took {st.session_state.last_run_duration:.2f} seconds)" if 'last_run_duration' in st.session_state else ""
        st.success(f"**Report Complete!** {duration_str} Data has been successfully saved to the database.")
        
        df_to_display = st.session_state.final_df
        st.dataframe(df_to_display, use_container_width=True)
        
        st.subheader("Download Report")
        col1, col2, _ = st.columns([1, 1, 4])
        
        excel_data = to_excel(df_to_display)
        csv_data = to_csv(df_to_display)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        col1.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f'PriceScout_Report_{timestamp}.csv',
            mime='text/csv',
            use_container_width=True
        )
        
        col2.download_button(
            label="📊 Download as Excel",
            data=excel_data,
            file_name=f'PriceScout_Report_{timestamp}.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            use_container_width=True
        )

        st.balloons()

    if st.session_state.dev_mode and "last_run_log" in st.session_state:
        with st.expander("Developer Mode: Scraper Log"):
            st.code(st.session_state.last_run_log, language='text')