import streamlit as st
import time
from app.imdb_scraper import IMDbScraper
from app.box_office_mojo_scraper import BoxOfficeMojoScraper
from app.omdb_client import OMDbClient
import datetime as dt
import asyncio
from app.utils import run_async_in_thread, _extract_company_name
from app import db_adapter as database, ui_components
from thefuzz import fuzz
import re
from itertools import groupby
import pandas as pd

def render_poster_mode(scout, markets_data, cache_data, IS_DISABLED, parent_company):
    st.title("Poster Board")
    st.info("Visually discover and select films from the database to build a pricing report.")

    if 'poster_mode_stage' not in st.session_state:
        st.session_state.poster_mode_stage = 'film_selection'

    if st.session_state.poster_mode_stage == 'film_selection':
        render_film_selection(IS_DISABLED)
    elif st.session_state.poster_mode_stage == 'date_selection':
        render_date_selection(IS_DISABLED)
    elif st.session_state.poster_mode_stage == 'theater_selection':
        render_theater_selection_ui(scout, markets_data, cache_data, IS_DISABLED, parent_company)
    elif st.session_state.poster_mode_stage == 'confirm_and_scrape':
        render_confirmation_and_scrape_ui(scout, IS_DISABLED)

def render_film_selection(IS_DISABLED):
    """Renders the initial UI for discovering and selecting films."""
    st.subheader("Step 1: Select Films from Database")
    st.info(
        "This board displays all films currently in your database. "
        "To add new films, use the 'Discover Coming Soon' button or the tools in the 'Data Management' mode."
    )
    
    # Reset selections if we are at the start
    if 'films_to_scrape' not in st.session_state:
        st.session_state.films_to_scrape = []

    # --- Film Discovery Buttons ---
    with st.expander("Film Discovery Tools"):
        col1, col2, col3 = st.columns([2, 1, 2])

        with col1:
            if st.button("Enrich All Films with Box Office Mojo Financials", use_container_width=True):
                enrich_all_films_with_bom()
        with col2:
            if st.button("Discover from Fandango", use_container_width=True):
                discover_and_enrich_films_from_fandango(and_select=True)
        with col3:
            if st.button("Discover from IMDb Calendar", use_container_width=True):
                discover_and_enrich_from_imdb(and_select=True)

    # --- FIX: Always load films from the database to ensure the list is fresh on every run ---
    # This prevents the list from disappearing after actions like 'Select All'.
    load_films_from_db()

    if 'discovered_films' in st.session_state:
        if not st.session_state.discovered_films:
            st.info("🎬 No films in your database yet. Use the **Discover** buttons below to import upcoming films from IMDb or Fandango.")
        else:
            # --- NEW: Search and Filter Controls ---
            all_films = st.session_state.discovered_films
            
            search_query = st.text_input("Search films by title...", key="poster_search_query")
            
            if search_query:
                filtered_films = [film for film in all_films if search_query.lower() in film['film_title'].lower()]
            else:
                filtered_films = all_films

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Select All Films", use_container_width=True):
                    for film in filtered_films:
                        st.session_state[f"select_{film['film_title']}"] = True
                    st.rerun()
            with col2:
                if st.button("Deselect All Films", use_container_width=True):
                    for film in filtered_films:
                        st.session_state[f"select_{film['film_title']}"] = False
                    st.rerun()
            
            display_films(filtered_films, IS_DISABLED)

    # --- Navigation Button ---
    st.divider()
    selected_film_titles = [film['film_title'] for film in st.session_state.get('discovered_films', []) if st.session_state.get(f"select_{film['film_title']}")]
    st.session_state.films_to_scrape = selected_film_titles

    if st.button("Next: Select Date", type="primary", use_container_width=True, disabled=not st.session_state.films_to_scrape):
        st.session_state.poster_mode_stage = 'date_selection'
        st.rerun()

def enrich_all_films_with_bom():
    """Fetches financial data from Box Office Mojo for all films in the database."""
    
    async def _enrich_single_film(film, bom_scraper):
        """Async helper to enrich one film."""
        bom_url = await bom_scraper.discover_film_url_async(film['film_title'])
        if bom_url:
            financials = await bom_scraper.get_film_financials_async(bom_url)
            if financials.get('opening_weekend_domestic') or financials.get('domestic_gross'):
                film.update(financials)
                database.upsert_film_details(film) # Save back to DB
                return True
        return False

    async def main_enrichment():
        """Main async function to run all enrichments concurrently."""
        bom_scraper = BoxOfficeMojoScraper()
        with st.spinner("Loading films from database..."):
            films_in_db = database.get_all_films_for_enrichment()
        if not films_in_db:
            st.warning("No films in the database to enrich.")
            return 0

        progress_bar = st.progress(0, text="Enriching films with financial data...")
        tasks = [_enrich_single_film(film, bom_scraper) for film in films_in_db]
        
        results = await asyncio.gather(*tasks)
        updated_count = sum(1 for r in results if r)

        progress_bar.empty()
        return updated_count

    with st.spinner("Enriching films... This may take a moment."):
        thread, get_results = run_async_in_thread(main_enrichment)
        thread.join()
        status, updated_count, _, _ = get_results()
        st.success(f"Enrichment complete. Updated financial data for {updated_count} films.")

    # Reload films from DB to show updated data
    load_films_from_db()
    st.rerun()

def discover_and_enrich_from_imdb(and_select=False):
    """Fetches upcoming films from IMDb, enriches with OMDb, and stores in the database."""
    imdb_scraper = IMDbScraper()
    omdb_client = OMDbClient()
    
    async def main_imdb_discovery():
        with st.spinner("Discovering upcoming releases from IMDb Calendar..."):
            films = imdb_scraper.discover_upcoming_releases()

        if not films:
            st.warning("Could not discover any upcoming films from IMDb.")
            return []

        newly_discovered_titles = []
        tasks = []

        async def enrich_and_save(film):
            title = film['title']
            if not database.check_film_exists(title):
                year = film.get('release_date', '').split('-')[0] if film.get('release_date') else None
                omdb_details = await omdb_client.get_film_details_async(title, year=year)
                
                # --- NEW: Prioritize IMDb release date if OMDb's is missing ---
                if omdb_details:
                    # If OMDb doesn't provide a release date, keep the one from IMDb.
                    if not omdb_details.get('release_date'):
                        omdb_details['release_date'] = film.get('release_date')
                    film.update(omdb_details) # Update with enriched data

                film['film_title'] = title
                database.upsert_film_details(film)
                return title
            return None

        with st.spinner("Enriching and saving new films from IMDb..."):
            tasks = [enrich_and_save(film) for film in films]
            results = await asyncio.gather(*tasks)
            newly_discovered_titles = [title for title in results if title]
        
        return newly_discovered_titles

    thread, get_results = run_async_in_thread(main_imdb_discovery)
    thread.join()
    status, newly_discovered_titles, _, _ = get_results()
    
    if isinstance(newly_discovered_titles, list):
        st.success(f"Discovered and saved {len(newly_discovered_titles)} new films from IMDb.")
        
        load_films_from_db()
        if and_select:
            for title in newly_discovered_titles:
                st.session_state[f"select_{title}"] = True
        st.rerun()
    else:
        st.error("⚠️ Could not discover films from IMDb. This may be due to network issues or site changes. Please try again later.")


def discover_and_enrich_films_from_fandango(and_select=False):
    """Fetches 'Coming Soon' films from Fandango, enriches with OMDb, and stores in session state."""
    from app.scraper import Scraper # Local import to avoid circular dependency issues if any
    scraper = Scraper()
    omdb_client = OMDbClient()

    async def main_fandango_discovery():
        with st.spinner("Discovering 'Coming Soon' films from Fandango..."):
            films = await scraper.get_coming_soon_films()

        if not films:
            st.warning("Could not discover any 'Coming Soon' films from Fandango.")
            return []

        async def enrich_and_save(film):
            title = film.get('film_title')
            if not title:
                return None
            
            if not database.check_film_exists(title):
                omdb_details = await omdb_client.get_film_details_async(title)
                if omdb_details:
                    for key, value in omdb_details.items():
                        if key not in film or film[key] in [None, 'N/A']:
                            film[key] = value
                
                film['film_title'] = title
                database.upsert_film_details(film)
                return title
            return None

        with st.spinner("Enriching and saving new films..."):
            tasks = [enrich_and_save(film) for film in films]
            results = await asyncio.gather(*tasks)
            newly_discovered_titles = [title for title in results if title]

        return newly_discovered_titles

    thread, get_results = run_async_in_thread(main_fandango_discovery)
    thread.join()
    status, newly_discovered_titles, _, _ = get_results()

    if isinstance(newly_discovered_titles, list):
        st.success(f"✅ Discovered and saved {len(newly_discovered_titles)} new films to the database.")
    else:
        st.error("⚠️ Could not discover films from Fandango. This may be due to network issues or site changes. Please try again later.")
    
    # Reload all films from the database to update the view
    load_films_from_db()

    # If requested, automatically select the newly discovered films
    if and_select:
        for title in newly_discovered_titles:
            st.session_state[f"select_{title}"] = True
    st.rerun()

def display_films(films, IS_DISABLED):
    """Displays the grid of film posters and details for selection."""
    if not films:
        st.info("No films match your search criteria.")
        return

    st.markdown("---")

    # --- NEW: Group films by release month and year ---
    def get_release_group(film):
        # First, try to group by the official release date from OMDb
        release_date_str = film.get('release_date')
        if release_date_str:
            try:
                release_date = dt.datetime.strptime(release_date_str, '%Y-%m-%d').date()
                return release_date.strftime('%B %Y')
            except (ValueError, TypeError):
                pass # Fallback to first play date

        # Fallback: Group by the first date the film was seen in a scrape
        first_play_date_str = film.get('first_play_date')
        if first_play_date_str:
            first_play_date = dt.datetime.strptime(first_play_date_str, '%Y-%m-%d').date()
            return f"First Seen: {first_play_date.strftime('%B %Y')}"

        return "Uncategorized" # Ultimate fallback

    # --- FIX: Sort films to handle missing release dates gracefully ---
    # This new sort key places films with a release date first (newest to oldest),
    # and groups all films without a release date at the bottom.
    films.sort(key=lambda x: x.get('release_date') or '0000-00-00', reverse=True)

    # --- FIX: Group all films, including those without a release date ---
    grouped_films = {k: list(v) for k, v in groupby(films, key=get_release_group)}

    for group_name, film_list in grouped_films.items():
        st.subheader(group_name)
        num_columns = 5
        cols = st.columns(num_columns)

        for i, film in enumerate(film_list):
            with cols[i % num_columns]:
                st.markdown(f"**{film['film_title']}**")
                if film.get('poster_url') and film['poster_url'] != 'N/A':
                    st.image(film['poster_url'])
                else:
                    st.image("https://via.placeholder.com/150x222.png?text=No+Poster", use_container_width=True)

                details = []
                if film.get('mpaa_rating') and film['mpaa_rating'] != 'N/A': details.append(f"**Rating:** {film['mpaa_rating']}")
                if film.get('runtime') and film['runtime'] != 'N/A': details.append(f"**Runtime:** {film['runtime']}")
                if film.get('genre') and film.get('genre') != 'N/A': details.append(f"**Genre:** {film['genre']}")
                if film.get('metascore') and film['metascore'] != 'N/A': details.append(f"**Metascore:** {film['metascore']}")
                st.caption("\n".join(details))

                opening = film.get('opening_weekend_domestic')
                gross = film.get('domestic_gross')
                if opening and isinstance(opening, (int, float)): st.caption(f"**Opening:** ${int(opening):,}")
                else: st.caption("**Opening (Dom):** N/A")
                if gross and isinstance(gross, (int, float)): st.caption(f"**Total Gross (Dom):** ${int(gross):,}")
                else: st.caption("**Total Gross (Dom):** N/A")

                # --- NEW: Select and Ignore buttons ---
                if st.button("Select & Continue", key=f"select_and_go_{film['film_title']}", use_container_width=True):
                    # This is the shortcut action
                    st.session_state.films_to_scrape = [film['film_title']]
                    st.session_state.poster_mode_stage = 'date_selection'
                    st.rerun()

                # --- Existing selection controls ---
                btn_cols = st.columns(2)
                with btn_cols[0]:
                    st.checkbox("Select", key=f"select_{film['film_title']}", disabled=IS_DISABLED, label_visibility="collapsed")
                with btn_cols[1]:
                    if st.button("🗑️", key=f"ignore_{film['film_title']}", help="Ignore this film", use_container_width=True):
                        database.add_film_to_ignore_list(film['film_title'])
                        st.rerun()
        st.divider()

def render_date_selection(IS_DISABLED):
    """Renders the UI for selecting the date range for the scrape."""
    st.subheader("Step 2: Select Date Range")
    st.info(f"You have selected **{len(st.session_state.films_to_scrape)}** film(s): **{', '.join(st.session_state.films_to_scrape)}**")

    today = dt.date.today()
    default_start = today
    
    scrape_date_range = st.date_input(
        "Select Date Range for Showtimes",
        value=(default_start, default_start),
        key="poster_date_range",
        disabled=IS_DISABLED
    )
    st.session_state.scrape_date_range = scrape_date_range

    # --- NEW: Add warning for same-day scrapes after 4 PM ---
    if isinstance(scrape_date_range, (list, tuple)) and len(scrape_date_range) > 0:
        start_date = scrape_date_range[0]
        if start_date == dt.date.today() and dt.datetime.now().hour >= 16:
            st.warning("You are running a same-day scan after 4 PM. Showtime availability may be limited.")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back to Film Selection", use_container_width=True):
            st.session_state.poster_mode_stage = 'film_selection'
            st.rerun()
    with col2:
        if st.button("Next: Select Theaters", type="primary", use_container_width=True, disabled=not (scrape_date_range and len(scrape_date_range) == 2)):
            st.session_state.poster_mode_stage = 'theater_selection'
            st.rerun()

def render_theater_selection_ui(scout, markets_data, cache_data, IS_DISABLED, parent_company):
    """Renders the UI for selecting director, market, and theaters."""
    st.subheader("Step 3: Select Theaters")
    
    date_start, date_end = st.session_state.scrape_date_range
    date_range_str = date_start.strftime('%b %d') if date_start == date_end else f"{date_start.strftime('%b %d')} to {date_end.strftime('%b %d')}"
    st.info(f"**Films:** {', '.join(st.session_state.films_to_scrape)}\n\n**Date Range:** {date_range_str}")

    # --- Standard Theater Selection Logic ---
    if 'selected_region' not in st.session_state: st.session_state.selected_region = None
    if 'selected_market' not in st.session_state: st.session_state.selected_market = None

    # --- NEW: Advanced "Select All" buttons ---
    if st.button(f"Select All {parent_company} Theaters", use_container_width=True, disabled=IS_DISABLED, key="poster_select_all_company_theaters"):
        all_theaters_for_selection = []
        for region_name, markets_in_region in markets_data[parent_company].items():
            for market_name, market_info in markets_in_region.items():
                theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
                scrapeable_theaters = [t for t in theaters_in_market if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango", False)]
                all_theaters_for_selection.extend(scrapeable_theaters)
        st.session_state.selected_theaters = [t['name'] for t in all_theaters_for_selection]
        st.rerun()

    regions = list(markets_data[parent_company].keys())
    st.write("**Select Director**")
    
    cols = st.columns(len(regions))
    for i, region in enumerate(regions):
        is_selected = st.session_state.selected_region == region
        if cols[i].button(region, key=f"poster_region_{region}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
            st.session_state.selected_region = region
            st.session_state.selected_market = None
            # Set theater context for the director
            all_theaters_in_director = []
            for market_name in markets_data[parent_company][region]:
                all_theaters_in_director.extend(cache_data.get("markets", {}).get(market_name, {}).get("theaters", []))
            st.session_state.theaters = all_theaters_in_director
            st.rerun()

    if st.session_state.selected_region:
        st.divider()
        # --- NEW: Select All for Director ---
        all_theaters_in_director = [t for t in st.session_state.get('theaters', []) if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango", False)]
        all_director_theater_names = {t['name'] for t in all_theaters_in_director}
        selected_names_set = set(st.session_state.get('selected_theaters', []))
        is_all_director_selected = all_director_theater_names.issubset(selected_names_set) and all_director_theater_names

        if st.button(f"Deselect All in {st.session_state.selected_region}" if is_all_director_selected else f"Select All in {st.session_state.selected_region}", use_container_width=True, type="primary" if is_all_director_selected else "secondary"):
            if is_all_director_selected:
                st.session_state.selected_theaters = list(selected_names_set - all_director_theater_names)
            else:
                st.session_state.selected_theaters = list(selected_names_set.union(all_director_theater_names))
            st.rerun()

        st.write("**Select Market**")
        markets = list(markets_data[parent_company][st.session_state.selected_region].keys())
        market_cols = st.columns(4)
        for i, market in enumerate(markets):
            is_selected = st.session_state.selected_market == market
            if market_cols[i % 4].button(market, key=f"poster_market_{market}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                st.session_state.selected_market = market
                st.session_state.theaters = cache_data.get("markets", {}).get(market, {}).get("theaters", [])
                st.rerun()

    if st.session_state.selected_market:
        st.divider()
        # --- NEW: Select All for Market ---
        all_theaters_in_market = [t for t in st.session_state.get('theaters', []) if "(Permanently Closed)" not in t.get("name", "") and not t.get("not_on_fandango", False)]
        all_market_theater_names = {t['name'] for t in all_theaters_in_market}
        selected_names_set = set(st.session_state.get('selected_theaters', []))
        is_all_market_selected = all_market_theater_names.issubset(selected_names_set) and all_market_theater_names

        if st.button(f"Deselect All in {st.session_state.selected_market}" if is_all_market_selected else f"Select All in {st.session_state.selected_market}", use_container_width=True, type="primary" if is_all_market_selected else "secondary"):
            if is_all_market_selected:
                st.session_state.selected_theaters = list(selected_names_set - all_market_theater_names)
            else:
                st.session_state.selected_theaters = list(selected_names_set.union(all_market_theater_names))
            st.rerun()

    if st.session_state.get('theaters'):
        st.write("**Select Theaters**")
        theater_cols = st.columns(4)
        theaters = st.session_state.get('theaters', [])
        for i, theater in enumerate(theaters):
            theater_name = theater['name']
            if not ("(Permanently Closed)" in theater_name or theater.get('not_on_fandango', False)):
                is_selected = theater_name in st.session_state.get('selected_theaters', [])
                if theater_cols[i % 4].button(theater_name, key=f"poster_theater_{i}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=IS_DISABLED):
                    if 'selected_theaters' not in st.session_state: st.session_state.selected_theaters = []
                    if is_selected: st.session_state.selected_theaters.remove(theater_name)
                    else: st.session_state.selected_theaters.append(theater_name)
                    st.rerun()
    
    # --- Navigation Buttons ---
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back to Date Selection", use_container_width=True):
            st.session_state.poster_mode_stage = 'date_selection'
            st.rerun()
    with col2:
        if st.button("Next: Confirm & Scrape", type="primary", use_container_width=True, disabled=not st.session_state.get('selected_theaters')):
            st.session_state.poster_mode_stage = 'confirm_and_scrape'
            st.rerun()

def render_confirmation_and_scrape_ui(scout, IS_DISABLED):
    """Final step to confirm selections and trigger the scrape."""
    st.subheader("Step 4: Confirm and Scrape")

    # --- Display Summary of Selections ---
    date_start, date_end = st.session_state.scrape_date_range
    date_range_str = date_start.strftime('%b %d, %Y') if date_start == date_end else f"{date_start.strftime('%b %d, %Y')} to {date_end.strftime('%b %d, %Y')}"
    
    st.info(f"""
    **Selected Films:** {', '.join(st.session_state.films_to_scrape)}
    
    **Date Range:** {date_range_str}
    
    **Selected Theaters:** {', '.join(st.session_state.selected_theaters)}
    """)

    # --- Scrape Button ---
    if st.button("Find Showtimes & Generate Pricing Report", type="primary", use_container_width=True, disabled=IS_DISABLED):
        with st.spinner("Finding all available films and showtimes for the selected date range..."):
            theaters_to_scrape = [t for t in st.session_state.theaters if t['name'] in st.session_state.selected_theaters]
            start_date, end_date = st.session_state.scrape_date_range

            all_showings_by_date = {}
            failed_theaters = set()

            for date in pd.date_range(start_date, end_date):
                date_str = date.strftime('%Y-%m-%d')
                thread, get_results = run_async_in_thread(scout.get_all_showings_for_theaters, theaters_to_scrape, date_str)
                thread.join()
                status, result, _, _ = get_results()

                if status == 'success':
                    all_showings_by_date[date_str] = result
                    database.upsert_showings(result, date.date())
                    for theater_obj in theaters_to_scrape:
                        if not result.get(theater_obj['name']):
                            failed_theaters.add(theater_obj['name'])
                else:
                    for theater_obj in theaters_to_scrape:
                        failed_theaters.add(theater_obj['name'])
            
            if failed_theaters:
                st.warning(f"**Could not find showtimes for the following theaters:** {', '.join(sorted(list(failed_theaters)))}. Their URLs may be stale. Please go to **Data Management** mode to re-match them or rebuild the theater cache.")

            st.session_state.all_showings = all_showings_by_date

            # --- Auto-select all showtimes for the chosen films ---
            ui_components.apply_daypart_auto_selection({"All"}, all_showings_by_date, st.session_state.films_to_scrape, st.session_state.selected_theaters)

            # --- Trigger the price scrape confirmation ---
            st.session_state.confirm_scrape = True
            st.rerun()

    st.divider()
    if st.button("Back to Theater Selection", use_container_width=True):
        st.session_state.poster_mode_stage = 'theater_selection'
        st.rerun()

    # This part is legacy and might be removed or refactored if the above works well.
    # It was the original final step.
    if False and st.session_state.get('selected_theaters'):
        if st.button("Generate Live Pricing Report (Legacy)", type="primary", use_container_width=True, disabled=IS_DISABLED):
            scrape_date = st.session_state.scrape_date_range[0] # Use start date for simplicity
            theaters_to_scrape = [t for t in st.session_state.theaters if t['name'] in st.session_state.selected_theaters]
            thread, get_results = run_async_in_thread(
                scout.get_all_showings_for_theaters, 
                theaters_to_scrape, 
                scrape_date.strftime('%Y-%m-%d')
            )
            thread.join()
            status, all_showings, _, _ = get_results()

            if status == 'success':
                st.session_state.all_showings = all_showings
                database.upsert_showings(all_showings, scrape_date)
                
                selected_showtimes = {scrape_date.strftime('%Y-%m-%d'): {}}
                films_to_scrape = st.session_state.films_to_scrape

                for theater_name, showings in all_showings.items():
                    if theater_name not in st.session_state.selected_theaters:
                        continue
                    
                    selected_showtimes[scrape_date.strftime('%Y-%m-%d')][theater_name] = {}
                    
                    for showing in showings:
                        if showing['film_title'] in films_to_scrape:
                            film_title = showing['film_title']
                            if film_title not in selected_showtimes[scrape_date.strftime('%Y-%m-%d')][theater_name]:
                                selected_showtimes[scrape_date.strftime('%Y-%m-%d')][theater_name][film_title] = {}
                            
                            showtime_key = f"{showing['showtime']}_{showing['format']}"
                            selected_showtimes[scrape_date.strftime('%Y-%m-%d')][theater_name][film_title][showtime_key] = {
                                'url': showing['ticket_url'],
                                'format': showing['format']
                            }
                
                st.session_state.selected_showtimes = selected_showtimes
                st.session_state.confirm_scrape = True
                st.rerun()
            else:
                st.error("❌ Failed to retrieve showtimes. Please check your theater selection and try again.")


def load_films_from_db():
    """Loads all films from the database into session state, excluding ignored films."""
    with st.spinner("Loading films from database..."):
        all_films = database.get_all_films_for_enrichment()
        ignored_titles = set(database.get_ignored_film_titles())
        
        filtered_films = [film for film in all_films if film['film_title'] not in ignored_titles]
        
        # --- NEW: Augment films with their first play date for better grouping ---
        first_play_dates = database.get_first_play_date_for_all_films()
        for film in filtered_films:
            if film['film_title'] in first_play_dates:
                film['first_play_date'] = first_play_dates[film['film_title']]

        st.session_state.discovered_films = filtered_films
        # --- NEW: De-duplicate films after loading ---
        _deduplicate_films()

def _deduplicate_films(threshold=90):
    """
    Groups films by fuzzy title matching and selects the best candidate from each group.
    This cleans up near-duplicates like 'Film A' and 'Film A (2024)'.
    """
    if 'discovered_films' not in st.session_state or not st.session_state.discovered_films:
        return

    def _normalize_title_for_matching(title: str) -> str:
        """Removes year from the end of a title, e.g., 'Film (2024)' -> 'Film'."""
        return re.sub(r'\s*\(\d{4}\)$', '', title).strip()

    all_films = st.session_state.discovered_films
    
    # Sort by a "completeness" score to make the first item in a group more likely to be the best
    def completeness_score(film):
        score = 0
        if film.get('poster_url') and film['poster_url'] != 'N/A': score += 5
        if film.get('release_date'): score += 3
        if film.get('opening_weekend_domestic'): score += 2
        if film.get('domestic_gross'): score += 2
        if film.get('plot') and film['plot'] != 'N/A': score += 1
        return score

    sorted_films = sorted(all_films, key=completeness_score, reverse=True)

    canonical_films = []
    processed_indices = set()

    for i, film1 in enumerate(sorted_films):
        if i in processed_indices:
            continue

        # This film is the first in a new potential group
        group = [film1]
        processed_indices.add(i)
        normalized_title1 = _normalize_title_for_matching(film1['film_title'])

        for j, film2 in enumerate(sorted_films):
            if j in processed_indices:
                continue
            normalized_title2 = _normalize_title_for_matching(film2['film_title'])
            if fuzz.token_set_ratio(normalized_title1, normalized_title2) > threshold:
                group.append(film2)
                processed_indices.add(j)
        
        # The first film in the group is the best one due to pre-sorting by completeness
        canonical_films.append(group[0])

    st.session_state.discovered_films = canonical_films