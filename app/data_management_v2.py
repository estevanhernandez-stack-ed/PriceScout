import streamlit as st
import pandas as pd
import json
from thefuzz import fuzz
import asyncio
import os
import sys
import re
import traceback
import copy
import datetime
import time
from scraper import Scraper # Assuming scraper.py is in the same directory
from config import PROJECT_DIR

# Initialize the scraper
scraper = Scraper()

def get_markets_data(uploaded_file):
    """Loads and caches the markets.json data from an uploaded file."""
    if uploaded_file is not None:
        # To read file as string, decode it
        string_data = uploaded_file.getvalue().decode("utf-8")
        st.session_state['markets_data'] = json.loads(string_data)
        return st.session_state['markets_data']
    return None

def _strip_common_terms(name):
    """Removes common cinema brand names and amenities to improve matching."""
    name_lower = name.lower()
    # List of terms to remove
    terms_to_strip = [
        'amc', 'cinemark', 'marcus', 'regal', 'movie tavern', 'studio movie grill',
        'dine-in', 'imax', 'dolby', 'xd', 'ultrascreen', 'superscreen',
        'cinema', 'theatres', 'theaters', 'cine', 'movies'
    ]
    # Create a regex pattern to find any of these whole words
    pattern = r'\b(' + '|'.join(re.escape(term) for term in terms_to_strip) + r')\b'
    stripped_name = re.sub(pattern, '', name_lower)
    # Clean up extra spaces
    return re.sub(r'\s+', ' ', stripped_name).strip()

def _extract_zip_from_market_name(market_name):
    """Extracts a 5-digit zip code from the end of a market name string."""
    match = re.search(r'\b(\d{5})\b$', market_name)
    return match.group(1) if match else None


async def process_market(market_name, market_theaters, progress_callback=None, threshold=55):
    """
    Processes a list of theaters in a market to find their best Fandango matches
    using a more robust multi-phase matching strategy.
    """
    results = []
    
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    date_str = tomorrow.strftime('%Y-%m-%d')
    market_zip_cache = {}

    # --- OPTIMIZATION: Phase 1 - Start with the main market ZIP ---
    if progress_callback: progress_callback(0.1, "Phase 1: Searching main market ZIP...")
    main_market_zip = _extract_zip_from_market_name(market_name)
    if main_market_zip:
        try:
            zip_results = await scraper.live_search_by_zip(main_market_zip, date_str)
            market_zip_cache.update(zip_results)
        except Exception:
            st.warning(f"Could not process main market ZIP {main_market_zip}.")

    # --- Attempt to match all theaters from the main market cache ---
    theaters_to_find_in_fallback = []
    for theater in market_theaters:
        if theater.get('status') == 'Permanently Closed':
            results.append({'Original Name': theater['name'], 'Matched Fandango Name': 'Permanently Closed', 'Match Score': 'N/A', 'Matched Fandango URL': 'N/A'})
            continue

        found_match, highest_ratio = None, 0
        original_name_stripped = _strip_common_terms(theater['name'])
        for live_name, live_data in market_zip_cache.items():
            live_name_stripped = _strip_common_terms(live_name)
            ratio_original = fuzz.token_sort_ratio(theater['name'], live_name)
            ratio_stripped = fuzz.token_sort_ratio(original_name_stripped, live_name_stripped)
            current_ratio = max(ratio_original, ratio_stripped)
            if current_ratio > highest_ratio:
                highest_ratio = current_ratio
                found_match = live_data
        
        if found_match and highest_ratio > threshold:
            results.append({'Original Name': theater['name'], 'Matched Fandango Name': found_match['name'], 'Match Score': f"{highest_ratio}%", 'Matched Fandango URL': found_match['url']})
        else:
            theaters_to_find_in_fallback.append(theater)

    # --- Fallback 1: Search using individual theater ZIP codes ---
    if theaters_to_find_in_fallback:
        if progress_callback: progress_callback(0.5, "Fallback 1: Searching individual ZIPs...")
        
        individual_zips = {t.get('zip') for t in theaters_to_find_in_fallback if t.get('zip')}
        # Only search zips we haven't already searched
        zips_to_search = individual_zips - {main_market_zip} 
        
        for zip_code in zips_to_search:
            try:
                zip_results = await scraper.live_search_by_zip(zip_code, date_str)
                market_zip_cache.update(zip_results)
            except Exception:
                st.warning(f"Could not process ZIP {zip_code}.")

        still_unmatched = []
        for theater in theaters_to_find_in_fallback:
            found_match, highest_ratio = None, 0
            original_name_stripped = _strip_common_terms(theater['name'])
            for live_name, live_data in market_zip_cache.items():
                live_name_stripped = _strip_common_terms(live_name)
                ratio_original = fuzz.token_sort_ratio(theater['name'], live_name)
                ratio_stripped = fuzz.token_sort_ratio(original_name_stripped, live_name_stripped)
                current_ratio = max(ratio_original, ratio_stripped)
                if current_ratio > highest_ratio:
                    highest_ratio = current_ratio
                    found_match = live_data
            
            if found_match and highest_ratio > threshold:
                results.append({'Original Name': theater['name'], 'Matched Fandango Name': found_match['name'], 'Match Score': f"{highest_ratio}%", 'Matched Fandango URL': found_match['url']})
            else:
                still_unmatched.append(theater)
        theaters_to_find_in_fallback = still_unmatched

    # --- Fallback 2: Targeted name search ---
    if theaters_to_find_in_fallback:
        for i, theater in enumerate(theaters_to_find_in_fallback):
            if progress_callback: progress_callback(0.7 + (0.3 * (i + 1) / len(theaters_to_find_in_fallback)), f"Fallback 2: Targeted search for {theater['name']}...")
            
            search_results = {}
            try:
                # Attempt 1: Search with the full name
                full_name_results = await scraper.live_search_by_name(theater['name'])
                if full_name_results: search_results.update(full_name_results)

                # Attempt 2: If full name search yields few results, try with a stripped name
                stripped_search_term = _strip_common_terms(theater['name'])
                if stripped_search_term and stripped_search_term.lower() != theater['name'].lower():
                    # Avoid re-searching if the stripped name is what we already searched
                    if not any(stripped_search_term in name for name in search_results.keys()):
                        print(f"    [INFO] Full name search produced few results. Retrying with stripped name: '{stripped_search_term}'")
                        stripped_name_results = await scraper.live_search_by_name(stripped_search_term)
                        if stripped_name_results: search_results.update(stripped_name_results)

                if search_results:
                    best_match_from_fallback, highest_ratio_fallback = None, 0
                    original_name_stripped_fb = _strip_common_terms(theater['name'])
                    for fandango_name, details in search_results.items():
                        live_name_stripped_fb = _strip_common_terms(fandango_name)
                        ratio_original_fb = fuzz.token_sort_ratio(theater['name'], fandango_name)
                        ratio_stripped_fb = fuzz.token_sort_ratio(original_name_stripped_fb, live_name_stripped_fb)
                        current_ratio_fb = max(ratio_original_fb, ratio_stripped_fb)
                        if current_ratio_fb > highest_ratio_fallback:
                            highest_ratio_fallback = current_ratio_fb
                            best_match_from_fallback = details
                    
                    if best_match_from_fallback:
                        results.append({'Original Name': theater['name'], 'Matched Fandango Name': best_match_from_fallback['name'], 'Match Score': f"{highest_ratio_fallback}%", 'Matched Fandango URL': best_match_from_fallback['url']})
                    else: raise ValueError("No suitable match.")
                else: raise ValueError("No results from name search.")
            except Exception:
                results.append({'Original Name': theater['name'], 'Matched Fandango Name': 'No match found', 'Match Score': '0%', 'Matched Fandango URL': ''})

    if progress_callback: progress_callback(1.0, "Complete!")
    return results


async def process_all_markets(markets_data, selected_company=None, selected_director=None, threshold=55):
    """Iterates through selected scopes and processes them to build a theater_cache.json structure."""
    theater_cache = {"metadata": {"last_updated": datetime.datetime.now().isoformat()}, "markets": {}}
    updated_markets_data = copy.deepcopy(markets_data)
    all_results = []
    data_to_process = {}
    if selected_company and selected_company in markets_data:
        data_to_process[selected_company] = markets_data[selected_company]
        if selected_director and selected_director != "All Directors" and selected_director in data_to_process[selected_company]:
            data_to_process = {selected_company: {selected_director: markets_data[selected_company][selected_director]}}
    else: 
        data_to_process = markets_data

    total_markets = sum(len(markets) for regions in data_to_process.values() for markets in regions.values())
    if total_markets == 0:
        st.warning("No markets found for the selected scope.")
        return None, None, None

    progress_bar = st.progress(0, text="Starting full scan...")
    processed_markets = 0
    for company, regions in data_to_process.items():
        for region, markets in regions.items():
            for market, market_info in markets.items():
                processed_markets += 1
                progress_text = f"Processing Market {processed_markets}/{total_markets}: {market}"
                progress_bar.progress(processed_markets / total_markets, text=progress_text)
                
                theaters_in_market = market_info.get('theaters', [])
                if not theaters_in_market: continue

                matched_theaters_list = await process_market(market, theaters_in_market, threshold=threshold)

                # Add original zip back for display
                zip_map = {t['name']: t.get('zip', 'N/A') for t in theaters_in_market}
                for r in matched_theaters_list: r['Zip Code'] = zip_map.get(r['Original Name'])

                all_results.extend(matched_theaters_list)
                match_map = {m['Original Name']: m for m in matched_theaters_list}

                cache_theater_list = []
                for theater in theaters_in_market:
                    match = match_map.get(theater['name'])
                    if match is not None:
                        if match['Matched Fandango Name'] in ['Permanently Closed', 'Confirmed Closed']:
                            cache_theater_list.append({"name": f"{theater['name']} (Permanently Closed)", "url": "N/A"})
                        elif match['Matched Fandango Name'] in ['No match found', 'Not on Fandango']:
                            pass # Exclude from theater_cache
                        else:
                            cache_theater_list.append({"name": match['Matched Fandango Name'], "url": match['Matched Fandango URL']})
                
                theater_cache["markets"][market] = {"theaters": cache_theater_list}

                # Update the markets_data with the new names
                for theater in updated_markets_data[company][region][market].get('theaters', []):
                    original_name = theater['name']
                    match = match_map.get(original_name)
                    if match is not None and match['Matched Fandango Name'] not in ['No match found', 'Permanently Closed', 'Confirmed Closed', 'Not on Fandango']:
                        theater['name'] = match['Matched Fandango Name']

    progress_bar.progress(1.0, text="Full scan complete!")
    return theater_cache, updated_markets_data, all_results


async def rematch_single_theater(theater_name, theater_zip, manual_url=None, new_manual_name=None, threshold=55):
    """
    Attempts to find a match for a single theater, with an option for a manual URL override.
    """
    if manual_url:
        # If a new name is provided, use it. Otherwise, use the original name.
        matched_name = new_manual_name if new_manual_name else theater_name
        # Basic validation for the URL
        if "fandango.com" in manual_url:
            # To get a more official name, we could try to scrape the title from the URL,
            # but for now, we'll just use the name provided.
            return {
                'Original Name': theater_name, 
                'Matched Fandango Name': matched_name, # Or a placeholder like "Manual Entry"
                'Match Score': '100%', 
                'Matched Fandango URL': manual_url
            }
        else:
            st.warning("Invalid manual URL provided. It must be a fandango.com URL.")
            # Return a no-match so it remains in the unmatched list
            return {
                'Original Name': theater_name, 
                'Matched Fandango Name': 'No match found', 
                'Match Score': '0%', 
                'Matched Fandango URL': ''
            }

    # If no manual URL, proceed with the standard matching process
    theaters_to_process = [{'name': theater_name, 'zip': theater_zip}]
    
    # Use a dummy market name since it's not relevant for a single theater
    # The progress callback is omitted for this single run.
    results = await process_market("rematch_market", theaters_to_process, threshold=threshold)
    
    if results:
        # process_market returns a list, we need the first element
        return results[0]
    else:
        # If process_market returns nothing, it's a failed match
        return {
            'Original Name': theater_name, 
            'Matched Fandango Name': 'No match found', 
            'Match Score': '0%', 
            'Matched Fandango URL': ''
        }

def regenerate_outputs_from_results(all_results_df, original_markets_data):
    """
    Re-generates the theater_cache and updated_markets data from an updated
    results dataframe.
    """
    theater_cache = {"metadata": {"last_updated": datetime.datetime.now().isoformat()}, "markets": {}}
    updated_markets_data = copy.deepcopy(original_markets_data)
    
    match_map = {row['Original Name']: row for index, row in all_results_df.iterrows()}

    for company, regions in original_markets_data.items():
        for region, markets in regions.items():
            for market, market_info in markets.items():
                theaters_in_market = market_info.get('theaters', [])
                if not theaters_in_market: continue

                cache_theater_list = []
                for theater in theaters_in_market:
                    match = match_map.get(theater['name'])
                    if match is not None:
                        if match['Matched Fandango Name'] in ['Permanently Closed', 'Confirmed Closed']:
                            cache_theater_list.append({"name": f"{theater['name']} (Permanently Closed)", "url": "N/A"})
                        elif match['Matched Fandango Name'] in ['No match found', 'Not on Fandango']:
                            pass # Exclude from theater_cache
                        else:
                            cache_theater_list.append({"name": match['Matched Fandango Name'], "url": match['Matched Fandango URL']})
                
                if cache_theater_list:
                    theater_cache["markets"][market] = {"theaters": cache_theater_list}

                # Update the markets_data with the new names
                for theater in updated_markets_data[company][region][market].get('theaters', []):
                    original_name = theater['name']
                    match = match_map.get(original_name)
                    if match is not None and match['Matched Fandango Name'] not in ['No match found', 'Permanently Closed', 'Confirmed Closed', 'Not on Fandango']:
                        theater['name'] = match['Matched Fandango Name']

    return theater_cache, updated_markets_data


def main():
    st.set_page_config(layout="wide")
    st.title("Theater Name Matching Tool")
    st.write("This tool helps you match theater names from your `markets.json` file with their official names on Fandango.")

    uploaded_file = st.file_uploader("Choose your markets.json file", type="json")
    
    if 'markets_data' not in st.session_state: st.session_state['markets_data'] = None
    if uploaded_file is not None: get_markets_data(uploaded_file)

    if st.session_state.get('markets_data'):
        markets_data = st.session_state['markets_data']
        st.sidebar.header("Configuration")
        match_threshold = st.sidebar.slider("Match Score Threshold", min_value=0, max_value=100, value=55, step=5)

        st.sidebar.header("Select Mode")
        mode = st.sidebar.radio("Mode", ["Single Market Mode", "All Markets Mode"])

        if mode == "Single Market Mode":
            st.sidebar.header("Select a Market")
            parent_company = st.sidebar.selectbox("Parent Company", list(markets_data.keys()))
            if parent_company and markets_data.get(parent_company):
                regions = markets_data[parent_company]
                region_name = st.sidebar.selectbox("Director", list(regions.keys()))
                if region_name and regions.get(region_name):
                    markets = regions[region_name]
                    market_name = st.sidebar.selectbox("Market", list(markets.keys()))
                    if market_name and markets.get(market_name):
                        theaters_in_market = markets[market_name].get('theaters', [])
                        st.sidebar.info(f"Found {len(theaters_in_market)} theaters in {market_name}.")
                        if st.sidebar.button("Start Matching"):
                            st.session_state['market_name'] = market_name
                            progress_bar = st.progress(0, text="Starting...")
                            def update_progress(val, text): progress_bar.progress(val, text)
                            results = asyncio.run(process_market(market_name, theaters_in_market, update_progress, threshold=match_threshold))
                            
                            # Add original zip back for display
                            zip_map = {t['name']: t.get('zip', 'N/A') for t in theaters_in_market}
                            for r in results: r['Zip Code'] = zip_map.get(r['Original Name'])

                            results_df = pd.DataFrame(results)
                            st.session_state['results_df'] = results_df
        
        elif mode == "All Markets Mode":
            st.sidebar.info("This mode will scan all markets for a selected scope and generate a theater_cache.json file.")
            selected_company = st.sidebar.selectbox("Parent Company", list(markets_data.keys()))
            if selected_company and markets_data.get(selected_company):
                director_options = ["All Directors"] + list(markets_data[selected_company].keys())
                selected_director = st.sidebar.selectbox("Director", director_options)
                if st.sidebar.button("Start Full Scan"):
                    st.session_state.selected_company = selected_company
                    theater_cache, updated_markets, all_results = asyncio.run(process_all_markets(markets_data, selected_company, selected_director, threshold=match_threshold))
                    st.session_state['theater_cache_data'] = theater_cache
                    if updated_markets:
                        st.session_state['updated_markets_json_all'] = json.dumps(updated_markets, indent=2)
                    if all_results:
                        st.session_state['all_results_df'] = pd.DataFrame(all_results)
        
        with st.sidebar.expander("Add a Theater"):
            with st.form("add_theater_form"):
                st.write("Add a new theater to the current markets data.")
                add_company = st.text_input("Parent Company")
                add_region = st.text_input("Director")
                add_market = st.text_input("Market")
                add_name = st.text_input("New Theater Name")
                add_zip = st.text_input("New Theater Zip Code")
                submitted = st.form_submit_button("Add Theater")
                if submitted and all([add_company, add_region, add_market, add_name, add_zip]):
                    company_data = st.session_state['markets_data'].setdefault(add_company, {})
                    region_data = company_data.setdefault(add_region, {})
                    market_data = region_data.setdefault(add_market, {"theaters": []})
                    market_data['theaters'].append({"name": add_name, "zip": add_zip})
                    st.success(f"Added '{add_name}' to {add_market}.")
                    st.rerun()
                elif submitted:
                    st.error("Please fill out all fields to add a theater.")

    if 'results_df' in st.session_state:
        st.header("Matching Results")
        results_df = st.session_state['results_df'].copy()

        # --- Charting Section ---
        st.subheader("Results Overview")
        
        # Calculate stats
        total_theaters = len(results_df)
        unmatched_theaters = results_df[results_df['Matched Fandango Name'] == 'No match found']
        num_unmatched = len(unmatched_theaters)
        num_matched = total_theaters - num_unmatched
        
        col1, col2, col3 = st.columns(3)
        col1.metric(label="Total Theaters Processed", value=total_theaters)
        col2.metric(label="Theaters Matched", value=num_matched)
        col3.metric(label="Theaters Unmatched", value=num_unmatched)

        if num_matched > 0:
            # Prepare data for chart
            chart_df = results_df.copy()
            chart_df['Match Score Int'] = pd.to_numeric(chart_df['Match Score'].str.replace('%', ''), errors='coerce').fillna(0)
            st.subheader("Match Score Distribution")
            
            score_data = chart_df[chart_df['Match Score Int'] > 0]
            if not score_data.empty:
                st.bar_chart(score_data.set_index('Original Name')['Match Score Int'])

        # --- End Charting Section ---

        results_df['Manual Search'] = results_df['Zip Code'].apply(lambda z: f"https://www.fandango.com/{z}_movietimes" if z and z != 'N/A' else None)
        edited_df = st.data_editor(results_df, column_config={"Matched Fandango URL": st.column_config.LinkColumn(), "Manual Search": st.column_config.LinkColumn(display_text="Open Search"), "Zip Code": None}, hide_index=True, use_container_width=True, column_order=["Original Name", "Matched Fandango Name", "Match Score", "Matched Fandango URL", "Manual Search"])
        st.success("Matching complete. You can now review and edit the matches above.")

        with st.expander("Theaters Requiring Attention", expanded=True):
            unmatched_df = edited_df[edited_df['Matched Fandango Name'].isin(['No match found', 'Permanently Closed'])]
            if unmatched_df.empty:
                st.write("No theaters requiring attention.")
            else:
                st.write("The following theaters could not be matched or are marked as closed.")
                for index, row in unmatched_df.iterrows():
                    st.markdown("---")
                    with st.form(key=f"form_{index}"):
                        st.write(f"**Original Name:** {row['Original Name']}")
                        new_name = st.text_input("Search Name", value=row['Original Name'], key=f"name_{index}")
                        new_zip = st.text_input("ZIP Code", value=row['Zip Code'], key=f"zip_{index}")
                        st.markdown("**Manual Override**")
                        manual_url = st.text_input("Manual Fandango URL (Optional)", key=f"url_{index}")
                        new_manual_name = st.text_input("New Theater Name (if renaming)", key=f"manual_name_{index}")
                        
                        action = st.radio("Action:", ("Re-run Match", "Mark as Not on Fandango", "Mark as Closed"), key=f"action_{index}")

                        if st.form_submit_button("Submit"):
                            if action == "Re-run Match":
                                new_match_result = asyncio.run(rematch_single_theater(new_name, new_zip, manual_url, new_manual_name, threshold=match_threshold))
                                st.session_state['results_df'].loc[index, 'Matched Fandango Name'] = new_match_result['Matched Fandango Name']
                                st.session_state['results_df'].loc[index, 'Match Score'] = new_match_result['Match Score']
                                st.session_state['results_df'].loc[index, 'Matched Fandango URL'] = new_match_result['Matched Fandango URL']
                                if new_match_result['Matched Fandango Name'] != 'No match found':
                                    st.success(f"Successfully re-matched '{new_match_result['Original Name']}' to '{new_match_result['Matched Fandango Name']}'.")
                                    time.sleep(2)
                            elif action == "Mark as Not on Fandango":
                                st.session_state['results_df'].loc[index, 'Matched Fandango Name'] = 'Not on Fandango'
                                st.success(f"'{row['Original Name']}' has been marked as Not on Fandango.")
                                time.sleep(1)
                            elif action == "Mark as Closed":
                                st.session_state['results_df'].loc[index, 'Matched Fandango Name'] = 'Confirmed Closed'
                                st.success(f"'{row['Original Name']}' has been confirmed as closed.")
                                time.sleep(1)
                            st.rerun()
        
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Save Results as CSV"):
                data_dir = "data"
                os.makedirs(data_dir, exist_ok=True)
                file_market_name = st.session_state.get('market_name', 'results').replace(" ", "_")
                file_path = os.path.join(data_dir, f'{file_market_name}_fandango_matches.csv')
                download_df = edited_df.drop(columns=['Manual Search'])
                download_df.to_csv(file_path, index=False)
                st.success(f"Results saved to `{file_path}`")

        with col2:
            if st.button("Generate and Save Updated markets.json"):
                updated_markets_data = copy.deepcopy(st.session_state['markets_data'])
                
                match_map = edited_df.set_index('Original Name')['Matched Fandango Name'].to_dict()

                for company, regions in updated_markets_data.items():
                    for region, markets in regions.items():
                        if st.session_state.get('market_name') in markets:
                             for theater in markets[st.session_state.get('market_name')].get('theaters', []):
                                original_name = theater['name']
                                new_name = match_map.get(original_name)
                                
                                if new_name and new_name not in ['No match found', 'Permanently Closed', 'Confirmed Closed', 'Not on Fandango']:
                                    theater['name'] = new_name

                updated_json_str = json.dumps(updated_markets_data, indent=2)
                
                data_dir = "data"
                os.makedirs(data_dir, exist_ok=True)
                file_path = os.path.join(data_dir, "markets_updated.json")
                with open(file_path, 'w') as f:
                    f.write(updated_json_str)
                st.success(f"Updated markets file saved to `{file_path}`")

    if 'theater_cache_data' in st.session_state:
        st.header("Full Scan Complete")
        
        if 'all_results_df' in st.session_state:
            st.dataframe(st.session_state['all_results_df'])

            with st.expander("Theaters Requiring Attention", expanded=True):
                unmatched_df = st.session_state['all_results_df'][st.session_state['all_results_df']['Matched Fandango Name'].isin(['No match found', 'Permanently Closed'])]
                if unmatched_df.empty:
                    st.write("No theaters requiring attention.")
                else:
                    st.write("The following theaters could not be matched or are marked as closed.")
                    for index, row in unmatched_df.iterrows():
                        st.markdown("---")
                        with st.form(key=f"form_all_{index}"):
                            st.write(f"**Original Name:** {row['Original Name']}")
                            new_name = st.text_input("Search Name", value=row['Original Name'], key=f"name_all_{index}")
                            zip_value = row.get('Zip Code', '') 
                            new_zip = st.text_input("ZIP Code", value=zip_value, key=f"zip_all_{index}")
                            st.markdown("**Manual Override**")
                            manual_url = st.text_input("Manual Fandango URL (Optional)", key=f"url_all_{index}")
                            new_manual_name = st.text_input("New Theater Name (if renaming)", key=f"manual_name_all_{index}")
                            
                            action = st.radio("Action:", ("Re-run Match", "Mark as Not on Fandango", "Mark as Closed"), key=f"action_all_{index}")

                            if st.form_submit_button("Submit"):
                                if action == "Re-run Match":
                                    new_match_result = asyncio.run(rematch_single_theater(new_name, new_zip, manual_url, new_manual_name))
                                    st.session_state['all_results_df'].loc[index, 'Matched Fandango Name'] = new_match_result['Matched Fandango Name']
                                    st.session_state['all_results_df'].loc[index, 'Match Score'] = new_match_result['Match Score']
                                    st.session_state['all_results_df'].loc[index, 'Matched Fandango URL'] = new_match_result['Matched Fandango URL']
                                    if new_match_result['Matched Fandango Name'] != 'No match found':
                                        st.success(f"Successfully re-matched '{new_match_result['Original Name']}' to '{new_match_result['Matched Fandango Name']}'.")
                                        time.sleep(2)
                                elif action == "Mark as Not on Fandango":
                                    st.session_state['all_results_df'].loc[index, 'Matched Fandango Name'] = 'Not on Fandango'
                                    st.success(f"'{row['Original Name']}' has been marked as Not on Fandango.")
                                    time.sleep(1)
                                elif action == "Mark as Closed":
                                    st.session_state['all_results_df'].loc[index, 'Matched Fandango Name'] = 'Confirmed Closed'
                                    st.success(f"'{row['Original Name']}' has been confirmed as closed.")
                                    time.sleep(1)
                                st.rerun()

        st.success("The new theater cache has been generated. You can download it below, or re-generate it after making corrections.")

        if st.button("Re-generate and Save Output Files"):
            theater_cache, updated_markets = regenerate_outputs_from_results(st.session_state['all_results_df'], st.session_state['markets_data'])
            st.session_state['theater_cache_data'] = theater_cache
            st.session_state['updated_markets_json_all'] = json.dumps(updated_markets, indent=2)
            st.success("Output files have been re-generated with your corrections.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Backup Old and Replace theater_cache.json"):
                file_path = os.path.join(PROJECT_DIR, "app", "theater_cache.json")
                if os.path.exists(file_path):
                    os.rename(file_path, file_path + ".bak")
                    st.info("Backed up existing theater_cache.json to theater_cache.json.bak")
                with open(file_path, 'w') as f:
                    json.dump(st.session_state['theater_cache_data'], f, indent=2)
                st.success(f"Theater cache saved to `{file_path}`")

            if st.button("Restore Old theater_cache.json"):
                file_path = os.path.join(PROJECT_DIR, "app", "theater_cache.json")
                backup_path = file_path + ".bak"
                if os.path.exists(backup_path):
                    os.rename(backup_path, file_path)
                    st.success("Restored theater_cache.json from backup.")
                else:
                    st.warning("No backup file found.")

        with col2:
            if st.button("Backup Old and Replace markets.json"):
                selected_company = st.session_state.get('selected_company', 'Unknown')
                file_path = os.path.join(PROJECT_DIR, "data", selected_company, "markets.json")
                if os.path.exists(file_path):
                    os.rename(file_path, file_path + ".bak")
                    st.info(f"Backed up existing markets.json to markets.json.bak in {selected_company} folder")
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w') as f:
                    f.write(st.session_state['updated_markets_json_all'])
                st.success(f"Updated markets file saved to `{file_path}`")

            if st.button("Restore Old markets.json"):
                selected_company = st.session_state.get('selected_company', 'Unknown')
                file_path = os.path.join(PROJECT_DIR, "data", selected_company, "markets.json")
                backup_path = file_path + ".bak"
                if os.path.exists(backup_path):
                    os.rename(backup_path, file_path)
                    st.success("Restored markets.json from backup.")
                else:
                    st.warning("No backup file found.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    main()