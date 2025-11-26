import datetime
import pandas as pd
from playwright.async_api import async_playwright
import asyncio
import threading
import os
import json
import re
import io
from typing import Any
from unittest.mock import MagicMock
import sqlite3
import copy
import streamlit as st

# Local application imports (ensure no leading indentation to avoid IndentationError)
from app import db_adapter as database
from app import security_config
from app import config

def run_async_in_thread(coro, *args, **kwargs):
    result: list[Any] = [None, None, None, None]  # status, value, log, duration

    def thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_time = datetime.datetime.now()
        log_capture = []

        class LogCapture:
            def write(self, s):
                log_capture.append(s)
            def flush(self):
                pass

        import sys
        original_stdout = sys.stdout
        sys.stdout = LogCapture()

        try:
            value = loop.run_until_complete(coro(*args, **kwargs))
            result[0] = 'success'
            result[1] = value
        except Exception as e:
            result[0] = 'error'
            result[1] = e
        finally:
            end_time = datetime.datetime.now()
            result[3] = (end_time - start_time).total_seconds()
            result[2] = "".join(log_capture)
            sys.stdout = original_stdout
            loop.close()

    thread = threading.Thread(target=thread_target)
    thread.start()

    def get_results():
        thread.join()
        return result

    return thread, get_results

def format_price_change(old_price, new_price):
    if old_price is None or new_price is None:
        return "N/A"
    
    old_val = float(old_price.replace('$', ''))
    new_val = float(new_price.replace('$', ''))
    
    if new_val > old_val:
        return f"▲{new_val - old_val:.2f}"
    elif new_val < old_val:
        return f"▼{old_val - new_val:.2f}"
    else:
        return "—"

def style_price_change_v2(val):
    if isinstance(val, str) and val.startswith('▲'):
        return 'color: green'
    elif isinstance(val, str) and val.startswith('▼'):
        return 'color: red'
    return ''

def check_cache_status():
    if not os.path.exists(config.CACHE_FILE):
        return "missing", None
    
    try:
        with open(config.CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        
        last_updated_str = cache_data.get("metadata", {}).get("last_updated")
        if not last_updated_str:
            return "stale", "Unknown (no timestamp)"
        
        last_updated = datetime.datetime.fromisoformat(last_updated_str)
        
        if (datetime.datetime.now() - last_updated).days >= config.CACHE_EXPIRATION_DAYS:
            return "stale", last_updated.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return "fresh", last_updated.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "stale", "Error reading cache"

def get_report_path(mode, timestamp):
    assert config.REPORTS_DIR is not None, "REPORTS_DIR is not configured"
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    return os.path.join(config.REPORTS_DIR, f"{mode}_Report_{timestamp}.xlsx")

def log_runtime(mode, num_theaters, num_showings, duration):
    assert config.REPORTS_DIR is not None, "REPORTS_DIR is not configured"
    assert config.RUNTIME_LOG_FILE is not None, "RUNTIME_LOG_FILE is not configured"
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    file_exists = os.path.exists(config.RUNTIME_LOG_FILE)
    with open(config.RUNTIME_LOG_FILE, 'a') as f:
        if not file_exists:
            f.write("timestamp,mode,num_theaters,num_showings,duration_seconds\n")
        f.write(f"{datetime.datetime.now().isoformat()},{mode},{num_theaters},{num_showings},{duration}\n")

def clear_workflow_state():
    # List of session state keys to clear for a new workflow
    keys_to_clear = [
        'selected_region', 'selected_market', 'selected_theaters', 'selected_films', 'selected_showtimes',
        'final_df', 'stage', 'report_running', 'run_diagnostic', 'markets_to_test', 'op_hours_processed_for_run',
        'compsnipe_theaters', 'zip_search_input', 'cs_date', 'market_date', 'daypart_selections',
        'op_hours_theaters', 'op_hours_selected_theaters', 'op_hours_selection',
        'op_hours_director', 'op_hours_results', 'all_showings', 'last_run_log'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

def reset_session():
    for key in st.session_state.keys():
        if key not in ['logged_in', 'user_name', 'is_admin', 'company', 'selected_company', 'search_mode', 'capture_html']:
            del st.session_state[key]
    st.rerun()

def style_price_change(val):
    if isinstance(val, str) and val.startswith('▲'):
        return 'background-color: #e6ffe6' # Light green
    elif isinstance(val, str) and val.startswith('▼'):
        return 'background-color: #ffe6e6' # Light red
    return ''

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data

def to_excel_multi_sheet(report_data: list[dict]) -> bytes:
    """
    Converts a list of report dictionaries into a single Excel file with multiple sheets.
    Each dictionary should contain 'theater_name' and 'report' (a DataFrame).
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for theater_report in report_data:
            df = theater_report['report']
            # Sanitize sheet name for Excel limitations (max 31 chars, no invalid chars)
            sheet_name = re.sub(r'[\[\]\*\/\\?\:]', '', theater_report['theater_name'])[:31]
            df.to_excel(writer, index=False, sheet_name=sheet_name)
    processed_data = output.getvalue()
    return processed_data

def to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def get_error_message(e):
    if isinstance(e, Exception):
        return str(e)
    return "An unknown error occurred."

def estimate_scrape_time(num_showings, mode_filter=None):
    assert config.RUNTIME_LOG_FILE is not None, "RUNTIME_LOG_FILE is not configured"
    if not os.path.exists(config.RUNTIME_LOG_FILE):
        return -1 # Indicate no historical data
    
    try:
        df_log = pd.read_csv(config.RUNTIME_LOG_FILE)
        # --- NEW: Filter by mode if specified ---
        if mode_filter and 'mode' in df_log.columns:
            df_log = df_log[df_log['mode'].str.contains(mode_filter, case=False, na=False)]        
        if df_log.empty:
            return -1
        
        # Filter out diagnostic runs as they are not representative of full scrapes
        df_log = df_log[df_log['mode'] != 'diagnostic']

        # Prevent division by zero if a log entry has 0 showings.
        df_log = df_log[df_log['num_showings'] > 0]

        if df_log.empty:
            return -1

        # Use only the last 20 valid runs to keep the estimate relevant
        df_log = df_log.tail(20)

        # Calculate average time per showing
        df_log['time_per_showing'] = df_log['duration_seconds'] / df_log['num_showings']
        avg_time_per_showing = df_log['time_per_showing'].mean()
        
        if pd.isna(avg_time_per_showing):
            return -1

        estimated_time = avg_time_per_showing * num_showings
        return estimated_time
    except Exception as e:
        # Sanitize exception details before printing
        sanitized_error = security_config.sanitize_log_data(str(e))
        print(f"Error estimating scrape time: {sanitized_error}")
        return -1

def format_time_to_human_readable(seconds: float) -> str:
    """Converts a duration in seconds to a human-readable string (e.g., '1h 15m 30s')."""
    if seconds < 0:
        return "N/A"
    
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {remaining_seconds}s"
    elif minutes > 0:
        return f"{minutes}m {remaining_seconds}s"
    else:
        return f"{remaining_seconds}s"

def is_run_allowed(market_timezone):
    # Get current time in the market's timezone
    from pytz import timezone
    import pytz
    
    try:
        market_tz = timezone(market_timezone)
        now_in_market = datetime.datetime.now(pytz.utc).astimezone(market_tz)
    except pytz.exceptions.UnknownTimeZoneError:
        # Fallback to a default if timezone is unknown
        market_tz = timezone("America/Chicago")
        now_in_market = datetime.datetime.now(pytz.utc).astimezone(market_tz)

    # Define the cutoff time (8 AM)
    cutoff_time = now_in_market.replace(hour=8, minute=0, second=0, microsecond=0)

    # If current time is past 8 AM, return False
    return now_in_market < cutoff_time

def normalize_time_string(time_str: str) -> str:
    """
    Normalizes a variety of time string formats into a standard format for parsing.
    e.g., '4:15p' -> '04:15PM', '10:30 AM' -> '10:30AM'
    """
    if not isinstance(time_str, str):
        return ""

    # General cleanup
    time_str = time_str.lower().strip().replace('.', '').replace(' ', '')

    # Handle single letter 'p' or 'a'
    if time_str.endswith('p'):
        time_str = time_str[:-1] + 'pm'
    elif time_str.endswith('a'):
        time_str = time_str[:-1] + 'am'

    # Add leading zero if needed (e.g., 4:15pm -> 04:15pm)
    match = re.match(r'^(\d):(\d{2}(?:am|pm))$', time_str)
    if match:
        time_str = f"0{match.group(1)}:{match.group(2)}"

    return time_str.upper()

def format_theater_name_for_display(name: str) -> str:
    # Remove "Theater" or "Theatre" if it's at the end of the string
    # Case-insensitive, and handles optional trailing punctuation/spaces
    cleaned_name = re.sub(r'\s+(Theater|Theatre)\s*$', '', name, flags=re.IGNORECASE)
    return cleaned_name.strip()

def clean_film_title(title: str) -> str:
    """
    [NEW] Centralized function to clean and normalize film titles for searching.
    - Handles 'Mystery Movie' patterns.
    - Removes punctuation that can break searches.
    - Strips common event-related tags (e.g., 'Re-release', 'Advanced Screening').
    """
    if not title:
        return ""

    # --- NEW: Remove year in parentheses (e.g., "My Film (2025)") ---
    # Remove year anywhere in the title, not just at the end
    cleaned_title = re.sub(r'\s*\(\d{4}\)', '', title).strip()

    # --- 1. Handle "Mystery Movie" variations first ---
    mystery_patterns = {
        "Mystery Movie": re.compile(r'^(amc )?mystery movie.*', re.IGNORECASE),
        "Secret Movie": re.compile(r'^secret movie.*', re.IGNORECASE),
        "Secret Screening": re.compile(r'^secret screening.*', re.IGNORECASE),
    }
    for canonical_name, pattern in mystery_patterns.items():
        if pattern.match(cleaned_title):
            return canonical_name

    # --- NEW: Remove a wider range of punctuation that can break searches ---
    # This pattern will remove common punctuation like apostrophes, colons, commas, etc.
    # e.g., "The Devil's Rejects" -> "The Devils Rejects", "Mission: Impossible" -> "Mission Impossible"
    punctuation_to_remove = r"[':,.!?&]"
    cleaned_title = re.sub(punctuation_to_remove, "", cleaned_title)

    # First, strip common suffixes like "40th Anniversary", "25th Anniversary", etc.
    # This must run BEFORE stripping just "anniversary" to avoid orphaning "40th"
    ordinal_anniversary = re.compile(r'\s+\d+(?:st|nd|rd|th)\s+anniversary\s*$', re.IGNORECASE)
    cleaned_title = ordinal_anniversary.sub('', cleaned_title)

    # Terms to remove (parenthetical, hyphenated, or trailing)
    event_terms = [
        'fathom events', 'fathom', 'anniversary', 're-release', 'rerelease',
        'special event', 'classic', 'big screen', 'ghibli fest', 'in concert',
        'live', 'directors cut', "director's cut", 'dubbed', 'subtitled',
        'advanced screening', 'early access', 'fan event', 'sneak peek'
    ]
    for term in event_terms:
        # Remove from parentheses: "Film (Re-release)" -> "Film"
        paren_pattern = re.compile(r'\s*\([^)]*' + re.escape(term) + r'[^)]*\)', re.IGNORECASE)
        cleaned_title = paren_pattern.sub('', cleaned_title)
        # Remove hyphenated at end: "Film - Anniversary" -> "Film"
        hyphen_pattern = re.compile(r'\s*-\s*' + re.escape(term) + r'\s*$', re.IGNORECASE)
        cleaned_title = hyphen_pattern.sub('', cleaned_title)
        # Remove trailing term: "Film Re-Release" -> "Film" (handles "Re-Release" as single word)
        trailing_pattern = re.compile(r'\s+' + re.escape(term).replace(r'\-', r'[-]?') + r'\s*$', re.IGNORECASE)
        cleaned_title = trailing_pattern.sub('', cleaned_title)

    return cleaned_title.strip(' -')

def _extract_company_name(name):
    """Extracts a company name from a theater name string."""
    name_lower = name.lower()
    # More comprehensive list of company names
    company_keywords = {
        "Marcus Theatres": ["marcus", "marcus theatres", "movie tavern", "wehrenberg"],
        "Cinemark Theatres": ["cinemark", "cinemark theatres", "rave", "century"],
        "AMC Theatres": ["amc", "amc theatres"],
        "Regal Cinemas": ["regal", "regal cinemas", "edwards", "ua"],
        "B&B Theatres": ["b&b theatres", "b&b"],
        "Studio Movie Grill": ["studio movie grill", "smg"],
        "Alamo Drafthouse": ["alamo drafthouse"],
        "Landmark Theatres": ["landmark"],
        "Classic Cinemas": ["classic cinemas"],
        "Emagine Entertainment": ["emagine"],
        "NCG Cinema": ["ncg"],
        "ACX Cinemas": ["acx"],
        "Flix Brewhouse": ["flix brewhouse"]
    }
    for company, keywords in company_keywords.items():
        if any(keyword in name_lower for keyword in keywords):
            return company
    return "Unknown"

def process_and_save_operating_hours(results_by_date, context, duration=None, silent=False):
    """
    Processes raw showtime data to calculate operating hours and saves them to the database.
    """
    # --- FIX: Ensure all theaters from the scrape are accounted for, even if they have no showings ---
    all_theaters_in_scrape = set()
    for date_str, theaters in results_by_date.items():
        all_theaters_in_scrape.update(theaters.keys())

    operating_hours_data = []
    for date_str, theaters in results_by_date.items():
        # Add entries for theaters that were scraped but had no showings on this date
        theaters_with_showings = set(theaters.keys())
        theaters_without_showings = all_theaters_in_scrape - theaters_with_showings
        for theater_name in theaters_without_showings:
            # Find the market for this theater from any other day's data if possible
            market = next((s[0].get('market', 'N/A') for d in results_by_date.values() for t, s in d.items() if t == theater_name and s), 'N/A')
            operating_hours_data.append({"Date": date_str, "Market": market, "Theater": theater_name, "Showtime Range": "No showtimes found", "Duration (hrs)": 0.0})

        # Process theaters that did have showings
        for theater_name, showings in theaters.items():
            if showings:  # This check prevents the error for theaters with no showtimes
                market = showings[0].get('market', 'N/A')
                all_times = [datetime.datetime.strptime(normalize_time_string(s['showtime']), "%I:%M%p") for s in showings if normalize_time_string(s['showtime'])]
                if all_times:
                    min_time = min(all_times)
                    max_time = max(all_times)
                    min_time_str = min_time.strftime("%I:%M %p")
                    max_time_str = max_time.strftime("%I:%M %p")
                    time_diff = max_time - min_time
                    hours_diff = time_diff.total_seconds() / 3600
                    showtime_range = f"{min_time_str} - {max_time_str}"
                else:
                    showtime_range = "No valid showtimes found"
                    hours_diff = 0.0
                operating_hours_data.append({
                    "Date": date_str,
                    "Market": market,
                    "Theater": theater_name,
                    "Showtime Range": showtime_range,
                    "Duration (hrs)": round(hours_diff, 1)
                })

    all_theaters = list(set(item['Theater'] for item in operating_hours_data))
    all_dates = list(set(datetime.datetime.strptime(item['Date'], '%Y-%m-%d').date() for item in operating_hours_data))

    # Delete old operating hours for these theaters and dates
    for date_obj in all_dates:
        database.delete_operating_hours(all_theaters, date_obj, None)
    
    # Save new operating hours using db_adapter
    database.save_operating_hours(None, operating_hours_data, None)

    if not silent:
        success_message = "Operating hours saved to database."
        if duration and not isinstance(duration, MagicMock):
            success_message += f" (Took {duration:.2f} seconds)"
        
        st.success(success_message)
        st.dataframe(pd.DataFrame(operating_hours_data), use_container_width=True)

def save_operating_hours_from_all_showings(all_showings, theaters_to_process, scrape_date, market, duration=None, silent=False):
    """
    Wrapper to prepare data from a general scrape and save operating hours.
    """
    date_str = scrape_date.strftime('%Y-%m-%d')
    # The 'all_showings' passed here is for a single day's worth of data.
    # The market data is now added in ui_components.py, so we just need to pass it along.
    results_by_date = {date_str: all_showings}
    
    theater_names_str_list = [t['name'] if isinstance(t, dict) else t for t in theaters_to_process]
    context = f"Operating hours from Market/CompSnipe run. Market/ZIP: {market}, Theaters: {', '.join(theater_names_str_list)}"
    
    process_and_save_operating_hours(results_by_date, context, duration=duration, silent=silent)

def showtime_selection_to_dataframe(selected_showtimes: dict) -> pd.DataFrame:
    """Converts the nested selected_showtimes dictionary into a flat DataFrame."""
    rows = []
    # Structure is {'date': {'theater': {'film': {'showtime': [showings]}}}}
    for date_str, daily_selections in selected_showtimes.items():
        for theater_name, theater_selections in daily_selections.items():
            for film_title, film_selections in theater_selections.items():
                for time_str, showings_at_time in film_selections.items():
                    for showing in showings_at_time:
                        rows.append({
                            "Date": date_str,
                            "Theater Name": theater_name,
                            "Film Title": film_title,
                            "Showtime": time_str,
                            "Format": showing.get('format', 'N/A'),
                            "Daypart": showing.get('daypart', 'N/A'),
                            "Ticket URL": showing.get('ticket_url', 'N/A')
                        })
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    # Ensure consistent column order
    return df[["Date", "Theater Name", "Film Title", "Showtime", "Format", "Daypart", "Ticket URL"]]
def generate_selection_analysis_report(selected_showtimes: dict) -> pd.DataFrame:
    """
    Processes the selected_showtimes dictionary into a summarized, pivoted analysis DataFrame.
    """
    if not selected_showtimes:
        return pd.DataFrame()

    report_rows = []
    # Structure is {'date': {'theater': {'film': {'showtime': [showings]}}}}
    for date_str, daily_selections in selected_showtimes.items():
        for theater_name, theater_selections in daily_selections.items():
            for film_title, film_selections in theater_selections.items():
                if not film_selections:
                    continue

                report_rows.append({
                    "Date": date_str,
                    "Theater Name": theater_name,
                    "Film Title": film_title,
                    "Number of Selected Showings": len(film_selections),
                })

    if not report_rows:
        return pd.DataFrame()

    long_df = pd.DataFrame(report_rows)
    
    # Create the pivot table
    pivot_df = long_df.pivot_table(
        index=['Date', 'Theater Name'],
        columns='Film Title',
        values='Number of Selected Showings',
        fill_value=0
    )

    # Add a total column for all showings at that theater for that day
    pivot_df['Total Showings Per Day'] = pivot_df.sum(axis=1)

    # Reset index to make 'Date' and 'Theater Name' regular columns
    pivot_df = pivot_df.reset_index()

    return pivot_df

def _categorize_formats(format_str: str, plf_formats: set) -> tuple[list[str], list[str]]:
    """
    Splits a format string into premium formats and general amenities.
    Premium formats are defined as 3D, D-BOX, or anything in the PLF list.
    """
    if not format_str:
        return [], []
    
    all_formats = {part.strip() for part in format_str.split(',')}
    
    # Define what constitutes a "premium" format for display purposes
    premium_keywords = {'3d', 'd-box'}.union(plf_formats)
    
    premium = sorted([f for f in all_formats if f.lower() in premium_keywords])
    general = sorted([f for f in all_formats if f.lower() not in premium_keywords and f.lower() != '2d'])
    return premium, general

def generate_human_readable_summary(df: pd.DataFrame):
    """
    Processes a raw scrape DataFrame into a nested dictionary for a human-readable summary.
    """
    if df.empty:
        return {}

    summary = {}
    df_copy = df.copy()
    
    # Ensure 'play_date' exists and is not null
    if 'play_date' not in df_copy.columns or df_copy['play_date'].isnull().all():
        return {}

    # --- NEW: Add Market column if it doesn't exist, for backward compatibility ---
    if 'Market' not in df_copy.columns:
        df_copy['Market'] = 'Unknown Market'

    # Convert price to numeric for calculations
    df_copy['price_numeric'] = df_copy['Price'].astype(str).str.replace('$', '', regex=False).astype(float)

    # --- NEW: Pre-fetch all film details to avoid querying in a loop ---
    all_film_titles_in_df = df_copy['Film Title'].unique()
    film_details_map = {}
    for title in all_film_titles_in_df:
        details = database.get_film_details(title)
        if details:
            # --- NEW: Load PLF formats from ticket_types.json ---
            try:
                with open(os.path.join(os.path.dirname(__file__), 'ticket_types.json'), 'r') as f:
                    plf_formats = set(json.load(f).get('plf_formats', []))
            except (FileNotFoundError, json.JSONDecodeError):
                plf_formats = set()
            film_details_map[title] = details

    # Group by date, then market, then theater, then film
    grouped = df_copy.groupby(['play_date', 'Market', 'Theater Name', 'Film Title'])

    for (play_date, market_name, theater_name, film_title), group in grouped:
        if play_date not in summary:
            summary[play_date] = {}
        if market_name not in summary[play_date]:
            summary[play_date][market_name] = {}
        if theater_name not in summary[play_date][market_name]:
            summary[play_date][market_name][theater_name] = []

        # --- Calculate film-level stats ---
        try:
            unique_showtimes = sorted(group['Showtime'].unique(), key=lambda x: datetime.datetime.strptime(normalize_time_string(x), "%I:%M%p").time())
        except (ValueError, TypeError):
            unique_showtimes = sorted(group['Showtime'].unique())

        all_film_amenities = set()
        showtime_strings = []
        for showtime in unique_showtimes:
            # Find all formats for this specific showtime
            formats_for_time = group[group['Showtime'] == showtime]['Format'].unique()
            
            premium_formats, general_amenities = _categorize_formats(",".join(formats_for_time), plf_formats)
            all_film_amenities.update(general_amenities)

            format_str = f" ({', '.join(premium_formats)})" if premium_formats else ""
            showtime_strings.append(f"{showtime}{format_str}") # Only show premium formats by the time

        # --- Detailed price breakdown including formats/amenities ---
        price_breakdown_parts = []
        # Group by Ticket Type and Format to get specific price points
        for (ticket_type, format_str, daypart), price_group in group.groupby(['Ticket Type', 'Format', 'Daypart']):
            prices = sorted(price_group['price_numeric'].unique())
            price_str = ", ".join([f"${p:.2f}" for p in prices])
            
            premium_formats, general_amenities = _categorize_formats(format_str, plf_formats)
            all_film_amenities.update(general_amenities)

            # Build the label with ticket type and premium formats, then add the daypart
            base_label = f"{ticket_type} ({', '.join(premium_formats)})" if premium_formats else ticket_type
            label = f"{base_label} ({daypart})"
            price_breakdown_parts.append(f"{label}: {price_str}")
        price_breakdown_str = " | ".join(sorted(price_breakdown_parts))
        
        details = film_details_map.get(film_title, {})

        film_summary = {
            'film_title': film_title,
            'num_showings': len(unique_showtimes),
            'poster_url': details.get('poster_url'),
            'rating': details.get('mpaa_rating'),
            'runtime': details.get('runtime'),
            'showtimes': showtime_strings,
            'price_breakdown_str': price_breakdown_str,
            'general_amenities': sorted(list(all_film_amenities))
        }
        summary[play_date][market_name][theater_name].append(film_summary)
        
    return summary

def generate_human_readable_summary_by_film(df: pd.DataFrame):
    """
    [NEW] Processes a raw scrape DataFrame into a nested dictionary grouped by film for a human-readable summary.
    Structure: Date -> Market -> Film -> Theater -> Details
    """
    if df.empty:
        return {}

    summary = {}
    df_copy = df.copy()
    
    if 'play_date' not in df_copy.columns or df_copy['play_date'].isnull().all():
        return {}

    if 'Market' not in df_copy.columns:
        df_copy['Market'] = 'Unknown Market'

    df_copy['price_numeric'] = df_copy['Price'].astype(str).str.replace('$', '', regex=False).astype(float)

    all_film_titles_in_df = df_copy['Film Title'].unique()
    film_details_map = {}
    for title in all_film_titles_in_df:
        details = database.get_film_details(title)
        if details:
            # --- NEW: Load PLF formats from ticket_types.json ---
            try:
                with open(os.path.join(os.path.dirname(__file__), 'ticket_types.json'), 'r') as f:
                    plf_formats = set(json.load(f).get('plf_formats', []))
            except (FileNotFoundError, json.JSONDecodeError):
                plf_formats = set()
            film_details_map[title] = details

    # Group by date, then market, then film, then theater
    grouped = df_copy.groupby(['play_date', 'Market', 'Film Title', 'Theater Name'])

    for (play_date, market_name, film_title, theater_name), group in grouped:
        date_level = summary.setdefault(play_date, {})
        market_level = date_level.setdefault(market_name, {})
        film_level = market_level.setdefault(film_title, {
            'film_details': film_details_map.get(film_title, {}),
            'theaters': []
        })

        try:
            unique_showtimes = sorted(group['Showtime'].unique(), key=lambda x: datetime.datetime.strptime(normalize_time_string(x), "%I:%M%p").time())
        except (ValueError, TypeError):
            unique_showtimes = sorted(group['Showtime'].unique())

        showtime_strings = []
        for showtime in unique_showtimes:
            formats_for_time = group[group['Showtime'] == showtime]['Format'].unique()
            
            premium_formats, _ = _categorize_formats(",".join(formats_for_time), plf_formats)
            format_str = f" ({', '.join(premium_formats)})" if premium_formats else ""
            showtime_strings.append(f"{showtime}{format_str}")

        price_breakdown_parts = []
        for (ticket_type, format_str, daypart), price_group in group.groupby(['Ticket Type', 'Format', 'Daypart']):
            prices = sorted(price_group['price_numeric'].unique())
            price_str = ", ".join([f"${p:.2f}" for p in prices])

            premium_formats, _ = _categorize_formats(format_str, plf_formats)
            
            # Build the label with ticket type and premium formats, then add the daypart
            base_label = f"{ticket_type} ({', '.join(premium_formats)})" if premium_formats else ticket_type
            label = f"{base_label} ({daypart})"
            price_breakdown_parts.append(f"{label}: {price_str}")
        price_breakdown_str = " | ".join(sorted(price_breakdown_parts))

        theater_summary = {
            'theater_name': theater_name,
            'showtimes': showtime_strings,
            'price_breakdown_str': price_breakdown_str
        }
        film_level['theaters'].append(theater_summary)
        
    return summary

async def generate_summary_pdf_report(summary_data: dict) -> bytes:
    """Generates a PDF document of the scrape summary using Playwright."""
    
    # --- HTML Generation ---
    html = """
    <html>
    <head>
        <title>Scrape Summary Report</title>
        <style>
            body { font-family: Helvetica, Arial, sans-serif; margin: 20px; background-color: #f0f2f6; color: #31333F; }
            h1, h2, h3, h4 { color: #0e1117; page-break-after: avoid; }
            h2 { border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-bottom: 10px; }
            h3 { background-color: #f7f7f7; padding: 8px; border-radius: 6px; margin-bottom: 10px; }
            
            .date-section { page-break-before: always; }
            .date-section:first-of-type { page-break-before: auto; }
            .theater-section { 
                background-color: white; 
                border: 1px solid #ddd;
                border-radius: 12px; 
                padding: 15px; 
                margin-bottom: 20px; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                page-break-inside: avoid;
            }
            .film-grid { display: grid; grid-template-columns: 150px auto; gap: 20px; border-top: 1px solid #eee; padding-top: 15px; margin-top: 15px; }
            .poster { width: 150px; }
            .poster img { max-width: 100%; border-radius: 8px; }
            .film-details { font-size: 0.9em; }
            .film-details h4 { margin-top: 0; margin-bottom: 5px; }
            .film-details p { margin: 4px 0; }
            .film-details .caption { font-size: 0.8em; color: #666; }
        </style>
    </head>
    <body>
        <h1>Scrape Summary</h1>
    """

    if not summary_data:
        html += "<p>No data to summarize.</p>"
    else:
        sorted_dates = sorted(summary_data.keys())
        for play_date in sorted_dates:
            try:
                date_obj = datetime.datetime.strptime(play_date, '%Y-%m-%d').date()
                html += f"<div class='date-section'><h2>🗓️ {date_obj.strftime('%A, %B %d, %Y')}</h2>"
            except (ValueError, TypeError):
                html += f"<div class='date-section'><h2>🗓️ {play_date}</h2>"

            markets_data_for_date = summary_data[play_date]
            for market_name, theaters_data in sorted(markets_data_for_date.items()):
                html += f"<h3>Market: {market_name}</h3>"
                for theater_name, films_list in sorted(theaters_data.items()):
                    html += f"<div class='theater-section'><h4>{theater_name}</h4>"
                    
                    for film_summary in sorted(films_list, key=lambda x: x['film_title']):
                        html += "<div class='film-grid'>"
                        # Poster column
                        html += "<div class='poster'>"
                        if film_summary.get('poster_url') and film_summary['poster_url'] != 'N/A':
                            html += f"<img src='{film_summary['poster_url']}' alt='{film_summary['film_title']} poster'>"
                        html += "</div>"
                        
                        # Details column
                        html += "<div class='film-details'>"
                        html += f"<h5>{film_summary['film_title']}</h5>"
                        
                        detail_parts = []
                        if film_summary.get('rating') and film_summary['rating'] != 'N/A':
                            detail_parts.append(f"Rated {film_summary['rating']}")
                        if film_summary.get('runtime') and film_summary['runtime'] != 'N/A':
                            detail_parts.append(film_summary['runtime'])
                        html += f"<p class='caption'>{' | '.join(detail_parts)}</p>"
                        
                        html += f"<p><strong>Showtimes:</strong> {', '.join(film_summary.get('showtimes', []))}</p>"
                        html += f"<p><strong>Ticket Prices & Amenities:</strong></p>"
                        price_breakdown_str = film_summary.get('price_breakdown_str')
                        if price_breakdown_str:
                            html += f"<p class='caption'>{price_breakdown_str}</p>"
                        else:
                            html += f"<p class='caption'>No price information available.</p>"
                        
                        html += "</div>" # close film-details
                        html += "</div>" # close film-grid
                    
                    html += "</div>" # close theater-section
            
            html += "</div>" # close date-section

    html += "</body></html>"
    html_content = html

    # --- PDF Generation ---
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.set_content(html_content, wait_until="networkidle")
            pdf_bytes = await page.pdf(format='Letter', print_background=True, margin={'top': '20px', 'bottom': '20px', 'left': '20px', 'right': '20px'})
        finally:
            await browser.close()
            
    return pdf_bytes


def generate_showtime_html_report(all_showings, selected_films, theaters, scrape_date_range, cache_data, context_title=None):
    """Generates a static HTML file that visually represents the showtime selection UI."""
    
    # --- NEW: Group theaters by market ---
    theater_to_market_map = {}
    if cache_data:
        for market_name, market_info in cache_data.get("markets", {}).items():
            for theater in market_info.get("theaters", []):
                theater_to_market_map[theater['name']] = market_name

    theaters_by_market = {}
    for theater in theaters:
        market_name = theater_to_market_map.get(theater['name'], "Uncategorized")
        if market_name not in theaters_by_market:
            theaters_by_market[market_name] = []
        theaters_by_market[market_name].append(theater)

    # Basic CSS for styling to mimic the Streamlit app's look
    html = """
    <html>
    <head>
        <title>Showtime Selection Report</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"; margin: 20px; background-color: #f0f2f6; color: #31333F; }
            h1 { font-size: 1.8em; margin-bottom: 15px; }
            h2, h3, h4 {
                color: #0e1117; 
                page-break-after: avoid; /* Avoids a break right after a heading */
            }
            .report-body { margin-top: 20px; }
            .market-section { 
                border: 2px solid #8b0e04; 
                border-radius: 15px; padding: 15px; 
                margin-bottom: 20px; 
                background-color: #fff8f8; 
            }
            .date-section {
                margin-bottom: 25px;
                /* page-break-before is now handled manually in the loop */
            }
            .theater-section:last-of-type {
                margin-bottom: 0; /* Removes extra space at the end of a market/date group */
            }
            .theater-section { 
                background-color: white; 
                border: 1px solid #e0e0e0; 
                border-radius: 12px; 
                padding: 15px; 
                margin-bottom: 15px; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                page-break-inside: avoid; /* Tries to keep a theater block on one page */
            }
            .film-section { margin-top: 15px; border-top: 1px solid #eee; padding-top: 15px; page-break-inside: avoid; }
            .film-section:first-child { border-top: none; padding-top: 0; margin-top: 0; }
            .film-title { font-weight: bold; font-size: 1.1em; margin-bottom: 10px; display: block; }
            .showtime-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; }
            .showtime-btn { 
                padding: 6px; 
                border: 1px solid #ccc; 
                border-radius: 8px; 
                text-align: center; 
                background-color: #f8f9fa;
                font-size: 0.8em;
            }
        </style>
    </head>
    <body>
    """

    if context_title:
        html += f"<h1>Showtime Selection Report for {context_title}</h1>"
    else:
        html += "<h1>Showtime Selection Report</h1>"

    html += "<div class='report-body'>"

    # --- NEW: Re-architected loop for correct page breaks (Date -> Market -> Theater) ---
    start_date, end_date = scrape_date_range
    is_first_date_with_content = True # Flag to manage page breaks

    for date in pd.date_range(start_date, end_date):
        date_str = date.strftime('%Y-%m-%d')
        daily_showings = all_showings.get(date_str, {})

        # Check if there are any showings on this date across all relevant markets before creating a date section
        has_any_showings_on_date = any(
            daily_showings.get(t['name']) 
            for market_group in theaters_by_market.values() 
            for t in market_group
        )
        if not has_any_showings_on_date:
            continue # Skip this date entirely if no showings exist
        
        # If this is not the first date that has content, add a page break before it.
        if not is_first_date_with_content:
            html += '<div style="page-break-before: always;"></div>'
        
        html += f"<div class='date-section'><h2>🗓️ {date.strftime('%A, %B %d, %Y')}</h2>"

        for market_name, theaters_in_market in sorted(theaters_by_market.items()):
            # Check if this specific market has showings on this date before creating a market section
            has_showings_in_market_on_date = any(
                daily_showings.get(t['name']) for t in theaters_in_market
            )
            if not has_showings_in_market_on_date:
                continue

            if len(theaters_by_market) > 1:
                html += f"<div class='market-section'><h3>Market: {market_name}</h3>"

            for theater in theaters_in_market:
                theater_name = theater['name']
                showings_for_theater = daily_showings.get(theater_name, [])
                if not showings_for_theater:
                    continue # Skip this theater if it has no showings on this date

                time_range_str = ""
                all_times = [datetime.datetime.strptime(normalize_time_string(s['showtime']), "%I:%M%p") for s in showings_for_theater if normalize_time_string(s['showtime'])]
                if all_times:
                    min_time, max_time = min(all_times), max(all_times)
                    time_range_str = f" | {min_time.strftime('%I:%M %p')} - {max_time.strftime('%I:%M %p')} ({(max_time - min_time).total_seconds() / 3600:.1f} hrs)"
                
                html += f"<div class='theater-section'><h4>{theater_name}{time_range_str}</h4>"
                
                films_to_display = sorted([f for f in selected_films if f in {s['film_title'] for s in showings_for_theater}])
                
                if not films_to_display:
                    html += "<p>No selected films are showing at this theater for this date.</p>"
                
                for film in films_to_display:
                    film_showings = sorted([s for s in showings_for_theater if s['film_title'] == film], key=lambda x: datetime.datetime.strptime(normalize_time_string(x['showtime']), "%I:%M%p").time())

                    showings_by_time = {}
                    for s in film_showings:
                        showings_by_time.setdefault(s['showtime'], []).append(s)

                    showtime_count = len(showings_by_time)
                    showings_plural = 's' if showtime_count != 1 else ''

                    html += f"<div class='film-section'><span class='film-title'>{film} ({showtime_count} showing{showings_plural})</span><div class='showtime-grid'>"
                    
                    for time_str, showings_at_time in showings_by_time.items():
                        formats = sorted(list(set(s.get('format', '2D') for s in showings_at_time if s.get('format') != '2D')))
                        label = f"{time_str} ({', '.join(formats)})" if formats else time_str
                        html += f"<div class='showtime-btn'>{label}</div>"
                    
                    html += "</div></div>"
                
                html += "</div>" # close theater-section

            if len(theaters_by_market) > 1:
                html += "</div>" # Close market-section div
        
        html += "</div>" # Close date-section div

        # After processing the first valid date, set the flag to false.
        is_first_date_with_content = False

    html += "</div>" # Close report-body
    html += "</body></html>"
    return html.encode('utf-8')

async def generate_showtime_pdf_report(all_showings, selected_films, theaters, scrape_date_range, cache_data, context_title=None):
    """Generates a PDF document of the showtime selection UI using Playwright."""
    html_bytes = generate_showtime_html_report(all_showings, selected_films, theaters, scrape_date_range, cache_data, context_title)
    html_content = html_bytes.decode('utf-8')

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            # Load the generated HTML content into the page
            await page.set_content(html_content, wait_until="networkidle")
            
            # Generate a PDF of the page
            pdf_bytes = await page.pdf(format='Letter', print_background=True, margin={'top': '20px', 'bottom': '20px', 'left': '20px', 'right': '20px'})
        finally:
            # Ensure the browser is always closed
            await browser.close()
            
    return pdf_bytes