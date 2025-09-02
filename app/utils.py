import io
import os
import pandas as pd
import json
import datetime
import time
import asyncio
import traceback
import sys
import threading
import queue
from contextlib import redirect_stdout
import streamlit as st

from config import CACHE_FILE, REPORTS_DIR, RUNTIME_LOG_FILE, CACHE_EXPIRATION_DAYS
from scraper import Scraper

scout = Scraper()

def run_async_in_thread(target_func, *args, progress_queue=None, **kwargs):
    log_stream = io.StringIO()
    status, value, duration = 'error', None, 0.0
    
    if progress_queue:
        kwargs['progress_queue'] = progress_queue

    def thread_target():
        nonlocal status, value, duration
        start_time = time.time()
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        try:
            with redirect_stdout(log_stream):
                result = asyncio.run(target_func(*args, **kwargs))
            duration = time.time() - start_time
            status, value = 'success', result
        except Exception:
            duration = time.time() - start_time
            error_str = traceback.format_exc()
            print(f"\n--- TRACEBACK ---\n{error_str}", file=log_stream)
            status, value = 'error', error_str
        finally:
            if progress_queue:
                progress_queue.put(None)

    thread = threading.Thread(target=thread_target)
    thread.start()
    
    return thread, lambda: (status, value, log_stream.getvalue(), duration)

def format_price_change(change):
    """Formats the price change value for display."""
    if pd.isna(change):
        return "N/A"
    if change > 0:
        return f"+${change:.2f}"
    elif change < 0:
        return f"-${abs(change):.2f}"
    return "$0.00"

def style_price_change_v2(val):
    """Applies color styling for the price change column."""
    if isinstance(val, str):
        if val.startswith('+'):
            return 'color: red; font-weight: bold;' # Price increased
        elif val.startswith('-'):
            return 'color: green; font-weight: bold;' # Price decreased
    return ''

def check_cache_status():
    if not os.path.exists(CACHE_FILE):
        return "missing", None
    try:
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        last_updated_str = cache_data.get("metadata", {}).get("last_updated")
        if not last_updated_str:
            return "invalid", None
        last_updated = datetime.datetime.fromisoformat(last_updated_str)
        if (datetime.datetime.now() - last_updated).days >= CACHE_EXPIRATION_DAYS:
            return "stale", last_updated.strftime('%Y-%m-%d %H:%M')
        return "fresh", last_updated.strftime('%Y-%m-%d %H:%M')
    except (json.JSONDecodeError, KeyError):
        return "invalid", None

def get_report_path(mode, region=None, market=None):
    if mode == "Market Mode":
        path = os.path.join(REPORTS_DIR, "MarketMode", scout._sanitize_filename(region or ""), scout._sanitize_filename(market or ""))
    elif mode == "CompSnipe Mode":
        path = os.path.join(REPORTS_DIR, "SnipeMode")
    else:
        path = os.path.join(REPORTS_DIR, "misc")
    os.makedirs(path, exist_ok=True)
    return path

def log_runtime(mode, theater_count, showtime_count, duration):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    file_exists = os.path.isfile(RUNTIME_LOG_FILE)
    with open(RUNTIME_LOG_FILE, 'a', newline='') as f:
        writer = pd.DataFrame([{
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'mode': mode,
            'theater_count': theater_count,
            'showtime_count': showtime_count,
            'duration_seconds': round(duration, 2)
        }])
        writer.to_csv(f, header=not file_exists, index=False)

def clear_workflow_state():
    """Clears session state related to a report workflow, but preserves the mode."""
    keys_to_clear = [
        'stage', 'selected_region', 'selected_market', 'theaters',
        'selected_theaters', 'all_showings', 'selected_films',
        'selected_showtimes', 'confirm_scrape', 'compsnipe_theaters',
        'live_search_results', 'daypart_selections',
        'compsnipe_film_filter_mode', 'market_films_filter'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

def reset_session():
    """Resets the entire session state to its initial default."""
    st.session_state.search_mode = "Market Mode"
    keys_to_reset = [
        'stage', 'selected_region', 'selected_market', 'theaters',
        'selected_theaters', 'all_showings', 'selected_films',
        'selected_showtimes', 'confirm_scrape', 'compsnipe_theaters',
        'live_search_results', 'last_mode', 'run_diagnostic', 'last_run_duration',
        'daypart_selections', 'compsnipe_film_filter_mode', 'market_films_filter'
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    if 'final_df' in st.session_state:
        del st.session_state.final_df
    st.rerun()

def style_price_change(val):
    if isinstance(val, str):
        if val.startswith('-$'):
            return 'color: green; font-weight: bold;'
        elif val.startswith('$') and val != '$0.00':
            return 'color: red; font-weight: bold;'
    return ''

@st.cache_data
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='PriceScout_Report')
    processed_data = output.getvalue()
    return processed_data

@st.cache_data
def to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def get_error_message(traceback_str):
    """Extracts the last line of a traceback string."""
    if not traceback_str:
        return "No details available."
    lines = traceback_str.strip().split('\n')
    return lines[-1]