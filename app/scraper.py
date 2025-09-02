import re
import json
import datetime
import os
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import streamlit as st
import random
import urllib.parse
from thefuzz import fuzz

from config import DEBUG_DIR, CACHE_FILE

class Scraper:
    def _strip_common_terms(self, name: str) -> str:
        """Removes common cinema brand names and amenities to improve matching."""
        name_lower = name.lower()
        terms_to_strip = [
            'amc', 'cinemark', 'marcus', 'regal', 'movie tavern', 'studio movie grill',
            'dine-in', 'imax', 'dolby', 'xd', 'ultrascreen', 'superscreen',
            'cinema', 'theatres', 'theaters', 'cine', 'movies'
        ]
        pattern = r'\b(' + '|'.join(re.escape(term) for term in terms_to_strip) + r')\b'
        stripped_name = re.sub(pattern, '', name_lower)
        return re.sub(r'\s+', ' ', stripped_name).strip()

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
            # Improved scrolling
            for _ in range(3):
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(500)
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
            for _ in range(3):
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(500)
            js_condition = "() => window.Fandango && window.Fandango.pageDetails && window.Fandango.pageDetails.localTheaters && window.Fandango.pageDetails.localTheaters.length > 0"
            await page.wait_for_function(js_condition, timeout=20000)
            theaters_data = await page.evaluate('() => window.Fandango.pageDetails.localTheaters')
            results = {t.get('name'): {"name": t.get('name'), "url": "https://www.fandango.com" + t.get('theaterPageUrl')} for t in theaters_data if t.get('name') and t.get('theaterPageUrl')}
            await browser.close()
            return results

    async def live_search_by_name(self, search_term):
        print(f"  - Live searching for: {search_term}")
        results = {}
        encoded_search_term = urllib.parse.quote(search_term)
        search_url = f"https://www.fandango.com/search?q={encoded_search_term}&mode=all"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(search_url, timeout=60000)
                await page.wait_for_selector('li.fd-theater', timeout=30000)
                
                search_results_items = await page.query_selector_all('li.fd-theater')

                for item in search_results_items:
                    link_elem = await item.query_selector('a.light')
                    if link_elem:
                        href = await link_elem.get_attribute('href')
                        if href and isinstance(href, str) and '/theater-page' in href:
                            # Click on the link to navigate to the theater page
                            await link_elem.click()
                            await page.wait_for_load_state()

                            # Get the URL of the theater page
                            theater_page_url = page.url

                            # Get the theater name from the theater page
                            theater_name_elem = await page.query_selector('h1.hero-title')
                            theater_name = await theater_name_elem.inner_text() if theater_name_elem else search_term
                            
                            results[theater_name] = {"name": theater_name, "url": theater_page_url}

                            # Go back to the search results page
                            await page.go_back()
                            await page.wait_for_selector('li.fd-theater', timeout=30000)

            except Exception as e:
                print(f"    [WARNING] Could not complete live name search for '{search_term}'. Error: {e}")
                # Create a debug directory if it doesn't exist
                os.makedirs(DEBUG_DIR, exist_ok=True)
                # Sanitize the search term for the filename
                sanitized_term = self._sanitize_filename(search_term)
                # Create a unique filename with a timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(DEBUG_DIR, f"failure_{sanitized_term}_{timestamp}.png")
                # Take the screenshot
                try:
                    await page.screenshot(path=screenshot_path)
                    print(f"    [DEBUG] Screenshot of the failure page saved to: {screenshot_path}")
                except Exception as screenshot_error:
                    print(f"    [ERROR] Failed to take screenshot: {screenshot_error}")
            await browser.close()
            return results

    async def get_theater_name_from_url(self, url: str) -> str | None:
        """Fetches a Fandango theater page and extracts the theater name."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_selector('h1.heading-large', timeout=15000)
                soup = BeautifulSoup(await page.content(), 'html.parser')
                name_elem = soup.select_one('h1.heading-large')
                return name_elem.get_text(strip=True) if name_elem else None
            except Exception as e:
                print(f"    [ERROR] Could not fetch name from URL {url}. Error: {e}")
                return None
            finally:
                await browser.close()

    async def build_theater_cache(self, markets_json_path, progress_queue=None):
        with open(markets_json_path, 'r') as f:
            markets_data = json.load(f)

        matched_theaters = []
        unmatched_theaters = []
        new_cache_data = {"metadata": {"last_updated": datetime.datetime.now().isoformat()}, "markets": {}}

        theaters_to_process = []
        for parent_company, regions in markets_data.items():
            for region_name, markets in regions.items():
                for market_name, market_info in markets.items():
                    if "theaters" in market_info:
                        for theater in market_info["theaters"]:
                            theaters_to_process.append((market_name, theater))

        total_theaters = len(theaters_to_process)
        
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        date_str = tomorrow.strftime('%Y-%m-%d')

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            all_zips = sorted(list({t['zip'] for _, t in theaters_to_process if t.get('zip')}))
            market_zip_cache = {}
            
            # --- Phase 1: ZIP Code Scraping (20% of progress) ---
            zip_progress_weight = 0.2
            if progress_queue:
                progress_queue.put((0.0, "Starting ZIP code scraping..."))
            for i, zip_code in enumerate(all_zips):
                if progress_queue:
                    progress = (i / len(all_zips)) * zip_progress_weight
                    progress_queue.put((progress, f"Scraping ZIP codes... ({i+1}/{len(all_zips)})"))
                zip_results = await self._get_theaters_from_zip_page(page, zip_code, date_str)
                market_zip_cache.update(zip_results)

            # --- Phase 2: Theater Matching (80% of progress) ---
            theater_progress_weight = 0.8
            processed_count = 0
            for market_name, theater_from_json in theaters_to_process:
                processed_count += 1
                if progress_queue:
                    base_progress = zip_progress_weight
                    theater_progress = (processed_count / total_theaters) * theater_progress_weight
                    total_progress = base_progress + theater_progress
                    progress_queue.put((total_progress, f"Matching {theater_from_json['name']}..."))

                name_to_find = theater_from_json['name']
                best_match = None
                highest_ratio = 0

                original_stripped = self._strip_common_terms(name_to_find)
                for live_name, live_data in market_zip_cache.items():
                    live_stripped = self._strip_common_terms(live_name)
                    ratio = fuzz.token_sort_ratio(original_stripped, live_stripped)
                    if ratio > highest_ratio:
                        highest_ratio = ratio
                        best_match = live_data

                if highest_ratio < 75:
                    search_results = await self.live_search_by_name(name_to_find)
                    for live_name, live_data in search_results.items():
                        live_stripped = self._strip_common_terms(live_name)
                        ratio = fuzz.token_sort_ratio(original_stripped, live_stripped)
                        if ratio > highest_ratio:
                            highest_ratio = ratio
                            best_match = live_data
                
                if market_name not in new_cache_data["markets"]:
                    new_cache_data["markets"][market_name] = {"theaters": []}

                if best_match and highest_ratio > 70:
                    matched_theaters.append({
                        "original_name": name_to_find,
                        "matched_name": best_match['name'],
                        "score": highest_ratio,
                        "url": best_match['url'],
                        "market": market_name
                    })
                    new_cache_data["markets"][market_name]["theaters"].append({
                        "name": best_match['name'],
                        "url": best_match['url']
                    })
                else:
                    unmatched_theaters.append({
                        "original_name": name_to_find,
                        "market": market_name,
                        "zip": theater_from_json.get('zip', 'N/A')
                    })

            await browser.close()

        return matched_theaters, unmatched_theaters, new_cache_data

    async def test_single_market(self, market_name, markets_data):
        # This function can be simplified or removed in favor of the new build_theater_cache logic
        # For now, let's just return a placeholder
        return {"status": "deprecated"}

    async def _get_movies_from_theater_page(self, page, theater, date):
        full_url = f"{theater['url']}?date={date}"
        html_content = ""
        try:
            await page.goto(full_url, timeout=60000)
            await page.locator('div.theater-presenting-formats, li.fd-panel').first.wait_for(timeout=30000)
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            showings = []
            movie_blocks = soup.select('li.fd-panel')
            if not movie_blocks and st.session_state.get('capture_html', False):
                os.makedirs(DEBUG_DIR, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"debug_{self._sanitize_filename(theater['name'])}_{timestamp}.html"
                filepath = os.path.join(DEBUG_DIR, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"  [DEBUG] No films found for {theater['name']}. Saved HTML snapshot to {filepath}")
            for movie_block in movie_blocks:
                film_title_elem = movie_block.select_one('h2.thtr-mv-list__detail-title a')
                film_title = film_title_elem.get_text(strip=True) if film_title_elem else "Unknown Title"
                variant_title_elem = movie_block.select_one('.movie-variant-title')
                variant_title = variant_title_elem.get_text(strip=True) if variant_title_elem else None
                showtime_links = movie_block.select('ol.showtimes-btn-list a.showtime-btn')
                for link in showtime_links:
                    time_label_elem = link.select_one('.showtime-btn-label')
                    amenity_elem = link.select_one('.showtime-btn-amenity')
                    time_str = time_label_elem.get_text(strip=True) if time_label_elem else link.get_text(strip=True)
                    amenity_str = amenity_elem.get_text(strip=True) if amenity_elem else variant_title
                    movie_format = amenity_str if amenity_str else "2D"
                    
                    href = link.get('href')
                    if href and isinstance(href, str):
                        ticket_url_suffix = href.split('jump.aspx')[-1]
                        ticket_url = "https://tickets.fandango.com/transaction/ticketing/mobile/jump.aspx" + ticket_url_suffix
                        if film_title != "Unknown Title" and time_str and ticket_url and re.match(r'\d{1,2}:\d{2}[ap]m?', time_str, re.IGNORECASE):
                            showings.append({"film_title": film_title, "format": movie_format, "showtime": time_str, "daypart": self._classify_daypart(time_str), "ticket_url": ticket_url})
            return showings
        except Exception as e:
            print(f"    [ERROR] Failed to get movies for {theater['name']}. Error: {e}")
            return []

    async def _get_prices_and_capacity(self, page, showing_details):
        showtime_url = showing_details['ticket_url']
        results = {"tickets": [], "capacity": "N/A", "error": None}
        try:
            await page.goto(showtime_url, timeout=60000)
            await page.wait_for_timeout(random.randint(1500, 2500))
            
            scripts = await page.query_selector_all('script')
            for script in scripts:
                content = await script.inner_html()
                if content and 'window.Commerce.models' in content:
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
                            
                            ticket_types = data.get('tickets', {}).get('seatingAreas', [{}])[0].get('ticketTypes', [])
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

                            if results["tickets"]: return results
        except Exception as e:
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

    async def scrape_details(self, theaters, selected_showtimes):
        all_price_data = []
        showings_to_scrape = []
        for theater in theaters:
            if theater['name'] in selected_showtimes:
                for film, times in selected_showtimes[theater['name']].items():
                    for time_str, showing_info_list in times.items():
                        for showing_info in showing_info_list:
                            showings_to_scrape.append({**showing_info, "theater_name": theater['name']})

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            for showing in showings_to_scrape:
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
                page = await context.new_page()
                scrape_results = await self._get_prices_and_capacity(page, showing)
                await context.close()

                if scrape_results["error"]:
                    print(f"  [ERROR] Scraping {showing['film_title']} at {showing['theater_name']}: {scrape_results['error']}")
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
