import streamlit as st
import pandas as pd
import json
import asyncio
import sys
import os
import datetime
import glob
import tempfile
from app.scraper import Scraper
from app.utils import run_async_in_thread, get_error_message
from app import database, config
from app.box_office_mojo_scraper import BoxOfficeMojoScraper
from app.omdb_client import OMDbClient

# Initialize the scraper
scraper = Scraper()

def render_failed_film_matcher(session_state_key):
    """Renders an interactive form to manually correct and re-match failed film titles."""
    st.header("Unmatched Film Review")
    st.info("These films were found during scrapes but could not be automatically matched with OMDb. Review them here to improve your data quality.")

    failed_films_df = database.get_unmatched_films()
    if failed_films_df.empty:
        st.success("No unmatched films to review.")
        return

    for i, film_title in enumerate(failed_films_df['film_title'].tolist()):
        st.markdown("---")
        st.write(f"**Original Title:** `{film_title}`")

        action = st.radio(
            "Action:", 
            ("Re-match with OMDb", "Search Fandango", "Enter Manually", "Accept as Special Event", "Mark as Mystery Movie"),
            key=f"action_{session_state_key}_{i}",
            horizontal=True
        )

        if action == "Re-match with OMDb":
            col1, col2 = st.columns([3, 1])
            with col1:
                new_title = st.text_input("Search Title", value=film_title, key=f"rematch_{session_state_key}_{i}", label_visibility="collapsed")
            with col2:
                if st.button("Re-match", key=f"rematch_btn_{session_state_key}_{i}", use_container_width=True):
                    with st.spinner(f"Searching for '{new_title}'..."):
                        omdb_client = OMDbClient()
                        film_details = omdb_client.get_film_details(new_title)
                        if film_details:
                            film_details['film_title'] = film_title
                            database.upsert_film_details(film_details)
                            database.delete_unmatched_film(film_title)
                            st.success(f"Successfully matched '{film_title}' as '{film_details.get('canonical_title', new_title)}'.")
                            st.rerun()
                        else:
                            st.error(f"Could not find details for '{new_title}'. Please try a different name.")
        
        elif action == "Enter Manually":
            with st.form(key=f"manual_form_{session_state_key}_{i}"):
                st.write("Enter film details manually:")
                
                c1, c2, c3 = st.columns(3)
                mpaa_rating = c1.text_input("MPAA Rating (e.g., PG-13)", key=f"manual_rating_{i}")
                runtime = c2.text_input("Runtime (e.g., 120 min)", key=f"manual_runtime_{i}")
                genre = c3.text_input("Genre(s) (comma-separated)", key=f"manual_genre_{i}")
                
                poster_url = st.text_input("Poster URL", key=f"manual_poster_{i}")
                plot = st.text_area("Plot Summary", key=f"manual_plot_{i}")

                submitted = st.form_submit_button("Save Manual Details")
                if submitted:
                    manual_details = {
                        "film_title": film_title, "mpaa_rating": mpaa_rating, "runtime": runtime,
                        "genre": genre, "poster_url": poster_url, "plot": plot,
                        "imdb_id": None, "director": None, "actors": None,
                        "metascore": None, "imdb_rating": None, "release_date": None, 
                        "domestic_gross": None, "opening_weekend_domestic": None, 
                        "last_omdb_update": datetime.datetime.now()
                    }
                    database.upsert_film_details(manual_details)
                    database.delete_unmatched_film(film_title)
                    st.success(f"Manually saved details for '{film_title}'.")
                    st.rerun()

        elif action == "Search Fandango":
            search_key = f"fandango_search_{i}"
            results_key = f"fandango_results_{i}"
            preview_key = f"fandango_preview_{i}"

            fandango_search_term = st.text_input("Fandango Search Term", value=film_title, key=search_key)
            if st.button("Search", key=f"fandango_search_btn_{i}"):
                # --- NEW: Live log viewer ---
                st.session_state[results_key] = None # Clear previous results
                log_container = st.empty()
                log_messages = []

                def log_to_streamlit(message):
                    log_messages.append(message)
                    log_container.code("\n".join(log_messages))

                with st.spinner(f"Searching Fandango for '{fandango_search_term}'... See log below."):
                    search_results = asyncio.run(scraper.search_fandango_for_film_url(fandango_search_term, log_callback=log_to_streamlit))
                    if search_results:
                        st.session_state[results_key] = search_results
                        log_container.empty() # Clear the log on success
                    else:
                        # The log container will show the final error messages from the scraper
                        log_messages.append("\n[FAILURE] No matching films found.")
                        log_messages.append(f"A debug screenshot may have been saved to the `{DEBUG_DIR}` folder.")
                        log_container.code("\n".join(log_messages))

                        # This is the key fix: ensure the key is deleted if the search fails
                        if results_key in st.session_state: del st.session_state[results_key]
                st.rerun()
            
            if results_key in st.session_state and st.session_state[results_key] is not None:
                # Only show search results if we are not in the preview stage
                if preview_key not in st.session_state:
                    st.write("Select the correct film from the search results:")
                    for result in st.session_state[results_key]:
                        if st.button(result['title'], key=f"fandango_result_{i}_{result['url']}"):
                            with st.spinner(f"Scraping details for '{result['title']}'..."):
                                fandango_details = asyncio.run(scraper.get_film_details_from_fandango_url(result['url']))
                                if fandango_details:
                                    st.session_state[preview_key] = fandango_details
                                    st.rerun()
                                else:
                                    st.error("Failed to scrape details from the selected Fandango page.")
            
            # --- NEW: Preview and Confirm Step ---
            if preview_key in st.session_state:
                st.subheader("Scraped Data Preview")
                details = st.session_state[preview_key]
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    if details.get('poster_url') and details['poster_url'] != 'N/A':
                        st.image(details['poster_url'])
                with col2:
                    st.write(f"**Title:** {details.get('film_title', 'N/A')}")
                    st.write(f"**Rating:** {details.get('mpaa_rating', 'N/A')}")
                    st.write(f"**Runtime:** {details.get('runtime', 'N/A')}")
                    st.write(f"**Genre:** {details.get('genre', 'N/A')}")
                    st.caption(f"**Plot:** {details.get('plot', 'N/A')}")

                btn_col1, btn_col2, _ = st.columns([1, 1, 4])
                if btn_col1.button("Confirm and Save", key=f"confirm_save_{i}", type="primary"):
                    details['film_title'] = film_title # Assign the original unmatched title as the primary key
                    database.upsert_film_details(details)
                    database.delete_unmatched_film(film_title)
                    st.success(f"Successfully saved details for '{film_title}' from Fandango.")
                    # Clean up session state
                    for key in [results_key, preview_key]:
                        if key in st.session_state: del st.session_state[key]
                    st.rerun()
                if btn_col2.button("Cancel", key=f"cancel_save_{i}"):
                    del st.session_state[preview_key]
                    st.rerun()
        
        elif action == "Mark as Mystery Movie":
            st.write("This will categorize the film under a standard 'Mystery Movie' title.")
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("Mark as Mystery", key=f"mystery_btn_{session_state_key}_{i}", use_container_width=True):
                    # Use the same helper function to get the canonical name
                    canonical_name = database._get_canonical_mystery_movie_name(film_title) or "Mystery Movie"
                    
                    # Create a minimal record for the canonical name if it doesn't exist
                    if not database.check_film_exists(canonical_name):
                        minimal_details = {
                            "film_title": canonical_name, "mpaa_rating": "N/A", "runtime": "N/A",
                            "genre": "Special Event", "plot": "A special mystery screening event.",
                            "imdb_id": None, "director": None, "actors": None, "poster_url": None,
                            "metascore": None, "imdb_rating": None, "release_date": None,
                            "domestic_gross": None, "opening_weekend_domestic": None,
                            "last_omdb_update": datetime.datetime.now()
                        }
                        database.upsert_film_details(minimal_details)
                    database.delete_unmatched_film(film_title)
                    st.success(f"Categorized '{film_title}' as '{canonical_name}'.")
                    st.rerun()

        elif action == "Accept as Special Event":
            st.write("This will create a basic entry for this title to prevent future OMDb lookups. Use this for generic titles like 'Private Event'.")
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("Accept", key=f"accept_btn_{session_state_key}_{i}", use_container_width=True):
                    # Create a minimal record to prevent future lookups
                    minimal_details = {
                        "film_title": film_title, "mpaa_rating": "N/A", "runtime": "N/A",
                        "genre": "Special Event", "plot": "No plot summary available.",
                        "imdb_id": None, "director": None, "actors": None,
                        "poster_url": None, "metascore": None, "imdb_rating": None,
                        "release_date": None, "domestic_gross": None, "opening_weekend_domestic": None,
                        "last_omdb_update": datetime.datetime.now()
                    }
                    database.upsert_film_details(minimal_details)
                    database.delete_unmatched_film(film_title)
                    st.success(f"Accepted '{film_title}' as a special event. It will not be checked against OMDb again.")
                    st.rerun()

def render_ticket_type_manager():
    """Renders a UI for reviewing and categorizing unmatched ticket types."""
    st.header("Ticket Type Management")

    # Load current ticket types
    ticket_types_path = os.path.join(config.SCRIPT_DIR, 'ticket_types.json')
    try:
        with open(ticket_types_path, 'r+') as f:
            ticket_types_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st.error("Could not load ticket_types.json.")
        return

    # --- NEW: Charting Section ---
    st.subheader("Current Ticket Type Usage")
    st.info("This chart shows how many times each defined 'Base Type' has been found in your scraped price data.")
    usage_df = database.get_ticket_type_usage_counts()
    if not usage_df.empty:
        usage_df = usage_df.set_index('ticket_type').sort_values(by='count', ascending=False)
        st.bar_chart(usage_df)
    else:
        st.info("No price data found in the database to analyze ticket type usage.")
    
    with st.expander("View Defined Ticket Types & Amenities"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Defined Base Types**")
            st.json(ticket_types_data.get('base_type_map', {}))
        with col2:
            st.write("**Defined Amenities**")
            st.json(ticket_types_data.get('amenity_map', {}))

    st.divider()

    st.subheader("Unmatched Ticket Type Review")
    st.info("Review and categorize ticket descriptions that were not automatically matched. This will improve future scrapes.")
    unmatched_df = database.get_unmatched_ticket_types()

    if unmatched_df.empty:
        st.success("No unmatched ticket types to review.")
        return

    st.write(f"Found {len(unmatched_df)} unmatched ticket types to review.")

    for index, row in unmatched_df.iterrows():
        st.markdown("---")
        unmatched_id = row['id']
        unmatched_part = row['unmatched_part']
        original_desc = row['original_description']

        # --- NEW: Display more context ---
        context_parts = [
            f"**Theater:** {row.get('theater_name', 'N/A')}",
            f"**Film:** {row.get('film_title', 'N/A')}",
            f"**Date:** {row.get('play_date', 'N/A')}",
            f"**Time:** {row.get('showtime', 'N/A')}",
            f"**Format:** {row.get('format', 'N/A')}"
        ]
        
        st.write(f"**Unmatched Part:** `{unmatched_part}` (from original: `{original_desc}`)")
        st.caption(" | ".join(context_parts))
        # ---

        col1, col2, col3 = st.columns(3)
        with col1:
            action = st.radio("Action:", ("Add as New Type", "Map to Existing", "Ignore"), key=f"action_{unmatched_id}")
        
        with col2:
            if action == "Add as New Type":
                new_type_category = st.selectbox("Category:", ["Base Type", "Amenity"], key=f"new_cat_{unmatched_id}")
                new_type_name = st.text_input("Official Name:", value=unmatched_part.title(), key=f"new_name_{unmatched_id}")
            elif action == "Map to Existing":
                map_category = st.selectbox("Category:", ["Base Type", "Amenity"], key=f"map_cat_{unmatched_id}")
                existing_options = list(ticket_types_data['base_type_map' if map_category == "Base Type" else 'amenity_map'].keys())
                target_type = st.selectbox("Map to:", existing_options, key=f"map_target_{unmatched_id}")

        with col3:
            st.write("") # Spacer
            if st.button("Submit Action", key=f"submit_{unmatched_id}", use_container_width=True):
                if action == "Ignore":
                    database.delete_unmatched_ticket_type(unmatched_id)
                    st.toast(f"Ignored '{unmatched_part}'.")
                else: # Handle Add and Map
                    if action == "Add as New Type":
                        map_key = 'base_type_map' if new_type_category == "Base Type" else 'amenity_map'
                        ticket_types_data[map_key][new_type_name] = [unmatched_part.lower()]
                    elif action == "Map to Existing":
                        map_key = 'base_type_map' if map_category == "Base Type" else 'amenity_map'
                        ticket_types_data[map_key][target_type].append(unmatched_part.lower())
                    
                    with open(ticket_types_path, 'w') as f:
                        json.dump(ticket_types_data, f, indent=4, sort_keys=True)
                    database.delete_unmatched_ticket_type(unmatched_id)
                    st.success(f"Processed '{unmatched_part}'.")
                st.rerun()

def merge_external_db(uploaded_file):
    """
    Merges scrape data from an uploaded .db file into the current company's database.
    This function does not touch user data.
    """
    with st.spinner("Merging database... This may take a moment."):
        # Save uploaded file to a temporary path to be able to connect to it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp.write(uploaded_file.getvalue())
            source_db_path = tmp.name
        
        st.info("Merging scrape data from the uploaded database. This will not affect user accounts.")

        source_conn = None # Define here to ensure it's available in the finally block
        try:
            with database._get_db_connection() as master_conn:
                master_cursor = master_conn.cursor()
                source_conn = sqlite3.connect(source_db_path) # Connect to the source DB
                
                # Get a list of tables in the source DB to handle different schema versions
                source_cursor = source_conn.cursor()
                source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                source_tables = [row[0] for row in source_cursor.fetchall()]
                
                # 1. Merge all showings from source to master first.
                if 'showings' in source_tables:
                    showings_df = pd.read_sql_query("SELECT * FROM showings", source_conn)
                    if not showings_df.empty:
                        if 'showing_id' in showings_df.columns:
                            showings_df = showings_df.drop(columns=['showing_id'])
                        
                        showings_to_insert = showings_df.to_records(index=False).tolist()
                        master_cursor.executemany("""
                            INSERT OR IGNORE INTO showings 
                            (play_date, theater_name, film_title, showtime, format, daypart, ticket_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, showings_to_insert)
                        master_conn.commit()
                        st.write(f"  - Upserted {master_cursor.rowcount} showings from source database.")

                # 2. Merge all films from source to master.
                if 'films' in source_tables:
                    films_df = pd.read_sql_query("SELECT * FROM films", source_conn)
                    if not films_df.empty:
                        for _, film_row in films_df.iterrows():
                            database.upsert_film_details(film_row.to_dict())
                        st.write(f"  - Upserted {len(films_df)} film metadata records.")

                # 3. Iterate through runs and merge their data.
                runs_df = pd.read_sql_query("SELECT * FROM scrape_runs", source_conn)
                if runs_df.empty:
                    st.warning("No new runs to merge from the uploaded database.")
                    return

                # --- OPTIMIZATION: Fetch all existing runs once to avoid N+1 queries ---
                master_cursor.execute("SELECT run_timestamp, run_context FROM scrape_runs")
                existing_runs_set = set(master_cursor.fetchall())

                runs_merged_count = 0
                for index, run in runs_df.iterrows():
                    old_run_id = run['run_id']
                    
                    # Check if this exact run already exists to avoid duplicates
                    run_tuple = (run['run_timestamp'], run.get('run_context'))
                    if run_tuple in existing_runs_set:
                        st.write(f"  - Skipping run from {run['run_timestamp']} as it appears to already exist.")
                        continue

                    master_cursor.execute('INSERT INTO scrape_runs (run_timestamp, mode, run_context) VALUES (?, ?, ?)', (run['run_timestamp'], run['mode'], run.get('run_context')))
                    new_run_id = master_cursor.lastrowid
                    
                    # For each run, get its prices joined with showing details
                    if 'prices' in source_tables and 'showings' in source_tables:
                        prices_with_details_query = """
                            SELECT 
                                s.play_date, s.theater_name AS "Theater Name", s.film_title AS "Film Title", 
                                s.showtime AS "Showtime", s.format AS "Format", s.daypart AS "Daypart",
                                p.ticket_type AS "Ticket Type", p.price AS "Price", p.capacity AS "Capacity",
                                s.play_date
                            FROM prices p
                            JOIN showings s ON p.showing_id = s.showing_id
                            WHERE p.run_id = ?
                        """
                        prices_df = pd.read_sql_query(prices_with_details_query, source_conn, params=(old_run_id,))
                        
                        if not prices_df.empty:
                            prices_df['Price'] = prices_df['Price'].apply(lambda x: f"${x:.2f}")
                            try:
                                database.save_prices(new_run_id, prices_df)
                            except Exception as e:
                                print(f"Error in save_prices: {e}")
                    
                    if 'operating_hours' in source_tables:
                        op_hours_df = pd.read_sql_query(f"SELECT * FROM operating_hours WHERE run_id = {old_run_id}", source_conn)
                        if not op_hours_df.empty:
                            op_hours_df['run_id'] = new_run_id
                            if 'operating_hours_id' in op_hours_df.columns:
                                op_hours_df = op_hours_df.drop(columns=['operating_hours_id'])
                            op_hours_df.to_sql('operating_hours', master_conn, if_exists='append', index=False)

                    runs_merged_count += 1
                
                master_conn.commit()
                st.success(f"Successfully merged {runs_merged_count} new scrape runs and their associated data.")
        except Exception as e:
            st.error(f"An error occurred during the merge: {e}")
        finally:
            if source_conn:
                source_conn.close() # Explicitly close the connection before deleting
            os.remove(source_db_path)

async def discover_and_add_new_films_from_fandango():
    """Discovers new films from Fandango's main page and adds them to the database."""
    omdb_client = OMDbClient()
    discovered_titles = await scraper.discover_films_from_main_page()
    new_films = []
    existing_films = []
    failed_films = []

    for title in discovered_titles:
        if database.check_film_exists(title):
            existing_films.append(title)
        else:
            film_details = omdb_client.get_film_details(title)
            if film_details:
                film_details['film_title'] = title
                database.upsert_film_details(film_details)
                new_films.append(title)
            else:
                database.log_unmatched_film(title)
                failed_films.append({"Title": title, "Error": "Could not find match on OMDb."})
    return new_films, existing_films, failed_films

def discover_and_add_new_films_from_bom(year):
    """Discovers new films from Box Office Mojo for a given year and adds them."""
    bom_scraper = BoxOfficeMojoScraper()
    omdb_client = OMDbClient()
    discovered_films = bom_scraper.discover_films_by_year(year)
    new_films = []
    existing_films = []
    failed_films = []

    for film_info in discovered_films:
        title = film_info['title']
        if database.check_film_exists(title):
            existing_films.append(title)
        else:
            film_details = omdb_client.get_film_details(title)
            if film_details:
                film_details['film_title'] = title
                database.upsert_film_details(film_details)
                new_films.append(title)
            else:
                database.log_unmatched_film(title)
                failed_films.append({"Title": title, "Error": "Could not find match on OMDb."})
    return new_films, existing_films, failed_films

def _add_unmatched_ticket_type_local(unmatched_part, original_description):
    """
    Local implementation to add an unmatched ticket type to the database for review.
    This is a temporary fix until it can be moved to the central database module.
    """
    with database._get_db_connection() as conn:
        cursor = conn.cursor()
        # Insert a minimal record for review, ensuring NOT NULL constraints are met.
        cursor.execute(
            "INSERT INTO unmatched_ticket_types (unmatched_part, original_description, first_seen) VALUES (?, ?, ?)",
            (unmatched_part, original_description, datetime.datetime.now())
        )
        conn.commit()

def _render_ticket_type_editor():
    """Renders the UI for managing ticket type normalization mappings."""
    TICKET_TYPES_FILE = os.path.join(config.SCRIPT_DIR, 'ticket_types.json')

    # --- Helper Functions ---
    def load_ticket_types():
        try:
            with open(TICKET_TYPES_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"ticket_type_mappings": {}, "plf_formats": []}

    def save_ticket_types(data):
        with open(TICKET_TYPES_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        st.toast("✅ Ticket type mappings saved!")

    ticket_types_data = load_ticket_types()
    base_type_mappings = ticket_types_data.get("base_type_map", {})
    amenity_mappings = ticket_types_data.get("amenity_map", {})

    # --- Ticket Type Editor ---
    st.info(
        "Define how raw ticket types are normalized into standard categories (e.g., map 'children' to 'Child')."
    )

    with st.form("new_mapping_form"):
        col1, col2 = st.columns(2)
        canonical_name = col1.text_input("Standard Name (e.g., Child, Senior)")
        raw_variation = col2.text_input("Raw Variation (e.g., kids, senior citizen)")
        
        if st.form_submit_button("Add Mapping", use_container_width=True):
            if canonical_name and raw_variation:
                canonical_name = canonical_name.strip()
                raw_variation_lower = raw_variation.strip().lower()
                if canonical_name not in base_type_mappings:
                    base_type_mappings[canonical_name] = []
                if raw_variation_lower not in base_type_mappings[canonical_name]:
                    base_type_mappings[canonical_name].append(raw_variation_lower)
                    base_type_mappings[canonical_name].sort()
                    save_ticket_types(ticket_types_data)
                    st.rerun()
                else:
                    st.warning(f"The variation '{raw_variation}' already exists for '{canonical_name}'.")
            else:
                st.error("Both fields must be filled out.")

    st.markdown("##### Existing Mappings")
    if not base_type_mappings:
        st.info("No mappings defined yet.")
    else:
        sorted_canonical_names = sorted(base_type_mappings.keys())
        for name in sorted_canonical_names:
            with st.expander(f"**{name}** ({len(base_type_mappings[name])} variations)"):
                for i, variation in enumerate(base_type_mappings[name]):
                    cols = st.columns([0.7, 0.2, 0.1])
                    cols[0].text(variation)
                    if cols[1].button("Move to Amenities", key=f"move_base_{name}_{i}", help=f"Move '{variation}' to an amenity category."):
                        base_type_mappings[name].remove(variation)
                        if not base_type_mappings[name]:
                            del base_type_mappings[name]
                        _add_unmatched_ticket_type_local(unmatched_part=variation, original_description=f"Moved from Ticket Type '{name}'")
                        save_ticket_types(ticket_types_data)
                        st.toast(f"Moved '{variation}' to be re-categorized as an amenity.")
                        st.rerun()
                    if cols[2].button("❌", key=f"del_base_{name}_{i}", help=f"Remove '{variation}' and mark for rematching."):
                        base_type_mappings[name].remove(variation)
                        if not base_type_mappings[name]:
                            del base_type_mappings[name]
                        _add_unmatched_ticket_type_local(unmatched_part=variation, original_description=f"Removed from Ticket Type '{name}'")
                        save_ticket_types(ticket_types_data)
                        st.toast(f"Removed '{variation}' and marked for rematching.")
                        st.rerun()

def _render_amenity_editor():
    """Renders the UI for managing amenity normalization mappings."""
    TICKET_TYPES_FILE = os.path.join(config.SCRIPT_DIR, 'ticket_types.json')

    # --- Helper Functions ---
    def load_ticket_types():
        try:
            with open(TICKET_TYPES_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"ticket_type_mappings": {}, "plf_formats": []}

    def save_ticket_types(data):
        with open(TICKET_TYPES_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        st.toast("✅ Amenity mappings saved!")

    ticket_types_data = load_ticket_types()
    base_type_mappings = ticket_types_data.get("base_type_map", {})
    amenity_mappings = ticket_types_data.get("amenity_map", {})
    ignored_amenities = ticket_types_data.setdefault("ignored_amenities", [])

    # --- Amenity Editor ---
    st.info(
        "Define how raw format/amenity tags are normalized (e.g., map 'd-box' to 'D-BOX')."
    )

    with st.form("new_amenity_form"):
        col1, col2 = st.columns(2)
        canonical_name = col1.text_input("Standard Name (e.g., IMAX, 3D)")
        raw_variation = col2.text_input("Raw Variation (e.g., imax 2d, 3d format)")
        
        if st.form_submit_button("Add Amenity Mapping", use_container_width=True):
            if canonical_name and raw_variation:
                canonical_name = canonical_name.strip()
                raw_variation_lower = raw_variation.strip().lower()
                if canonical_name not in amenity_mappings:
                    amenity_mappings[canonical_name] = []
                if raw_variation_lower not in amenity_mappings[canonical_name]:
                    amenity_mappings[canonical_name].append(raw_variation_lower)
                    amenity_mappings[canonical_name].sort()
                    save_ticket_types(ticket_types_data)
                    st.rerun()
                else:
                    st.warning(f"The variation '{raw_variation}' already exists for '{canonical_name}'.")
            else:
                st.error("Both fields must be filled out.")

    st.markdown("##### Existing Amenity Mappings")
    if not amenity_mappings:
        st.info("No amenity mappings defined yet.")
    else:
        sorted_canonical_names = sorted(amenity_mappings.keys())
        for name in sorted_canonical_names:
            with st.expander(f"**{name}** ({len(amenity_mappings[name])} variations)"):
                for i, variation in enumerate(amenity_mappings[name]):
                    cols = st.columns([0.6, 0.2, 0.1, 0.1])
                    cols[0].text(variation)
                    if cols[1].button("Move to Ticket Types", key=f"move_amenity_{name}_{i}", help=f"Move '{variation}' to a ticket type category for re-categorization."):
                        amenity_mappings[name].remove(variation)
                        if not amenity_mappings[name]:
                            del amenity_mappings[name]
                        _add_unmatched_ticket_type_local(unmatched_part=variation, original_description=f"Moved from Amenity '{name}'")
                        save_ticket_types(ticket_types_data)
                        st.toast(f"Moved '{variation}' to be re-categorized.")
                        st.rerun()
                    if cols[2].button("Ignore", key=f"ignore_amenity_{name}_{i}", help=f"Add '{variation}' to the ignore list."):
                        amenity_mappings[name].remove(variation)
                        if not amenity_mappings[name]:
                            del amenity_mappings[name]
                        if variation not in ignored_amenities:
                            ignored_amenities.append(variation)
                            ignored_amenities.sort()
                        save_ticket_types(ticket_types_data)
                        st.toast(f"Added '{variation}' to the ignore list.")
                        st.rerun()
                    if cols[3].button("❌", key=f"del_amenity_{name}_{i}", help=f"Remove '{variation}' and mark for rematching."):
                        amenity_mappings[name].remove(variation)
                        if not amenity_mappings[name]:
                            del amenity_mappings[name]
                        _add_unmatched_ticket_type_local(unmatched_part=variation, original_description=f"Removed from Amenity '{name}'")
                        save_ticket_types(ticket_types_data)
                        st.toast(f"Removed '{variation}' and marked for rematching.")
                        st.rerun()

    st.divider()
    st.markdown("##### Ignored Amenities")
    st.info("These variations will be completely ignored during ticket type parsing. To use one again, remove it from this list and it will reappear in the 'Unmatched' queue for re-categorization.")
    if not ignored_amenities:
        st.info("No amenities are currently being ignored.")
    else:
        # Display in columns for better layout
        cols = st.columns(4)
        for i, ignored_item in enumerate(ignored_amenities):
            with cols[i % 4]:
                col1, col2 = st.columns([0.8, 0.2])
                col1.text(ignored_item)
                if col2.button("🗑️", key=f"unignore_{i}", help=f"Stop ignoring '{ignored_item}' and mark for re-categorization."):
                    ignored_amenities.remove(ignored_item)
                    _add_unmatched_ticket_type_local(unmatched_part=ignored_item, original_description="Removed from ignore list")
                    save_ticket_types(ticket_types_data)
                    st.toast(f"'{ignored_item}' will now be re-categorized.")
                    st.rerun()

def _render_database_tools():
    """Renders the UI for all database maintenance and enrichment tools."""
    st.header("Database Tools")
    
    st.subheader("Export/Import Database")
    st.info(f"This will prepare the database file for '{st.session_state.get('selected_company', 'the selected company')}' for download. This file can be merged into another Price Scout instance.")
    
    db_path = config.DB_FILE
    if db_path and os.path.exists(db_path):
        with open(db_path, "rb") as fp:
            st.download_button(
                label=f"Download {st.session_state.get('selected_company', 'current')} Database",
                data=fp,
                file_name=f"price_scout_{st.session_state.get('selected_company', 'export').replace(' ', '_')}.db",
                mime="application/x-sqlite3",
                use_container_width=True
            )
    else:
        st.warning("No database file found for the current company to export.")

    uploaded_db_file = st.file_uploader("Upload a .db file to merge into the current database", type="db", key="db_merger_uploader")
    if uploaded_db_file is not None:
        if st.button("Merge Uploaded Database", key="merge_db_button", use_container_width=True):
            merge_external_db(uploaded_db_file)
    st.divider()

    with st.expander("Discover New Films"):
        st.write("Discover new films from Fandango's main page or Box Office Mojo and add them to the database.")
        
        cols = st.columns(4)
        if cols[0].button("Discover New Films from Fandango", use_container_width=True):
            with st.spinner("Discovering new films from Fandango..."):
                thread, result_func = run_async_in_thread(discover_and_add_new_films_from_fandango)
                thread.join()
                status, result, log, _ = result_func()
                if status == 'success':
                    new_films, existing_films, failed_films = result
                    st.success(f"Discovery complete! Found {len(new_films)} new films, {len(existing_films)} existing, and {len(failed_films)} failed.")
                    if new_films:
                        st.write("New Films Added:")
                        st.dataframe(pd.DataFrame(new_films, columns=["Title"]), use_container_width=True)
                    if failed_films:
                        st.write("Failed to Add:")
                        st.dataframe(pd.DataFrame(failed_films, columns=["Title", "Error"]), use_container_width=True)
                else:
                    st.error(f"An error occurred: {get_error_message(result)}")
                    st.code(log)

        # --- FIX for UnboundLocalError ---
        bom_year = None 
        with cols[1]:
            bom_year = st.selectbox("Select Year", [None] + list(range(datetime.date.today().year, 2010, -1)), key="bom_year_select")

        if cols[2].button("Discover from Box Office Mojo", use_container_width=True, disabled=not bom_year):
            if bom_year:
                with st.spinner(f"Discovering films from {bom_year}..."):
                    thread, result_func = run_async_in_thread(discover_and_add_new_films_from_bom, bom_year)
                    thread.join()
                    status, result, log, _ = result_func()
                    if status == 'success':
                        new_films, existing_films, failed_films = result
                        st.success(f"Discovery complete! Found {len(new_films)} new films, {len(existing_films)} existing, and {len(failed_films)} failed.")
                        if new_films:
                            st.write("New Films Added:")
                            st.dataframe(pd.DataFrame(new_films, columns=["Title"]), use_container_width=True)
                        if failed_films:
                            st.write("Failed to Add:")
                            st.dataframe(pd.DataFrame(failed_films, columns=["Title", "Error"]), use_container_width=True)
                    else:
                        st.error(f"An error occurred: {get_error_message(result)}")
                        st.code(log)

    with st.expander("Manage Ticket Type Normalization"):
        _render_ticket_type_editor()

    with st.expander("Manage Amenity Normalization"):
        _render_amenity_editor()

    with st.expander("Consolidate Data"):
        st.subheader("Ticket Type Consolidation")
        st.info(
            "This tool will scan your database for ticket types that can be mapped to a standard (canonical) name "
            "based on the rules in `ticket_types.json`. For example, it will update all 'Children' entries to 'Child'."
        )
        if st.button("Consolidate All Ticket Types", use_container_width=True):
            with st.spinner("Consolidating ticket types in the database..."):
                updated_count = database.consolidate_ticket_types()
                if updated_count > 0:
                    st.success(f"Successfully consolidated {updated_count} ticket type records.")
                    st.rerun()
                else:
                    st.info("No ticket types needed consolidation.")

    with st.expander("Backfill Film Data"):
        st.write("Run processes to fill in missing data for films already in the database.")
        
        cols = st.columns(4)
        if cols[0].button("Backfill Missing Film Details", use_container_width=True):
            with st.spinner("Backfilling film details (MPAA rating, runtime, poster)..."):
                count = database.backfill_film_details_from_fandango()
                st.success(f"Successfully backfilled details for {count} films.")

        if cols[1].button("Backfill Missing IMDB IDs", use_container_width=True):
            with st.spinner("Backfilling IMDB IDs..."):
                count = database.backfill_imdb_ids_from_fandango()
                st.success(f"Successfully backfilled IMDB IDs for {count} films.")

        if cols[2].button("Backfill Missing Showtimes Data", use_container_width=True):
            with st.spinner("Backfilling showtimes data..."):
                count = database.backfill_showtimes_data_from_fandango()
                st.success(f"Successfully backfilled showtimes data for {count} films.")

def main():
    st.set_page_config(layout="wide")
    st.title("Data Quality & Enrichment")
    st.write("Manage data quality and perform database maintenance and enrichment.")

    st.header("Data Quality Tools")
    render_ticket_type_manager()
    st.divider()
    render_failed_film_matcher("db_unmatched")
    st.divider()
    _render_database_tools()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    main()
