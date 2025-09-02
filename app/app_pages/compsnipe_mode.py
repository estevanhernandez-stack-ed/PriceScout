import streamlit as st
import pandas as pd
import datetime
from utils import run_async_in_thread
from ui_components import render_daypart_selector

def render(scout, IS_DISABLED):
    st.subheader("Step 1: Select Theaters")
    scrape_date_cs = st.date_input("Select Date for Showtimes", datetime.date.today() + datetime.timedelta(days=1), key="cs_date", disabled=IS_DISABLED)
    zip_col, zip_btn_col = st.columns([4, 1])
    with zip_col:
        zip_search_term = st.text_input("Enter 5-digit ZIP code to find theaters", max_chars=5, key="zip_search_input",
                                        on_change=lambda: st.session_state.update(live_search_results={}, compsnipe_theaters=[]), disabled=IS_DISABLED)
    with zip_btn_col:
        st.write("") 
        if st.button("Search by ZIP", key="search_by_zip_btn", disabled=IS_DISABLED):
            with st.spinner(f"Live searching Fandango for theaters near {zip_search_term}..."):
                status, result, log, _ = run_async_in_thread(scout.live_search_by_zip, zip_search_term, scrape_date_cs.strftime('%Y-%m-%d'))
                st.session_state.last_run_log = log
                if status == 'success': st.session_state.live_search_results = result
                else: st.error("Failed to perform live ZIP search.")
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
                status, result, log, duration = run_async_in_thread(scout.get_all_showings_for_theaters, st.session_state.compsnipe_theaters, scrape_date_cs.strftime('%Y-%m-%d'))
                st.session_state.last_run_log = log
                if status == 'success':
                    st.info(f"Film search completed in {duration:.2f} seconds.")
                    st.session_state.all_showings = result
                    st.session_state.stage = 'cs_films_found'
                else: st.error("Failed to fetch showings.")
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