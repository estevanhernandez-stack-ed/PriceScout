import streamlit as st
import pandas as pd
import datetime
from functools import reduce
from utils import run_async_in_thread
from ui_components import render_daypart_selector

def render(scout, markets_data, cache_data, IS_DISABLED):
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
                status, result, log, duration = run_async_in_thread(scout.get_all_showings_for_theaters, theaters_to_scrape, scrape_date.strftime('%Y-%m-%d'))
                st.session_state.last_run_log = log
                if status == 'success':
                    st.info(f"Film search completed in {duration:.2f} seconds.")
                    st.session_state.all_showings = result
                    st.session_state.selected_films = []
                    st.session_state.selected_showtimes = {}
                    st.session_state.stage = 'data_fetched'
                else: st.error("Failed to fetch showings for theaters.")
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
                        if cols[i % 8].button(time_str, key=f"time_{theater_name}_{film}_{time_str}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
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