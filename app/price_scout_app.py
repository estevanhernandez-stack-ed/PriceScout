# price_scout_app.py - The Streamlit User Interface & Scraping Engine (v27.0 - Enhanced Data Management)

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.utils import format_time_to_human_readable
import streamlit as st
import pandas as pd
import datetime
import asyncio
import time
import json
import sqlite3
import glob
import pytz
from app import theming
from app import config

from app.config import SCRIPT_DIR, PROJECT_DIR, DEBUG_DIR, DATA_DIR, CACHE_FILE, CACHE_EXPIRATION_DAYS
from app import database
from app import users
from app.utils import run_async_in_thread, format_price_change, style_price_change_v2, check_cache_status, get_report_path, log_runtime, clear_workflow_state, reset_session, style_price_change, to_excel, to_csv, get_error_message, estimate_scrape_time, generate_human_readable_summary
from app.ui_components import render_daypart_selector, apply_daypart_auto_selection, render_film_and_showtime_selection
from app.modes.market_mode import render_market_mode
from app.modes.operating_hours_mode import render_operating_hours_mode
from app.modes.compsnipe_mode import render_compsnipe_mode
from app.utils import process_and_save_operating_hours, save_operating_hours_from_all_showings
from app.modes.analysis_mode import render_analysis_mode
from app.modes.poster_mode import render_poster_mode
from app.admin import admin_page

def load_ui_config():
    with open(os.path.join(SCRIPT_DIR, 'ui_config.json'), 'r', encoding='utf-8') as f:
        return json.load(f)

ui_config = load_ui_config()

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

def login():
    users.init_database() # Ensure the database is initialized

    if st.session_state.get("logged_in"):
        return True

    st.image(os.path.join(SCRIPT_DIR, 'PriceScoutLogo.png'), width=300)
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        # --- NEW: Caps Lock Warning ---
        caps_lock_warning_script = """
        <div id="caps-lock-warning" style="color: orange; display: none; font-size: 0.9rem; margin-top: -10px; margin-bottom: 10px;">Warning: Caps Lock is on.</div>
        <script>
            const passwordInput = document.querySelector("input[type='password']");
            const warningDiv = document.getElementById("caps-lock-warning");

            if (passwordInput) {
                // Function to check and display warning
                const checkCapsLock = (event) => {
                    if (event.getModifierState("CapsLock")) {
                        warningDiv.style.display = "block";
                    } else {
                        warningDiv.style.display = "none";
                    }
                };

                // Add listeners to check on keyup and when the field is focused
                passwordInput.addEventListener("keyup", checkCapsLock);
                passwordInput.addEventListener("focus", checkCapsLock);
            }
        </script>
        """
        st.markdown(caps_lock_warning_script, unsafe_allow_html=True)

        submitted = st.form_submit_button("Login")
        
        if submitted:
            user = users.verify_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user_name = user['username']
                st.session_state.is_admin = user['is_admin']
                st.session_state.company = user['company']
                st.session_state.default_company = user['default_company'] # --- FIX: sqlite3.Row uses key access, not .get() ---
                st.rerun()
            else:
                st.error("Incorrect username or password")
    return False

def render_scheduled_tasks_list():
    """Renders a list of existing scheduled tasks with their status and controls."""
    st.subheader("Existing Scheduled Tasks")
    
    tasks_dir = config.SCHEDULED_TASKS_DIR
    if not os.path.exists(tasks_dir) or not os.listdir(tasks_dir):
        st.info("No scheduled tasks found for this company.")
        return

    task_files = sorted(glob.glob(os.path.join(tasks_dir, '*.json')))
    
    # Header for the list
    c1, c2, c3, c4 = st.columns([4, 5, 3, 2])
    c1.write("**Task Name & Schedule**")
    c2.write("**Details**")
    c3.write("**Last Run (UTC)**")
    c4.write("**Controls**")
    st.divider()

    for task_file in task_files:
        try:
            with open(task_file, 'r+') as f:
                task_config = json.load(f)
                
                task_name = task_config.get('task_name', os.path.basename(task_file))
                task_type = task_config.get('task_type', 'market_scrape')
                is_enabled = task_config.get('enabled', False)
                last_run = task_config.get('last_run')
                
                last_run_str = "Never"
                if last_run:
                    last_run_dt = datetime.datetime.fromisoformat(last_run.replace('Z', '+00:00')).astimezone(pytz.utc)
                    last_run_str = last_run_dt.strftime('%Y-%m-%d %H:%M')

                if task_type == "weekly_op_hours_report":
                    schedule_info = f"on {task_config.get('day_of_week', 'N/A')} at {task_config.get('schedule_time_utc', 'N/A')} UTC"
                    details = "Weekly Operating Hours Report"
                else:
                    schedule_info = f"at {task_config.get('schedule_time_utc', 'N/A')} UTC"
                    details = f"Markets: {', '.join(task_config.get('markets', []))}"

                c1, c2, c3, c4 = st.columns([4, 5, 3, 2])
                c1.write(f"**{task_name}**")
                c1.caption(f"Schedule: {schedule_info}")
                c2.caption(details)
                c3.write(last_run_str)
                
                c4_1, c4_2 = c4.columns(2)
                new_enabled_state = c4_1.toggle("On", value=is_enabled, key=f"enable_{task_name}", help="Enable/Disable Task")
                if c4_2.button("🗑️", key=f"delete_{task_name}", help="Delete this task"):
                    os.remove(task_file)
                    st.toast(f"Deleted task '{task_name}'")
                    st.rerun()
                
                if new_enabled_state != is_enabled:
                    task_config['enabled'] = new_enabled_state
                    f.seek(0)
                    json.dump(task_config, f, indent=4)
                    f.truncate()
                    st.rerun()
        except Exception as e:
            st.error(f"Error loading task file {os.path.basename(task_file)}: {e}")

from app.state import initialize_session_state

def setup_application(markets_data):
    """Handles company selection, dynamic path setup, and database initialization."""
    # Ensure st.session_state.selected_company is valid after initialization or reload
    all_available_companies = list(markets_data.keys())
    if not all_available_companies:
        st.warning("No markets data loaded. Please upload a markets.json file in Data Management mode.")
        return False

    # If selected_company is not set, or is no longer in available companies, default it
    if 'selected_company' not in st.session_state or st.session_state.selected_company not in all_available_companies:
        # --- NEW: Prioritize the user's default company setting ---
        if st.session_state.get('default_company') and st.session_state.default_company in all_available_companies:
            st.session_state.selected_company = st.session_state.default_company
        elif st.session_state.is_admin:
            st.session_state.selected_company = all_available_companies[0] # Fallback for admin
        elif st.session_state.company and st.session_state.company in all_available_companies:
            st.session_state.selected_company = st.session_state.company
        else:
            st.session_state.selected_company = all_available_companies[0]

    # --- Company Selection ---
    if st.session_state.is_admin:
        st.sidebar.subheader("Company Selection")
        # --- FIX: Detect company change and reset dependent state ---
        previous_company = st.session_state.get('selected_company')
        selected_company = st.sidebar.selectbox(
            "Select Company",
            options=all_available_companies,
            index=all_available_companies.index(st.session_state.selected_company),
            key="company_selector"
        )
        if selected_company != previous_company:
            st.session_state.selected_company = selected_company
            # A different company was selected, so clear the workflow state to avoid errors
            clear_workflow_state()
            st.rerun()

    if not st.session_state.selected_company:
        st.warning("No valid company selected. Please contact an admin.")
        return False

    st.sidebar.info(f"User: **{st.session_state.user_name}**\n\nCompany: **{st.session_state.selected_company}**")

    # --- Set Dynamic Paths ---
    selected_company_path = os.path.join(DATA_DIR, st.session_state.selected_company)

    config.DB_FILE = os.path.join(selected_company_path, 'price_scout.db')
    config.REPORTS_DIR = os.path.join(selected_company_path, 'reports')
    config.RUNTIME_LOG_FILE = os.path.join(config.REPORTS_DIR, 'runtime_log.csv')
    config.SCHEDULED_TASKS_DIR = os.path.join(selected_company_path, 'scheduled_tasks')

    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    os.makedirs(config.SCHEDULED_TASKS_DIR, exist_ok=True)

    database.init_database()
    database.update_database_schema()
    return True

def render_sidebar_modes(is_disabled, dev_mode_enabled):
    """Renders the mode selection buttons in the sidebar."""
    st.sidebar.subheader(ui_config['sidebar']['select_mode_subheader'])
    
    # --- NEW: Dynamically build modes from ui_config.json ---
    cache_available = os.path.exists(CACHE_FILE)
    
    # Get the ordered list of modes from the config
    sidebar_modes = ui_config.get('sidebar_modes', [])
    current_mode = st.session_state.get('search_mode', "Market Mode")

    for mode_config in sidebar_modes:
        mode = mode_config.get("name")
        if not mode: continue

        # Determine if the mode should be shown or disabled
        is_admin_only = mode_config.get("admin_only", False)
        is_dev_only = mode_config.get("dev_only", False)
        requires_cache = mode_config.get("requires_cache", False)

        if (is_admin_only and not st.session_state.get("is_admin")) or \
           (is_dev_only and not dev_mode_enabled):
            continue # Don't render the button at all

        disabled = (requires_cache and not cache_available) or is_disabled

        if st.sidebar.button(mode, use_container_width=True, type="primary" if current_mode == mode else "secondary", disabled=disabled or is_disabled):
            if st.session_state.search_mode != mode:
                st.session_state.search_mode = mode
                clear_workflow_state() 
                st.rerun()

def render_main_content(scout, markets_data, cache_data, all_theaters_list_unique, is_disabled):
    """Dispatches to the correct mode's rendering function."""
    mode = st.session_state.search_mode
    if mode == "Market Mode":
        render_market_mode(scout, markets_data, cache_data, is_disabled, st.session_state.selected_company)
    elif mode == "Poster Board":
        render_poster_mode(scout, markets_data, cache_data, is_disabled, st.session_state.selected_company)
    elif mode == "Operating Hours Mode":
        render_operating_hours_mode(scout, markets_data, cache_data, is_disabled, process_and_save_operating_hours)
    elif mode == "CompSnipe Mode":
        render_compsnipe_mode(scout, all_theaters_list_unique, is_disabled, save_operating_hours_from_all_showings, markets_data, cache_data)
    elif mode == "Historical Data and Analysis":
        render_analysis_mode(markets_data, cache_data)
    elif mode == "Data Management":
        from app.data_management_v2 import main as data_management_main
        data_management_main()
    elif mode == "Theater Matching":
        from app.theater_matching_tool import main as theater_matching_main
        theater_matching_main()
    elif mode == "Admin":
        admin_page(markets_data)

def handle_scrape_confirmation():
    """Renders the confirmation dialog for long scrapes."""
    showtime_count = 0
    # --- FIX: Correctly count the total number of individual showings, not just unique times ---
    selected_showtimes = st.session_state.get('selected_showtimes', {})
    for daily_selections in selected_showtimes.values():
        for theater_selections in daily_selections.values():
            for film_selections in theater_selections.values():
                for showings_at_time in film_selections.values():
                    showtime_count += len(showings_at_time)

    estimated_time = estimate_scrape_time(showtime_count, mode_filter='price')

    if estimated_time != -1 and estimated_time < 30:
        st.session_state.report_running = True
        st.session_state.confirm_scrape = False
    else:
        if estimated_time != -1:
            confirm_message = f"This scrape involves {showtime_count} showings and is estimated to take about {format_time_to_human_readable(estimated_time)}. Do you want to proceed?"
        else:
            confirm_message = ui_config['scraper']['confirm_message']
        
        st.info(confirm_message)
        if st.button(ui_config['scraper']['proceed_button'], use_container_width=True, type="primary"):
            st.session_state.report_running = True
            st.session_state.confirm_scrape = False
            st.rerun() # Rerun immediately after setting the state
    # Do not rerun here, let the button click handle it.

def _render_sidebar_footer():
    """Renders the cache status and application footer at the bottom of the sidebar."""
    st.sidebar.divider()
    cache_status, last_updated = check_cache_status()
    if cache_status == "missing":
        st.sidebar.error("Cache missing. Build in Data Mgmt.")
    elif last_updated:
        st.sidebar.caption(f"Cache last updated: {last_updated}")
    
    st.sidebar.markdown('<div style="text-align: center; color: grey; font-size: 0.8em;">Developed @ 626Labs LLC</div>', unsafe_allow_html=True)

def _render_scrape_progress():
    """Renders the UI for an in-progress scrape, including progress bar and time estimate."""
    mode = st.session_state.search_mode
    queue = st.session_state.scrape_queue
    current_index = st.session_state.scrape_current_index

    header_text = "Scrape in Progress"
    if mode == "Market Mode":
        market = st.session_state.get('selected_market', 'selected markets')
        header_text += f" for Market: {market}"
    elif mode == "CompSnipe Mode":
        num_theaters = len(queue)
        header_text += f" for {queue[0]['name']}" if num_theaters == 1 else f" for {num_theaters} selected theaters"
    st.header(header_text)

    time_remaining_str = ""
    if current_index > 0 and 'scrape_total_duration' in st.session_state:
        avg_time_per_theater = st.session_state.scrape_total_duration / current_index
        theaters_remaining = len(queue) - current_index
        time_remaining_str = f" (est. {format_time_to_human_readable(avg_time_per_theater * theaters_remaining)} remaining)"

    progress_text = f"Processing theater {current_index} of {len(queue)}...{time_remaining_str}"
    st.progress(current_index / len(queue) if queue else 0, text=progress_text)
    if st.button("Cancel Scrape", type="primary"):
        st.session_state.cancel_scrape = True
        st.warning("Cancellation requested. The scrape will stop.")
        st.rerun()

def _finalize_scrape_session():
    """Cleans up and finalizes the scrape session, preparing the report or handling cancellation."""
    # If there are any results, even if they are empty, we should proceed to the report stage.
    # The report function can handle an empty dataframe.
    if st.session_state.get('scrape_results') is not None:
        st.session_state.last_run_duration = st.session_state.get('scrape_total_duration', 0)
        df_current = pd.DataFrame(st.session_state.scrape_results)
        log_runtime(st.session_state.search_mode, st.session_state.scrape_current_index, len(st.session_state.scraped_showings), st.session_state.scrape_total_duration)
        st.session_state.final_df = df_current
        st.session_state.stage = 'report_generated'
    elif st.session_state.get('cancel_scrape'):
        st.info("Scrape was cancelled. No report generated.")
        st.session_state.stage = 'ready_for_input'
    else:
        # This case handles if the scrape was initiated but no results were produced at all.
        if 'scrape_total_duration' in st.session_state:
            st.error(ui_config['scraper']['no_data_error'].format(duration=st.session_state.scrape_total_duration))
        else:
            st.error("Scrape failed to start or was interrupted before any data could be processed.")
        st.session_state.stage = 'ready_for_input'

    # Clean up session state keys related to the scrape run
    for key in ['scrape_queue', 'scrape_results', 'scraped_showings', 'scrape_total_duration', 'scrape_current_index', 'cancel_scrape', 'report_running', 'scrape_run_context', 'scrape_run_id', 'scrape_thread', 'get_scrape_results', 'scrape_status_container']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def _initialize_scrape_session():
    """Initializes the session state for a new scrape run."""
    theaters_to_scrape = []
    if st.session_state.search_mode == "Market Mode":
        # In Market Mode, selected_theaters is a list of names. We need the full objects.
        all_theaters_in_context = st.session_state.get('theaters', [])
        selected_names = st.session_state.get('selected_theaters', [])
        theaters_to_scrape = [t for t in all_theaters_in_context if t.get('name') in selected_names]
    elif st.session_state.search_mode == "CompSnipe Mode":
        # In CompSnipe Mode, compsnipe_theaters is already a list of theater objects.
        theaters_to_scrape = st.session_state.get('compsnipe_theaters', [])
    elif st.session_state.search_mode == "Poster Board":
        # In Poster Board, selected_theaters is a list of names. We need the full objects.
        all_theaters_in_context = st.session_state.get('theaters', [])
        selected_names = st.session_state.get('selected_theaters', [])
        theaters_to_scrape = [t for t in all_theaters_in_context if t['name'] in selected_names]

    st.session_state.scrape_queue = theaters_to_scrape
    st.session_state.scrape_results = []
    st.session_state.scraped_showings = []
    st.session_state.scrape_total_duration = 0
    st.session_state.scrape_current_index = 0
    st.session_state.cancel_scrape = False
    st.session_state.scrape_run_context = f"Mode: {st.session_state.search_mode}, Theaters: {len(theaters_to_scrape)}"
    st.session_state.scrape_run_id = database.create_scrape_run(st.session_state.search_mode, st.session_state.scrape_run_context)

def _process_single_theater_scrape(scout):
    """Manages the async task of scraping a single theater and updating the UI."""
    theater = st.session_state.scrape_queue[st.session_state.scrape_current_index]

    if 'scrape_thread' not in st.session_state:
        st.session_state.scrape_status_container = ["Initializing..."]
        thread, get_results = run_async_in_thread(
            scout.scrape_details,
            [theater],
            st.session_state.selected_showtimes,
            status_container=st.session_state.scrape_status_container
        )
        st.session_state.scrape_thread = thread
        st.session_state.get_scrape_results = get_results
        st.rerun()
    else:
        status_container = st.session_state.scrape_status_container
        thread = st.session_state.scrape_thread
        with st.status(f"Scraping {theater['name']}: {status_container[0]}", expanded=True) as status_ui:
            if thread.is_alive():
                time.sleep(1.5)
                st.rerun()
            else:
                status, value, log, duration = st.session_state.get_scrape_results()
                st.session_state.last_run_log += log
                st.session_state.scrape_total_duration += duration
                if status == 'success':
                    result, showings_scraped = value
                    if result:
                        st.session_state.scrape_results.extend(result)
                        st.session_state.scraped_showings.extend(showings_scraped)
                        database.save_prices(st.session_state.scrape_run_id, pd.DataFrame(result))
                        status_ui.update(label=f"Scrape for {theater['name']} complete!", state="complete", expanded=False)
                    else:
                        status_ui.update(label=f"No prices found for {theater['name']}. (Showtimes may be sold out or unavailable).", state="complete", expanded=False)
                else:
                    st.error(f"Failed to scrape {theater['name']}: {get_error_message(value)}")
                    status_ui.update(label=f"Error scraping {theater['name']}.", state="error", expanded=False)
                
                st.session_state.scrape_current_index += 1
                for key in ['scrape_thread', 'get_scrape_results', 'scrape_status_container']:
                    if key in st.session_state: del st.session_state[key]
                st.rerun()

def execute_scrape(scout):
    """Runs the main scraping logic by orchestrating initialization, progress, and finalization steps."""
    if 'scrape_queue' not in st.session_state:
        _initialize_scrape_session()

    _render_scrape_progress()

    if st.session_state.get('cancel_scrape') or st.session_state.scrape_current_index >= len(st.session_state.scrape_queue):
        _finalize_scrape_session()
    else:
        _process_single_theater_scrape(scout)

def render_report():
    """Displays the final report dataframe and download buttons."""
    st.header(ui_config['report']['header'])
    
    duration_str = f"(Took {st.session_state.last_run_duration:.2f} seconds)" if 'last_run_duration' in st.session_state else ""
    st.success(ui_config['report']['complete_message'].format(duration_str=duration_str))
    
    df_to_display = st.session_state.final_df

    # --- Human-Readable Summary ---
    st.subheader("Scrape Summary")

    # --- NEW: View Toggle ---
    view_mode = st.radio(
        "Group Summary By:",
        ("Theater", "Film"),
        horizontal=True,
        key="report_view_mode"
    )

    if view_mode == "Theater":
        summary_data = generate_human_readable_summary(df_to_display)
    else: # "Film"
        from app.utils import generate_human_readable_summary_by_film
        summary_data = generate_human_readable_summary_by_film(df_to_display)

    if not summary_data:
        st.info("No data to summarize.")
    else:
        # --- NEW: Chart for Average Price by Theater ---
        if not df_to_display.empty and 'Price' in df_to_display.columns and 'Theater Name' in df_to_display.columns:
            chart_df = df_to_display.copy()
            chart_df['price_numeric'] = pd.to_numeric(chart_df['Price'].astype(str).str.replace('$', '', regex=False), errors='coerce')
            chart_df.dropna(subset=['price_numeric'], inplace=True)

            # If a theater appears on multiple dates, average its average prices for the chart
            if not chart_df.empty:
                avg_price_per_theater = chart_df.groupby('Theater Name')['price_numeric'].mean().sort_values(ascending=False)
            else:
                avg_price_per_theater = pd.Series()
            
            if not avg_price_per_theater.empty:
                st.subheader("Average Price by Theater")
                st.bar_chart(avg_price_per_theater)
                st.divider()

        # Sort dates for chronological order
        if view_mode == "Theater":
            sorted_dates = sorted(summary_data.keys())
            for play_date in sorted_dates:
                try:
                    date_obj = datetime.datetime.strptime(play_date, '%Y-%m-%d').date()
                    st.markdown(f"### 🗓️ {date_obj.strftime('%A, %B %d, %Y')}")
                except (ValueError, TypeError):
                    st.markdown(f"### 🗓️ {play_date}")
                
                markets_data_for_date = summary_data[play_date]
                for market_name, theaters_data in sorted(markets_data_for_date.items()):
                    st.markdown(f"#### Market: {market_name}")
                    for theater_name, films_list in sorted(theaters_data.items()):
                        with st.expander(f"**{theater_name}**", expanded=True):
                            for film_summary in sorted(films_list, key=lambda x: x['film_title']):
                                col1, col2 = st.columns([1, 4])

                                with col1:
                                    if film_summary.get('poster_url') and film_summary['poster_url'] != 'N/A':
                                        st.image(film_summary['poster_url'])
                                
                                with col2:
                                    st.markdown(f"##### {film_summary['film_title']} ({film_summary.get('num_showings', 0)} showings)")
                                    
                                    detail_parts = []
                                    if film_summary.get('rating') and film_summary['rating'] != 'N/A':
                                        detail_parts.append(f"Rated {film_summary['rating']}")
                                    if film_summary.get('runtime') and film_summary['runtime'] != 'N/A':
                                        detail_parts.append(film_summary['runtime'])
                                    st.caption(" | ".join(detail_parts))
                                    
                                    if film_summary.get('general_amenities'):
                                        st.caption(f"Amenities: {', '.join(film_summary['general_amenities'])}")

                                    st.write(f"**Showtimes:** {', '.join(film_summary['showtimes'])}")
                                    
                                    st.write("**Ticket Prices:**")
                                    price_breakdown_str = film_summary.get('price_breakdown_str')
                                    if price_breakdown_str:
                                        st.caption(price_breakdown_str)
                                    else:
                                        st.caption("No price information available.")
                                
                                st.markdown("---")
        else: # "By Film" view
            sorted_dates = sorted(summary_data.keys())
            for play_date in sorted_dates:
                try:
                    date_obj = datetime.datetime.strptime(play_date, '%Y-%m-%d').date()
                    st.markdown(f"### 🗓️ {date_obj.strftime('%A, %B %d, %Y')}")
                except (ValueError, TypeError):
                    st.markdown(f"### 🗓️ {play_date}")

                markets_data_for_date = summary_data[play_date]
                for market_name, films_data in sorted(markets_data_for_date.items()):
                    st.markdown(f"#### Market: {market_name}")
                    for film_title, film_info in sorted(films_data.items()):
                        film_details = film_info['film_details']
                        with st.expander(f"**{film_title}**", expanded=True):
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                if film_details.get('poster_url') and film_details['poster_url'] != 'N/A':
                                    st.image(film_details['poster_url'])
                            with col2:
                                for theater_summary in sorted(film_info['theaters'], key=lambda x: x['theater_name']):
                                    num_showings = theater_summary.get('num_showings', 0)
                                    st.markdown(f"##### {theater_summary['theater_name']} ({num_showings} showings)")
                                    st.write(f"**Showtimes:** {', '.join(theater_summary['showtimes'])}")
                                    st.caption(f"**Prices:** {theater_summary['price_breakdown_str']}")
                                    st.markdown("---")
    
    st.divider()
    st.subheader("Raw Scrape Data")
    st.dataframe(df_to_display, use_container_width=True)
    
    st.subheader(ui_config['report']['download_subheader'])
    col1, col2, col3 = st.columns(3)
    
    excel_data = to_excel(df_to_display)
    csv_data = to_csv(df_to_display)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    
    col1.download_button(
        label=ui_config['report']['download_csv_button'],
        data=csv_data,
        file_name=f'PriceScout_Report_{timestamp}.csv',
        mime='text/csv',
        use_container_width=True
    )
    
    col2.download_button(
        label=ui_config['report']['download_excel_button'],
        data=excel_data,
        file_name=f'PriceScout_Report_{timestamp}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        use_container_width=True
    )

    with col3:
        if 'summary_pdf_bytes' in st.session_state and st.session_state.summary_pdf_bytes:
            st.download_button(
                label="📥 Download Summary PDF",
                data=st.session_state.summary_pdf_bytes,
                file_name=f"Scrape_Summary_{timestamp}.pdf",
                mime="application/pdf",
                use_container_width=True,
                on_click=lambda: st.session_state.update({'summary_pdf_bytes': None})
            )
        else:
            if st.button("📄 Generate Summary PDF", use_container_width=True):
                with st.spinner("Generating summary PDF..."):
                    from app.utils import generate_summary_pdf_report
                    pdf_bytes = asyncio.run(generate_summary_pdf_report(summary_data))
                    st.session_state.summary_pdf_bytes = pdf_bytes
                st.rerun()

    st.balloons()

@st.cache_data
def load_all_markets_data():
    """Loads and caches all market data from all company directories."""
    markets_data = {}
    for market_file in glob.glob(os.path.join(DATA_DIR, '*', 'markets.json')):
        with open(market_file, 'r') as f:
            try:
                markets_data.update(json.load(f))
            except json.JSONDecodeError:
                print(f"Warning: Could not load or parse {market_file}. Skipping.")
    return markets_data

@st.cache_data
def load_cache_data():
    """Loads and caches the shared theater_cache.json file."""
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

@st.cache_resource
def get_scraper_instance(dev_mode=False):
    """Initializes and caches the Scraper instance."""
    from app.scraper import Scraper
    # In dev mode, run with a visible browser and open DevTools for debugging.
    is_dev = dev_mode or st.session_state.get('dev_mode', False)
    return Scraper(headless=not is_dev, devtools=is_dev)

def main():
    if not login():
        return

    st.title(ui_config['main']['title'])
    theming.theme_selector_component() # <-- ADD THIS LINE
    
    # --- NEW: Use cached functions to load data ---
    markets_data = load_all_markets_data()
    cache_data = load_cache_data()
    if not cache_data:
        st.warning(f"Shared cache file (`{CACHE_FILE}`) not found. You can build it in Data Management mode.")

    initialize_session_state()

    # --- Setup Company, Paths, and DB ---
    if not setup_application(markets_data):
        return # Stop if setup fails (e.g., no company data)

    scout = get_scraper_instance()

    # --- Prepare shared data ---
    all_theaters_list = [t for market in cache_data.get("markets", {}).values() for t in market.get("theaters", [])]
    unique_theaters_by_name = {t['name']: t for t in all_theaters_list}
    all_theaters_list_unique = sorted(list(unique_theaters_by_name.values()), key=lambda x: x['name'])

    IS_DISABLED = st.session_state.report_running

    # --- Render Sidebar ---
    st.sidebar.title(ui_config['sidebar']['controls_title'])
    st.sidebar.image(os.path.join(SCRIPT_DIR, 'PriceScoutLogo.png'))
    if st.sidebar.button(ui_config['sidebar']['start_new_report_button'], use_container_width=True, disabled=IS_DISABLED):
        reset_session()
    st.sidebar.divider()
    render_sidebar_modes(IS_DISABLED, DEV_MODE_ENABLED)
    st.sidebar.divider()

    if DEV_MODE_ENABLED:
        st.sidebar.header(ui_config['sidebar']['developer_tools_header'])
        st.session_state.dev_mode = True
        scout.capture_html = st.sidebar.toggle("Capture HTML on Failure", help="Save HTML files for analysis.", disabled=IS_DISABLED)
        st.session_state.capture_html = st.sidebar.toggle(ui_config['sidebar']['capture_html_toggle'], help="Save HTML files for analysis.", disabled=IS_DISABLED)
        if st.sidebar.button(ui_config['sidebar']['run_diagnostic_button'], use_container_width=True, disabled=IS_DISABLED):
            st.session_state.run_diagnostic = True
            st.rerun()
        if st.sidebar.button(ui_config['sidebar']['delete_cache_button'], key="dev_delete_cache"):
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
                st.success("Theater cache removed.")
                st.rerun()
    else:
        st.session_state.dev_mode = False

    if st.session_state.get('run_diagnostic'):
        st.header(ui_config['diagnostic']['header'])
        st.warning(ui_config['diagnostic']['warning'])
        all_markets = []
        selected_company = st.session_state.selected_company
        if selected_company in markets_data:
            for director, markets in markets_data[selected_company].items():
                all_markets.extend(markets.keys())
        all_markets = sorted(list(set(all_markets)))

        if 'markets_to_test' not in st.session_state:
            st.session_state.markets_to_test = []

        st.write(ui_config['diagnostic']['select_markets_prompt'])
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
        if st.button(ui_config['diagnostic']['start_button'], type="primary", disabled=IS_DISABLED):
            st.session_state.report_running = True
            st.rerun()

    if st.session_state.report_running and st.session_state.get('run_diagnostic'):
        markets_to_test = st.session_state.get('markets_to_test', [])
        with st.spinner(ui_config['diagnostic']['spinner_text']):
            diag_date_str = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            thread, get_results = run_async_in_thread(scout.run_diagnostic_scrape, markets_to_test, diag_date_str)
            thread.join() # Wait for the thread to complete
            status, result, log, duration = get_results()
            st.session_state.last_run_log += log
            if status == 'success':
                st.success(ui_config['diagnostic']['success_message'].format(duration=duration))
                df_diag = pd.DataFrame(result)
                st.dataframe(df_diag)
            else:
                st.error(ui_config['diagnostic']['error_message'].format(duration=duration))
            st.session_state.report_running = False
            st.session_state.run_diagnostic = False
            st.rerun()
    _render_sidebar_footer()
    with st.expander(ui_config['scheduler']['expander_label']):
        st.write(ui_config['scheduler']['description'])
        
        all_markets = []
        if markets_data:
            for parent, regions in markets_data.items():
                for region, markets in regions.items():
                    all_markets.extend(markets.keys())
        all_markets = sorted(list(set(all_markets)))

        with st.form("scheduler_form", clear_on_submit=True):
            task_name = st.text_input(ui_config['scheduler']['task_name_label'])
            markets_to_schedule = st.multiselect(ui_config['scheduler']['select_markets_label'], options=all_markets)
            schedule_time = st.time_input(ui_config['scheduler']['time_label'], datetime.time(8, 0)) # Default to 8:00 UTC (3 AM CDT)
            notification_email = st.text_input(ui_config['scheduler']['email_label'])
            
            submitted = st.form_submit_button(ui_config['scheduler']['save_button'])

            if submitted:
                if not task_name or not markets_to_schedule:
                    st.error(ui_config['scheduler']['error_missing_fields'])
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
                    os.makedirs(config.SCHEDULED_TASKS_DIR, exist_ok=True)
                    filepath = os.path.join(config.SCHEDULED_TASKS_DIR, f"{sanitized_name}.json")
                    with open(filepath, 'w') as f:
                        json.dump(task_config, f, indent=4)
                    st.success(ui_config['scheduler']['success_message'].format(task_name=task_name))
                    st.toast(ui_config['scheduler']['toast_message'].format(filepath=filepath))
        
        st.divider()
        render_scheduled_tasks_list()
    st.divider()

    # --- Main Application Logic (State Machine) ---
    if st.session_state.get('confirm_scrape'):
        handle_scrape_confirmation()
    elif st.session_state.report_running and not st.session_state.get('run_diagnostic'):
        execute_scrape(scout)
    elif st.session_state.get('stage') == 'report_generated' and 'final_df' in st.session_state and not st.session_state.final_df.empty:
        render_report()
    else:
        # --- NEW: Clear markets_data from session state if not on the matching page ---
        if st.session_state.search_mode != "Theater Matching" and 'markets_data' in st.session_state:
            del st.session_state['markets_data']
        # Default state: render the UI for the selected mode
        render_main_content(scout, markets_data, cache_data, all_theaters_list_unique, IS_DISABLED)

    # --- Render Dev Log ---
    if st.session_state.dev_mode and "last_run_log" in st.session_state:
        with st.expander(ui_config['developer']['log_expander']):
            st.code(st.session_state.last_run_log, language='text')

if __name__ == "__main__":
    main()
