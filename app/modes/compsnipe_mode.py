import streamlit as st
import datetime
from thefuzz import fuzz

import asyncio
from app.utils import run_async_in_thread, get_error_message, _extract_company_name
from app.ui_components import render_film_and_showtime_selection

def render_compsnipe_mode(scout, all_theaters_list_unique, IS_DISABLED, save_operating_hours_from_all_showings, markets_data, cache_data):
    st.title("CompSnipe Mode")
    st.info("Perform targeted scrapes by ZIP code or theater name to find and compare competitor pricing for specific films.")

    st.subheader("Step 1: Select Theaters")

    # --- Fuzzy Search Section ---
    st.write("#### Search Known Theaters (from Cache)")
    search_query = st.text_input("Start typing a theater name to search...", key="compsnipe_fuzzy_search", disabled=IS_DISABLED)

    if search_query:
        search_results = []
        for theater in all_theaters_list_unique:
            score = fuzz.token_set_ratio(search_query.lower(), theater['name'].lower())
            if score > 80:
                search_results.append(theater)

        if search_results:
            st.write("Matching Theaters Found:")
            cols = st.columns(4)
            for i, theater in enumerate(search_results):
                if 'compsnipe_theaters' not in st.session_state: st.session_state.compsnipe_theaters = []
                is_selected = any(t['name'] == theater['name'] for t in st.session_state.compsnipe_theaters)

                button_text = theater['name']
                if cols[i % 4].button(button_text, key=f"cs_fuzzy_{theater['name']}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                    if is_selected:
                        st.session_state.compsnipe_theaters = [t for t in st.session_state.compsnipe_theaters if t['name'] != theater['name']]
                    else:
                        st.session_state.compsnipe_theaters.append(theater)
                    st.rerun()
        else:
            st.info("No matching theaters found in the local cache.")
    
    st.divider()

    # --- Live Fandango Name Search ---
    st.write("#### Live Fandango Name Search")
    with st.form(key="fandango_name_search_form"):
        name_search_term = st.text_input("Enter a theater name to search on Fandango")
        submit_name_search = st.form_submit_button("Search by Name")

    if submit_name_search and name_search_term:
        with st.spinner(f"Searching Fandango for '{name_search_term}'..."):
            thread, result_func = run_async_in_thread(scout.live_search_by_name, name_search_term)
            thread.join()
            status, result, log, _ = result_func()
            st.session_state.last_run_log += log
            if status == 'success':
                st.session_state.live_name_search_results = result
            else:
                st.error(f"Failed to perform live name search: {get_error_message(result)}")
                st.session_state.live_name_search_results = {}
        st.rerun()

    if 'live_name_search_results' in st.session_state and st.session_state.live_name_search_results:
        st.write("Search Results:")
        cols = st.columns(4)
        i = 0
        for name, theater_data in st.session_state.live_name_search_results.items():
            is_selected = any(t['name'] == name for t in st.session_state.get('compsnipe_theaters', []))
            if cols[i % 4].button(name, key=f"select_live_{name}", type="primary" if is_selected else "secondary", use_container_width=True):
                if 'compsnipe_theaters' not in st.session_state:
                    st.session_state.compsnipe_theaters = []
                
                if is_selected:
                    st.session_state.compsnipe_theaters = [t for t in st.session_state.compsnipe_theaters if t['name'] != name]
                else:
                    st.session_state.compsnipe_theaters.append(theater_data)
                st.rerun()
            i += 1
    
    st.divider()

    # --- Live ZIP Search Section ---
    st.write("#### Live Search by ZIP (from Fandango)")
    with st.form(key="zip_search_form"):
        zip_search_term = st.text_input("Enter 5-digit ZIP code to find theaters", max_chars=5, key="zip_search_input", disabled=IS_DISABLED)
        scrape_date_zip = st.date_input("Select Date for Showtimes", datetime.date.today(), key="cs_zip_date", disabled=IS_DISABLED)
        submit_button = st.form_submit_button(label="Search by ZIP", use_container_width=True)

    if submit_button:
        with st.spinner(f"Live searching Fandango for theaters near {zip_search_term}..."):
            date_str = scrape_date_zip.strftime('%Y-%m-%d')
            # Store the selected date for reuse in showtime fetching
            st.session_state.compsnipe_selected_date = scrape_date_zip
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
            op_hours_str = st.session_state.get('compsnipe_operating_hours', {}).get(name, '')
            button_text = f"{name} ({op_hours_str})" if op_hours_str else name
            if cols[i % 4].button(button_text, key=f"cs_theater_{i}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                theater_obj = st.session_state.live_search_results[name]
                if is_selected:
                    st.session_state.compsnipe_theaters = [t for t in st.session_state.compsnipe_theaters if t['name'] != name]
                else:
                    st.session_state.compsnipe_theaters.append(theater_obj)
                st.rerun()

    if st.session_state.get('compsnipe_theaters'):
        # Reuse date from ZIP search, but allow user to change if needed
        default_date = st.session_state.get('compsnipe_selected_date', datetime.date.today())
        scrape_date_cs = st.date_input(
            "Confirm date for showtimes (from ZIP search)", 
            default_date, 
            key="cs_date", 
            disabled=IS_DISABLED,
            help="This date was used in your ZIP search. You can change it if needed."
        )

        # --- NEW: Add warning for same-day scrapes after 4 PM ---
        if scrape_date_cs == datetime.date.today() and datetime.datetime.now().hour >= 16:
            st.warning("You are running a same-day scan after 4 PM. Showtime availability may be limited.")
        
        if st.button("Find Available Films", use_container_width=True, disabled=IS_DISABLED):
            with st.spinner("Finding all available films and showtimes..."):
                thread, result_func = run_async_in_thread(scout.get_all_showings_for_theaters, st.session_state.compsnipe_theaters, scrape_date_cs.strftime('%Y-%m-%d'))
                thread.join()
                status, result, log, duration = result_func()
                st.session_state.last_run_log = log
                if status == 'success':
                    st.info(f"Film search completed in {duration:.2f} seconds.")
                    # Create the date-keyed dictionary expected by the UI component
                    all_showings_by_date = {scrape_date_cs.strftime('%Y-%m-%d'): result}
                    st.session_state.all_showings = all_showings_by_date
                    # --- NEW: Save showtimes to DB immediately ---
                    from app import db_adapter as database
                    database.upsert_showings(result, scrape_date_cs)
                    # --- NEW: Log the runtime of the showtime discovery scrape ---
                    num_showings_found = sum(len(s) for s in result.values())
                    from app.utils import log_runtime
                    log_runtime("Showtime Discovery", len(st.session_state.compsnipe_theaters), num_showings_found, duration)

                    st.session_state.compsnipe_film_search_duration = duration
                    st.session_state.stage = 'cs_films_found'

                    # --- NEW: Check for failed theaters ---
                    failed_theaters = [t['name'] for t in st.session_state.compsnipe_theaters if not result.get(t['name'])]
                    if failed_theaters:
                        st.warning(f"**Could not find showtimes for the following theaters:** {', '.join(sorted(failed_theaters))}. This may be due to a stale or incorrect URL. Since this is a live search, you can try removing and re-adding them. If the issue persists, the theater may not be on Fandango.")
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
        scrape_date_range_cs = (st.session_state.cs_date, st.session_state.cs_date)
        render_film_and_showtime_selection(st.session_state.compsnipe_theaters, st.session_state.all_showings, scrape_date_range_cs, "cs", save_operating_hours_from_all_showings, IS_DISABLED, markets_data, cache_data, market=st.session_state.zip_search_input, op_hours_duration=st.session_state.get('compsnipe_film_search_duration'))

        # Check if there are any selections in the nested dictionary
        selections_exist = any(ts for ds in st.session_state.get('selected_showtimes', {}).values() for ts in ds.values())

        if selections_exist:
            st.subheader("Step 4: Generate Report")
            
            from app.utils import generate_selection_analysis_report, to_csv, generate_showtime_pdf_report, generate_showtime_html_report

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button('📄 Generate Sniper Report', use_container_width=True, disabled=IS_DISABLED):
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
                if st.button(" Generate PDF View", use_container_width=True, disabled=IS_DISABLED):
                    context_title = ""
                    if st.session_state.get('zip_search_input'):
                        context_title = f"ZIP Code: {st.session_state.zip_search_input}"

                    with st.spinner("Generating PDF report... This may take a moment."):
                        try:
                            pdf_bytes = asyncio.run(generate_showtime_pdf_report(
                                st.session_state.all_showings,
                                st.session_state.selected_films,
                                st.session_state.compsnipe_theaters,
                                (st.session_state.cs_date, st.session_state.cs_date),
                                cache_data,
                                context_title=context_title
                            ))
                            st.session_state.pdf_report_bytes = pdf_bytes
                        except Exception as e:
                            st.warning("PDF generation failed. Install Playwright browsers: 'playwright install chromium' inside your venv.")
                            html_bytes = generate_showtime_html_report(
                                st.session_state.all_showings,
                                st.session_state.selected_films,
                                st.session_state.compsnipe_theaters,
                                (st.session_state.cs_date, st.session_state.cs_date),
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