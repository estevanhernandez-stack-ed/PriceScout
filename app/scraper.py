import re
import json
import datetime
import os
import asyncio
from playwright.async_api import async_playwright, Page
import logging
from bs4 import BeautifulSoup
import urllib.parse
from thefuzz import fuzz
from app.utils import clean_film_title

from app import database
from app.config import DEBUG_DIR, CACHE_FILE

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.debug("Scraper class initialized")
class Scraper:
    def __init__(self, headless=True, devtools=False):
        """Initializes the Scraper, loading and pre-compiling ticket type data."""
        self.ticket_types_data = self._load_ticket_types()
        self.headless = headless
        self.devtools = devtools
        self.capture_html = False # New flag to control debug snapshots
        logger.info(f"Scraper initialized with headless={self.headless}, devtools={self.devtools}")

        # Pre-compile regex for amenities to avoid recompilation in loops
        self.amenity_map_re = {}
        for amenity, keywords in self.ticket_types_data.get("amenity_map", {}).items():
            self.amenity_map_re[amenity] = [re.compile(r'(?<!\w)' + re.escape(kw) + r'(?!\w)', re.IGNORECASE) for kw in keywords]
        
        # Pre-compile regex for base ticket types
        self.base_type_map_re = {}
        for base_type, keywords in self.ticket_types_data.get("base_type_map", {}).items():
            self.base_type_map_re[base_type] = [re.compile(r'(?<!\w)' + re.escape(kw) + r'(?!\w)', re.IGNORECASE) for kw in keywords]

        # Load the list of PLF formats and convert to a lowercase set for efficient lookup
        self.plf_formats = {f.lower() for f in self.ticket_types_data.get("plf_formats", [])}

        # --- NEW: Load ignored amenities ---
        self.ignored_amenities = {term.lower() for term in self.ticket_types_data.get("ignored_amenities", [])}

        # Pre-compile regex for stripping common terms
        self.strip_terms_pattern = re.compile(r'\b(' + '|'.join(re.escape(term) for term in [
            'amc', 'cinemark', 'marcus', 'regal', 'movie tavern', 'studio movie grill',
            'b&b theatres', 'b&b',
            'dine-in', 'imax', 'dolby', 'xd', 'ultrascreen', 'superscreen',
            'cinema', 'theatres', 'theaters', 'cine', 'movies', 'by'
        ]) + r')\b')

    def _strip_common_terms(self, name: str) -> str:
        """Removes common cinema brand names and amenities to improve matching."""
        name_lower = name.lower()
        stripped_name = self.strip_terms_pattern.sub(' ', name_lower)
        # Clean up extra punctuation and spaces
        cleaned_name = re.sub(r'[\s,]+', ' ', stripped_name)
        return cleaned_name.strip()

    def _sanitize_filename(self, name):
        return re.sub(r'[\\/*?:",<>|]', '', name).replace(' ', '_')

    def _find_amenities_in_string(self, text: str) -> list[str]:
        """Finds all known amenities from a string based on ticket_types.json."""
        if not text:
            return []
        
        found = []
        text_lower = text.lower()

        for amenity, patterns in self.amenity_map_re.items():
            for pattern in patterns:
                if pattern.search(text_lower):
                    found.append(amenity)
                    break  # Found one keyword for this amenity, move to the next amenity
        logger.debug(f"[AMENITIES] Found amenities in text '{text}': {found}")
        return list(set(found)) # Return unique amenities

    def _load_ticket_types(self):
        """Loads ticket type and amenity mappings from an external JSON file."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ticket_types_path = os.path.join(script_dir, 'ticket_types.json')
        try:
            with open(ticket_types_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"    [ERROR] Could not load ticket_types.json: {e}")
            return {"amenity_map": {}, "base_type_map": {}}

    def _parse_ticket_description(self, description: str, showing_details: dict | None = None) -> dict:
        """
        [REFACTORED] Parses a ticket description string to extract the base type and any amenities.
        This version uses a multi-pass approach to be more robust against complex descriptions.
        """
        if not description:
            return {"base_type": "Unknown", "amenities": []}

        context = showing_details or {} # For logging context
        # Normalize the description: lowercase, fix dashes, remove most punctuation, normalize whitespace.
        remaining_desc = description.lower().replace('−', '-').strip()

        found_amenities = []

        # --- Pass 1: Find known amenities and remove them ---
        for amenity, patterns in self.amenity_map_re.items():
            for pattern in patterns:
                new_desc, count = pattern.subn('', remaining_desc) # Use subn to count replacements
                if count > 0:
                    found_amenities.append(amenity)
                    remaining_desc = new_desc.strip()

        # --- Pass 2: Find a known base ticket type (e.g., Adult, Child) ---
        found_base_type = None
        # Sort by length of keywords to match longer phrases first (e.g., "General Admission" before "General")
        sorted_base_types = sorted(self.base_type_map_re.items(), key=lambda item: -max(len(p.pattern) for p in item[1]))
        for base_type, patterns in sorted_base_types:
            for pattern in sorted(patterns, key=lambda p: -len(p.pattern)):
                new_desc, count = pattern.subn('', remaining_desc)
                if count > 0:
                    found_base_type = base_type
                    remaining_desc = new_desc.strip()
                    break
            if found_base_type:
                break

        # --- Pass 3: Handle what's left ---
        # Clean up the remainder by removing extra spaces and non-alphanumeric characters
        # that might be left over (like parentheses).
        remaining_parts = [part for part in re.split(r'[\s\(\)\[\]]+', remaining_desc) if part]

        for part in remaining_parts:
            # If no base type was found yet, the first significant part becomes the base type.
            if not found_base_type:
                found_base_type = part.title()
                # Log this new base type for review if it's not a price string
                if not re.match(r'^\$\d+\.\d{2}$', found_base_type):
                    try:
                        database.log_unmatched_ticket_type(description, found_base_type, context)
                    except Exception as e:
                        print(f"    [DB-WARN] Failed to log unmatched ticket type '{found_base_type}'. Reason: {e}")
            # If a base type is already found, treat other parts as potential amenities.
            elif part.lower() not in self.ignored_amenities:
                found_amenities.append(part.title())

        # Final fallback if nothing was found at all.
        if not found_base_type:
            found_base_type = "Unknown"
            # Log the original description for review
            try:
                database.log_unmatched_ticket_type(description, found_base_type, context)
            except Exception as e:
                print(f"    [DB-WARN] Failed to log unmatched ticket type '{description}'. Reason: {e}")
        
        return {"base_type": found_base_type, "amenities": sorted(list(set(found_amenities)))}

    def _parse_showtime_for_daypart(self, time_str: str):
        """Parses a showtime string into a time object for daypart classification."""
        time_str = time_str.lower().strip().replace('.', '')
        # Replace variations of am/pm
        time_str = time_str.replace('p.m.', 'pm').replace('a.m.', 'am')
        time_str = time_str.replace('p ', 'pm').replace('a ', 'am')
        # Ensure it ends with am or pm
        if not time_str.endswith('am') and not time_str.endswith('pm'):
            if time_str.endswith('p'):
                time_str = time_str[:-1] + 'pm'
            elif time_str.endswith('a'):
                time_str = time_str[:-1] + 'am'
            else:
                # Guess am/pm based on hour if no indicator is present
                try:
                    hour = int(time_str.split(':')[0])
                    if hour < 8 or hour == 12:
                        time_str += 'am'
                    else:
                        time_str += 'pm'
                except (ValueError, IndexError):
                    # Fallback for times without a colon, e.g., "10"
                    try:
                        hour = int(time_str)
                        if hour < 8 or hour == 12:
                            time_str += 'am'
                        else:
                            time_str += 'pm'
                    except ValueError:
                        pass # Let strptime handle the final error
        return datetime.datetime.strptime(time_str, "%I:%M%p").time()

    def _classify_daypart(self, showtime_str: str) -> str:
        try:
            t = self._parse_showtime_for_daypart(showtime_str)
            if t < datetime.time(4, 0): # 12:00am to 3:59am
                return "Late Night"
            if t < datetime.time(16, 0): # 4:00am to 3:59pm
                return "Matinee"
            if t < datetime.time(18, 0): # 4:00pm to 5:59pm
                return "Twilight"
            if t <= datetime.time(21, 0): # 6:00pm to 9:00pm
                return "Prime"
            return "Late Night" # 9:01pm to 11:59pm
        except Exception as e:
            print(f"        [WARNING] Could not classify daypart for '{showtime_str}'. Error: {e}")
            return "Unknown"

    async def check_url_status(self, url: str) -> bool:
        """Performs a lightweight check to see if a URL is active."""
        if not url or url == "N/A":
            return False
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                response = await page.request.head(url, timeout=10000) # Use HEAD request for efficiency
                status = response.status
                return 200 <= status < 400 # Consider 2xx and 3xx as active
            except TimeoutError:
                print(f"        [WARNING] URL check timed out for {url}.")
                return False
            except Exception as e:
                print(f"        [WARNING] URL check failed for {url} with unexpected error: {e}")
                return False
            finally:
                await browser.close()
    def _process_movie_block(self, movie_block, theater, base_format=""):
        """Processes a single movie block (li.fd-panel) to extract all its showings."""
        showings = []
        film_title_elem = movie_block.select_one('h2.thtr-mv-list__detail-title a')
        film_title = film_title_elem.get_text(strip=True) if film_title_elem else "Unknown Title"
        
        # Scrape block-level amenities (e.g., from 'ul.fd-movie__amenity-list')
        amenity_list_elem = movie_block.select_one('ul.fd-movie__amenity-list')
        block_amenities = []
        if amenity_list_elem:
            for li in amenity_list_elem.find_all('li'):
                button = li.find('button')
                if button and button.has_attr('data-amenity-name'):
                    amenity_name = button['data-amenity-name']
                    if amenity_name:
                        block_amenities.append(amenity_name)

        # Scrape additional details from Fandango page for fallbacks
        meta_elem = movie_block.select_one('.thtr-mv-list__detail-meta')
        meta_text = meta_elem.get_text(separator='|', strip=True) if meta_elem else ""
        fandango_rating = "N/A"
        fandango_runtime = "N/A"
        if meta_text:
            parts = [p.strip() for p in meta_text.split('|')]
            runtime_part = next((p for p in parts if 'hr' in p or 'min' in p), None)
            if runtime_part: fandango_runtime = runtime_part
            rating_part = next((p for p in parts if p in ['G', 'PG', 'PG-13', 'R', 'NC-17', 'Not Rated', 'NR', 'UNRATED']), None)
            if rating_part: fandango_rating = rating_part
        synopsis_elem = movie_block.select_one('.thtr-mv-list__detail-synopsis')
        fandango_plot = synopsis_elem.get_text(strip=True) if synopsis_elem else "N/A"

        # Handle new amenity group layout
        amenity_groups = movie_block.select('.thtr-mv-list__amenity-group')
        if not amenity_groups:
            amenity_groups = [movie_block] # Fallback: treat the whole block as one group

        for group in amenity_groups:
            # Get format from the group's H3 heading (e.g., "IMAX")
            group_format_elem = group.select_one('h3.thtr-mv-list__showtimes-title')
            group_format = group_format_elem.get_text(strip=True) if group_format_elem else ''

            # Get amenities from buttons within the group
            group_amenities_elems = group.select('ul.fd-list-inline button[data-amenity-name]')
            group_amenities = [btn['data-amenity-name'] for btn in group_amenities_elems]

            # Get other formats from the main movie block (they apply to all groups)
            variant_title_elem = movie_block.select_one('.movie-variant-title')
            variant_title = variant_title_elem.get_text(strip=True) if variant_title_elem else ''
            other_format_elems = movie_block.select('h2.thtr-mv-list__detail-title span, h2.thtr-mv-list__detail-title em')
            other_format_text = ' '.join([elem.get_text(strip=True) for elem in other_format_elems])

            showtime_links = group.select('ol.showtimes-btn-list a.showtime-btn')
            for link in showtime_links:
                time_label_elem = link.select_one('.showtime-btn-label')
                amenity_elem = link.select_one('.showtime-btn-amenity')
                time_str = time_label_elem.get_text(strip=True) if time_label_elem else link.get_text(strip=True)
                
                amenity_text = amenity_elem.get_text(strip=True) if amenity_elem else ''
                block_amenities_text = " ".join(block_amenities)
                
                # Combine all format sources into one string for parsing
                full_format_text = f"{film_title} {base_format} {variant_title} {other_format_text} {group_format} {' '.join(group_amenities)} {block_amenities_text} {amenity_text}".strip()
                logger.debug(f"[FORMAT TEXT] For '{film_title}' at '{time_str}': '{full_format_text}'")
                all_formats = set(self._find_amenities_in_string(full_format_text))
                
                if len(all_formats) > 1 and '2D' in all_formats:
                    all_formats.remove('2D')
                
                # Check if any of the canonical amenities found are in our configured PLF list
                is_plf = any(amenity.lower() in self.plf_formats for amenity in all_formats)

                movie_format = ", ".join(sorted(list(all_formats))) if all_formats else "2D"
                
                href = link.get('href')
                if href and isinstance(href, str):
                    ticket_url_suffix = href.split('jump.aspx')[-1]
                    ticket_url = "https://tickets.fandango.com/transaction/ticketing/mobile/jump.aspx" + ticket_url_suffix
                    logger.info(f"[SHOWTIME DISCOVERY] Theater: {theater['name']}, Film: {film_title}, Time: {time_str}, Format: {movie_format}")
                    if film_title != "Unknown Title" and time_str and ticket_url and re.match(r'\d{1,2}:\d{2}[ap]m?', time_str, re.IGNORECASE):
                        showings.append({
                            "theater_name": theater['name'], "film_title": film_title, 
                            "format": movie_format, "is_plf": is_plf, "showtime": time_str, 
                            "daypart": self._classify_daypart(time_str), "ticket_url": ticket_url,
                            "fandango_rating": fandango_rating, "fandango_runtime": fandango_runtime,
                            "fandango_plot": fandango_plot
                        })
        return showings

    async def _get_movies_from_theater_page(self, page, theater, date): # noqa: C901
        full_url = f"{theater['url']}?date={date}"
        html_content = ""
    async def live_search_by_zip(self, zip_code, date_str, page=None):
        """Searches for theaters by ZIP code on Fandango."""
        async def search(page):
            url = f"https://www.fandango.com/{zip_code}_movietimes?date={date_str}"
            await page.goto(url, timeout=30000)
            for _ in range(3):
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(500)
            js_condition = "() => window.Fandango && window.Fandango.pageDetails && window.Fandango.pageDetails.localTheaters && window.Fandango.pageDetails.localTheaters.length > 0"
            await page.wait_for_function(js_condition, timeout=20000)
            theaters_data = await page.evaluate('() => window.Fandango.pageDetails.localTheaters')
            return {t.get('name'): {"name": t.get('name'), "url": "https://www.fandango.com" + t.get('theaterPageUrl')} for t in theaters_data if t.get('name') and t.get('theaterPageUrl')}

        if page:
            return await search(page)
        else:
            async with async_playwright() as p: # type: ignore
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                results = await search(page)
                await browser.close()
                return results

    async def live_search_by_name(self, search_term, page: 'Page' = None): # type: ignore
        print(f"  - Live searching for: {search_term}")
        encoded_search_term = urllib.parse.quote(search_term)
        search_url = f"https://www.fandango.com/search?q={encoded_search_term}&mode=all"

        async def _search(page_to_use: 'Page'): # type: ignore
            results = {}
            try:
                await page_to_use.goto(search_url, timeout=60000)

                # Handle cases where Fandango redirects directly to a theater page
                if "/theater-page" in page_to_use.url:
                    print("  - Redirected directly to theater page.")
                    soup = BeautifulSoup(await page_to_use.content(), 'html.parser')
                    name_elem = soup.select_one('h1.heading-large')
                    if name_elem:
                        theater_name = name_elem.get_text(strip=True)
                        results[theater_name] = {"name": theater_name, "url": page.url}
                else:
                    # We are on a search results page, so wait for the theater links
                    await page_to_use.wait_for_selector('a[href*="/theater-page"]', timeout=15000)
                    html_content = await page_to_use.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    theater_links = soup.select('a[href*="/theater-page"]')

                    for link_elem in theater_links:
                        theater_name = link_elem.get_text(strip=True)
                        if theater_name: # Ensure the link has a name
                            theater_page_url = "https://www.fandango.com" + str(link_elem['href']) # type: ignore
                            results[theater_name] = {"name": theater_name, "url": theater_page_url}

            except TimeoutError:
                print(f"    [WARNING] Live name search timed out for '{search_term}'.")
            except Exception as e:
                print(f"    [WARNING] Could not complete live name search for '{search_term}'. Unexpected error: {e}")
                try:
                    os.makedirs(DEBUG_DIR, exist_ok=True)
                    sanitized_term = self._sanitize_filename(search_term)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_path = os.path.join(DEBUG_DIR, f"failure_{sanitized_term}_{timestamp}.png")
                    await page_to_use.screenshot(path=screenshot_path)
                    print(f"    [DEBUG] Screenshot of the failure page saved to: {screenshot_path}") # type: ignore
                except Exception as screenshot_error:
                    print(f"    [ERROR] Failed to take screenshot: {screenshot_error}")
            return results

        if page:
            return await _search(page)
        else:
            async with async_playwright() as p: # type: ignore
                browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
                page = await browser.new_page()
                results = await _search(page)
                await browser.close()
                return results

    async def get_theater_name_from_url(self, url: str) -> str | None:
        """Fetches a Fandango theater page and extracts the theater name."""
        async with async_playwright() as p: # type: ignore
            browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_selector('h1.heading-large', timeout=15000)
                soup = BeautifulSoup(await page.content(), 'html.parser')
                name_elem = soup.select_one('h1.heading-large')
                return name_elem.get_text(strip=True) if name_elem else None
            except TimeoutError:
                print(f"    [ERROR] Timeout while fetching name from URL {url}.")
                return None
            except Exception as e:
                print(f"    [ERROR] Could not fetch name from URL {url}. Unexpected error: {e}")
                return None

        if page:
            return await _get_name(page)
        else:
            async with async_playwright() as p: # type: ignore
                browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
                page = await browser.new_page()
                result = await _get_name(page)
                await browser.close()
                return result

    async def search_fandango_for_film_url(self, title: str, log_callback=None, page: 'Page' = None) -> list[dict]: # type: ignore
        """Searches Fandango for a film and returns potential matches with overview URLs."""
        def log(message):
            print(message)
            if log_callback:
                log_callback(message)

        # --- NEW: Clean the title before searching ---
        cleaned_title = clean_film_title(title)

        results = []
        encoded_title = urllib.parse.quote(cleaned_title)
        search_url = f"https://www.fandango.com/search?q={encoded_title}&mode=movie"
        
        async def _search(page: 'Page'): # type: ignore
            try:
                log(f"  [Fandango Search] Navigating to: {search_url}")
                await page.goto(search_url, timeout=30000)
                
                # Handle cases where Fandango redirects directly to a movie overview page
                if "/movie-overview" in page.url:
                    log("  [Fandango Search] Redirected directly to movie page. Waiting for content...")
                    # Wait for either of the possible title selectors to ensure the page is loaded
                    await page.locator('h1.movie-detail-header__title, h1.movie-details__title').first.wait_for(timeout=15000)
                    soup = BeautifulSoup(await page.content(), 'html.parser')
                    # Check for both possible title selectors to be robust
                    title_elem = soup.select_one('h1.movie-detail-header__title, h1.movie-details__title')
                    if title_elem:
                        film_title = title_elem.get_text(strip=True)
                        log(f"  [Fandango Search] Found direct match: {film_title}")
                        results.append({"title": film_title, "url": page.url})
                else:
                    # We are on a search results page, wait for results to appear
                    log("  [Fandango Search] On search results page. Waiting for results to load...")
                    await page.wait_for_selector('li.search__panel', timeout=10000)
                    soup = BeautifulSoup(await page.content(), 'html.parser')
                    search_panels = soup.select('li.search__panel')
                    log(f"  [Fandango Search] Found {len(search_panels)} potential matches.")
                    for panel in search_panels:
                        title_elem = panel.select_one('a.search__movie-title')
                        if title_elem:
                            film_title = title_elem.get_text(strip=True)
                            film_url = "https://www.fandango.com" + title_elem['href']
                            results.append({"title": film_title, "url": film_url})

            except Exception as e:
                log(f"  [Fandango Search] Could not find film '{title}' on Fandango. Reason: {e}")
                # --- Screenshot on failure for debugging ---
                try:
                    if page: # Only try to take a screenshot if the page object exists
                        os.makedirs(DEBUG_DIR, exist_ok=True)
                        sanitized_title = self._sanitize_filename(title)
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        screenshot_path = os.path.join(DEBUG_DIR, f"fandango_search_failure_{sanitized_title}_{timestamp}.png")
                        await page.screenshot(path=screenshot_path)
                        log(f"  [DEBUG] Screenshot of the failure page saved to: {screenshot_path}")
                except Exception as screenshot_error:
                    log(f"  [ERROR] Failed to take a debug screenshot. Reason: {screenshot_error}")
            return results

        if page:
            return await _search(page)
        else:
            async with async_playwright() as p: # type: ignore
                browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
                page = await browser.new_page()
                results = await _search(page)
                await browser.close()
                return results

    async def get_film_details_from_fandango_url(self, url: str, page: 'Page' = None) -> dict | None: # type: ignore
        """Scrapes a Fandango movie overview page for metadata."""
        async def _get_details(page: 'Page'): # type: ignore
            try:
                await page.goto(url, timeout=30000)
                # Wait for either the new or old title selector to appear
                await page.locator('h1.movie-detail-header__title, h1.movie-details__title').first.wait_for(timeout=15000)
                
                soup = BeautifulSoup(await page.content(), 'html.parser')
                
                details = {
                    "film_title": None, "mpaa_rating": "N/A", "runtime": "N/A",
                    "genre": "N/A", "plot": "N/A", "poster_url": None,
                    "director": None, "actors": None, "release_date": None, "imdb_id": None, 
                    "metascore": None, "imdb_rating": None, "domestic_gross": None, 
                    "opening_weekend_domestic": None, "last_omdb_update": datetime.datetime.now()
                }

                # --- NEW: Check for the new page layout first ---
                if title_elem := soup.select_one('h1.movie-detail-header__title'):
                    details['film_title'] = title_elem.get_text(strip=True)
                    if poster_elem := soup.select_one('img.movie-detail__poster'): details['poster_url'] = poster_elem.get('src')
                    if synopsis_elem := soup.select_one('p.movie-details__synopsis-text'): details['plot'] = synopsis_elem.get_text(strip=True)
                    if rating_elem := soup.select_one('span.movie-detail-header__additional-info-rating'): details['mpaa_rating'] = rating_elem.get_text(strip=True)
                    for item in soup.select('span.movie-detail-header__info-item'):
                        text = item.get_text(strip=True)
                        if 'min' in text or 'hr' in text: details['runtime'] = text
                    
                    # --- NEW: Find release date in the details section ---
                    # --- CORRECTED: Also find Genre in this same section ---
                    for dt_element in soup.select('dt.movie-details__detail-term'):
                        term_text = dt_element.get_text(strip=True).lower().strip()
                        if term_text == 'release date':
                            if dd_element := dt_element.find_next_sibling('dd'):
                                details['release_date'] = dd_element.get_text(strip=True)
                        elif term_text == 'genre(s)':
                            if dd_element := dt_element.find_next_sibling('dd'):
                                details['genre'] = dd_element.get_text(strip=True)

                # --- Fallback to the old page layout ---
                elif title_elem := soup.select_one('h1.movie-details__title'):
                    details['film_title'] = title_elem.get_text(strip=True)
                    if poster_elem := soup.select_one('img.movie-details__poster-img'): details['poster_url'] = poster_elem.get('src')
                    if synopsis_elem := soup.select_one('p.movie-details__synopsis-text'): details['plot'] = synopsis_elem.get_text(strip=True)
                    for item in soup.select('ul.movie-details__header-meta li'):
                        text = item.get_text(strip=True)
                        if 'min' in text or 'hr' in text: details['runtime'] = text
                        elif text in ['G', 'PG', 'PG-13', 'R', 'NC-17', 'Not Rated']: details['mpaa_rating'] = text
                        elif re.match(r'\d{4}', text): details['release_date'] = text
                        else: details['genre'] = text

                # --- Shared logic for credits (often the same) ---
                for item in soup.select('.movie-details__credits-list dt'):
                    if (label := item.get_text(strip=True).lower()) and (value_elem := item.find_next_sibling('dd')):
                        value = value_elem.get_text(strip=True)
                        if 'starring' in label: details['actors'] = value
                        elif 'director' in label: details['director'] = value
                
                return details

            except Exception as e:
                print(f"  [Fandango Scrape] Failed to scrape details from {url}. Reason: {e}")
                return None

        if page:
            return await _get_details(page)
        else:
            async with async_playwright() as p: # type: ignore
                browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
                page = await browser.new_page()
                details = await _get_details(page)
                await browser.close()
                return details

    async def get_coming_soon_films(self) -> list[dict]:
        """Scrapes Fandango's 'Coming Soon' page for a list of upcoming films."""
        url = "https://www.fandango.com/coming-soon"
        film_urls = []
        async with async_playwright() as p: # type: ignore
            browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
            try:
                page = await browser.new_page()
                print(f"  [Fandango Scrape] Navigating to: {url}")
                await page.goto(url, timeout=30000)
                await page.wait_for_selector('div.movie-list-item', timeout=15000)

                for _ in range(5):
                    await page.mouse.wheel(0, 2000)
                    await page.wait_for_timeout(500)

                soup = BeautifulSoup(await page.content(), 'html.parser')
                movie_cards = soup.select('div.movie-list-item')
                print(f"  [Fandango Scrape] Found {len(movie_cards)} 'Coming Soon' film cards.")

                for card in movie_cards:
                    link_elem = card.select_one('a.movie-list-item-link')
                    if link_elem and link_elem.has_attr('href'):
                        film_urls.append("https://www.fandango.com" + link_elem['href'])

                print(f"  [Fandango Scrape] Discovered {len(film_urls)} film detail URLs. Scraping details concurrently...")

                # --- REFACTORED: Concurrently scrape details using a shared browser context ---
                async def scrape_with_page(film_url):
                    # Each task gets its own page, but they share the browser instance.
                    scrape_page = await browser.new_page()
                    details = await self.get_film_details_from_fandango_url(film_url, page=scrape_page)
                    await scrape_page.close()
                    return details
                tasks = [scrape_with_page(film_url) for film_url in film_urls]
                results = await asyncio.gather(*tasks)

                # Filter out any None results from failed scrapes
                successful_results = [res for res in results if res]
                print(f"  [Fandango Scrape] Successfully scraped details for {len(successful_results)} films.")
                return successful_results

            except Exception as e:
                print(f"  [Fandango Scrape] Failed to scrape 'Coming Soon' page. Reason: {e}")
                return []
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

        async with async_playwright() as p: # type: ignore
            browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
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
                zip_results = await self.live_search_by_zip(zip_code, date_str, page=page)
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

                if highest_ratio < 75: # type: ignore
                    search_results = await self.live_search_by_name(name_to_find, page=page)
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

    async def _get_movies_from_theater_page(self, page, theater, date): # noqa: C901
        full_url = f"{theater['url']}?date={date}"
        html_content = ""
        try:
            await page.goto(full_url, timeout=30000)
            await page.locator('div.theater-presenting-formats, li.fd-panel').first.wait_for(timeout=15000)
            html_content = await page.content()

            soup = BeautifulSoup(html_content, 'html.parser')
            showings = []

            # --- NEW LOGIC to handle different page layouts ---
            format_containers = soup.select('div.theater-presenting-formats')

            if format_containers:
                # Layout where movies are grouped by a parent format container (e.g., for Marcus Superscreen)
                for container in format_containers:
                    container_format_elem = container.select_one('h3')
                    base_format = container_format_elem.get_text(strip=True) if container_format_elem else "2D"
                    
                    movie_blocks_in_container = container.select('li.fd-panel')
                    for movie_block in movie_blocks_in_container:
                        # This block is now very similar to the 'else' block, let's process it
                        showings.extend(self._process_movie_block(movie_block, theater, base_format=base_format))
            else:
                # Original layout where format is inside the movie block or button
                movie_blocks = soup.select('li.fd-panel')
                for movie_block in movie_blocks:
                    # Process the movie block without a base_format
                    showings.extend(self._process_movie_block(movie_block, theater))

            if not showings:
                os.makedirs(DEBUG_DIR, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"debug_{self._sanitize_filename(theater['name'])}_{timestamp}.html"
                filepath = os.path.join(DEBUG_DIR, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"  [DEBUG] No showings found for {theater['name']}. Saved HTML snapshot to {filepath}")
            return showings
        except TimeoutError:
            print(f"    [ERROR] Timeout while getting movies for {theater['name']}.")
            return []
        except Exception as e:
            print(f"    [ERROR] Failed to get movies for {theater['name']}. Unexpected error: {e}")
            return []

    async def _get_prices_and_capacity(self, page: 'Page', showing_details: dict) -> dict:
        """
        [REFACTORED] Scrapes ticket prices and capacity from a Fandango ticketing page.

        This function navigates to a specific showtime URL and extracts pricing data
        from an inline JSON object within a <script> tag.

        Args:
            page (Page): The Playwright page object to use for navigation.
            showing_details (dict): A dictionary containing the 'ticket_url' for the showing.

        Returns:
            dict: A dictionary containing 'tickets', 'capacity', and 'error' keys.
        """
        showtime_url = showing_details['ticket_url']
        results = {"tickets": [], "capacity": "N/A", "error": None}
        html_content = ""

        try: # Reverting to the known-good logic from the working copy.
            await page.goto(showtime_url, timeout=60000)
            html_content = await page.content() # Get content once
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
                            
                            # Check for seating areas in both possible locations
                            seating_areas = data.get('seatingAreas')
                            if not seating_areas and 'tickets' in data and isinstance(data['tickets'], dict):
                                seating_areas = data['tickets'].get('seatingAreas', [])

                            if not seating_areas:
                                results["error"] = "No 'seatingAreas' found in the pricing data."
                                return results

                            seating_area = seating_areas[0]
                            ticket_types = seating_area.get('ticketTypes', [])

                            for tt in ticket_types:
                                description, price = tt.get('description'), tt.get('price')
                                if description and price is not None:
                                    parsed_ticket = self._parse_ticket_description(description, showing_details)
                                    results["tickets"].append({
                                        "type": parsed_ticket["base_type"],
                                        "price": f"${price:.2f}",
                                        "amenities": parsed_ticket["amenities"]
                                    })

                            results["capacity"] = "Sold Out" if seating_area.get('isSoldOut') else "Available"

                            if results["tickets"]: return results
            # If loop finishes without returning, it means data was not found.
            results["error"] = "Could not find 'window.Commerce.models' in any script tag."

        except TimeoutError:
            results["error"] = 'Scraping timed out.'
        except json.JSONDecodeError as e:
            # This can happen if the regex matches something that isn't valid JSON
            results["error"] = f"Failed to parse pricing JSON: {e}"
            # Save HTML on this specific failure for debugging
            if html_content and self.capture_html:
                self._save_debug_html(html_content, "get_prices_json_failure")
        except Exception as e:
            results["error"] = f'Scraping failed with unexpected error: {e}'
            # --- NEW: Save HTML on failure for easier debugging ---
            if html_content:
                os.makedirs(DEBUG_DIR, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"get_prices_failure_{timestamp}.html"
                filepath = os.path.join(DEBUG_DIR, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.error(f"  [DEBUG] Saved failing HTML for _get_prices_and_capacity to {filepath}")

        return results

    def _save_debug_html(self, html_content, prefix="debug"):
        """Saves HTML content to a file in the debug directory."""
        os.makedirs(DEBUG_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.html"
        filepath = os.path.join(DEBUG_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f: f.write(html_content)
        logger.error(f"  [DEBUG] Saved failing HTML to {filepath}")

    async def get_all_showings_for_theaters(self, theaters, date):
        CONCURRENCY = 8  # Limit concurrent browser pages for stability
        showings_by_theater = {}

        async with async_playwright() as p: # type: ignore
            browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
            
            semaphore = asyncio.Semaphore(CONCURRENCY)

            async def scrape_single_theater(theater):
                """Worker to scrape showtimes for a single theater concurrently."""
                async with semaphore:
                    page = await context.new_page()
                    try:
                        showings = await self._get_movies_from_theater_page(page, theater, date)
                        return theater['name'], showings
                    except Exception as e:
                        print(f"  [ERROR] Worker for {theater['name']} failed during showtime discovery: {e}")
                        return theater['name'], []
                    finally:
                        await page.close()

            tasks = [scrape_single_theater(theater) for theater in theaters]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, tuple):
                    theater_name, showings = result
                    showings_by_theater[theater_name] = showings
                elif isinstance(result, Exception):
                    print(f"  [ERROR] A showtime discovery task failed unexpectedly: {result}")

            await browser.close()
        return showings_by_theater

    async def scrape_details(self, theaters: list, selected_showtimes: dict, status_container: list | None = None) -> tuple[list, list]:
        """
        [REFACTORED] Scrapes ticket prices for a list of selected showtimes concurrently.

        This function is optimized to:
        1. Use a single shared browser instance for all scraping tasks.
        2. Run multiple price-scraping tasks in parallel using a semaphore to control concurrency.
        3. Handle errors on a per-showing basis, allowing the scrape to continue even if some showings fail.

        Args:
            theaters (list): A list containing a single theater object to be scraped.
            selected_showtimes (dict): The nested dictionary of showtimes to scrape.
            status_container (list | None): A mutable list to report progress back to the UI.

        Returns:
            tuple[list, list]: A tuple containing the list of all successfully scraped price data
                               and the list of all showings that were attempted.
        """
        all_price_data = []
        showings_to_scrape = []

        if not theaters:
            return [], []
        theater = theaters[0]
        theater_name = theater['name']

        # --- 1. Flatten the nested selected_showtimes dictionary into a simple list ---
        for date_str, daily_selections in selected_showtimes.items():
            if theater_name in daily_selections:
                for film, times in daily_selections[theater_name].items():
                    for time_str, showing_info_list in times.items():
                        for showing_info in showing_info_list:
                            # Add the theater name and play_date to each showing for context
                            showings_to_scrape.append({**showing_info, "theater_name": theater_name, "play_date": date_str})

        if not showings_to_scrape:
            return [], []

        # --- 2. Set up a shared browser context and concurrency controls ---
        CONCURRENCY_LIMIT = 5
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        all_price_data = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

            # --- 3. REFACTORED: Create a pool of reusable pages ---
            page_pool = [await context.new_page() for _ in range(CONCURRENCY_LIMIT)]

            async def worker(showing, index, total):
                # The semaphore must be here, before the page is taken from the pool.
                async with semaphore:
                    page = None
                    try:
                        page = page_pool.pop()
                        if status_container:
                            status_container[0] = f"Scraping showing {index + 1}/{total}: {showing['film_title']} at {showing['showtime']}"

                        scrape_results = await self._get_prices_and_capacity(page, showing)

                        if scrape_results.get("error"):
                            logger.error(f"  [ERROR] Scraping {showing['film_title']} at {showing['theater_name']}: {scrape_results['error']}")
                            return []

                        processed_tickets = []
                        for ticket in scrape_results.get('tickets', []):
                            initial_format_str = showing.get('format', '2D')
                            ticket_amenities = ticket.get('amenities', [])
                            initial_amenities_set = {f.strip() for f in initial_format_str.split(',') if f.strip()}
                            all_amenities = initial_amenities_set.union(set(ticket_amenities))

                            if len(all_amenities) > 1 and '2D' in all_amenities:
                                all_amenities.remove('2D')

                            final_format_str = ", ".join(sorted(list(all_amenities))) if all_amenities else "2D"
                            is_plf = showing.get('is_plf', False)

                            price_point = {
                                "Theater Name": showing['theater_name'], "Film Title": showing['film_title'],
                                "Format": final_format_str, "Is PLF": "Yes" if is_plf else "No",
                                "Showtime": showing['showtime'], "Daypart": showing['daypart'],
                                "Ticket Type": ticket['type'], "Price": ticket['price'],
                                "Capacity": scrape_results.get('capacity', 'N/A'),
                                "play_date": showing.get('play_date'), "Market": showing.get('market', 'N/A')
                            }
                            processed_tickets.append(price_point)
                        return processed_tickets
                    finally:
                        if page:
                            page_pool.append(page)

            tasks = [worker(showing, i, len(showings_to_scrape)) for i, showing in enumerate(showings_to_scrape)]
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            # --- 4. Close the page pool and flatten results ---
            for page in page_pool:
                await page.close()

            for result in results_list:
                if result is not None and isinstance(result, list):
                    all_price_data.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"A price scraping worker failed with an exception: {result}")


        return all_price_data, showings_to_scrape

    async def run_full_diagnostic(self, log_callback):
        """
        Runs a comprehensive, step-by-step diagnostic of all scraping and database functions.
        """
        results = []
        test_zip = "76107" # A known good ZIP code
        test_theater_name = "AMC Palace 9"
        test_film_title = "Dune" # A common film for testing enrichment

        async def run_test(name, func, *args, **kwargs):
            log_callback(f"▶️ RUNNING: {name}...")
            try:
                result = await func(*args, **kwargs)
                if result:
                    log_callback(f"✅ PASSED: {name}")
                    results.append({"Test": name, "Status": "✅ Passed", "Result": "Success"})
                    return result
                else:
                    log_callback(f"❌ FAILED: {name} - No data returned.")
                    results.append({"Test": name, "Status": "❌ Failed", "Result": "No data returned"})
                    return None
            except Exception as e:
                log_callback(f"❌ FAILED: {name} - {e}")
                results.append({"Test": name, "Status": "❌ Failed", "Result": str(e)})
                return None

        # --- Database Checks ---
        log_callback("--- 1. DATABASE CHECKS ---")
        try:
            database.init_database() # This also checks for table existence
            latest_run = database.get_scrape_runs().head(1)
            latest_run_info = "No runs found"
            if not latest_run.empty:
                latest_run_info = f"Latest run on {latest_run['run_timestamp'].iloc[0]}"
            log_callback("✅ PASSED: Database Connection & Schema Check")
            results.append({"Test": "DB Connection & Schema", "Status": "✅ Passed", "Result": latest_run_info})
        except Exception as e:
            log_callback(f"❌ FAILED: Database Connection - {e}")
            results.append({"Test": "DB Connection & Schema", "Status": "❌ Failed", "Result": str(e)})
            return results # Stop if DB is down

        # --- Scraping Workflow ---
        log_callback("\n--- 2. CORE SCRAPING WORKFLOW ---")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
            page = await browser.new_page()
            try:
                # 2.1 ZIP Search
                zip_theaters = await run_test("ZIP Code Search", self.live_search_by_zip, test_zip, "2025-01-01", page=page)
                if not zip_theaters:
                    log_callback("--- DIAGNOSTIC STOPPED: Critical ZIP search failed. ---")
                    return results

                # 2.2 Name Search
                await run_test("Theater Name Search", self.live_search_by_name, test_theater_name, page=page)

                # 2.3 Showtime Discovery & Price Scrape
                theater_to_scrape = next((t for t in zip_theaters.values() if test_theater_name in t['name']), None)
                if not theater_to_scrape:
                    log_callback(f"❌ SKIPPED: Showtime/Price Scrape - Could not find '{test_theater_name}' in ZIP results.")
                else:
                    showings = await run_test("Showtime Discovery", self._get_movies_from_theater_page, page, theater_to_scrape, "2025-01-01")
                    if showings:
                        first_showing = showings[0]
                        await run_test("Price & Capacity Scrape", self._get_prices_and_capacity, page, first_showing)
            finally:
                await browser.close()

        # --- Enrichment Service Checks ---
        log_callback("\n--- 3. ENRICHMENT SERVICES ---")
        
        # 3.1 Fandango Film Search
        fandango_results = await run_test("Fandango Film Search", self.search_fandango_for_film_url, test_film_title)
        if fandango_results:
            # 3.2 Fandango Film Details
            await run_test("Fandango Film Details", self.get_film_details_from_fandango_url, fandango_results[0]['url'])

        # 3.3 OMDb Client
        try:
            from app.omdb_client import OMDbClient
            omdb_client = OMDbClient()
            await run_test("OMDb API Client", omdb_client.get_film_details_async, test_film_title)
        except Exception as e:
            log_callback(f"❌ FAILED: OMDb API Client - {e}")
            results.append({"Test": "OMDb API Client", "Status": "❌ Failed", "Result": str(e)})

        # 3.4 IMDb Scraper
        try:
            from app.imdb_scraper import IMDbScraper
            imdb_scraper = IMDbScraper()
            # This is not an async function, so we wrap it
            async def run_imdb(): return imdb_scraper.discover_upcoming_releases()
            await run_test("IMDb Release Calendar", run_imdb)
        except Exception as e:
            log_callback(f"❌ FAILED: IMDb Release Calendar - {e}")
            results.append({"Test": "IMDb Release Calendar", "Status": "❌ Failed", "Result": str(e)})

        # 3.5 Box Office Mojo Scraper
        try:
            from app.box_office_mojo_scraper import BoxOfficeMojoScraper
            bom_scraper = BoxOfficeMojoScraper()
            bom_url = await bom_scraper.discover_film_url_async(test_film_title)
            if bom_url:
                await run_test("Box Office Mojo Financials", bom_scraper.get_film_financials_async, bom_url)
            else:
                log_callback("❌ FAILED: Box Office Mojo - Could not discover film URL.")
                results.append({"Test": "Box Office Mojo", "Status": "❌ Failed", "Result": "Could not discover film URL"})
        except Exception as e:
            log_callback(f"❌ FAILED: Box Office Mojo - {e}")
            results.append({"Test": "Box Office Mojo", "Status": "❌ Failed", "Result": str(e)})

        return results

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

        CONCURRENCY_LIMIT = 5

        async def worker(page, theater):
            """Worker function to process a single theater."""
            result_row = {"Market": theater['market'], "Theater Name": theater['name'], "Status": "Failed", "Details": "No showtimes found", "Sample Price": "N/A"}
            try:
                showings = await self._get_movies_from_theater_page(page, theater, date)
                if showings:
                    first_showing = showings[0]
                    price_results = await self._get_prices_and_capacity(page, first_showing)
                    if price_results.get('tickets'):
                        first_ticket = price_results['tickets'][0]
                        result_row.update({
                            "Status": "Success",
                            "Details": f"Scraped '{first_showing['film_title']}' at {first_showing['showtime']}",
                            "Sample Price": f"{first_ticket['type']}: {first_ticket['price']}"
                        })
                    else:
                        result_row["Details"] = price_results.get('error', "Failed to extract price from ticket page.")
                return result_row
            except Exception as e:
                result_row["Details"] = f"An unexpected error occurred: {str(e)}"
                return result_row

        async with async_playwright() as p: # type: ignore
            browser = await p.chromium.launch(headless=self.headless, devtools=self.devtools)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
            
            semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
            async def bound_worker(theater):
                async with semaphore:
                    page = await context.new_page()
                    try:
                        return await worker(page, theater)
                    finally:
                        await page.close()

            tasks = [bound_worker(theater) for theater in theaters_to_test]
            diagnostic_results = await asyncio.gather(*tasks)

        return diagnostic_results
