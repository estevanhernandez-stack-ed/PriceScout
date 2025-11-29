import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from opentelemetry import trace

# Get tracer for custom spans
tracer = trace.get_tracer(__name__)

class BoxOfficeMojoScraper:
    """
    A client for fetching film data from Box Office Mojo.
    - Discovers films by year by scraping the yearly release schedule.
    - Scrapes financial data (budget, worldwide gross) directly from film pages.
    """

    BASE_URL = "https://www.boxofficemojo.com"

    def __init__(self):
        """Initializes the scraper."""
        pass

    def discover_films_by_year(self, year: int) -> list[dict]:
        """
        Discovers films for a given year by scraping the monthly release schedules.

        Args:
            year (int): The year to fetch the release schedule for.

        Returns:
            list[dict]: A list of dictionaries, each containing a film's title and bom_url.
        """
        with tracer.start_as_current_span(
            "box_office_mojo.discover_films_by_year",
            attributes={"bom.year": year}
        ) as span:
            try:
                all_films = []
                for month in range(1, 13):
                    monthly_films = self.discover_films_by_month(year, month)
                    all_films.extend(monthly_films)
                
                # Remove duplicates
                seen_titles = set()
                unique_films = []
                for film in all_films:
                    if film['title'] not in seen_titles:
                        unique_films.append(film)
                        seen_titles.add(film['title'])

                print(f"[BOM Scraper] Discovered {len(unique_films)} unique films for {year}.")
                
                # Add business metrics
                span.set_attribute("bom.films_discovered", len(unique_films))
                span.set_attribute("bom.total_entries", len(all_films))
                span.set_attribute("bom.duplicates_removed", len(all_films) - len(unique_films))
                
                return unique_films
            except Exception as e:
                span.set_attribute("bom.error", str(e))
                span.set_attribute("bom.error_type", type(e).__name__)
                raise

    def discover_films_by_month(self, year: int, month: int) -> list[dict]:
        """
        Discovers films for a given month and year by scraping the release schedule.

        Args:
            year (int): The year to fetch the release schedule for.
            month (int): The month to fetch the release schedule for.

        Returns:
            list[dict]: A list of dictionaries, each containing a film's title and bom_url.
        """
        schedule_url = f"{self.BASE_URL}/calendar/{year}-{str(month).zfill(2)}-01/"
        print(f"[BOM Scraper] Discovering films from: {schedule_url}...")
        film_list = []
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }

        try:
            with httpx.Client(headers=headers, follow_redirects=True) as client:
                response = client.get(schedule_url)
                response.raise_for_status()

            soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')

            # Find all links that point to a film release page
            film_links = soup.find_all('a', href=re.compile(r'^/release/'))

            for link in film_links:
                h3 = link.find('h3')
                if h3:
                    title = h3.get_text(strip=True)
                    relative_url = link['href']
                    full_url = urljoin(self.BASE_URL, relative_url)
                    
                    film_list.append({
                        "title": title,
                        "bom_url": full_url
                    })
            
            print(f"[BOM Scraper] Discovered {len(film_list)} films for {year}-{month}.")
            return film_list

        except httpx.RequestError as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                print(f"[BOM Scraper] [INFO] Schedule page for {year}-{month} not found (404). It might not exist yet or the URL format has changed.")
            else:
                print(f"[BOM Scraper] [ERROR] HTTP request failed for {schedule_url}. Reason: {e}")
            return []
        except Exception as e:
            print(f"[BOM Scraper] [ERROR] Failed to parse schedule for {year}-{month}. Reason: {e}")
            return []

    def discover_film_url(self, title: str) -> str | None:
        """
        Searches Box Office Mojo for a specific film and returns its URL.

        Args:
            title (str): The title of the film to search for.

        Returns:
            str | None: The URL of the film's main page, or None if not found.
        """
        search_url = f"{self.BASE_URL}/search/?q={title}"
        print(f"[BOM Scraper] Searching for '{title}' at: {search_url}...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }

        try:
            with httpx.Client(headers=headers, follow_redirects=True) as client:
                response = client.get(search_url)
                response.raise_for_status()

            soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')

            # Find the first search result link that points to a title page
            # The most relevant result is usually the first one.
            result_link = soup.find('a', href=re.compile(r'^/title/tt\d+/$'))

            if result_link:
                relative_url = result_link['href']
                full_url = urljoin(self.BASE_URL, relative_url)
                print(f"[BOM Scraper] Found URL for '{title}': {full_url}")
                return full_url
            else:
                print(f"[BOM Scraper] [INFO] No direct match found for '{title}' on Box Office Mojo.")
                return None

        except httpx.RequestError as e:
            print(f"[BOM Scraper] [ERROR] HTTP request failed during search for '{title}'. Reason: {e}")
            return None
        except Exception as e:
            print(f"[BOM Scraper] [ERROR] Failed to parse search results for '{title}'. Reason: {e}")
            return None

    async def discover_film_url_async(self, title: str) -> str | None:
        """
        Asynchronously searches Box Office Mojo for a specific film and returns its URL.
        """
        search_url = f"{self.BASE_URL}/search/?q={title}"
        print(f"[BOM Scraper] Async searching for '{title}' at: {search_url}...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }

        try:
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                response = await client.get(search_url)
                response.raise_for_status()

            soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')

            result_link = soup.find('a', href=re.compile(r'^/title/tt\d+/$'))

            if result_link:
                relative_url = result_link['href']
                full_url = urljoin(self.BASE_URL, relative_url)
                print(f"[BOM Scraper] Found URL for '{title}': {full_url}")
                return full_url
            else:
                print(f"[BOM Scraper] [INFO] No direct match found for '{title}' on Box Office Mojo.")
                return None

        except httpx.RequestError as e:
            print(f"[BOM Scraper] [ERROR] HTTP request failed during async search for '{title}'. Reason: {e}")
            return None
        except Exception as e:
            print(f"[BOM Scraper] [ERROR] Failed to parse async search results for '{title}'. Reason: {e}")
            return None

    def get_film_financials(self, bom_url: str) -> dict:
        """
        Fetches detailed financial data for a single film using its Box Office Mojo URL.
        """
        print(f"[BOM Scraper] Getting financials from: {bom_url}...")
        financials = {"opening_weekend_domestic": None, "domestic_gross": None}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }

        try:
            response = httpx.get(bom_url, headers=headers, follow_redirects=True, timeout=15.0)
            response.raise_for_status()
            soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')

            # Find the domestic gross
            domestic_gross_label = soup.find('span', string='Domestic Gross')
            if domestic_gross_label and domestic_gross_label.find_next_sibling('span'):
                financials['domestic_gross'] = self._parse_money(domestic_gross_label.find_next_sibling('span').get_text(strip=True))

            # Find the opening weekend domestic gross
            opening_weekend_label = soup.find('span', string='Opening Weekend')
            if opening_weekend_label and opening_weekend_label.find_next_sibling('span'):
                financials['opening_weekend_domestic'] = self._parse_money(opening_weekend_label.find_next_sibling('span').get_text(strip=True))

            return financials

        except httpx.RequestError as e:
            print(f"[BOM Scraper] [ERROR] HTTP request failed for {bom_url}. Reason: {e}")
            return financials
        except Exception as e:
            print(f"[BOM Scraper] [ERROR] Failed to parse financial data for {bom_url}. Reason: {e}")
            return financials

    async def get_film_financials_async(self, bom_url: str) -> dict:
        """
        Asynchronously fetches detailed financial data for a single film.
        """
        with tracer.start_as_current_span(
            "box_office_mojo.get_film_financials",
            attributes={"bom.url": bom_url}
        ) as span:
            try:
                print(f"[BOM Scraper] Async getting financials from: {bom_url}...")
                financials = {"opening_weekend_domestic": None, "domestic_gross": None}

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
                }

                async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as client:
                    response = await client.get(bom_url)
                    response.raise_for_status()
                soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
                
                # Find the domestic gross
                domestic_gross_label = soup.find('span', string='Domestic Gross')
                if domestic_gross_label and domestic_gross_label.find_next_sibling('span'):
                    financials['domestic_gross'] = self._parse_money(domestic_gross_label.find_next_sibling('span').get_text(strip=True))

                # Find the opening weekend domestic gross
                opening_weekend_label = soup.find('span', string='Opening Weekend')
                if opening_weekend_label and opening_weekend_label.find_next_sibling('span'):
                    financials['opening_weekend_domestic'] = self._parse_money(opening_weekend_label.find_next_sibling('span').get_text(strip=True))

                # Add telemetry
                span.set_attribute("bom.domestic_gross_found", financials['domestic_gross'] is not None)
                span.set_attribute("bom.opening_weekend_found", financials['opening_weekend_domestic'] is not None)
                if financials['domestic_gross']:
                    span.set_attribute("bom.domestic_gross_value", financials['domestic_gross'])

                return financials
            except httpx.RequestError as e:
                print(f"[BOM Scraper] [ERROR] Async HTTP request failed for {bom_url}. Reason: {e}")
                span.set_attribute("bom.error", str(e))
                span.set_attribute("bom.error_type", "HTTPError")
                return financials
            except Exception as e:
                print(f"[BOM Scraper] [ERROR] Async failed to parse financial data for {bom_url}. Reason: {e}")
                span.set_attribute("bom.error", str(e))
                span.set_attribute("bom.error_type", type(e).__name__)
                return financials

    def _parse_money(self, money_str: str) -> int | None:
        """
        Parses a money string like '$1,234,567' into an integer.
        """
        if not money_str or money_str == 'N/A':
            return None
        try:
            return int(re.sub(r'[$,]', '', money_str))
        except (ValueError, TypeError):
            return None