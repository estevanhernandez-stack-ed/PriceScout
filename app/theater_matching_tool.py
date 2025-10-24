import streamlit as st
import pandas as pd
import json
import asyncio
import os
import re
import copy
import datetime
import glob
from thefuzz import fuzz

from app.scraper import Scraper
from app.config import PROJECT_DIR, CACHE_FILE
from app import utils

# Initialize the scraper
scraper = Scraper()

def get_markets_data(uploaded_file):
    """Loads and caches the markets.json data from an uploaded file."""
    if uploaded_file is not None:
        # To read file as string, decode it
        string_data = uploaded_file.getvalue().decode("utf-8")
        markets_data = json.loads(string_data)
        
        # Sanitize company names: replace None with parent company
        for parent_company, regions in markets_data.items():
            for region, markets in regions.items():
                for market, market_info in markets.items():
                    for theater in market_info.get('theaters', []):
                        if theater.get('company') is None:
                            theater['company'] = parent_company # Default to parent company if None
        
        st.session_state['markets_data'] = markets_data
        st.session_state['file_uploaded'] = True # Set the flag
        return st.session_state['markets_data']
    return None

def _strip_common_terms(name):
    """Removes common cinema brand names and amenities to improve matching."""
    name_lower = name.lower()
    # List of terms to remove
    terms_to_strip = [
        'amc', 'cinemark', 'marcus', 'regal', 'studio movie grill', 'b&b',
        'dine-in', 'imax', 'dolby', 'xd', 'ultrascreen', 'superscreen',
        'cinema', 'theatres', 'theaters', 'cine', 'movies'
    ]
    # Create a regex pattern to find any of these whole words
    pattern = r'\b(' + '|'.join(re.escape(term) for term in terms_to_strip) + r')\b'
    stripped_name = re.sub(pattern, ' ', name_lower)
    # Clean up extra punctuation and spaces
    cleaned_name = re.sub(r'[\s,&]+', ' ', stripped_name)
    return cleaned_name.strip()

def _extract_zip_from_market_name(market_name):
    """Extracts a 5-digit zip code from the end of a market name string."""
    match = re.search(r'\b(\d{5})\b$', market_name)
    return match.group(1) if match else None


async def process_market(market_name, market_theaters, progress_callback=None, threshold=55):
    """
    Processes a list of theaters in a market to find their best Fandango matches
    using a more robust, company-aware, multi-phase matching strategy.
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

    # --- Match processing function ---
    def find_best_match(theater, search_space, threshold):
        best_match, highest_score, match_type = None, 0, None
        original_company = utils._extract_company_name(theater['name'])

        # First pass for perfect matches
        for live_name, live_data in search_space.items():
            if fuzz.ratio(theater['name'].lower(), live_name.lower()) == 100:
                return live_data, 100, "Perfect"

        # Second pass for other matches
        original_name_stripped = _strip_common_terms(theater['name'])
        for live_name, live_data in search_space.items():
            live_name_stripped = _strip_common_terms(live_name)
            
            ratio_original = fuzz.token_set_ratio(theater['name'], live_name)
            ratio_stripped = fuzz.token_set_ratio(original_name_stripped, live_name_stripped)
            
            # Company-aware scoring
            live_company = utils._extract_company_name(live_name)
            company_match_bonus = 0
            if original_company != "Unknown" and live_company != "Unknown" and original_company == live_company:
                company_match_bonus = 10 # Add a bonus for matching companies

            final_score_original = ratio_original + company_match_bonus
            final_score_stripped = (ratio_stripped * 0.9) + company_match_bonus # Stripped score is already penalized

            if final_score_original > highest_score:
                highest_score = final_score_original
                best_match = live_data
                match_type = "Original"
            
            if final_score_stripped > highest_score:
                highest_score = final_score_stripped
                best_match = live_data
                match_type = "Stripped"

        if highest_score > threshold:
            return best_match, highest_score, match_type
        return None, 0, None

    initial_strict_threshold = 98 # User-defined strict threshold for initial match

    # --- Attempt to match all theaters from the main market cache ---
    theaters_to_find_in_fallback = []
    for theater in market_theaters:
        found_match, highest_ratio, match_type = find_best_match(theater, market_zip_cache, initial_strict_threshold)

        if found_match:
            results.append({'Original Name': theater['name'], 'Matched Fandango Name': found_match['name'], 'Match Score': f"{int(highest_ratio)}% ({match_type})", 'Matched Fandango URL': found_match['url']})
        else:
            theaters_to_find_in_fallback.append(theater)


    # --- Fallback 1: Search using individual theater ZIP codes ---
    if theaters_to_find_in_fallback:
        if progress_callback: progress_callback(0.5, "Fallback 1: Searching individual ZIPs concurrently...")
        
        individual_zips = {t.get('zip') for t in theaters_to_find_in_fallback if t.get('zip')}
        zips_to_search = individual_zips - {main_market_zip} 
        
        if zips_to_search:
            if progress_callback: progress_callback(0.5, f"Fallback 1: Searching {len(zips_to_search)} ZIPs concurrently...")
            tasks = [scraper.live_search_by_zip(zip_code, date_str) for zip_code in zips_to_search]
            all_zip_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in all_zip_results:
                if isinstance(result, dict):
                    market_zip_cache.update(result)
                elif isinstance(result, Exception):
                    print(f"    [WARN] A ZIP search failed during concurrent processing: {result}")

        still_unmatched = []
        for theater in theaters_to_find_in_fallback:
            found_match, highest_ratio, match_type = find_best_match(theater, market_zip_cache, threshold)
            if found_match:
                results.append({'Original Name': theater['name'], 'Matched Fandango Name': found_match['name'], 'Match Score': f"{int(highest_ratio)}% ({match_type})", 'Matched Fandango URL': found_match['url']})
            else:
                still_unmatched.append(theater)
        theaters_to_find_in_fallback = still_unmatched

    # --- Fallback 2: Targeted name search (Concurrent) ---
    if theaters_to_find_in_fallback:
        if progress_callback: progress_callback(0.7, f"Fallback 2: Starting concurrent targeted name searches for {len(theaters_to_find_in_fallback)} theaters...")
        
        async def _search_for_single_theater(theater):
            search_results = {}
            search_term = theater['name']
            stripped_search_term = _strip_common_terms(search_term)
            
            try:
                tasks = [scraper.live_search_by_name(search_term)]
                if stripped_search_term and stripped_search_term.lower() != search_term.lower():
                    tasks.append(scraper.live_search_by_name(stripped_search_term))
                
                task_results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in task_results:
                    if isinstance(result, dict):
                        search_results.update(result)
                    elif isinstance(result, Exception):
                        print(f"    [WARN] A name search for '{search_term}' failed: {result}")

            except Exception as e:
                print(f"    [WARN] Targeted search for '{search_term}' failed unexpectedly: {e}")
            
            return theater, search_results

        tasks = [_search_for_single_theater(theater) for theater in theaters_to_find_in_fallback]
        all_search_results = await asyncio.gather(*tasks)

        for i, (theater, search_results) in enumerate(all_search_results):
            if progress_callback: progress_callback(0.7 + (0.3 * (i + 1) / len(all_search_results)), f"Fallback 2: Matching {theater['name']}...")

            if search_results:
                best_match_from_fallback, highest_ratio_fallback, match_type_fb = find_best_match(theater, search_results, threshold)
                if best_match_from_fallback:
                    results.append({'Original Name': theater['name'], 'Matched Fandango Name': best_match_from_fallback['name'], 'Match Score': f"{int(highest_ratio_fallback)}% ({match_type_fb})", 'Matched Fandango URL': best_match_from_fallback['url']})
                else:
                    results.append({'Original Name': theater['name'], 'Matched Fandango Name': 'No match found', 'Match Score': '0%', 'Matched Fandango URL': ''})
            else:
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
                
                theaters_in_market = [
                    t for t in market_info.get('theaters', [])
                    if t.get('status') != 'Permanently Closed'
                ]
                if not theaters_in_market: continue

                matched_theaters_list = await process_market(market, theaters_in_market, threshold=threshold)

                zip_map = {t['name']: t.get('zip', 'N/A') for t in theaters_in_market}
                original_theater_company_map = {t['name']: t.get('company', company) for t in market_info.get('theaters', [])}
                for r in matched_theaters_list:
                    r['Zip Code'] = zip_map.get(r['Original Name'])
                    r['Company'] = original_theater_company_map.get(r['Original Name'], company)

                all_results.extend(matched_theaters_list)
                match_map = {m['Original Name']: m for m in matched_theaters_list}

                cache_theater_list = []
                for theater in market_info.get('theaters', []):
                    theater_company = theater.get('company', company)
                    if theater.get('status') == 'Permanently Closed':
                        cache_theater_list.append({"name": f"{theater['name']} (Permanently Closed)", "url": "N/A", "company": theater_company})
                        continue

                    match = match_map.get(theater['name'])
                    if match is not None:
                        if match['Matched Fandango Name'] in ['Permanently Closed', 'Confirmed Closed']:
                            cache_theater_list.append({"name": f"{theater['name']} (Permanently Closed)", "url": "N/A", "company": theater_company})
                        elif match['Matched Fandango Name'] == 'Not on Fandango':
                            cache_theater_list.append({"name": theater['name'], "url": match['Matched Fandango URL'], "not_on_fandango": True, "company": theater_company})
                        elif match['Matched Fandango Name'] in ['No match found']:
                            pass
                        else:
                            cache_theater_list.append({"name": match['Matched Fandango Name'], "url": match['Matched Fandango URL'], "company": theater_company})
                
                theater_cache["markets"][market] = {"theaters": cache_theater_list}

                for theater in updated_markets_data[company][region][market].get('theaters', []):
                    original_name = theater['name']
                    match = match_map.get(original_name)
                    if match is not None and match['Matched Fandango Name'] not in ['No match found', 'Permanently Closed', 'Confirmed Closed', 'Not on Fandango']:
                        theater['name'] = match['Matched Fandango Name']

    progress_bar.progress(1.0, text="Full scan complete!")
    return theater_cache, updated_markets_data, all_results


async def rematch_single_theater(theater_name, theater_zip, manual_url=None, new_manual_name=None, company=None, threshold=55):
    """
    Attempts to find a match for a single theater, with an option for a manual URL override.
    """
    if not company:
        company = utils._extract_company_name(theater_name)

    if manual_url:
        matched_name = new_manual_name if new_manual_name else theater_name
        if "fandango.com" in manual_url:
            return {
                'Original Name': theater_name, 
                'Matched Fandango Name': matched_name,
                'Match Score': '100%', 
                'Matched Fandango URL': manual_url,
                'Company': company
            }
        else:
            st.warning("Invalid manual URL provided. It must be a fandango.com URL.")
            return {
                'Original Name': theater_name, 
                'Matched Fandango Name': 'No match found', 
                'Match Score': '0%', 
                'Matched Fandango URL': '',
                'Company': company
            }

    theaters_to_process = [{'name': theater_name, 'zip': theater_zip}]
    results = await process_market("rematch_market", theaters_to_process, threshold=threshold)
    
    if results:
        result = results[0]
        result['Company'] = company
        return result
    else:
        return {
            'Original Name': theater_name, 
            'Matched Fandango Name': 'No match found', 
            'Match Score': '0%', 
            'Matched Fandango URL': '',
            'Company': company
        }

def regenerate_outputs_from_results(all_results_df, original_markets_data):
    theater_cache = {"metadata": {"last_updated": datetime.datetime.now().isoformat()}, "markets": {}}
    updated_markets_data = {}

    original_theater_map = {}
    for company, regions in original_markets_data.items():
        for region, markets in regions.items():
            for market, market_info in markets.items():
                for theater in market_info.get('theaters', []):
                    original_theater_map[theater['name']] = {
                        'region': region, 
                        'market': market, 
                        'data': theater,
                        'original_company': company
                    }

    for index, row in all_results_df.iterrows():
        original_name = row['Original Name']
        new_company = row['Company']
        
        original_info = original_theater_map.get(original_name)
        if not original_info: continue
        
        region = original_info['region']
        market = original_info['market']

        company_data = updated_markets_data.setdefault(new_company, {})
        region_data = company_data.setdefault(region, {})
        market_data = region_data.setdefault(market, {"theaters": []})
        
        new_theater_data = copy.deepcopy(original_info['data'])
        
        matched_name = row.get('Matched Fandango Name', 'No match found')
        matched_url = row.get('Matched Fandango URL', '')

        if matched_name not in ['No match found', 'Permanently Closed', 'Confirmed Closed', 'Not on Fandango']:
            new_theater_data['name'] = matched_name
            new_theater_data['url'] = matched_url
        elif matched_name == 'Not on Fandango':
            new_theater_data['url'] = matched_url
        
        market_data['theaters'].append(new_theater_data)

        cache_market = theater_cache['markets'].setdefault(market, {"theaters": []})
        if matched_name in ['Permanently Closed', 'Confirmed Closed']:
            cache_market['theaters'].append({"name": f"{original_name} (Permanently Closed)", "url": "N/A", "company": new_company})
        elif matched_name == 'Not on Fandango':
            cache_market['theaters'].append({"name": original_name, "url": matched_url, "not_on_fandango": True, "company": new_company})
        elif matched_name != 'No match found':
            cache_market['theaters'].append({"name": matched_name, "url": matched_url, "company": new_company})

    return theater_cache, updated_markets_data

@st.cache_data
def load_all_markets_data_from_disk():
    """Loads and caches all market data from all company directories on disk."""
    markets_data = {}
    data_dir = os.path.join(PROJECT_DIR, "data")
    for market_file in glob.glob(os.path.join(data_dir, '*', 'markets.json')):
        with open(market_file, 'r') as f:
            try:
                markets_data.update(json.load(f))
            except json.JSONDecodeError:
                st.warning(f"Could not load or parse {market_file}. Skipping.")
    return markets_data

async def rebuild_theater_cache(current_theater_cache, markets_data):
    """
    Rebuilds the theater cache by checking URL statuses and re-matching broken entries.
    """
    st.info("Starting theater cache rebuild...")
    updated_cache = copy.deepcopy(current_theater_cache)
    re_matched_count = 0
    skipped_count = 0
    failed_re_match_count = 0

    theaters_to_process = []
    for market_name, market_info in updated_cache.get("markets", {}).items():
        for theater in market_info.get("theaters", []):
            theaters_to_process.append({"market_name": market_name, "theater": theater})

    total_theaters = len(theaters_to_process)
    if total_theaters == 0:
        st.warning("No theaters in the current cache to rebuild.")
        return updated_cache, {"re_matched": 0, "skipped": 0, "failed": 0}

    progress_bar = st.progress(0, text="Rebuilding cache...")

    for i, item in enumerate(theaters_to_process):
        market_name = item["market_name"]
        theater = item["theater"]
        original_name = theater.get("name", "Unknown")
        current_url = theater.get("url")
        theater_company = theater.get("company")

        progress_text = f"Processing {original_name} ({i+1}/{total_theaters})"
        progress_bar.progress((i + 1) / total_theaters, text=progress_text)

        if "Permanently Closed" in original_name or theater.get("not_on_fandango"):
            skipped_count += 1
            continue

        is_url_active = False
        if current_url and current_url != "N/A":
            is_url_active = await scraper.check_url_status(current_url)

        if not is_url_active:
            st.warning(f"URL for {original_name} is broken or inactive. Attempting to re-match...")
            original_zip = None
            for comp, regions in markets_data.items():
                for reg, markets in regions.items():
                    if market_name in markets:
                        for original_t in markets[market_name].get("theaters", []):
                            if original_t.get("name") == original_name:
                                original_zip = original_t.get("zip")
                                break
                    if original_zip: break
                if original_zip: break

            rematch_result = await rematch_single_theater(
                original_name,
                original_zip,
                company=theater_company
            )

            match_name = rematch_result.get("Matched Fandango Name") if rematch_result else None
            if match_name and match_name not in ["No match found", "Permanently Closed", "Confirmed Closed"]:
                theater["name"] = rematch_result["Matched Fandango Name"]
                theater["url"] = rematch_result["Matched Fandango URL"]
                theater["company"] = rematch_result["Company"]
                if "not_on_fandango" in theater:
                    del theater["not_on_fandango"]
                re_matched_count += 1
                st.success(f"Successfully re-matched {original_name} to {theater['name']}.")
            else:
                # --- NEW: If re-match fails, revert to the original name from markets.json if possible ---
                # This makes it easier to identify and fix later.
                original_name_from_markets = original_name # Default to current name
                if original_zip:
                    for t in markets[market_name].get("theaters", []):
                        if t.get("zip") == original_zip:
                            original_name_from_markets = t.get("name", original_name)
                            break
                if not rematch_result or match_name == "No match found":
                    failed_re_match_count += 1
                    st.error(f"Failed to re-match '{original_name}'. Reverting to original name and marking as 'Not on Fandango'.")
                    theater["name"] = original_name_from_markets
                    theater["url"] = ""
                    theater["not_on_fandango"] = True
                    theater["company"] = theater_company
                elif match_name in ["Permanently Closed", "Confirmed Closed"]:
                    st.warning(f"Re-match for {original_name} found it is now permanently closed.")
                    theater["name"] = f"{original_name} (Permanently Closed)"
                    theater["url"] = "N/A"
                    if "not_on_fandango" in theater:
                        del theater["not_on_fandango"]
        else:
            # --- NEW: Notify user if a previously broken URL is now active ---
            if "not_on_fandango" in theater:
                del theater["not_on_fandango"]
                st.info(f"URL for '{original_name}' is now active. Removing 'Not on Fandango' flag.")

    # --- FIX: Update the timestamp after rebuilding ---
    if "metadata" not in updated_cache: updated_cache["metadata"] = {}
    updated_cache["metadata"]["last_updated"] = datetime.datetime.now().isoformat()

    progress_bar.empty()
    st.success(f"Cache rebuild complete! Re-matched: {re_matched_count}, Skipped: {skipped_count}, Failed: {failed_re_match_count}.")
    return updated_cache, {"re_matched": re_matched_count, "skipped": skipped_count, "failed": failed_re_match_count}

def render_attention_theater_form(index, row, form_type):
    """
    Renders a standardized form for a single theater that requires manual attention.
    """
    st.markdown("---")

    if form_type == 'rematch':
        title = f"**Original Name:** {row['Original Name']}"
        radio_options = ("Re-run Match", "Mark as Not on Fandango", "Mark as Closed")
        default_radio_index = 0
        show_re_evaluate_checkbox = False
        st.write(title)
    elif form_type == 'closed':
        title = f"**Original Name:** {row['Original Name']}"
        status_text = f"Status: **{row['Matched Fandango Name']}**"
        radio_options = ("Re-run Match", "Mark as Not on Fandango", "Mark as Closed")
        default_radio_index = 2
        show_re_evaluate_checkbox = True
    elif form_type == 'not_fandango':
        title = f"**Original Name:** {row['Original Name']}"
        status_text = f"Status: **{row['Matched Fandango Name']}**"
        radio_options = ("Re-run Match", "Mark as Not on Fandango", "Mark as Closed")
        default_radio_index = 1
        show_re_evaluate_checkbox = True
    else:
        return

    re_evaluate = True
    if show_re_evaluate_checkbox:
        col_name, col_status, col_link, col_re_evaluate = st.columns([3, 2, 3, 1])
        with col_name: st.write(title)
        with col_status: st.write(status_text)
        with col_link:
            if form_type == 'not_fandango' and row['Matched Fandango URL']:
                st.link_button("External Link", row['Matched Fandango URL'])
        with col_re_evaluate:
            re_evaluate = st.checkbox("Re-evaluate", key=f"re_evaluate_{form_type}_{index}")

    if re_evaluate:
        with st.form(key=f"form_{form_type}_{index}"):
            if show_re_evaluate_checkbox: st.write(f"Re-evaluating: **{row['Original Name']}**")
            new_name = st.text_input("Search Name", value=row['Original Name'], key=f"name_{form_type}_{index}")
            new_zip = st.text_input("ZIP Code", value=row.get('Zip Code', ''), key=f"zip_{form_type}_{index}")
            st.markdown("**Manual Override**")
            manual_url = st.text_input("Manual Fandango URL (Optional)", key=f"url_{form_type}_{index}")
            new_manual_name = st.text_input("New Theater Name (if renaming)", key=f"manual_name_{form_type}_{index}")
            action = st.radio("Action:", radio_options, key=f"action_{form_type}_{index}", index=default_radio_index)
            website_url = st.text_input("Theater Website URL (for 'Not on Fandango')", value=row.get('Matched Fandango URL', ''), key=f"website_url_{form_type}_{index}")

            if st.form_submit_button("Submit"):
                if action == "Re-run Match":
                    new_match_result = asyncio.run(rematch_single_theater(new_name, new_zip, manual_url, new_manual_name, company=row['Company']))
                    st.session_state['all_results_df'].loc[index, ['Matched Fandango Name', 'Match Score', 'Matched Fandango URL']] = [new_match_result['Matched Fandango Name'], new_match_result['Match Score'], new_match_result['Matched Fandango URL']]
                    if new_match_result['Matched Fandango Name'] != 'No match found':
                        st.success(f"Successfully re-matched '{new_match_result['Original Name']}' to '{new_match_result['Matched Fandango Name']}'.")
                elif action == "Mark as Not on Fandango":
                    st.session_state['all_results_df'].loc[index, ['Matched Fandango Name', 'Matched Fandango URL']] = ['Not on Fandango', website_url]
                elif action == "Mark as Closed":
                    st.session_state['all_results_df'].loc[index, 'Matched Fandango Name'] = 'Confirmed Closed'
                st.rerun()

def find_duplicate_theaters(markets_data):
    duplicates = {}
    for company, regions in markets_data.items():
        for region, markets in regions.items():
            for market, market_info in markets.items():
                theater_names = [t['name'] for t in market_info.get('theaters', [])]
                seen = set()
                market_duplicates = [name for name in theater_names if name in seen or seen.add(name)]
                if market_duplicates:
                    if market not in duplicates:
                        duplicates[market] = []
                    duplicates[market].extend(market_duplicates)
    return duplicates

def _render_onboarding_ui():
    """Renders the UI for onboarding a new company or running a full scan from a file."""
    latest_markets_file = None
    if 'selected_company' in st.session_state and st.session_state['selected_company']:
        try:
            selected_company_name = st.session_state['selected_company']
            potential_path = os.path.join(PROJECT_DIR, "data", selected_company_name, "markets.json")
            if os.path.exists(potential_path):
                latest_markets_file = potential_path
        except Exception as e:
            st.warning(f"Could not search for latest markets.json file for {st.session_state['selected_company']}: {e}")

    st.header("Cache Onboarding / Full Scan")
    st.info("Use this section to build the cache from a `markets.json` file. This is for initial setup or major updates.")

    col1, col2 = st.columns([3, 1])
    with col2:
        st.write("")
        st.write("")
        if latest_markets_file:
            if st.button("Load Latest markets.json", use_container_width=True):
                with open(latest_markets_file, 'r') as f:
                    string_data = f.read()
                    st.session_state['markets_data'] = json.loads(string_data)
                    st.session_state['markets_file_path'] = latest_markets_file
                    st.session_state['file_uploaded'] = False
                st.success(f"Loaded latest markets file: {os.path.basename(latest_markets_file)}")
                st.rerun()
    return col1.file_uploader("Choose your markets.json file", type="json")

def main():
    """Main function to render the Theater Matching page."""
    st.set_page_config(layout="wide")
    st.title("Theater Cache Management")

    # --- NEW: Onboarding Section ---
    with st.expander("Onboard New Company"):
        st.info(
            "Upload a new `markets.json` file to onboard a new company. "
            "The application will create the necessary folder structure in the `data` directory."
        )
        onboarding_file = st.file_uploader("Upload a new company's markets.json", type="json", key="onboarding_uploader")
        if onboarding_file is not None:
            if st.button("Onboard Company"):
                try:
                    string_data = onboarding_file.getvalue().decode("utf-8")
                    new_markets_data = json.loads(string_data)
                    
                    if not isinstance(new_markets_data, dict) or len(new_markets_data.keys()) != 1:
                        st.error("Invalid markets.json format. The file should contain a single parent company key at the top level.")
                    else:
                        parent_company = list(new_markets_data.keys())[0]
                        company_dir = os.path.join(PROJECT_DIR, 'data', parent_company)
                        os.makedirs(company_dir, exist_ok=True)
                        
                        new_markets_file_path = os.path.join(company_dir, 'markets.json')
                        with open(new_markets_file_path, 'w') as f:
                            json.dump(new_markets_data, f, indent=2)
                        
                        st.success(f"Successfully onboarded '{parent_company}'.")
                        st.info(f"The markets.json file has been saved to {new_markets_file_path}")
                        st.warning("Please restart the Price Scout application to see the new company in the selection list.")
                except Exception as e:
                    st.error(f"An error occurred during onboarding: {e}")
    st.divider()
    
    # --- NEW: Cache Maintenance Section ---
    st.header("Cache Maintenance")
    st.info("Use this tool for routine maintenance on the existing `theater_cache.json` file. It will check for broken URLs and attempt to re-match them without requiring a file upload.")

    if st.button("Rebuild Theater Cache", use_container_width=True, type="primary", help="Scans the existing cache for broken links and attempts to fix them."):
        if os.path.exists(CACHE_FILE):
            with st.spinner("Loading cache and market data..."):
                with open(CACHE_FILE, 'r') as f:
                    current_cache = json.load(f)
                # Load all markets data from disk to get ZIP codes for re-matching
                all_markets_data = load_all_markets_data_from_disk()

            updated_cache, rebuild_stats = asyncio.run(
                rebuild_theater_cache(current_cache, all_markets_data)
            )
            st.session_state['theater_cache_data'] = updated_cache

            try:
                backup_path = CACHE_FILE + ".rebuild_bak"
                if os.path.exists(CACHE_FILE):
                    if os.path.exists(backup_path): os.remove(backup_path)
                    os.rename(CACHE_FILE, backup_path)
                with open(CACHE_FILE, 'w') as f:
                    json.dump(updated_cache, f, indent=2)
                st.success(f"Rebuilt cache saved to {CACHE_FILE}. Backup created at {backup_path}")
            except Exception as e: # noqa: E722
                st.error(f"Error saving rebuilt cache: {e}")
        else:
            st.warning(f"No existing cache file found at `{CACHE_FILE}` to rebuild. Please build one using the 'Cache Onboarding' section below.")
    st.divider()

    uploaded_file = _render_onboarding_ui()

    if uploaded_file is not None: get_markets_data(uploaded_file)

    if st.session_state.get('markets_data'):
        if 'original_markets_data' not in st.session_state:
             st.session_state.original_markets_data = copy.deepcopy(st.session_state.get('markets_data'))

        markets_data = st.session_state['markets_data']
        duplicates = find_duplicate_theaters(markets_data)
        if duplicates:
            st.warning("Duplicate theater names found!")
            for market, names in duplicates.items():
                st.write(f"**{market}:** {', '.join(names)}")
            
            st.info("You can edit the markets.json file below to fix the duplicates.")
            edited_markets_json = st.text_area("markets.json", value=json.dumps(st.session_state['markets_data'], indent=2), height=300)
            if st.button("Save and Re-run Check"):
                try:
                    new_markets_data = json.loads(edited_markets_json)
                    st.session_state['markets_data'] = new_markets_data
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Invalid JSON format. Please check your edits.")
        else:
            markets_data = st.session_state['markets_data']
        st.sidebar.header("Configuration")
        match_threshold = st.sidebar.slider("Match Score Threshold", min_value=0, max_value=100, value=80, step=5)

        st.sidebar.header("Select Mode")
        mode = st.sidebar.radio("Mode", ["Single Market Mode", "Full Scan Mode"])

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
                            
                            zip_map = {t['name']: t.get('zip', 'N/A') for t in theaters_in_market}
                            for r in results: r['Zip Code'] = zip_map.get(r['Original Name'])

                            results_df = pd.DataFrame(results)
                            st.session_state['results_df'] = results_df
        
        elif mode == "Full Scan Mode":
            st.sidebar.info("This mode will scan all markets for a selected scope and generate a theater_cache.json file.")
            company_options = ["All Companies"] + list(markets_data.keys())
            selected_company = st.sidebar.selectbox("Parent Company", company_options)
            
            director_options = ["All Directors"]
            if selected_company and selected_company != "All Companies":
                director_options.extend(list(markets_data[selected_company].keys()))
            selected_director = st.sidebar.selectbox("Director", director_options)

            col1, col2 = st.sidebar.columns(2)
            with col1:
                if st.button("Start Full Scan"):
                    st.session_state.selected_company = selected_company if selected_company != "All Companies" else None
                    st.session_state.selected_director = selected_director

                    theater_cache, updated_markets, all_results = asyncio.run(
                        process_all_markets(markets_data, st.session_state.selected_company, selected_director, threshold=match_threshold)
                    )
                    st.session_state['theater_cache_data'] = theater_cache
                    if updated_markets:
                        st.session_state['updated_markets_data_all'] = updated_markets
                    if all_results:
                        st.session_state['all_results_df'] = pd.DataFrame(all_results)
            with col2:
                if st.button("Merge & Save to Cache"):
                    st.session_state.selected_company = selected_company if selected_company != "All Companies" else None
                    st.session_state.selected_director = selected_director

                    theater_cache, _, _ = asyncio.run(
                        process_all_markets(markets_data, st.session_state.selected_company, selected_director, threshold=match_threshold)
                    )
                    st.session_state['theater_cache_data'] = theater_cache
                    
                    try:
                        if os.path.exists(CACHE_FILE):
                            with open(CACHE_FILE, 'r') as f:
                                shared_cache = json.load(f)
                        else:
                            shared_cache = {"metadata": {}, "markets": {}}

                        shared_cache['markets'].update(theater_cache['markets'])
                        shared_cache['metadata']['last_updated'] = datetime.datetime.now().isoformat()

                        backup_path = CACHE_FILE + ".bak"
                        if os.path.exists(CACHE_FILE):
                            if os.path.exists(backup_path): os.remove(backup_path)
                            os.rename(CACHE_FILE, backup_path)
                        with open(CACHE_FILE, 'w') as f:
                            json.dump(shared_cache, f, indent=2)
                        st.success(f"Merged and saved to shared theater_cache.json. Backup created at {backup_path}")

                    except Exception as e: # noqa: E722
                        st.error(f"An error occurred while merging the cache: {e}") # type: ignore

        with st.sidebar.expander("Add a Theater"):
            with st.form("add_theater_form"):
                st.write("Add a new theater to the current markets data.")
                add_company = st.text_input("Parent Company")
                add_region = st.text_input("Director")
                add_market = st.text_input("Market")
                add_name = st.text_input("New Theater Name")
                add_zip = st.text_input("New Theater Zip Code")
                submitted = st.form_submit_button("Add Theater")
                if submitted:
                    if not all([add_company, add_region, add_market, add_name, add_zip]):
                        st.error("Please fill out all fields to add a theater.")
                    elif markets_data is None:
                        st.error("Internal error: Market data not found.")
                    else:
                        company_data = markets_data.setdefault(add_company, {})
                        region_data = company_data.setdefault(add_region, {})
                        market_data = region_data.setdefault(add_market, {"theaters": []})
                        market_data['theaters'].append({"name": add_name, "zip": add_zip})
                        st.success(f"Added '{add_name}' to {add_market}.")
                        st.rerun()

    if 'all_results_df' in st.session_state:
        st.header("Full Scan Complete")
        
        edited_df = st.data_editor(
            st.session_state['all_results_df'], 
            hide_index=True, 
            use_container_width=True,
            key="editor_all_markets"
        )
        st.session_state.all_results_df = edited_df

        theater_cache, updated_markets = regenerate_outputs_from_results(
            edited_df, 
            st.session_state.original_markets_data
        )
        
        duplicates = find_duplicate_theaters(updated_markets)
        disable_save = False
        if duplicates:
            st.warning("Duplicate theater names found in the potential new markets.json!")
            for market, names in duplicates.items():
                st.write(f"**{market}:** {', '.join(list(set(names)))}")
            st.error("Please fix the duplicates in the table above before saving.")
            disable_save = True

        with st.expander("Theaters Requiring Attention", expanded=True):
            needs_rematch_df = edited_df[edited_df['Matched Fandango Name'] == 'No match found']
            permanently_closed_df = edited_df[edited_df['Matched Fandango Name'].isin(['Permanently Closed', 'Confirmed Closed'])]
            not_on_fandango_df = edited_df[edited_df['Matched Fandango Name'] == 'Not on Fandango']

            if needs_rematch_df.empty and permanently_closed_df.empty and not_on_fandango_df.empty:
                st.write("No theaters requiring attention.")
            else:
                if not needs_rematch_df.empty:
                    st.subheader("Theaters with No Match Found")
                    for index, row in needs_rematch_df.iterrows():
                        render_attention_theater_form(index, row, 'rematch')

                if not permanently_closed_df.empty:
                    st.subheader("Permanently Closed Theaters")
                    for index, row in permanently_closed_df.iterrows():
                        render_attention_theater_form(index, row, 'closed')

                if not not_on_fandango_df.empty:
                    st.subheader("Theaters Not on Fandango")
                    for index, row in not_on_fandango_df.iterrows():
                        render_attention_theater_form(index, row, 'not_fandango')

        c1, c2, c3, c4 = st.columns(4)
        
        c1.download_button(
            label="Download theater_cache.json",
            data=json.dumps(theater_cache, indent=2),
            file_name="theater_cache.json",
            mime="application/json",
            use_container_width=True,
            key="download_theater_cache"
        )

        c2.download_button(
            label="Download markets.json",
            data=json.dumps(updated_markets, indent=2),
            file_name="markets.json",
            mime="application/json",
            use_container_width=True,
            key="download_markets_json"
        )

        if c3.button("Merge and Save to Shared Cache", use_container_width=True, disabled=disable_save, key="merge_and_save_shared_cache"):
            try:
                if os.path.exists(CACHE_FILE):
                    with open(CACHE_FILE, 'r') as f:
                        shared_cache = json.load(f)
                else:
                    shared_cache = {"metadata": {}, "markets": {}}

                shared_cache['markets'].update(theater_cache['markets'])
                shared_cache['metadata']['last_updated'] = datetime.datetime.now().isoformat()

                backup_path = CACHE_FILE + ".bak"
                if os.path.exists(CACHE_FILE):
                    if os.path.exists(backup_path): os.remove(backup_path)
                    os.rename(CACHE_FILE, backup_path)
                with open(CACHE_FILE, 'w') as f:
                    json.dump(shared_cache, f, indent=2)
                st.success(f"Merged and saved to shared theater_cache.json. Backup created at {backup_path}")

            except Exception as e:
                st.error(f"An error occurred while merging the cache: {e}")

        if c4.button("Save markets.json", use_container_width=True, disabled=disable_save, key="save_markets_json"):
            if 'markets_file_path' in st.session_state:
                file_path = st.session_state['markets_file_path']
                backup_path = file_path + ".bak"
                if os.path.exists(file_path):
                    if os.path.exists(backup_path): os.remove(backup_path)
                    os.rename(file_path, backup_path)
                with open(file_path, 'w') as f:
                    json.dump(updated_markets, f, indent=2)
                st.success(f"Saved new markets.json. Backup created at {backup_path}")