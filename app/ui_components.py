import streamlit as st
import datetime
import pandas as pd
from functools import reduce
from app.utils import normalize_time_string

def handle_daypart_click(dp, all_showings, selected_films, selected_theaters):
    """
    Handles clicks on daypart buttons, correctly managing the selection state using a set.
    """
    if 'daypart_selections' not in st.session_state or not isinstance(st.session_state.daypart_selections, set):
        st.session_state.daypart_selections = set()

    selections = st.session_state.daypart_selections
    other_dayparts = {"Matinee", "Twilight", "Prime", "Late Night"}

    if dp == "All":
        if "All" in selections or selections.issuperset(other_dayparts):
            selections.clear()
        else:
            selections.update(other_dayparts)
            selections.add("All")
            st.session_state.expanders_expanded = False # Collapse expanders
    else:
        if dp in selections:
            selections.remove(dp)
        else:
            selections.add(dp)

        if selections.issuperset(other_dayparts):
            selections.add("All")
        else:
            selections.discard("All")

    # Now, call the new apply function with the updated state
    apply_daypart_auto_selection(selections, all_showings, selected_films, selected_theaters)


def apply_daypart_auto_selection(daypart_selections: set, all_showings: dict, films_to_process: list, theaters_to_process: list):
    """
    [REFACTORED] Efficiently clears and rebuilds selected_showtimes based on active dayparts.
    - If "All" is selected, it selects all showtimes.
    - Otherwise, it finds the earliest showtime for each selected daypart in a single pass.
    """
    st.session_state.selected_showtimes = {}
    if not daypart_selections:
        return

    for date_str, daily_showings in all_showings.items():
        st.session_state.selected_showtimes[date_str] = {}
        for theater_name in theaters_to_process:
            for film_title in films_to_process:
                showings_for_film = [s for s in daily_showings.get(theater_name, []) if s['film_title'] == film_title]
                if not showings_for_film:
                    continue
                
                if "All" in daypart_selections:
                    for showing in showings_for_film:
                        st.session_state.selected_showtimes[date_str].setdefault(theater_name, {}).setdefault(film_title, {}).setdefault(showing['showtime'], []).append(showing)
                else:
                    # --- OPTIMIZED LOGIC ---
                    # 1. Group all showings for the film by their daypart in a single pass.
                    showings_by_daypart = {}
                    for showing in showings_for_film:
                        daypart = showing.get('daypart', 'Unknown')
                        if daypart not in showings_by_daypart:
                            showings_by_daypart[daypart] = []
                        showings_by_daypart[daypart].append(showing)

                    # 2. For each desired daypart, find the earliest showtime and select it.
                    for daypart in daypart_selections:
                        if daypart in showings_by_daypart:
                            # Sort only the relevant list of showings for that daypart.
                            sorted_daypart_showings = sorted(showings_by_daypart[daypart], key=lambda x: datetime.datetime.strptime(normalize_time_string(x['showtime']), "%I:%M%p").time())
                            earliest_showing = sorted_daypart_showings[0]
                            # Select all showings that share the same earliest time (e.g., for different formats like 3D, IMAX).
                            showings_at_earliest_time = [s for s in showings_for_film if s['showtime'] == earliest_showing['showtime']]
                            st.session_state.selected_showtimes[date_str].setdefault(theater_name, {}).setdefault(film_title, {})[earliest_showing['showtime']] = showings_at_earliest_time

def render_daypart_selector(all_showings, selected_films, selected_theaters, is_disabled=False, key_prefix=""):
    st.write("Auto-select showtimes by Daypart:")
    daypart_cols = st.columns(5)
    dayparts = ["All", "Matinee", "Twilight", "Prime", "Late Night"]

    for i, dp in enumerate(dayparts):
        is_selected = dp in st.session_state.daypart_selections
        if daypart_cols[i].button(dp, key=f"{key_prefix}_dp_{dp}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=is_disabled):
            handle_daypart_click(dp, all_showings, selected_films, selected_theaters)
            st.rerun()

def render_film_and_showtime_selection(theaters, all_showings, scrape_date_range, mode_prefix, save_operating_hours_from_all_showings, IS_DISABLED, markets_data, cache_data, market=None, op_hours_duration=None):
    # --- NEW: Build theater_to_market_map first ---
    theater_to_market_map = {}
    if cache_data and "markets" in cache_data:
        for market_name, market_info in cache_data["markets"].items():
            for theater in market_info.get("theaters", []):
                theater_to_market_map[theater['name']] = market_name

    # --- NEW: Add market data to all_showings using the map ---
    for date_str, daily_showings in all_showings.items():
        for theater_name, showings_list in daily_showings.items():
            # Prioritize the map, but fall back to the passed 'market' parameter
            # for cases like CompSnipe where theaters might not be in the cache.
            theater_market = theater_to_market_map.get(theater_name, market or 'N/A')
            for showing in showings_list:
                showing['market'] = theater_market

    # --- Automatic Operating Hours Calculation ---
    # When this component renders, it means showtimes were just fetched.
    # We can automatically calculate and save the operating hours.
    if 'op_hours_processed_for_run' not in st.session_state:
        with st.spinner("Automatically calculating and saving operating hours..."):
            theaters_to_process_names = [t['name'] for t in theaters]
            # Loop through each date in the fetched data
            for date_str, daily_showings in all_showings.items():
                scrape_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                # The save function needs the list of all theaters that were part of this scrape
                # to correctly identify which ones had no showings.
                save_operating_hours_from_all_showings(daily_showings, theaters_to_process_names, scrape_date, market, op_hours_duration, silent=True)

            st.session_state.op_hours_processed_for_run = True # Flag to prevent re-running for this run
            st.toast("Operating hours for the selected dates have been automatically calculated and saved.")

    st.subheader("Step 4: Select Films & Showtimes")
            
    # Aggregate films from all dates in the new all_showings structure
    all_films_sets = [set(s['film_title'] for showings in daily_showings.values() for s in showings if s) for daily_showings in all_showings.values()]
    all_films_unfiltered = sorted(list(reduce(lambda a, b: a.union(b), all_films_sets, set())))
    
    if st.session_state.get(f'{mode_prefix}_films_filter'):
        # To find common films, we must check across all dates for each theater
        film_sets_by_theater = {t['name']: set() for t in theaters}
        for date_str, daily_showings in all_showings.items():
            for theater in theaters:
                films_in_theater_on_date = {s['film_title'] for s in daily_showings.get(theater['name'], [])}
                film_sets_by_theater[theater['name']].update(films_in_theater_on_date)
        
        common_films = set.intersection(*film_sets_by_theater.values()) if film_sets_by_theater else set()
        all_films_to_display = sorted(list(common_films))
    else:
        all_films_to_display = all_films_unfiltered

    st.write("Select Films:")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        is_all_selected = set(st.session_state.get('selected_films', [])) == set(all_films_to_display)
        button_type = "primary" if is_all_selected else "secondary"
        if st.button("Select All Films", key=f"{mode_prefix}_select_all_films", use_container_width=True, type=button_type):
            st.session_state.selected_films = all_films_to_display
            st.rerun()
    with col2:
        if st.button("Deselect All Films", key=f"{mode_prefix}_deselect_all_films", use_container_width=True):
            st.session_state.selected_films = []
            st.rerun()

    st.divider()

    cols = st.columns(4)
    for i, film in enumerate(all_films_to_display):
        is_selected = film in st.session_state.selected_films
        if cols[i % 4].button(film, key=f"film_{film}_{mode_prefix}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
            if is_selected: st.session_state.selected_films.remove(film)
            else: st.session_state.selected_films.append(film)
            st.rerun()
    st.divider()

    if st.session_state.selected_films:
        render_daypart_selector(all_showings, st.session_state.selected_films, [t['name'] for t in theaters], IS_DISABLED, mode_prefix)

    if 'expanders_expanded' not in st.session_state: st.session_state.expanders_expanded = True
    if st.button("Collapse All" if st.session_state.expanders_expanded else "Expand All", use_container_width=True):
        st.session_state.expanders_expanded = not st.session_state.expanders_expanded
        st.rerun()

    if not all_showings:
        st.warning("No showtimes were found for the selected criteria.")
        return

    market_to_director_map = {}
    if markets_data:
        for company, regions in markets_data.items():
            for director_name, markets in regions.items():
                for market_name in markets:
                    market_to_director_map[market_name] = director_name

    theaters_by_group = {}
    for theater in theaters:
        market_name = theater_to_market_map.get(theater['name'], "Uncategorized")
        director_name = market_to_director_map.get(market_name, "Uncategorized")
        
        theaters_by_group.setdefault(director_name, {}).setdefault(market_name, []).append(theater)

    start_date, end_date = scrape_date_range
    for date in pd.date_range(start_date, end_date):
        date_str = date.strftime('%Y-%m-%d')
        daily_showings = all_showings.get(date_str)

        with st.expander(f"🗓️ {date.strftime('%A, %B %d, %Y')}", expanded=True):
            if not daily_showings:
                st.info("No showtimes found for this date.")
                continue

            for director_name, markets in sorted(theaters_by_group.items()):
                # Only show director header if there's more than one director and it's not 'Uncategorized'
                if len(theaters_by_group) > 1 and director_name != "Uncategorized":
                    st.markdown(f"### Director: {director_name}")

                for market_name, theaters_in_market in sorted(markets.items()):
                    # Only show market header if there's more than one market in the director group
                    if len(markets) > 1:
                        st.markdown(f"#### Market: {market_name}")

                    for theater in theaters_in_market:
                        theater_name = theater['name']
                        # Check for selections on this specific date
                        has_selections = any(st.session_state.selected_showtimes.get(date_str, {}).get(theater_name, {}).values())

                        showings_for_theater = daily_showings.get(theater_name, [])
                        
                        # Calculate total unique showtimes for selected films at this theater on this date
                        total_unique_showtimes = 0
                        films_in_theater = {s['film_title'] for s in showings_for_theater}
                        films_to_count = films_in_theater.intersection(st.session_state.get('selected_films', []))
                        
                        if films_to_count:
                            filtered_showings = [s for s in showings_for_theater if s['film_title'] in films_to_count]
                            unique_times = {s['showtime'] for s in filtered_showings}
                            total_unique_showtimes = len(unique_times)
                        
                        time_range_str = ""
                        if showings_for_theater:
                            all_times = [datetime.datetime.strptime(normalize_time_string(s['showtime']), "%I:%M%p") for s in showings_for_theater if normalize_time_string(s['showtime'])]
                            if all_times:
                                min_time, max_time = min(all_times), max(all_times)
                                time_range_str = f"  |  {min_time.strftime('%I:%M %p')} - {max_time.strftime('%I:%M %p')} ({(max_time - min_time).total_seconds() / 3600:.1f} hrs)"

                        showtimes_str = f" ({total_unique_showtimes} Showtime{'s' if total_unique_showtimes != 1 else ''})" if total_unique_showtimes > 0 else ""

                        expander_label = f"✅  {theater_name}{showtimes_str}{time_range_str}" if has_selections else f"⚪️ {theater_name}{showtimes_str}{time_range_str}"
                        with st.expander(expander_label, expanded=st.session_state.expanders_expanded):
                            films_to_display = {f for f in st.session_state.selected_films if f in [s['film_title'] for s in showings_for_theater]}
                            if not films_to_display: st.write("No selected films are showing at this theater for this date.")
                            for film in sorted(list(films_to_display)):
                                film_showings = sorted([s for s in showings_for_theater if s['film_title'] == film], key=lambda x: datetime.datetime.strptime(normalize_time_string(x['showtime']), "%I:%M%p").time())
                                
                                showings_by_time = {}
                                for s in film_showings:
                                    showings_by_time.setdefault(s['showtime'], []).append(s)

                                showtime_count = len(showings_by_time)
                                st.markdown(f"**{film}** ({showtime_count} showing{'s' if showtime_count != 1 else ''})")

                                cols = st.columns(8)

                                def sort_key(item):
                                    time_str, showings_list = item

                                    # The `is_plf` flag is now pre-calculated by the scraper.
                                    # We just need to check if any showing at this time has the flag.
                                    is_plf = any(s.get('is_plf', False) for s in showings_list)
                                    is_dbox = any('d-box' in s.get('format', '').lower() for s in showings_list)

                                    time_obj = datetime.datetime.strptime(normalize_time_string(time_str), "%I:%M%p").time()
                                    # Sort by PLF status first (PLF comes first), then by time
                                    return (0 if is_plf and not is_dbox else 1, time_obj)

                                for i, (time_str, showings_at_time) in enumerate(sorted(showings_by_time.items(), key=sort_key)):
                                    is_selected = time_str in st.session_state.selected_showtimes.get(date_str, {}).get(theater_name, {}).get(film, {})
                                    button_key = f"{mode_prefix}_time_{date_str}_{theater_name}_{film}_{time_str}"

                                    # The `is_plf` flag is now pre-calculated by the scraper.
                                    is_plf = any(s.get('is_plf', False) for s in showings_at_time)

                                    all_formats = set()
                                    for s in showings_at_time:
                                        format_parts = [part.strip().lower() for part in s.get('format', '2D').split(',')]
                                        all_formats.update(format_parts)
                                    def consolidate_dbox_xd(formats):
                                        """Consolidates 'd-box' and 'xd' into 'd-box xd' if both are present."""
                                        if 'd-box' in formats and 'xd' in formats:
                                            formats.remove('d-box')
                                            formats.remove('xd')
                                            formats.add('d-box xd')
                                        return formats

                                    all_formats = consolidate_dbox_xd(all_formats)

                                    if len(all_formats) > 1 and '2d' in all_formats:
                                        all_formats.remove('2d')
                                    
                                    # --- NEW: Build button label with emojis for key formats ---
                                    emoji_map = {
                                        "imax": "📽️",
                                        "dolby cinema": "🔊",
                                        "4dx": "💨",
                                        "3d": "👓",
                                        "d-box": "💺"
                                    }
                                    emoji_prefix = ""

                                    # Find the most prominent emoji to display, but only one.
                                    for fmt, emoji in emoji_map.items():
                                        if fmt in all_formats:
                                            emoji_prefix = emoji + " "
                                            break  # Show only the most prominent emoji to avoid clutter

                                    # Fallback to the star for other PLFs if no specific emoji was found
                                    if not emoji_prefix and is_plf:
                                        emoji_prefix = "✨ "

                                    # Exclude only generic, non-descriptive amenities from the text label
                                    formats_to_exclude_from_label = {'recliner', 'promotion', 'luxury'}
                                    display_formats = sorted([f.title() for f in all_formats if f != '2d' and f.lower() not in formats_to_exclude_from_label])
                                    
                                    button_label = f"{emoji_prefix}{time_str}"
                                    if display_formats:
                                        button_label += f" ({', '.join(display_formats)})"
                                    
                                    if cols[i % 8].button(button_label, key=button_key, type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                                        date_selections = st.session_state.selected_showtimes.setdefault(date_str, {})
                                        theater_selections = date_selections.setdefault(theater_name, {})
                                        film_selections = theater_selections.setdefault(film, {})
                                        if is_selected:
                                            del film_selections[time_str]
                                        else:
                                            film_selections[time_str] = showings_at_time
                                        st.rerun()