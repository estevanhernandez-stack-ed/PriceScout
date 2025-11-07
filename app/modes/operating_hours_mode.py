import streamlit as st
import datetime
import pandas as pd
from app.utils import run_async_in_thread, is_run_allowed, get_error_message, format_theater_name_for_display, estimate_scrape_time, normalize_time_string, to_excel, to_excel_multi_sheet, _extract_company_name, format_time_to_human_readable
from app import database
import json
import os
from app.config import SCRIPT_DIR, DATA_DIR

def highlight_changes(row):
    if row.Changed in ['🔄 Changed', '✨ New']:
        return ['background-color: #0277bd; color: white'] * len(row)  # Medium Blue
    elif row.Changed == '✅ No Change':
        return ['background-color: #2e7d32; color: white'] * len(row)  # Medium Green
    return [''] * len(row)

def load_ui_config():
    with open(os.path.join(SCRIPT_DIR, 'ui_config.json'), 'r', encoding='utf-8') as f:
        return json.load(f)
ui_config = load_ui_config()

def _generate_op_hours_summary_by_film(all_current_results: dict) -> dict:
    """
    Processes raw showtime data into a nested dictionary grouped by film for an operating hours summary.
    Structure: Date -> Film -> [Theater Summary]
    """
    summary = {}
    if not all_current_results:
        return summary

    # Pre-fetch all film details to avoid querying in a loop
    all_film_titles = set(s['film_title'] for daily_results in all_current_results.values() for showings_list in daily_results.values() for s in showings_list)
    film_details_map = {title: database.get_film_details(title) for title in all_film_titles}

    for date_str, daily_results in all_current_results.items():
        summary[date_str] = {}
        films_on_date = {}
        # First, group all showings by film title
        for theater_name, showings_list in daily_results.items():
            for showing in showings_list:
                film_title = showing['film_title']
                if film_title not in films_on_date:
                    films_on_date[film_title] = []
                films_on_date[film_title].append({**showing, 'theater_name': theater_name})

        # Now, process each film
        for film_title, all_showings_for_film in films_on_date.items():
            theaters_playing_film = {}
            for showing in all_showings_for_film:
                theater_name = showing['theater_name']
                if theater_name not in theaters_playing_film:
                    theaters_playing_film[theater_name] = []
                theaters_playing_film[theater_name].append(showing)

            theater_summaries = []
            for theater_name, theater_showings in theaters_playing_film.items():
                all_times = [datetime.datetime.strptime(normalize_time_string(s['showtime']), "%I:%M%p") for s in theater_showings if normalize_time_string(s['showtime'])]
                if all_times:
                    # --- NEW: Count unique showtimes for this theater ---
                    showtimes = sorted(list(set(s['showtime'] for s in theater_showings)), key=lambda x: datetime.datetime.strptime(normalize_time_string(x), "%I:%M%p").time())
                    num_showings = len(showtimes)
                    theater_summaries.append({'theater_name': theater_name, 'showtimes': showtimes, 'num_showings': num_showings})

            summary[date_str][film_title] = {
                'film_details': film_details_map.get(film_title, {}),
                'theaters': sorted(theater_summaries, key=lambda x: x['theater_name'])
            }
    return summary

def _generate_op_hours_summary_by_theater(all_current_results: dict) -> dict:
    """
    [NEW] Processes raw showtime data into a nested dictionary grouped by theater for a summary.
    Structure: Date -> Theater -> [Film Summary]
    """
    summary = {}
    if not all_current_results:
        return summary

    all_film_titles = set(s['film_title'] for daily_results in all_current_results.values() for showings_list in daily_results.values() for s in showings_list)
    film_details_map = {title: database.get_film_details(title) for title in all_film_titles}

    for date_str, daily_results in all_current_results.items():
        summary[date_str] = {}
        theaters_on_date = {}
        for theater_name, showings_list in daily_results.items():
            if theater_name not in theaters_on_date:
                theaters_on_date[theater_name] = {}
            for showing in showings_list:
                film_title = showing['film_title']
                if film_title not in theaters_on_date[theater_name]:
                    theaters_on_date[theater_name][film_title] = []
                theaters_on_date[theater_name][film_title].append(showing)

        for theater_name, films_at_theater in theaters_on_date.items():
            film_summaries = []
            for film_title, film_showings in films_at_theater.items():
                all_times = [datetime.datetime.strptime(normalize_time_string(s['showtime']), "%I:%M%p") for s in film_showings if normalize_time_string(s['showtime'])]
                if all_times:
                    num_showings = len(set(s['showtime'] for s in film_showings))
                    film_summaries.append({
                        'film_title': film_title,
                        'film_details': film_details_map.get(film_title, {}),
                        'num_showings': num_showings,
                        'showtimes': sorted([s['showtime'] for s in film_showings], key=lambda x: datetime.datetime.strptime(normalize_time_string(x), "%I:%M%p").time())
                    })
            
            summary[date_str][theater_name] = sorted(film_summaries, key=lambda x: x['film_title'])
    return summary

def generate_weekly_report_data(scout, cache_data, all_theaters, selected_company):
    """Core, non-UI logic to generate a single DataFrame for the weekly op hours report."""
    from app.utils import process_and_save_operating_hours
    
    try:
        theater_to_market_map = {}
        for market_name, market_info in cache_data.get("markets", {}).items():
            for theater in market_info.get("theaters", []):
                theater_to_market_map[theater['name']] = market_name

        today = datetime.date.today()
        days_until_thursday = (3 - today.weekday() + 7) % 7
        this_thursday = today + datetime.timedelta(days=days_until_thursday)
        next_thursday = this_thursday + datetime.timedelta(days=7)
        scrape_date_range = pd.date_range(this_thursday, next_thursday, inclusive='left')
        previous_thursday = this_thursday - datetime.timedelta(days=7)
        end_of_previous_week = next_thursday - datetime.timedelta(days=7)

        all_current_results = {}
        for date in scrape_date_range:
            date_str = date.strftime('%Y-%m-%d')
            thread, result_func = run_async_in_thread(scout.get_all_showings_for_theaters, all_theaters, date_str)
            thread.join()
            status, result, _, _ = result_func()
            if status == 'success' and result:
                all_current_results[date_str] = result
        
        for date_str, theaters in all_current_results.items():
            for theater_name, showings in theaters.items():
                market = theater_to_market_map.get(theater_name, 'Unknown')
                for showing in showings:
                    showing['market'] = market

        current_week_data = []
        for date_str, theaters in all_current_results.items():
            for theater_name, showings in theaters.items():
                if not showings:
                    current_week_data.append({"scrape_date": date_str, "theater_name": theater_name, "open_time": "N/A", "close_time": "N/A", "duration_hours": 0.0})
                    continue
                
                all_times = []
                for s in showings:
                    normalized_time = normalize_time_string(s['showtime'])
                    if normalized_time:
                        try:
                            all_times.append(datetime.datetime.strptime(normalized_time, "%I:%M%p"))
                        except ValueError:
                            st.warning(f"Could not parse time '{s['showtime']}' for {theater_name} on {date_str}")
                
                if all_times:
                    min_time = min(all_times)
                    max_time = max(all_times)
                    min_time_str = min_time.strftime("%I:%M %p")
                    max_time_str = max_time.strftime("%I:%M %p")
                    duration_hours = round((max_time - min_time).total_seconds() / 3600, 1)
                    current_week_data.append({"scrape_date": date_str, "theater_name": theater_name, "open_time": min_time_str, "close_time": max_time_str, "duration_hours": duration_hours})
                else:
                    current_week_data.append({"scrape_date": date_str, "theater_name": theater_name, "open_time": "N/A", "close_time": "N/A", "duration_hours": 0.0})

        current_week_df = pd.DataFrame(current_week_data)

        if current_week_df.empty:
            st.warning("Failed to scrape any data for the current week's operating hours report.")
            return pd.DataFrame(), {}

        previous_week_df = database.get_operating_hours_for_theaters_and_dates([t['name'] for t in all_theaters], previous_thursday, end_of_previous_week)

        current_week_df['scrape_date'] = pd.to_datetime(current_week_df['scrape_date'])
        current_week_df['Day'] = current_week_df['scrape_date'].dt.day_name()

        # --- FIX: Handle cases where open/close times are missing (no showtimes) ---
        current_week_df['Current Week Hours'] = current_week_df.apply(
            lambda row: f"{row['open_time']} - {row['close_time']}" if pd.notna(row['open_time']) and row['open_time'] != 'N/A' else "No Showings Found",
            axis=1
        )
        current_week_df['Current Week Duration'] = current_week_df['duration_hours'].apply(lambda x: f"{x:.1f} hrs" if x > 0 else "")

        prev_lookup = {}
        if not previous_week_df.empty:
            previous_week_df['scrape_date'] = pd.to_datetime(previous_week_df['scrape_date'])
            previous_week_df['comparison_date'] = previous_week_df['scrape_date'] + datetime.timedelta(days=7)
            previous_week_df['Previous Week Hours'] = previous_week_df.apply(
                lambda row: f"{row['open_time']} - {row['close_time']}" if pd.notna(row['open_time']) and row['open_time'] != 'N/A' else "No Showings Found",
                axis=1
            )
            # --- NEW: Calculate duration for previous week ---
            def calculate_duration(row):
                if pd.notna(row['open_time']) and row['open_time'] != 'N/A' and pd.notna(row['close_time']) and row['close_time'] != 'N/A':
                    open_t = datetime.datetime.strptime(row['open_time'], "%I:%M %p")
                    close_t = datetime.datetime.strptime(row['close_time'], "%I:%M %p")
                    return round((close_t - open_t).total_seconds() / 3600, 1)
                return 0.0
            previous_week_df['Previous Week Duration'] = previous_week_df.apply(calculate_duration, axis=1).apply(lambda x: f"{x:.1f} hrs" if x > 0 else "")
            prev_lookup = {(row['theater_name'], row['comparison_date']): (row['Previous Week Hours'], row['scrape_date'].strftime('%a, %b %d'), row['Previous Week Duration']) for _, row in previous_week_df.iterrows()}

        current_week_df[['Previous Week Hours', 'Previous Week Date', 'Previous Week Duration']] = current_week_df.apply(lambda row: pd.Series(prev_lookup.get((row['theater_name'], row['scrape_date']), ('N/A', 'N/A', ''))), axis=1)
        current_week_df['Changed'] = current_week_df.apply(lambda row: '🔄 Changed' if row['Previous Week Hours'] != 'N/A' and row['Current Week Hours'] != row['Previous Week Hours'] else ('✨ New' if row['Previous Week Hours'] == 'N/A' else '✅ No Change'), axis=1)

        current_week_df['Current Week Date'] = current_week_df['scrape_date'].dt.strftime('%a, %b %d')

        days_order = ['Thursday', 'Friday', 'Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday']
        
        agg_funcs = {
            'Day': lambda days: ', '.join(sorted(set(days), key=lambda day: days_order.index(day))),
            'scrape_date': 'min', # Keep for sorting
            'Current Week Date': 'first', # Keep one example date
            'Previous Week Date': 'first' # Keep one example date
        }

        consolidated_df = current_week_df.groupby(['theater_name', 'Current Week Hours', 'Previous Week Hours', 'Changed', 'Current Week Duration', 'Previous Week Duration']).agg(agg_funcs).reset_index()

        # --- REFACTORED: Prepare and return a single DataFrame ---
        final_df = consolidated_df.sort_values(by=['theater_name', 'scrape_date'])
        final_df = final_df.rename(columns={'theater_name': 'Theater'})
        column_order = ['Theater', 'Day', 'Previous Week Date', 'Previous Week Hours', 'Previous Week Duration', 'Current Week Date', 'Current Week Hours', 'Current Week Duration', 'Changed']
        final_df = final_df[column_order]
        
        return final_df, all_current_results
    except Exception as e:
        print(f"[ERROR] An error occurred in generate_weekly_report_data: {e}")
        return pd.DataFrame(), {}

def run_weekly_report_logic(scout, cache_data, process_and_save_operating_hours_func, all_theaters):
    """UI wrapper for generating and displaying the weekly operating hours report."""
    """UI wrapper for generating and displaying the weekly operating hours report. Now also handles manual runs."""
    with st.spinner("Generating weekly operating hours report... This may take a few minutes."):
        # --- NEW: Store the raw results in session state for the new film view ---
        final_report_data, all_current_results = generate_weekly_report_data(scout, cache_data, all_theaters, st.session_state.selected_company)
        if final_report_data.empty:
            st.error("Failed to generate report data. The scrape may have been unsuccessful.")
        else:
            # Save the newly scraped data. This was previously missing.
            # The `process_and_save_operating_hours_func` is passed from the main app
            # and is a reference to the function in `utils.py`.
            if all_current_results:
                # --- NEW: Log the runtime for this weekly report ---
                num_showings_found = sum(len(showings) for showings_on_date in all_current_results.values() for showings in showings_on_date.values())
                total_duration = st.session_state.get('weekly_op_hours_total_duration', 0)
                from app.utils import log_runtime
                log_runtime("Operating Hours", len(all_theaters), num_showings_found, total_duration)

                context = f"Weekly Operating Hours Report for {st.session_state.selected_company} (Thu-Thu)"
                process_and_save_operating_hours_func(all_current_results, context, silent=True)

        st.session_state.weekly_op_hours_report_data = final_report_data
        st.session_state.weekly_op_hours_raw_results = all_current_results
        st.session_state.op_hours_theater_count = len(all_theaters)  # Store theater count
    st.session_state.run_weekly_op_hours_report = False

def render_op_hours_summary_report():
    """Renders the summary report UI for both weekly and manual op hours runs."""
    st.subheader("Showtime & Operating Hours Report")

    # --- NEW: View Toggle ---
    view_mode = st.radio(
        "Group Report By:",
        ("Theater", "Film"),
        horizontal=True,
        key="op_hours_view_mode"
    )

    if view_mode == "Film":
        # Generate the film-centric summary from the raw scrape results
        film_summary_data = _generate_op_hours_summary_by_film(st.session_state.get('op_hours_results', {}))
        
        if not film_summary_data:
            st.info("No data to display in film view.")
        else:
            for date_str, films_on_date in sorted(film_summary_data.items()):
                date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                st.markdown(f"### 🗓️ {date_obj.strftime('%A, %B %d, %Y')}")
                
                for film_title, film_info in sorted(films_on_date.items()):
                    with st.expander(f"**{film_title}**", expanded=True):
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            if film_info['film_details'] and film_info['film_details'].get('poster_url') != 'N/A':
                                st.image(film_info['film_details']['poster_url'])
                        with col2:
                            for theater_summary in film_info['theaters']:
                                st.markdown(f"##### {theater_summary['theater_name']} ({theater_summary.get('num_showings', 0)} showings)")
                                st.caption(f"Operating Hours: {theater_summary['operating_hours']}")
                                st.markdown("---")

def _generate_manual_run_comparison_table(results_by_date: dict) -> list[dict]:
    """
    [NEW] Generates the detailed week-over-week comparison table for a manual run.
    This encapsulates the logic previously in the main UI flow.
    """
    new_data_list = []
    for date_str, theaters in results_by_date.items():
        for theater_name, showings in theaters.items():
            if not showings:
                new_data_list.append({"scrape_date": date_str, "theater_name": theater_name, "open_time": "N/A", "close_time": "N/A", "duration_hours": 0.0})
                continue
            
            all_times = [datetime.datetime.strptime(normalize_time_string(s['showtime']), "%I:%M%p") for s in showings if normalize_time_string(s['showtime'])]
            if all_times:
                min_time, max_time = min(all_times), max(all_times)
                duration_hours = round((max_time - min_time).total_seconds() / 3600, 1)
                new_data_list.append({"scrape_date": date_str, "theater_name": theater_name, "open_time": min_time.strftime("%I:%M %p"), "close_time": max_time.strftime("%I:%M %p"), "duration_hours": duration_hours})

    if not new_data_list:
        return []

    new_df = pd.DataFrame(new_data_list)
    new_df['scrape_date'] = pd.to_datetime(new_df['scrape_date'])
    new_df['Day'] = new_df['scrape_date'].dt.day_name()
    new_df['Current Week Hours'] = new_df.apply(lambda row: f"{row['open_time']} - {row['close_time']}" if pd.notna(row['open_time']) else "No Showings Found", axis=1)
    new_df['Current Week Duration'] = new_df['duration_hours'].apply(lambda x: f"{x:.1f} hrs" if x > 0 else "")

    theater_list = new_df['theater_name'].unique().tolist()
    start_date_prev = new_df['scrape_date'].min() - datetime.timedelta(days=7)
    end_date_prev = new_df['scrape_date'].max() - datetime.timedelta(days=7)
    prev_df = database.get_operating_hours_for_theaters_and_dates(theater_list, start_date_prev, end_date_prev)
    if prev_df.empty:
        prev_df = database.calculate_operating_hours_from_showings(theater_list, start_date_prev, end_date_prev)

    if not prev_df.empty:
        prev_df['scrape_date'] = pd.to_datetime(prev_df['scrape_date'])
        prev_df['comparison_date'] = prev_df['scrape_date'] + datetime.timedelta(days=7)
        prev_df['Previous Week Hours'] = prev_df.apply(lambda r: f"{r['open_time']} - {r['close_time']}" if pd.notna(r['open_time']) else "No Showings Found", axis=1)
        def calc_dur(row):
            if pd.notna(row['open_time']) and pd.notna(row['close_time']):
                return round((datetime.datetime.strptime(row['close_time'], "%I:%M %p") - datetime.datetime.strptime(row['open_time'], "%I:%M %p")).total_seconds() / 3600, 1)
            return 0.0
        prev_df['Previous Week Duration'] = prev_df.apply(calc_dur, axis=1).apply(lambda x: f"{x:.1f} hrs" if x > 0 else "")
        prev_lookup = {(r['theater_name'], r['comparison_date']): (r['Previous Week Hours'], r['scrape_date'].strftime('%a, %b %d'), r['Previous Week Duration']) for _, r in prev_df.iterrows()}
        new_df[['Previous Week Hours', 'Previous Week Date', 'Previous Week Duration']] = new_df.apply(lambda r: pd.Series(prev_lookup.get((r['theater_name'], r['scrape_date']), ('N/A', 'N/A', ''))), axis=1)
    else:
        new_df['Previous Week Hours'] = 'N/A'
        new_df['Previous Week Date'] = 'N/A'
        new_df['Previous Week Duration'] = ''

    new_df['Current Week Date'] = new_df['scrape_date'].dt.strftime('%a, %b %d')
    new_df['Changed'] = new_df.apply(lambda r: '🔄 Changed' if r['Previous Week Hours'] != 'N/A' and r['Current Week Hours'] != r['Previous Week Hours'] else ('✨ New' if r['Previous Week Hours'] == 'N/A' else '✅ No Change'), axis=1)
    
    # Group into the same structure as the weekly report
    final_report_data = []
    for theater_name, group in new_df.groupby('theater_name'):
        report_df = group[['Day', 'Previous Week Date', 'Previous Week Hours', 'Previous Week Duration', 'Current Week Date', 'Current Week Hours', 'Current Week Duration', 'Changed']].copy()
        final_report_data.append({'theater_name': theater_name, 'report': report_df})
    
    return final_report_data

def create_op_hours_task(task_name, day_of_week, time_utc):
    """Creates a JSON task file for a recurring operating hours report."""
    company_name = st.session_state.selected_company
    tasks_dir = os.path.join(DATA_DIR, company_name, 'scheduled_tasks')
    os.makedirs(tasks_dir, exist_ok=True)
    sanitized_name = "".join(c for c in task_name if c.isalnum() or c in (' ', '_')).rstrip()
    filepath = os.path.join(tasks_dir, f"{sanitized_name.replace(' ', '_')}.json")
    task_config = {"task_name": task_name, "task_type": "weekly_op_hours_report", "day_of_week": day_of_week, "schedule_time_utc": time_utc, "enabled": True, "last_run": None}
    with open(filepath, 'w') as f:
        json.dump(task_config, f, indent=4)
    st.toast(f"Scheduled '{task_name}'!")

def render_report_section():
    # --- REFACTORED: Conditionally show the Summary Report toggle ---
    theater_count = st.session_state.get('op_hours_theater_count', 0)
    
    report_options = ["Detailed Comparison"]
    # Only allow summary report for smaller runs to prevent performance issues
    if theater_count < 10:
        report_options.insert(0, "Summary Report")
        report_type = st.radio(
            "Select Report Type:",
            report_options,
            index=1, # Default to Detailed Comparison
            horizontal=True,
            key="op_hours_report_type",
            help="The Summary Report is only available for runs with fewer than 10 theaters."
        )
    else:
        st.info("The 'Summary Report' view is disabled for scrapes involving 10 or more theaters to ensure performance. Please use the 'Detailed Comparison' below.")
        report_type = "Detailed Comparison"
        # Ensure the key is set so the rest of the logic works
        if 'op_hours_report_type' not in st.session_state:
            st.session_state.op_hours_report_type = report_type

    # Determine which data source to use (weekly or manual)
    is_weekly_run = 'weekly_op_hours_report_data' in st.session_state
    raw_results = st.session_state.get('weekly_op_hours_raw_results') if is_weekly_run else st.session_state.get('op_hours_results', {})

    if report_type == "Summary Report":
        st.subheader("Showtime & Operating Hours Summary")
        view_mode = st.radio(
            "Group Summary By:",
            ("Theater", "Film"),
            horizontal=True,
            key="op_hours_view_mode"
        )

        if not raw_results:
            st.info("No data available to generate a summary report. Please run a scrape first.")
            return

        if view_mode == "Film":
            film_summary_data = _generate_op_hours_summary_by_film(raw_results)
            if not film_summary_data:
                st.info("No data to display in film view.")
            else:
                for date_str, films_on_date in sorted(film_summary_data.items()):
                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                    st.markdown(f"### 🗓️ {date_obj.strftime('%A, %B %d, %Y')}")
                    
                    for film_title, film_info in sorted(films_on_date.items()):
                        with st.expander(f"**{film_title}**", expanded=True):
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                if film_info['film_details'] and film_info['film_details'].get('poster_url') != 'N/A':
                                    st.image(film_info['film_details']['poster_url'])
                            with col2:
                                for theater_summary in film_info['theaters']:
                                    st.markdown(f"##### {theater_summary['theater_name']} ({theater_summary.get('num_showings', 0)} showings)")
                                    st.caption(f"Showtimes: {', '.join(theater_summary['showtimes'])}")
                                    st.markdown("---")
        else: # "By Theater" view
            theater_summary_data = _generate_op_hours_summary_by_theater(raw_results)
            if not theater_summary_data:
                st.info("No data to display in theater view.")
            else:
                for date_str, theaters_on_date in sorted(theater_summary_data.items()):
                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                    st.markdown(f"### 🗓️ {date_obj.strftime('%A, %B %d, %Y')}")

                    for theater_name, film_summaries in sorted(theaters_on_date.items()):
                        with st.expander(f"**{theater_name}**", expanded=True):
                            for film_summary in film_summaries:
                                col1, col2 = st.columns([1, 4])
                                with col1:
                                    if film_summary['film_details'] and film_summary['film_details'].get('poster_url') != 'N/A':
                                        st.image(film_summary['film_details']['poster_url'])
                                with col2:
                                    st.markdown(f"##### {film_summary['film_title']} ({film_summary.get('num_showings', 0)} showings)")
                                    st.write(f"**Showtimes:** {', '.join(film_summary['showtimes'])}")
                                st.markdown("---")

    else: # Detailed Comparison Report
        st.subheader("Weekly Comparison Report")
        
        report_data = None
        if is_weekly_run:
            # The weekly run now returns a DataFrame directly
            report_data = st.session_state.get('weekly_op_hours_report_data', pd.DataFrame())
        elif 'op_hours_results' in st.session_state:
            # Generate the detailed comparison on the fly for manual runs
            with st.spinner("Analyzing changes from previous week..."):
                report_data = _generate_manual_run_comparison_table(st.session_state.op_hours_results)

        if report_data is not None and ((isinstance(report_data, pd.DataFrame) and not report_data.empty) or (isinstance(report_data, list) and report_data)):
            # --- Display summary metrics ---
            changed_count, new_count, no_change_count = 0, 0, 0
            # --- FIX: Handle both list-of-dicts (manual) and single DataFrame (weekly) formats ---
            if isinstance(report_data, pd.DataFrame):
                # This is the new weekly report format (a single DataFrame)
                report_groups = report_data.groupby('Theater')
            elif isinstance(report_data, list):
                # This is the old manual report format (a list of dicts)
                report_groups = [(item['theater_name'], item['report']) for item in report_data]

            for theater_name, theater_df in report_groups:
                statuses = set(theater_df['Changed'].unique())
                if '🔄 Changed' in statuses: changed_count += 1
                elif '✨ New' in statuses: new_count += 1
                else: no_change_count += 1
            
            st.subheader("Report Summary")
            summary_cols = st.columns(3)
            summary_cols[0].metric("Theaters with Changes", f"{changed_count}")
            summary_cols[1].metric("Theaters with New Hours", f"{new_count}")
            summary_cols[2].metric("Theaters with No Change", f"{no_change_count}")
            st.divider()

            # --- Display download button and dataframes ---
            file_prefix = "Weekly" if is_weekly_run else "Manual"
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            
            if is_weekly_run: # Weekly report is now a single DataFrame
                excel_data = to_excel(report_data)
                st.download_button(
                    label=f"📥 Download {file_prefix} Report as Excel",
                    data=excel_data,
                    file_name=f"{file_prefix}_OpHours_Report_{st.session_state.selected_company}_{timestamp}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    use_container_width=True,
                    type="primary"
                )
            elif isinstance(report_data, list): # Manual run logic remains similar, but let's ensure it produces a single DF
                # Manual report is a single DataFrame
                all_dfs = [item['report'].assign(Theater=item['theater_name']) for item in report_data]
                if all_dfs:
                    combined_df = pd.concat(all_dfs, ignore_index=True)
                    # Reorder columns for better display
                    cols_order = ['Theater', 'Day', 'Previous Week Date', 'Previous Week Hours', 'Previous Week Duration', 'Current Week Date', 'Current Week Hours', 'Current Week Duration', 'Changed']
                    display_df = combined_df[cols_order]
                    excel_data = to_excel(display_df)
                    st.download_button(
                        label=f"📥 Download {file_prefix} Report as Excel",
                        data=excel_data,
                        file_name=f"{file_prefix}_OpHours_Report_{st.session_state.selected_company}_{timestamp}.xlsx",
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        use_container_width=True,
                        type="primary"
                    )

            st.divider()

            if is_weekly_run:
                st.dataframe(report_data.style.apply(highlight_changes, axis=1), use_container_width=True, hide_index=True)
            elif 'op_hours_results' in st.session_state:
                # For manual run, display the combined table
                if 'display_df' in locals() and not display_df.empty:
                    st.dataframe(display_df.style.apply(highlight_changes, axis=1), use_container_width=True, hide_index=True)

        else:
            st.info("No data available to generate a detailed comparison report.")

def render_operating_hours_mode(scout, markets_data, cache_data, IS_DISABLED, process_and_save_operating_hours):
    st.header("Weekly Operating Hours Report")
    st.info("Analyze theater opening and closing times based on showtime data, either through manual scrapes or automated weekly reports.")

    # Pre-calculate the number of theaters for estimation
    selected_company = st.session_state.selected_company
    normalized_selected_company = _extract_company_name(selected_company)
    all_company_theaters = []
    for market in cache_data.get("markets", {}).values():
        for theater in market.get("theaters", []):
            normalized_theater_company = _extract_company_name(theater.get("company", ""))
            if normalized_theater_company == normalized_selected_company and "Permanently Closed" not in theater.get("name", ""):
                all_company_theaters.append(theater)
    num_theaters = len(all_company_theaters)

    if st.button("Get Next Week's Operating Hours (Thu-Thu)", use_container_width=True, type="primary", disabled=IS_DISABLED or num_theaters == 0):
        num_days = 8 # Thu to Thu inclusive
        assumed_showings_per_theater_day = 50 # A rough guess for estimation
        st.session_state.weekly_op_hours_est_time = estimate_scrape_time(num_theaters * num_days * assumed_showings_per_theater_day, mode_filter="Operating Hours")
        st.session_state.weekly_op_hours_confirm = True
        st.rerun()

    if st.session_state.get('weekly_op_hours_confirm'):
        estimated_time = st.session_state.get('weekly_op_hours_est_time', -1)
        if estimated_time > 0 and estimated_time < 30:
            st.session_state.run_weekly_op_hours_report = True
            st.session_state.weekly_op_hours_confirm = False
            st.rerun()
        else:
            if estimated_time > 0:
                confirm_message = f"This scrape will check {num_theaters} theaters for 8 days and is estimated to take about {format_time_to_human_readable(estimated_time)}. Do you want to proceed?"
            else:
                confirm_message = ui_config['scraper']['op_hours_confirm_message']
            st.info(confirm_message)
            if st.button(ui_config['scraper']['proceed_button'], use_container_width=True, type="primary"):
                st.session_state.run_weekly_op_hours_report = True
                st.session_state.weekly_op_hours_confirm = False
                st.rerun()

    if st.session_state.get('run_weekly_op_hours_report'):
        if not all_company_theaters:
            st.warning(f"No theaters found for company '{selected_company}' in the cache.")
            st.session_state.run_weekly_op_hours_report = False
        else:
            run_weekly_report_logic(scout, cache_data, process_and_save_operating_hours, all_company_theaters)

    st.divider()
    st.header("Schedule Common Checks")
    st.info("Schedule automated weekly checks for operating hours. Reports will be saved as Excel files in this company's reports directory.")
    cols = st.columns(3)
    with cols[0]:
        if st.button("Schedule Full Thursday Report", help="Runs the full Thu-Thu comparison report every Thursday at 08:00 UTC."):
            create_op_hours_task("Weekly Thursday Report", "Thursday", "08:00")
    with cols[1]:
        if st.button("Schedule Saturday Check", help="Re-runs the full Thu-Thu comparison report every Saturday at 08:00 UTC to catch weekend changes."):
            create_op_hours_task("Weekly Saturday Check", "Saturday", "08:00")
    with cols[2]:
        if st.button("Schedule Tuesday Check", help="Re-runs the full Thu-Thu comparison report every Tuesday at 08:00 UTC to catch mid-week changes."):
            create_op_hours_task("Weekly Tuesday Check", "Tuesday", "08:00")

    st.divider() # type: ignore
    st.header("Manual Operating Hours Overview")

    selected_company = st.session_state.selected_company

    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"Select All {selected_company} Markets", use_container_width=True, disabled=IS_DISABLED, key="op_hours_all_markets_btn"):
            theaters_to_process_with_market = []
            for region_name, markets_in_region in markets_data[selected_company].items():
                for market_name, market_info in markets_in_region.items():
                    theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                    scrapeable_theaters = [t for t in theaters_in_market if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango", False)]
                    for theater_obj in scrapeable_theaters:
                        theaters_to_process_with_market.append({'market': market_name, 'theater': theater_obj})
            st.session_state.op_hours_theaters = theaters_to_process_with_market
            st.session_state.op_hours_selected_theaters = [item['theater'] for item in theaters_to_process_with_market]
            st.session_state.op_hours_selection = {'type': 'all_company_markets'}
            st.rerun()
    with col2:
        if st.button(f"Select All {selected_company} Theaters", use_container_width=True, disabled=IS_DISABLED, key="op_hours_all_theaters_btn"):
            theaters_to_process_with_market = []
            normalized_selected_company = _extract_company_name(selected_company)
            for region_name, markets_in_region in markets_data[selected_company].items():
                for market_name, market_info in markets_in_region.items():
                    theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                    scrapeable_theaters = [t for t in theaters_in_market if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango", False)]
                    for theater_obj in scrapeable_theaters:
                        normalized_theater_company = _extract_company_name(theater_obj.get('company', ''))
                        if normalized_theater_company == normalized_selected_company:
                            theaters_to_process_with_market.append({'market': market_name, 'theater': theater_obj})
            st.session_state.op_hours_theaters = theaters_to_process_with_market
            st.session_state.op_hours_selected_theaters = [item['theater'] for item in theaters_to_process_with_market]
            st.session_state.op_hours_selection = {'type': 'all_company_theaters'}
            st.rerun()

    # Initialize session state variables for this mode
    if 'op_hours_selection' not in st.session_state:
        st.session_state.op_hours_selection = {}
    if 'op_hours_director' not in st.session_state:
        st.session_state.op_hours_director = None
    if 'op_hours_confirm' not in st.session_state:
        st.session_state.op_hours_confirm = False
    if 'op_hours_running' not in st.session_state:
        st.session_state.op_hours_running = False
    if 'weekly_op_hours_confirm' not in st.session_state:
        st.session_state.weekly_op_hours_confirm = False
    if 'run_weekly_op_hours_report' not in st.session_state:
        st.session_state.run_weekly_op_hours_report = False
    if 'weekly_op_hours_report_df' in st.session_state and st.session_state.get('run_weekly_op_hours_report') is False:
        del st.session_state.weekly_op_hours_report_df

    IS_DISABLED = IS_DISABLED or st.session_state.op_hours_running or st.session_state.op_hours_confirm or st.session_state.run_weekly_op_hours_report or st.session_state.weekly_op_hours_confirm

    # ZIP Code Search
    st.subheader("Search by ZIP Code")
    zip_code = st.text_input("Enter a 5-digit ZIP code to find theaters", max_chars=5)
    if st.button("Search by ZIP", key="op_hours_zip_search"):
        if zip_code:
            with st.spinner(f"Live searching Fandango for theaters near {zip_code}..."):
                date_str = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
                thread, result_func = run_async_in_thread(scout.live_search_by_zip, zip_code, date_str)
                thread.join()
                status, result, log, _ = result_func()
                if status == 'success' and result:
                    theaters = list(result.values())
                    # Store results in a dedicated 'unassigned' state
                    st.session_state.unassigned_theaters = [{'market': zip_code, 'theater': t} for t in theaters]
                    # Set the director to 'Unassigned' to activate that part of the UI
                    st.session_state.op_hours_director = 'Unassigned'
                    st.session_state.op_hours_selection = {}
                    st.session_state.op_hours_theaters = []
                    st.session_state.op_hours_selected_theaters = []
                    st.rerun()
                else:
                    st.error(f"Failed to perform live ZIP search: {get_error_message(result)}")
    
    st.divider()
    
    # Theater Selection
    st.subheader("Search by Market")
    
    # Director Buttons
    parent_company = st.session_state.selected_company
    regions = list(markets_data[parent_company].keys())
    
    # Dynamically add 'Unassigned' category if it exists in the session state
    if 'unassigned_theaters' in st.session_state and st.session_state.unassigned_theaters:
        if 'Unassigned' not in regions:
            regions.append('Unassigned')
    
    cols = st.columns(len(regions))
    for i, region in enumerate(regions):
        if cols[i].button(region, key=f"op_hours_director_{region}", use_container_width=True, type="primary" if st.session_state.op_hours_director == region else 'secondary'):
            st.session_state.op_hours_director = region
            st.session_state.op_hours_selection = {}
            st.session_state.op_hours_theaters = []
            st.session_state.op_hours_selected_theaters = []
            st.rerun()

    # Market Buttons
    if st.session_state.op_hours_director:
        selected_director = st.session_state.op_hours_director

        if selected_director == 'Unassigned':
            # If 'Unassigned' is selected, populate the theater list directly
            # and skip showing market buttons.
            st.session_state.op_hours_theaters = st.session_state.get('unassigned_theaters', [])
            st.session_state.op_hours_selection = {'type': 'unassigned'}
        else:
            # This is the existing logic for normal directors/regions
            st.subheader(f"Markets in {selected_director}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"All {selected_director} Markets", use_container_width=True, type="primary" if st.session_state.op_hours_selection.get('market') == 'all' else 'secondary'):
                    theaters_to_process_with_market = []
                    current_region_markets = markets_data[parent_company][selected_director]
                    for market_name, market_info in current_region_markets.items():
                        theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                        scrapeable_theaters = [t for t in theaters_in_market if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango", False)]
                        for theater_obj in scrapeable_theaters:
                            theaters_to_process_with_market.append({'market': market_name, 'theater': theater_obj})
                    st.session_state.op_hours_theaters = theaters_to_process_with_market
                    st.session_state.op_hours_selected_theaters = [item['theater'] for item in theaters_to_process_with_market]
                    st.session_state.op_hours_selection = {'type': 'director', 'director': selected_director, 'market': 'all'}
                    st.rerun()
            with c2:
                if st.button(f"All {selected_company} Theaters in {selected_director}", use_container_width=True, type="primary" if st.session_state.op_hours_selection.get('market') == 'all_company' else 'secondary'):
                    theaters_to_process_with_market = []
                    normalized_selected_company = _extract_company_name(selected_company)
                    current_region_markets = markets_data[parent_company][selected_director]
                    for market_name, market_info in current_region_markets.items():
                        theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                        scrapeable_theaters = [t for t in theaters_in_market if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango", False)]
                        for theater_obj in scrapeable_theaters:
                            normalized_theater_company = _extract_company_name(theater_obj.get('company', ''))
                            if normalized_theater_company == normalized_selected_company:
                                theaters_to_process_with_market.append({'market': market_name, 'theater': theater_obj})
                    st.session_state.op_hours_theaters = theaters_to_process_with_market
                    st.session_state.op_hours_selected_theaters = [item['theater'] for item in theaters_to_process_with_market]
                    st.session_state.op_hours_selection = {'type': 'director', 'director': selected_director, 'market': 'all_company'}
                    st.rerun()

            markets = list(markets_data[parent_company][selected_director].keys())
            cols = st.columns(4)
            for i, market in enumerate(markets):
                if cols[i%4].button(market, key=f"op_hours_market_{market}", use_container_width=True, type="primary" if st.session_state.op_hours_selection.get('market') == market else 'secondary'):
                    theaters_in_market = cache_data.get("markets", {}).get(market, {}).get("theaters", [])
                    st.session_state.op_hours_theaters = [{'market': market, 'theater': t} for t in theaters_in_market]
                    st.session_state.op_hours_selected_theaters = theaters_in_market
                    st.session_state.op_hours_selection = {'type': 'market', 'director': selected_director, 'market': market}
                    st.rerun()

    if 'op_hours_theaters' in st.session_state and st.session_state.op_hours_theaters:
        st.subheader("Select Theaters")
        cols = st.columns(4)
        for i, theater_item in enumerate(st.session_state.op_hours_theaters):
            theater = theater_item['theater']
            # --- FIX: Ensure non-scrapeable theaters are not selectable ---
            if "(Permanently Closed)" not in theater.get("name", "") and not theater.get("not_on_fandango", False):
                theater_name_for_display = format_theater_name_for_display(theater['name'])
                is_selected = theater in st.session_state.get('op_hours_selected_theaters', [])
                if cols[i % 4].button(theater_name_for_display, key=f"op_theater_{i}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                    if 'op_hours_selected_theaters' not in st.session_state:
                        st.session_state.op_hours_selected_theaters = []
                    if is_selected:
                        st.session_state.op_hours_selected_theaters = [t for t in st.session_state.op_hours_selected_theaters if t['name'] != theater['name']]
                    else:
                        st.session_state.op_hours_selected_theaters.append(theater)
                    st.rerun()

    # Date Selection and Run Button
    # This block should be visible unless a scrape is running or confirming
    if st.session_state.get('op_hours_selected_theaters') and not st.session_state.op_hours_running and not st.session_state.op_hours_confirm:
        st.divider()
        
        market_timezone = "America/Chicago" # Default timezone
        if st.session_state.op_hours_selection.get('type') == 'market':
            market_name = st.session_state.op_hours_selection.get('market')
            director = st.session_state.op_hours_selection.get('director')
            market_timezone = markets_data[parent_company][director][market_name].get('timezone', "America/Chicago")

        today = datetime.date.today()
        if not is_run_allowed(market_timezone):
            today = today + datetime.timedelta(days=1)
            st.warning("It's after 8am in the selected market, so the date has been automatically set to tomorrow.")

        st.session_state.op_hours_date_range = st.date_input("Select Date Range", value=(today, today + datetime.timedelta(days=1)), key="op_hours_date_range_widget")
        
        run_disabled = False
        if len(st.session_state.op_hours_date_range) == 2:
            start_date, end_date = st.session_state.op_hours_date_range
            if start_date == datetime.date.today() and not is_run_allowed(market_timezone):
                run_disabled = True
                st.warning("You can no longer run for today's date after 8am in this market.")
        else:
            run_disabled = True
            st.warning("Please select a date range.")

        if st.button("Get Operating Hours", use_container_width=True, disabled=IS_DISABLED or run_disabled):
            if not (isinstance(st.session_state.op_hours_date_range, (list, tuple)) and len(st.session_state.op_hours_date_range) == 2):
                st.error("Invalid date range selected. Please select a start and end date.")
            else:
                num_theaters = len(st.session_state.op_hours_selected_theaters)
                start_date, end_date = st.session_state.op_hours_date_range
                num_days = (end_date - start_date).days + 1
            # --- NEW: Estimate based on an assumed number of showtimes per theater ---
            assumed_showings_per_theater_day = 50 # A rough guess for estimation
            st.session_state.op_hours_est_time = estimate_scrape_time(num_theaters * num_days * assumed_showings_per_theater_day, mode_filter="Operating Hours")
            st.session_state.op_hours_confirm = True
            st.rerun()

    if 'weekly_op_hours_report_data' in st.session_state or 'op_hours_results' in st.session_state:
        render_report_section()

    # --- State Machine for Confirmation and Scraping ---
    if st.session_state.op_hours_confirm:
        estimated_time = st.session_state.get('op_hours_est_time', -1)
        if estimated_time > 0 and estimated_time < 30:
            st.session_state.op_hours_running = True
            st.session_state.op_hours_confirm = False
            st.rerun()
        else:
            if estimated_time > 0:
                confirm_message = f"This scrape is estimated to take about {format_time_to_human_readable(estimated_time)}. Do you want to proceed?"
            else:
                confirm_message = ui_config['scraper']['op_hours_confirm_message']
            st.info(confirm_message)
            if st.button(ui_config['scraper']['proceed_button'], use_container_width=True, type="primary"):
                st.session_state.op_hours_running = True
                st.session_state.op_hours_confirm = False
                st.rerun()

    if st.session_state.op_hours_running:
        with st.spinner(f"Finding operating hours..."):
            theaters_to_process = st.session_state.op_hours_selected_theaters
            theaters_to_process_with_market = st.session_state.op_hours_theaters
            start_date, end_date = st.session_state.op_hours_date_range

            all_results = {}
            total_duration = 0
            st.session_state.weekly_op_hours_total_duration = 0 # Initialize for logging
            for date in pd.date_range(start_date, end_date):
                date_str = date.strftime('%Y-%m-%d')
                thread, result_func = run_async_in_thread(scout.get_all_showings_for_theaters, theaters_to_process, date_str)
                thread.join()
                status, result, log, duration = result_func()
                if status == 'success' and result:
                    if duration: total_duration += duration
                    st.session_state.weekly_op_hours_total_duration += duration
                    for theater_name, showings in result.items():
                        for market_theater in theaters_to_process_with_market:
                            if market_theater['theater']['name'] == theater_name:
                                for showing in showings:
                                    showing['market'] = market_theater['market']
                                break
                    all_results[date_str] = result
                else:
                    st.error(f"Failed to fetch showtimes for {date_str}.")
            
            # --- NEW: Log the runtime of the operating hours scrape ---
            num_showings_found = sum(len(showings) for showings_on_date in all_results.values() for showings in showings_on_date.values())
            from app.utils import log_runtime
            log_runtime("Operating Hours", len(theaters_to_process), num_showings_found, total_duration)

            if all_results:
                st.session_state.op_hours_results = all_results
                # --- FIX: Save the results of the manual run to the database ---
                # --- NEW: Store the theater count for the report UI ---
                st.session_state.op_hours_theater_count = len(theaters_to_process)
                context = f"Manual Operating Hours run for {len(theaters_to_process)} theaters"
                process_and_save_operating_hours(all_results, context, silent=True)
                st.toast("✅ Manual run results saved to database.")
                st.session_state.op_hours_duration = total_duration
            st.session_state.op_hours_running = False
            st.rerun()
