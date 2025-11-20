import re
import json
import datetime
import os
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import streamlit as st
import random

from app.config import DEBUG_DIR, CACHE_FILE

class Scraper:
    def __init__(self, headless=True, devtools=False):
        """Initialize scraper - parameters kept for compatibility but not used in this version"""
        self.headless = headless
        self.devtools = devtools
    
    def _sanitize_for_comparison(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        text = re.sub(r'\s\d+\s', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _sanitize_filename(self, name):
        return re.sub(r'[\\/*?:"<>|]', '', name).replace(' ', '_')

    def _parse_ticket_description(self, description: str) -> dict:
        desc_lower = description.lower()
        amenity_map = {
            'D-BOX': ['d-box', 'dbox'], 'IMAX': ['imax'], 'XD': ['xd'],
            'Dolby Cinema': ['dolby'], 'Recliner': ['recliner'],
            'Luxury': ['luxury'], '4DX': ['4dx'],
            'Promotion': ['promotion', 'tuesday', 'unseen', 'fathom']
        }
        base_type_map = {'Adult': ['adult'], 'Child': ['child'], 'Senior': ['senior'], 'Military': ['military'], 'Student': ['student'], 'Matinee': ['matinee']}
        found_amenities = []
        remaining_desc = desc_lower
        for amenity, keywords in amenity_map.items():
            for keyword in keywords:
                if keyword in remaining_desc:
                    found_amenities.append(amenity)
                    remaining_desc = remaining_desc.replace(keyword, '').strip()
        found_base_type = None
        for base_type, keywords in base_type_map.items():
            for keyword in keywords:
                if keyword in remaining_desc:
                    found_base_type = base_type
                    remaining_desc = remaining_desc.replace(keyword, '').strip()
                    break
            if found_base_type: break
        if not found_base_type:
            remaining_desc = description.split('(')[0].strip()
            if remaining_desc.lower() in ['general admission', 'admission']:
                found_base_type = "General Admission"
            else:
                found_base_type = remaining_desc
        return {"base_type": found_base_type, "amenities": sorted(list(set(found_amenities)))}

    def _classify_daypart(self, showtime_str: str) -> str:
        try:
            s = showtime_str.strip().lower().replace('.', '')
            if s.endswith('p'): s = s[:-1] + 'pm'
            if s.endswith('a'): s = s[:-1] + 'am'
            s = s.replace('p.m.', 'pm').replace('a.m.', 'am').replace('p ', 'pm').replace('a ', 'am')
            if not any(x in s for x in ('am','pm')):
                hour_match = re.match(r'(\d{1,2})', s)
                if hour_match:
                    hour = int(hour_match.group(1))
                    s += 'am' if hour < 8 or hour == 12 else 'pm'
            t = datetime.datetime.strptime(s, "%I:%M%p").time()
            if t < datetime.time(16,0): return "Matinee"
            if t < datetime.time(18,0): return "Twilight"
            if t <= datetime.time(21,0): return "Prime"
            return "Late Night"
        except Exception as e:
            print(f"        [WARNING] Could not classify daypart for '{showtime_str}'. Error: {e}")
            return "Unknown"
            
    async def _get_theaters_from_zip_page(self, page, zip_code, date_str):
        url = f"https://www.fandango.com/{zip_code}_movietimes?date={date_str}"
        print(f"  - Checking ZIP: {zip_code} for date {date_str}")
        try:
            await page.goto(url, timeout=30000)
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(1500)
            js_condition = "() => window.Fandango && window.Fandango.pageDetails && window.Fandango.pageDetails.localTheaters && window.Fandango.pageDetails.localTheaters.length > 0"
            await page.wait_for_function(js_condition, timeout=20000)
            theaters_data = await page.evaluate('() => window.Fandango.pageDetails.localTheaters')
            return {t.get('name'): {"name": t.get('name'), "url": "https://www.fandango.com" + t.get('theaterPageUrl')} for t in theaters_data if t.get('name') and t.get('theaterPageUrl')}
        except Exception as e:
            print(f"    [WARNING] Could not process ZIP {zip_code}. Error: {e}")
            return {}
            
    async def live_search_by_zip(self, zip_code, date_str):
        """
        FIX: This function now correctly accepts the date_str argument.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            url = f"https://www.fandango.com/{zip_code}_movietimes?date={date_str}"
            await page.goto(url, timeout=30000)
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(1500)
            js_condition = "() => window.Fandango && window.Fandango.pageDetails && window.Fandango.pageDetails.localTheaters && window.Fandango.pageDetails.localTheaters.length > 0"
            await page.wait_for_function(js_condition, timeout=20000)
            theaters_data = await page.evaluate('() => window.Fandango.pageDetails.localTheaters')
            results = {t.get('name'): {"name": t.get('name'), "url": "https://www.fandango.com" + t.get('theaterPageUrl')} for t in theaters_data if t.get('name') and t.get('theaterPageUrl')}
            await browser.close()
            return results

    async def live_search_by_name(self, search_term):
        print(f"  - Live searching for: {search_term}")
        results = {}
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto("https://www.fandango.com", timeout=60000)
                await page.locator('[data-qa="search-input"]').fill(search_term)
                await page.locator('[data-qa="search-input"]').press('Enter')
                await page.wait_for_selector('[data-qa="search-results-item"]', timeout=15000)
                soup = BeautifulSoup(await page.content(), 'html.parser')
                search_results_items = soup.select('[data-qa="search-results-item"]')
                for item in search_results_items:
                    link_elem = item.select_one('a[data-qa="search-results-item-link"]')
                    if link_elem:
                        href = link_elem.get('href')
                        if href and isinstance(href, str) and '/theater-page' in href:
                            name = link_elem.get_text(strip=True)
                            url = "https://www.fandango.com" + href
                            results[name] = {"name": name, "url": url}
            except Exception as e:
                print(f"    [WARNING] Could not complete live name search. Error: {e}")
            await browser.close()
            return results

    async def build_theater_cache(self, markets_json_path):
        with open(markets_json_path, 'r') as f:
            markets_data = json.load(f)

        temp_cache = {"metadata": {"last_updated": datetime.datetime.now().isoformat()}, "markets": {}}
        total_theaters_to_find = 0
        total_theaters_found = 0
        
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        date_str = tomorrow.strftime('%Y-%m-%d')

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for parent_company, regions in markets_data.items():
                for region_name, markets in regions.items():
                    for market_name, market_info in markets.items():
                        print(f"\n--- Processing Market: {market_name} ---")
                        theaters_in_market = market_info.get('theaters', [])
                        total_theaters_to_find += len(theaters_in_market)

                        found_theaters_for_market = []
                        theaters_to_find_in_fallback = []

                        print("  [Phase 1] Starting fast ZIP code scrape...")
                        zip_pool = {t.get('zip') for t in theaters_in_market if t.get('zip')}
                        market_zip_cache = {}
                        for zip_code in zip_pool:
                            zip_results = await self._get_theaters_from_zip_page(page, zip_code, date_str)
                            market_zip_cache.update(zip_results)

                        for theater_from_json in theaters_in_market:
                            name_to_find = theater_from_json['name']
                            found = False
                            sanitized_target_name = self._sanitize_for_comparison(name_to_find)
                            for live_name, live_data in market_zip_cache.items():
                                sanitized_live_name = self._sanitize_for_comparison(live_name)
                                if sanitized_target_name in sanitized_live_name or sanitized_live_name in sanitized_target_name:
                                    found_theaters_for_market.append({'name': live_name, 'url': live_data['url']})
                                    found = True
                                    break
                            if not found:
                                theaters_to_find_in_fallback.append(name_to_find)

                        print(f"  [Phase 1] Found {len(found_theaters_for_market)} theaters via ZIP scrape.")

                        if theaters_to_find_in_fallback:
                            print(f"  [Phase 2] Starting targeted fallback search for {len(theaters_to_find_in_fallback)} theater(s)...")
                            for theater_name in theaters_to_find_in_fallback:
                                search_results = await self.live_search_by_name(theater_name)
                                if search_results:
                                    found_name, found_data = next(iter(search_results.items()))
                                    print(f"    [SUCCESS] Fallback found '{theater_name}' as '{found_name}'")
                                    found_theaters_for_market.append({'name': found_name, 'url': found_data['url']})
                                else:
                                    print(f"    [WARNING] Fallback could not find '{theater_name}'.")

                        temp_cache["markets"][market_name] = {"theaters": found_theaters_for_market}
                        total_theaters_found += len(found_theaters_for_market)

            await browser.close()

        print("\n--- Sanity Check ---")
        print(f"Found {total_theaters_found} out of {total_theaters_to_find} total theaters.")

        if total_theaters_to_find > 0 and (total_theaters_found / total_theaters_to_find) >= 0.75:
            print("[SUCCESS] Sanity check passed. Overwriting old cache.")
            with open(CACHE_FILE, 'w') as f:
                json.dump(temp_cache, f, indent=2)
            return temp_cache
        else:
            print("[FAILURE] Sanity check failed. Preserving existing cache to prevent errors.")
            return False

    async def test_single_market(self, market_name, markets_data):
        temp_cache = {"markets": {}}
        total_theaters_found = 0
        
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        date_str = tomorrow.strftime('%Y-%m-%d')

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for parent_company, regions in markets_data.items():
                for region_name, markets in regions.items():
                    if market_name in markets:
                        market_info = markets[market_name]
                        print(f"--- Processing Market: {market_name} ---")
                        theaters_in_market = market_info.get('theaters', [])
                        
                        found_theaters_for_market = []
                        theaters_to_find_in_fallback = []

                        print("  [Phase 1] Starting fast ZIP code scrape...")
                        zip_pool = {t.get('zip') for t in theaters_in_market if t.get('zip')}
                        market_zip_cache = {}
                        for zip_code in zip_pool:
                            zip_results = await self._get_theaters_from_zip_page(page, zip_code, date_str)
                            market_zip_cache.update(zip_results)

                        for theater_from_json in theaters_in_market:
                            name_to_find = theater_from_json['name']
                            found = False
                            sanitized_target_name = self._sanitize_for_comparison(name_to_find)
                            for live_name, live_data in market_zip_cache.items():
                                sanitized_live_name = self._sanitize_for_comparison(live_name)
                                if sanitized_target_name in sanitized_live_name or sanitized_live_name in sanitized_target_name:
                                    found_theaters_for_market.append({'name': live_name, 'url': live_data['url']})
                                    found = True
                                    break
                            if not found:
                                theaters_to_find_in_fallback.append(name_to_find)

                        print(f"  [Phase 1] Found {len(found_theaters_for_market)} theaters via ZIP scrape.")

                        if theaters_to_find_in_fallback:
                            print(f"  [Phase 2] Starting targeted fallback search for {len(theaters_to_find_in_fallback)} theater(s)...")
                            for theater_name in theaters_to_find_in_fallback:
                                search_results = await self.live_search_by_name(theater_name)
                                if search_results:
                                    found_name, found_data = next(iter(search_results.items()))
                                    print(f"    [SUCCESS] Fallback found '{theater_name}' as '{found_name}'")
                                    found_theaters_for_market.append({'name': found_name, 'url': found_data['url']})
                                else:
                                    print(f"    [WARNING] Fallback could not find '{theater_name}'.")

                        temp_cache["markets"][market_name] = {"theaters": found_theaters_for_market}
                        total_theaters_found += len(found_theaters_for_market)
                        break
            await browser.close()
        
        return temp_cache

    async def _get_movies_from_theater_page(self, page, theater, date):
        full_url = f"{theater['url']}?date={date}"
        html_content = ""
        try:
            await page.goto(full_url, timeout=60000)
            # Wait for the new showtime structure
            await page.locator('li.shared-movie-showtimes, a.showtime-btn').first.wait_for(timeout=30000)
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            showings = []
            
            # New Fandango structure uses li.shared-movie-showtimes
            movie_blocks = soup.select('li.shared-movie-showtimes')
            
            if not movie_blocks and st.session_state.get('capture_html', False):
                os.makedirs(DEBUG_DIR, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"debug_{self._sanitize_filename(theater['name'])}_{timestamp}.html"
                filepath = os.path.join(DEBUG_DIR, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"  [DEBUG] No films found for {theater['name']}. Saved HTML snapshot to {filepath}")
            
            for movie_block in movie_blocks:
                # Get film title from new structure
                film_title_elem = movie_block.select_one('h3.shared-movie-showtimes__movie-title a')
                film_title = film_title_elem.get_text(strip=True) if film_title_elem else "Unknown Title"

                # DEBUG: Print HTML structure for first TWO movie blocks to see format variations
                if len(showings) == 0:
                    print(f"\n[DEBUG HTML] Analyzing movie block structure...")
                    print(f"  Total movie blocks found: {len(movie_blocks)}")

                    # Print first 2 movie blocks to see if different formats are separate blocks
                    for block_idx in range(min(2, len(movie_blocks))):
                        block = movie_blocks[block_idx]
                        title_elem = block.select_one('h3.shared-movie-showtimes__movie-title a')
                        title = title_elem.get_text(strip=True) if title_elem else "Unknown"

                        print(f"\n  === Movie Block {block_idx + 1}: {title} ===")

                        # Check all text in the movie block to find format indicators
                        block_text = block.get_text(separator='|', strip=True)
                        print(f"  Full block text (first 200 chars): {block_text[:200]}")

                        # Look for specific format keywords in the text
                        format_keywords = ['3D', 'IMAX', 'UltraScreen', 'Dolby', 'XD', 'RPX', 'PLF', 'DFX', 'D-BOX']
                        found_keywords = [kw for kw in format_keywords if kw.lower() in block_text.lower()]
                        if found_keywords:
                            print(f"  Format keywords found: {found_keywords}")

                        # Print the movie block's direct children structure
                        print(f"  Direct children of movie block:")
                        for child in block.find_all(recursive=False):
                            child_classes = ' '.join(child.get('class', []))
                            child_text = child.get_text(strip=True)[:80]
                            print(f"    {child.name}.{child_classes}: {child_text}")

                        # Inspect the showtimes section in detail
                        showtimes_section = block.select_one('section.shared-movie-showtimes__showtimes')
                        if showtimes_section:
                            print(f"\n  Showtimes section children:")
                            for elem in showtimes_section.find_all(recursive=False):
                                elem_classes = ' '.join(elem.get('class', []))
                                elem_text = elem.get_text(strip=True)[:60]
                                print(f"    {elem.name}.{elem_classes}: '{elem_text}'")

                                # Show grandchildren too
                                for grandchild in elem.find_all(recursive=False):
                                    gc_classes = ' '.join(grandchild.get('class', []))
                                    gc_text = grandchild.get_text(strip=True)[:60]
                                    print(f"      └─ {grandchild.name}.{gc_classes}: '{gc_text}'")

                # Look for variant title or format indicators
                # Try multiple selectors that might contain format info
                variant_title = None
                variant_selectors = [
                    '.movie-variant-title',  # Old selector
                    '.fd-movie__variant-group-name',  # New Fandango structure
                    '[class*="variant"]',  # Any element with "variant" in class
                ]
                for selector in variant_selectors:
                    variant_title_elem = movie_block.select_one(selector)
                    if variant_title_elem:
                        variant_title = variant_title_elem.get_text(strip=True)
                        break
                
                # Get all showtime buttons for this movie
                showtime_links = movie_block.select('a.showtime-btn')
                
                for link in showtime_links:
                    # Extract time from aria-label (e.g., "Buy tickets for 7 o'clock PM showtime")
                    aria_label = link.get('aria-label', '')
                    time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:o\'clock\s*)?(?:AM|PM|am|pm))', aria_label, re.IGNORECASE)
                    
                    if time_match:
                        time_str = time_match.group(1).replace("o'clock", "").strip()
                        # Normalize time format
                        time_str = re.sub(r'\s+', '', time_str)  # Remove spaces
                        if not ':' in time_str:
                            # Add :00 if missing minutes
                            time_str = re.sub(r'(\d{1,2})(am|pm)', r'\1:00\2', time_str, flags=re.IGNORECASE)
                    else:
                        # Fallback: try to find time in button text
                        time_label_elem = link.select_one('.showtime-btn-label')
                        time_str = time_label_elem.get_text(strip=True) if time_label_elem else link.get_text(strip=True)
                    
                    # Get format/amenity info
                    # Priority: button amenity > variant title > default "2D"
                    amenity_elem = link.select_one('.showtime-btn-amenity')
                    if amenity_elem:
                        movie_format = amenity_elem.get_text(strip=True)
                    elif variant_title and variant_title.strip():
                        movie_format = variant_title.strip()
                    else:
                        movie_format = "2D"

                    # Debug: print what we found for format (only for first showing to avoid spam)
                    if len(showings) == 0:
                        print(f"    [DEBUG FORMAT] Film: {film_title[:30]}, Format: '{movie_format}', Variant: '{variant_title}', Amenity: {amenity_elem is not None}")

                    href = link.get('href')
                    if href and isinstance(href, str):
                        # Handle both full URLs and relative paths
                        if href.startswith('http'):
                            ticket_url = href
                        elif 'jump.aspx' in href:
                            ticket_url_suffix = href.split('jump.aspx')[-1]
                            ticket_url = "https://tickets.fandango.com/transaction/ticketing/mobile/jump.aspx" + ticket_url_suffix
                        else:
                            ticket_url = "https://tickets.fandango.com" + href
                        
                        if film_title != "Unknown Title" and time_str and ticket_url:
                            # Validate time format
                            if re.match(r'\d{1,2}:\d{2}\s*[ap]m?', time_str, re.IGNORECASE):
                                showings.append({
                                    "film_title": film_title,
                                    "format": movie_format,
                                    "showtime": time_str,
                                    "daypart": self._classify_daypart(time_str),
                                    "ticket_url": ticket_url
                                })
            
            print(f"  [SCRAPER] Found {len(showings)} showings for {theater['name']}")
            return showings
        except Exception as e:
            print(f"    [ERROR] Failed to get movies for {theater['name']}. Error: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _get_prices_and_capacity(self, page, showing_details):
        showtime_url = showing_details['ticket_url']
        results = {"tickets": [], "capacity": "N/A", "error": None}
        try:
            print(f"  [SCRAPER] Loading ticket URL: {showtime_url[:80]}...")
            await page.goto(showtime_url, timeout=60000)
            print(f"  [SCRAPER] Page loaded, waiting 5 seconds for dynamic content...")
            await page.wait_for_timeout(5000)  # Increased from 1.5-2.5s to 5s

            print(f"  [SCRAPER] Searching for pricing data...")
            scripts = await page.query_selector_all('script')
            found_commerce = False

            for script in scripts:
                content = await script.inner_html()
                if content and 'window.Commerce.models' in content:
                    found_commerce = True
                    print(f"  [SCRAPER] Found window.Commerce.models")

                    start_text = 'window.Commerce.models = '
                    start_index = content.find(start_text)
                    if start_index != -1:
                        json_start = content.find('{', start_index)
                        open_braces, json_end = 0, -1
                        for i in range(json_start, len(content)):
                            if content[i] == '{': open_braces += 1
                            elif content[i] == '}': open_braces -= 1
                            if open_braces == 0:
                                json_end = i + 1; break
                        if json_end != -1:
                            data = json.loads(content[json_start:json_end])
                            print(f"  [SCRAPER] Parsed JSON successfully")

                            ticket_types = data.get('tickets', {}).get('seatingAreas', [{}])[0].get('ticketTypes', [])
                            print(f"  [SCRAPER] Found {len(ticket_types)} ticket types")

                            for tt in ticket_types:
                                description, price = tt.get('description'), tt.get('price')
                                if description and price is not None:
                                    parsed_ticket = self._parse_ticket_description(description)
                                    results["tickets"].append({
                                        "type": parsed_ticket["base_type"],
                                        "price": f"${price:.2f}",
                                        "amenities": parsed_ticket["amenities"]
                                    })

                            seating_info = data.get('seating', {})
                            total_seats = seating_info.get('totalSeats')
                            available_seats = seating_info.get('availableSeats')
                            if available_seats is not None and total_seats is not None:
                                results["capacity"] = f"{available_seats} / {total_seats}"

                            if results["tickets"]:
                                print(f"  [SCRAPER] Successfully extracted {len(results['tickets'])} prices")
                                return results

            if not found_commerce:
                print(f"  [SCRAPER] WARNING: window.Commerce.models not found on page!")
                results["error"] = "window.Commerce.models not found"

        except Exception as e:
            print(f"  [SCRAPER] ERROR: {e}")
            import traceback
            traceback.print_exc()
            results["error"] = f'Scraping failed: {e}'
        return results

    async def get_all_showings_for_theaters(self, theaters, date):
        showings_by_theater = {}
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            for theater in theaters:
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
                page = await context.new_page()
                showings = await self._get_movies_from_theater_page(page, theater, date)
                showings_by_theater[theater['name']] = showings
                await context.close()
        return showings_by_theater

    async def scrape_details(self, theaters, selected_showtimes, status_container=None):
        all_price_data = []
        showings_to_scrape = []

        print(f"  [SCRAPER] Building showings list...")
        print(f"  [SCRAPER] selected_showtimes structure: {list(selected_showtimes.keys())}")

        # selected_showtimes has structure: {date: {theater_name: {film_title: {showtime: [showing_info_list]}}}}
        # We need to iterate through dates first to find the theater data
        for date_str, daily_selections in selected_showtimes.items():
            print(f"  [SCRAPER] Processing date: {date_str}")
            for theater in theaters:
                theater_name = theater['name']
                if theater_name in daily_selections:
                    print(f"  [SCRAPER] Found theater '{theater_name}' in selections for {date_str}")
                    for film, times in daily_selections[theater_name].items():
                        for time_str, showing_info_list in times.items():
                            for showing_info in showing_info_list:
                                showings_to_scrape.append({**showing_info, "theater_name": theater_name})

        print(f"  [SCRAPER] Starting price scrape for {len(showings_to_scrape)} showings")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # Back to headless for production
            for idx, showing in enumerate(showings_to_scrape, 1):
                print(f"\n  [SCRAPER] Processing showing {idx}/{len(showings_to_scrape)}: {showing['film_title']} at {showing.get('theater_name', 'Unknown')}")
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
                page = await context.new_page()
                scrape_results = await self._get_prices_and_capacity(page, showing)
                await context.close()

                if scrape_results["error"]:
                    print(f"  [SCRAPER] [ERROR] Scraping {showing['film_title']} at {showing.get('theater_name', 'Unknown')}: {scrape_results['error']}")
                    continue
                
                for ticket in scrape_results['tickets']:
                    initial_format = showing['format']
                    final_amenities = ticket['amenities']
                    combined_format_list = [initial_format] + final_amenities
                    unique_formats = sorted(list(set(combined_format_list)))
                    if len(unique_formats) > 1 and "2D" in unique_formats:
                        unique_formats.remove("2D")
                    
                    price_point = {
                        "Theater Name": showing['theater_name'], "Film Title": showing['film_title'],
                        "Format": ", ".join(unique_formats), "Showtime": showing['showtime'],
                        "Daypart": showing['daypart'], "Ticket Type": ticket['type'], "Price": ticket['price'],
                        "Capacity": scrape_results.get('capacity', 'N/A')
                    }
                    all_price_data.append(price_point)

        return all_price_data, showings_to_scrape

    async def run_diagnostic_scrape(self, markets_to_test, date):
        diagnostic_results = []
        theaters_to_test = []
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        for market_name in markets_to_test:
            theaters = cache.get("markets", {}).get(market_name, {}).get("theaters", [])
            for theater in theaters:
                theater['market'] = market_name
                theaters_to_test.append(theater)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            for i, theater in enumerate(theaters_to_test):
                print(f"Testing {i+1}/{len(theaters_to_test)}: {theater['name']}")
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
                page = await context.new_page()
                result_row = {"Market": theater['market'], "Theater Name": theater['name'], "Status": "Failed", "Details": "No showtimes found", "Sample Price": "N/A"}
                try:
                    showings = await self._get_movies_from_theater_page(page, theater, date)
                    if showings:
                        first_showing = showings[0]
                        price_results = await self._get_prices_and_capacity(page, first_showing)
                        if price_results['tickets']:
                            first_ticket = price_results['tickets'][0]
                            result_row.update({
                                "Status": "Success",
                                "Details": f"Scraped '{first_showing['film_title']}' at {first_showing['showtime']}",
                                "Sample Price": f"{first_ticket['type']}: {first_ticket['price']}"
                            })
                        else:
                            result_row["Details"] = "Failed to extract price from ticket page."
                    diagnostic_results.append(result_row)
                except Exception as e:
                    result_row["Details"] = f"An unexpected error occurred: {str(e)}"
                    diagnostic_results.append(result_row)
                finally:
                    await context.close()
        return diagnostic_results