import streamlit as st
import datetime
from functools import reduce
import pandas as pd
import asyncio
from app.utils import run_async_in_thread, get_error_message, save_operating_hours_from_all_showings, _extract_company_name
from app import db_adapter as database
from app.ui_components import render_daypart_selector, apply_daypart_auto_selection, render_film_and_showtime_selection

def render_market_mode(scout, markets_data, cache_data, IS_DISABLED, parent_company):
    st.title("Market Mode")
    st.info("This mode allows you to scrape prices for specific films and showtimes within a defined market.")

    if 'selected_region' not in st.session_state: st.session_state.selected_region = None
    if 'selected_market' not in st.session_state: st.session_state.selected_market = None

    regions = list(markets_data[parent_company].keys())
    st.subheader("Select Director")

    selected_company = st.session_state.selected_company

    if st.button(f"Select All {selected_company} Theaters", use_container_width=True, disabled=IS_DISABLED, key="select_all_company_theaters_btn"):
        all_theaters_for_display = []
        scrapeable_theaters_for_selection = []
        for region_name, markets_in_region in markets_data[parent_company].items():
            for market_name, market_info in markets_in_region.items():
                theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                for theater_obj in theaters_in_market:
                    normalized_theater_company = _extract_company_name(theater_obj.get('company', ''))
                    normalized_selected_company = _extract_company_name(selected_company)
                    if normalized_theater_company == normalized_selected_company:
                        all_theaters_for_display.append(theater_obj)
                        # Only add scrapeable theaters to the selection list
                        if not ("(Permanently Closed)" in theater_obj.get("name", "") or theater_obj.get("not_on_fandango")):
                            scrapeable_theaters_for_selection.append(theater_obj)

        # Set the list of theaters to display (including non-scrapeable ones)
        st.session_state.theaters = all_theaters_for_display
        # Set the list of selected theaters (only scrapeable ones)
        st.session_state.selected_theaters = [t['name'] for t in scrapeable_theaters_for_selection]

        st.session_state.selected_region = None
        st.session_state.selected_market = None
        st.session_state.stage = 'theaters_listed'
        st.rerun()

    if st.button(f"Select All {selected_company} Markets", use_container_width=True, disabled=IS_DISABLED, key="select_all_company_markets_btn"):
        all_theaters_for_display = []
        scrapeable_theaters_for_selection = []
        for region_name, markets_in_region in markets_data[parent_company].items():
            for market_name, market_info in markets_in_region.items():
                theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                all_theaters_for_display.extend(theaters_in_market)
                scrapeable_theaters = [t for t in theaters_in_market if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango")]
                scrapeable_theaters_for_selection.extend(scrapeable_theaters)

        # Set the list of theaters to display (including non-scrapeable ones)
        st.session_state.theaters = all_theaters_for_display
        # Set the list of selected theaters (only scrapeable ones)
        st.session_state.selected_theaters = [t['name'] for t in scrapeable_theaters_for_selection]

        st.session_state.selected_region = None
        st.session_state.selected_market = None
        st.session_state.stage = 'theaters_listed'
        st.rerun()

    cols = st.columns(len(regions))
    for i, region in enumerate(regions):
        is_selected = st.session_state.selected_region == region
        if cols[i].button(region, key=f"region_{region}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
            st.session_state.selected_region = region
            st.session_state.selected_market = None
            # --- NEW: Set the theater display context when a director is selected ---
            all_theaters_in_director = []
            current_region_markets = markets_data[parent_company][region]
            for market_name in current_region_markets:
                theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                all_theaters_in_director.extend(theaters_in_market)
            st.session_state.theaters = all_theaters_in_director
            # --- END NEW ---
            st.session_state.stage = 'region_selected'
            st.rerun()

    if st.session_state.selected_region:
        st.divider()
        # Calculate all relevant theaters for this director to determine button state
        all_relevant_theaters_in_director_objects = []
        current_region_markets = markets_data[parent_company][st.session_state.selected_region]
        for market_name, market_info in current_region_markets.items():
            theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
            for theater_obj in theaters_in_market:
                if "(Permanently Closed)" in theater_obj.get("name", "") or theater_obj.get("not_on_fandango"): continue
                normalized_theater_company = _extract_company_name(theater_obj.get('company', ''))
                normalized_selected_company = _extract_company_name(selected_company)
                if normalized_theater_company == normalized_selected_company:
                    all_relevant_theaters_in_director_objects.append(theater_obj)
        
        all_relevant_theater_names_in_director = {t['name'] for t in all_relevant_theaters_in_director_objects}
        currently_selected_theater_names = set(st.session_state.get('selected_theaters', []))

        is_all_selected = all_relevant_theater_names_in_director.issubset(currently_selected_theater_names) and all_relevant_theater_names_in_director

        button_label = f"Deselect All {selected_company} Theaters in {st.session_state.selected_region}" if is_all_selected else f"Select All {selected_company} Theaters in {st.session_state.selected_region}"
        button_type = "primary" if is_all_selected else "secondary"

        c1, c2 = st.columns(2)
        with c1:
            if st.button(button_label, use_container_width=True, disabled=IS_DISABLED, type=button_type, key="select_all_company_theaters_in_director_btn"):
                if is_all_selected:
                    st.session_state.selected_theaters = list(currently_selected_theater_names - all_relevant_theater_names_in_director)
                else:
                    st.session_state.selected_theaters = list(currently_selected_theater_names.union(all_relevant_theater_names_in_director))
                
                st.session_state.selected_market = None
                st.session_state.stage = 'theaters_listed'
                st.rerun()
        with c2:
            # --- NEW "All Markets" button logic ---
            all_theaters_in_region_objects = []
            current_region_markets = markets_data[parent_company][st.session_state.selected_region]
            for market_name in current_region_markets:
                theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                scrapeable_theaters = [t for t in theaters_in_market if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango")]
                all_theaters_in_region_objects.extend(scrapeable_theaters)
            
            all_theater_names_in_region = {t['name'] for t in all_theaters_in_region_objects}
            currently_selected_theater_names = set(st.session_state.get('selected_theaters', []))
            is_all_markets_selected = all_theater_names_in_region.issubset(currently_selected_theater_names) and all_theater_names_in_region

            all_markets_button_label = f"Deselect All Markets in {st.session_state.selected_region}" if is_all_markets_selected else f"Select All Markets in {st.session_state.selected_region}"
            all_markets_button_type = "primary" if is_all_markets_selected else "secondary"

            if st.button(all_markets_button_label, use_container_width=True, type=all_markets_button_type, key="select_all_markets_in_director_btn"):
                if is_all_markets_selected:
                    st.session_state.selected_theaters = list(currently_selected_theater_names - all_theater_names_in_region)
                else:
                    st.session_state.selected_theaters = list(currently_selected_theater_names.union(all_theater_names_in_region))
                
                st.session_state.selected_market = None
                st.session_state.stage = 'theaters_listed'
                st.rerun()
        st.subheader("Step 2: Select Market")
        markets = list(markets_data[parent_company][st.session_state.selected_region].keys())
        market_cols = st.columns(4)
        for i, market in enumerate(markets):
            is_selected = st.session_state.selected_market == market
            if market_cols[i % 4].button(market, key=f"market_{market}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                st.session_state.selected_market = market
                st.session_state.theaters = cache_data.get("markets", {}).get(market, {}).get("theaters", [])
                # When a market is selected, we just set the context. We no longer auto-select or clear selections.
                st.session_state.stage = 'theaters_listed'
                st.rerun()

    if st.session_state.selected_market:
        st.divider()
        st.subheader(f"Theater Controls for {st.session_state.selected_market}")

        theaters_in_market = cache_data.get("markets", {}).get(st.session_state.selected_market, {}).get("theaters", [])
        scrapeable_theaters_in_market = [
            t for t in theaters_in_market 
            if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango")
        ]
        scrapeable_theater_names = {t['name'] for t in scrapeable_theaters_in_market}
        
        currently_selected_theaters = set(st.session_state.get('selected_theaters', []))
        
        is_all_in_market_selected = scrapeable_theater_names.issubset(currently_selected_theaters) and scrapeable_theater_names

        button_label = f"Deselect All in {st.session_state.selected_market}" if is_all_in_market_selected else f"Select All in {st.session_state.selected_market}"
        button_type = "primary" if is_all_in_market_selected else "secondary"

        if st.button(button_label, use_container_width=True, disabled=IS_DISABLED, type=button_type, key="select_all_in_market_btn"):
            if is_all_in_market_selected:
                st.session_state.selected_theaters = list(currently_selected_theaters - scrapeable_theater_names)
            else:
                st.session_state.selected_theaters = list(currently_selected_theaters.union(scrapeable_theater_names))
            st.rerun()

    if st.session_state.stage in ['theaters_listed', 'data_fetched', 'report_generated']:
        st.subheader("Step 3: Select Theaters")
        cols = st.columns(4)
        theaters = st.session_state.get('theaters', [])
        for i, theater in enumerate(theaters):
            theater_name = theater['name']
            if "(Permanently Closed)" in theater_name:
                cols[i % 4].button(theater_name, key=f"theater_{i}", use_container_width=True, disabled=True)
            elif theater.get('not_on_fandango'):
                cols[i % 4].link_button(f"{theater['name']} (Not on Fandango- click for link)", theater['url'], use_container_width=True)
            else:
                is_selected = theater_name in st.session_state.get('selected_theaters', [])
                if cols[i % 4].button(theater_name, key=f"theater_{i}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                    if 'selected_theaters' not in st.session_state: st.session_state.selected_theaters = []
                    if is_selected: st.session_state.selected_theaters.remove(theater_name)
                    else: st.session_state.selected_theaters.append(theater_name)
                    st.rerun()
        
        st.toggle("Only show films playing at ALL selected theaters", key="market_films_filter", disabled=IS_DISABLED, help="Filters the film list to only show films common to every theater selected across the entire date range.")
        
        today = datetime.date.today()
        default_start = today
        scrape_date_range = st.date_input(
            "Select Date Range for Showtimes",
            (default_start, default_start),
            key="market_date_range",
            disabled=IS_DISABLED
        )

        # --- NEW: Add warning for same-day scrapes after 4 PM ---
        if isinstance(scrape_date_range, (list, tuple)) and len(scrape_date_range) > 0:
            start_date = scrape_date_range[0]
            if start_date == datetime.date.today() and datetime.datetime.now().hour >= 16:
                st.warning("You are running a same-day scan after 4 PM. Showtime availability may be limited.")
        
        if st.button("Find Films for Selected Theaters", disabled=IS_DISABLED, use_container_width=True):
            if not (isinstance(scrape_date_range, (list, tuple)) and len(scrape_date_range) == 2):
                st.error("Invalid date range selected. Please select a start and end date.")
                st.stop()

            theaters_to_scrape = [t for t in theaters if t['name'] in st.session_state.selected_theaters]
            start_date, end_date = scrape_date_range
            
            all_showings_by_date = {}
            total_duration = 0
            failed_theaters = set() # Use a set to avoid duplicate names
            
            with st.spinner("Finding all available films and showtimes for the selected date range..."):
                for date in pd.date_range(start_date, end_date):
                    date_str = date.strftime('%Y-%m-%d')
                    thread, get_results = run_async_in_thread(scout.get_all_showings_for_theaters, theaters_to_scrape, date_str)
                    thread.join()
                    status, result, log, duration = get_results()
                    st.session_state.last_run_log += log
                    if duration: total_duration += duration

                    if status == 'success':
                        all_showings_by_date[date_str] = result
                        database.upsert_showings(result, date.date())
                        # Check for theaters that returned no showings on this date
                        for theater_obj in theaters_to_scrape:
                            if not result.get(theater_obj['name']):
                                failed_theaters.add(theater_obj['name'])
                    else:
                        # If the entire scrape for a date fails, all theaters are considered failed for that date
                        for theater_obj in theaters_to_scrape:
                            failed_theaters.add(theater_obj['name'])
                
                # --- NEW: Log the runtime of the showtime discovery scrape ---
                num_showings_found = sum(len(showings) for showings_on_date in all_showings_by_date.values() for showings in showings_on_date.values())
                from app.utils import log_runtime
                log_runtime("Showtime Discovery", len(theaters_to_scrape), num_showings_found, total_duration)

                if failed_theaters:
                    st.warning(f"**Could not find showtimes for the following theaters:** {', '.join(sorted(list(failed_theaters)))}. Their URLs may be stale. Please go to **Data Management** mode to re-match them or rebuild the theater cache.")
                
                st.info(f"Film search completed in {total_duration:.2f} seconds.")
                st.session_state.all_showings = all_showings_by_date
                st.session_state.market_mode_film_search_duration = total_duration
                st.session_state.market_date_range_processed = scrape_date_range
                st.session_state.selected_films = []
                st.session_state.selected_showtimes = {}
                st.session_state.stage = 'data_fetched'
            st.rerun()

    if st.session_state.stage in ['data_fetched', 'report_generated']:
        st.divider()
        if st.button("Calculate & Save Operating Hours", use_container_width=True, key="market_op_hours_shortcut", help="This will select all films and showtimes for the currently selected theaters, save the operating hours to the database, and update the UI to reflect the selections."):
            # Determine which films to process based on the 'Only show common films' toggle
            # all_showings has structure: {date: {theater_name: [showings]}}
            # We need to iterate through dates first, then theaters
            all_films_sets = []
            for date_str, daily_showings in st.session_state.all_showings.items():
                for theater_name, showings in daily_showings.items():
                    if showings:
                        all_films_sets.append(set(s['film_title'] for s in showings))
            all_films_unfiltered = sorted(list(reduce(lambda a, b: a.union(b), all_films_sets, set())))
            theaters_in_scope = [t for t in st.session_state.theaters if t['name'] in st.session_state.selected_theaters]

            if st.session_state.get('market_films_filter'):
                film_sets = []
                for theater in theaters_in_scope:
                    theater_films = set()
                    for date_str, daily_showings in st.session_state.all_showings.items():
                        showings = daily_showings.get(theater['name'], [])
                        theater_films.update(s['film_title'] for s in showings)
                    if theater_films:
                        film_sets.append(theater_films)
                films_to_process = sorted(list(set.intersection(*film_sets))) if film_sets else []
            else:
                films_to_process = all_films_unfiltered
            
            theaters_to_process_names = [t['name'] for t in theaters_in_scope]

            # This function updates session state to select all showtimes
            apply_daypart_auto_selection({"All"}, st.session_state.all_showings, films_to_process, theaters_to_process_names)
            
            # This function saves the data to the database
            # This logic is now handled inside render_film_and_showtime_selection
            
            st.toast("✅ Operating hours saved!")
            st.rerun()

        theaters_in_scope = [t for t in st.session_state.theaters if t['name'] in st.session_state.selected_theaters]
        render_film_and_showtime_selection(theaters_in_scope, st.session_state.all_showings, st.session_state.market_date_range_processed, "market", save_operating_hours_from_all_showings, IS_DISABLED, markets_data, cache_data, market=st.session_state.selected_market, op_hours_duration=st.session_state.get('market_mode_film_search_duration'))

    # Check if there are any selections in the nested dictionary
    selections_exist = any(ts for ds in st.session_state.get('selected_showtimes', {}).values() for ts in ds.values())

    if selections_exist:
        st.subheader("Step 5: Generate Report")
        
        from app.utils import generate_selection_analysis_report, to_csv, generate_showtime_pdf_report, generate_showtime_html_report
        
        # Redefine theaters_in_scope to ensure it's available in this context
        theaters_in_scope = [t for t in st.session_state.theaters if t['name'] in st.session_state.selected_theaters]

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button('📄 Generate Live Pricing Report', use_container_width=True, disabled=IS_DISABLED):
                st.session_state.confirm_scrape = True
                st.rerun()
        
        with col2:
            showtimes_df = generate_selection_analysis_report(st.session_state.selected_showtimes)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                label="📥 Download Selection Analysis (.csv)",
                data=to_csv(showtimes_df),
                file_name=f"Showtime_Selection_Analysis_{timestamp}.csv",
                mime='text/csv',
                use_container_width=True,
                help="Download a CSV analysis of the currently selected showtimes."
            )
        
        with col3:
            if st.button("📄 Generate PDF View", use_container_width=True, disabled=IS_DISABLED):
                context_title = ""
                if st.session_state.get('selected_market'):
                    context_title = f"Market: {st.session_state.selected_market}"
                elif st.session_state.get('selected_region'):
                    context_title = f"Director: {st.session_state.selected_region}"

                with st.spinner("Generating PDF report... This may take a moment."):
                    try:
                        pdf_bytes = asyncio.run(generate_showtime_pdf_report(
                            st.session_state.all_showings,
                            st.session_state.selected_films,
                            theaters_in_scope,
                            st.session_state.market_date_range_processed,
                            cache_data,
                            context_title=context_title
                        ))
                        st.session_state.pdf_report_bytes = pdf_bytes
                    except Exception as e:
                        st.warning("PDF generation failed. Installing Playwright browsers may fix this. Run: 'playwright install chromium' inside your venv.")
                        html_bytes = generate_showtime_html_report(
                            st.session_state.all_showings,
                            st.session_state.selected_films,
                            theaters_in_scope,
                            st.session_state.market_date_range_processed,
                            cache_data,
                            context_title=context_title
                        )
                        st.session_state.html_report_bytes = html_bytes
                        st.info("HTML fallback is ready below.")
                st.rerun()

    if st.session_state.get('pdf_report_bytes'):
        st.info("Your PDF report is ready to download.")
        st.download_button(
            label="📥 Download PDF",
            data=st.session_state.pdf_report_bytes,
            file_name=f"Showtime_View_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            on_click=lambda: st.session_state.update({'pdf_report_bytes': None})
        )
    elif st.session_state.get('html_report_bytes'):
        st.info("PDF is unavailable. Download the HTML view instead.")
        st.download_button(
            label="📥 Download HTML View",
            data=st.session_state.html_report_bytes,
            file_name=f"Showtime_View_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.html",
            mime="text/html",
            use_container_width=True,
            on_click=lambda: st.session_state.update({'html_report_bytes': None})
        )