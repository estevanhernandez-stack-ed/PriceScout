import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import datetime

class IMDbScraper:
    """
    A client for fetching film data from IMDb.
    - Discovers upcoming films from the IMDb release calendar.
    """

    BASE_URL = "https://www.imdb.com"

    def __init__(self):
        """Initializes the scraper."""
        pass

    def discover_upcoming_releases(self) -> list[dict]:
        """
        Discovers upcoming films from the IMDb release calendar.

        Returns:
            list[dict]: A list of dictionaries, each containing a film's title and release_date.
        """
        calendar_url = f"{self.BASE_URL}/calendar/"
        print(f"[IMDb Scraper] Discovering films from: {calendar_url}...")
        film_list = []
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }

        try:
            with httpx.Client(headers=headers, follow_redirects=True) as client:
                response = client.get(calendar_url)
                response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all h4 tags which are the date headers
            date_headers = soup.find_all('h4')
            for header in date_headers:
                try:
                    # The date is the content of the h4 tag
                    release_date_str = header.get_text(strip=True)
                    release_date = datetime.datetime.strptime(release_date_str, '%d %B %Y').strftime('%Y-%m-%d')
                    
                    # The list of films is in the next sibling ul
                    film_ul = header.find_next_sibling('ul')
                    if film_ul:
                        for li in film_ul.find_all('li'):
                            title = li.get_text(strip=True)
                            # Clean up title from potential "(I) (2025)" suffixes
                            title = re.sub(r'\s*\(\w+\)\s*\(\d{4}\)$', '', title).strip()
                            film_list.append({"title": title, "release_date": release_date})
                except (ValueError, TypeError):
                    continue # Skip if date format is unexpected
            
            return film_list
        except Exception as e:
            print(f"[IMDb Scraper] [ERROR] Failed to parse IMDb calendar. Reason: {e}")
            return []