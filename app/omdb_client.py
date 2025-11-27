import os
import requests
import streamlit as st
import httpx
from datetime import datetime
import re
from thefuzz import fuzz

class OMDbClient:
    """
    A client to interact with the Open Movie Database (OMDb) API.
    Handles making requests, parsing data, and managing errors.
    """
    API_URL = "http://www.omdbapi.com/"

    def __init__(self):
        """Initializes the client with the API key from Streamlit secrets or environment."""
        api_key_value = ""
        try:
            api_key_value = st.secrets["omdb_api_key"]
        except (AttributeError, KeyError):
            # st.secrets not configured or key missing; fall back to env var
            pass

        # Fallback: environment variable
        if not api_key_value:
            api_key_value = os.getenv("OMDB_API_KEY", "")

        if not api_key_value:
            raise ValueError("OMDb API key not found. Set 'omdb_api_key' in .streamlit/secrets.toml or export OMDB_API_KEY env var.")

        # Be robust: if user pastes the full example URL, extract just the key
        if "apikey=" in api_key_value:
            self.api_key = api_key_value.split("apikey=")[-1]
        else:
            self.api_key = api_key_value

    def _parse_title_and_year(self, full_title: str) -> tuple[str, str | None]:
        """
        Parses a title string to separate the film name and year if present.
        e.g., "Movie Title (2023)" -> ("Movie Title", "2023")
        """
        match = re.search(r'\s*\((\d{4})\)$', full_title)
        if match:
            year = match.group(1)
            title = full_title[:match.start()].strip()
            return title, year
        return full_title, None

    def _parse_film_data(self, api_response: dict) -> dict:
        """Parses the raw JSON response from OMDb into a structured dictionary."""
        # Helper function to safely convert values
        def safe_convert(value, type_func, default=None):
            if value is None or value == 'N/A':
                return default
            try:
                # Remove commas from numbers like '1,234' before converting
                if isinstance(value, str):
                    value = value.replace(',', '')
                return type_func(value)
            except (ValueError, TypeError):
                return default

        def parse_release_date(date_str: str | None) -> str | None:
            """Parses OMDb's date format '15 Sep 2025' into '2025-09-15'."""
            if not date_str or date_str == 'N/A':
                return None
            try:
                return datetime.strptime(date_str, '%d %b %Y').strftime('%Y-%m-%d')
            except ValueError:
                # If format is unexpected, return the original string
                return date_str

        return {
            "film_title": api_response.get("Title"), # Use the official title as the primary key
            "imdb_id": api_response.get("imdbID"),
            "genre": api_response.get("Genre"),
            "mpaa_rating": api_response.get("Rated"),
            "runtime": api_response.get("Runtime"),
            "director": api_response.get("Director"),
            "actors": api_response.get("Actors"),
            "plot": api_response.get("Plot"),
            "poster_url": api_response.get("Poster"),
            "metascore": safe_convert(api_response.get("Metascore"), int),
            "imdb_rating": safe_convert(api_response.get("imdbRating"), float),
            "release_date": parse_release_date(api_response.get("Released")),
            "domestic_gross": self._parse_omdb_box_office(api_response.get("BoxOffice")),
            "opening_weekend_domestic": None, # OMDb does not provide this reliably
            "last_omdb_update": datetime.now()
        }

    def _search_omdb(self, title: str, year: str | None) -> dict | None:
        """Internal helper to perform a single search against the OMDb API."""
        # --- NEW: Always parse the year out of the title for the search query ---
        parsed_title, parsed_year_from_title = self._parse_title_and_year(title)
        final_year = year or parsed_year_from_title # Prioritize explicitly passed year

        params = {
            "apikey": self.api_key,
            "t": parsed_title,
            "plot": "full"
        }
        if final_year:
            params["y"] = final_year

        try:
            response = requests.get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  [OMDb] Error connecting to OMDb API: {e}")
            return None

    async def _search_omdb_async(self, title: str, year: str | None, client: httpx.AsyncClient) -> dict | None:
        """Async internal helper to perform a single search against the OMDb API."""
        parsed_title, parsed_year_from_title = self._parse_title_and_year(title)
        final_year = year or parsed_year_from_title

        params = {
            "apikey": self.api_key,
            "t": parsed_title,
            "plot": "full"
        }
        if final_year:
            params["y"] = final_year

        try:
            response = await client.get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            print(f"  [OMDb] Async error connecting to OMDb API: {e}")
            return None
        except Exception as e:
            print(f"  [OMDb] Async parsing error: {e}")
            return None

    def _parse_omdb_box_office(self, value: str | None) -> int | None:
        """Parses the BoxOffice string from OMDb into an integer."""
        if not value or value == 'N/A':
            return None
        try:
            return int(re.sub(r'[$,]', '', value))
        except (ValueError, TypeError):
            return None

    def _search_by_id(self, imdb_id: str) -> dict | None:
        """Internal helper to perform a search by IMDb ID."""
        params = {
            "apikey": self.api_key,
            "i": imdb_id,
            "plot": "full"
        }
        try:
            response = requests.get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  [OMDb] Error connecting to OMDb API by ID: {e}")
            return None

    def _fuzzy_search_and_match(self, title: str, year: str | None) -> dict | None:
        """Performs a general search and uses fuzzy matching to find the best result."""
        params = {"apikey": self.api_key, "s": title, "type": "movie"}
        if year:
            params["y"] = year
        try:
            response = requests.get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            search_results = response.json()
        except requests.exceptions.RequestException as e:
            print(f"  [OMDb] Fuzzy search request failed: {e}")
            return None

        if search_results.get("Response") == "True":
            best_match, highest_score = None, 0
            for result in search_results.get("Search", []):
                score = fuzz.ratio(title.lower(), result.get("Title", "").lower())
                if year and result.get("Year") == year:
                    score += 10
                if score > highest_score:
                    highest_score, best_match = score, result
            if highest_score > 90 and best_match:
                print(f"  [OMDb] Found high-confidence fuzzy match for '{title}': '{best_match['Title']}' (Score: {highest_score}). Fetching details by ID.")
                return self._search_by_id(best_match['imdbID'])
        return None

    def get_film_details(self, title: str, year: str = None) -> dict | None:
        """
        Fetches film details from OMDb by title. If a year is not provided,
        it attempts to parse one from the title string (e.g., "Film (2025)").
        It also attempts to clean the title of common event terms for a second-pass search.
        """
        # First attempt with the original title
        from app.utils import clean_film_title # Local import to break circular dependency
        data = self._search_omdb(title, year)

        if data and data.get("Response") == "True":
            return self._parse_film_data(data)
        
        # If the first attempt fails, try cleaning the title
        cleaned_title = clean_film_title(title)
        
        if cleaned_title.lower() != title.lower():
            print(f"  [OMDb] Initial search for '{title}' failed. Retrying with cleaned title: '{cleaned_title}'...")
            # Second attempt with the cleaned title
            cleaned_data = self._search_omdb(cleaned_title, year) # Note: year is passed along
            if cleaned_data and cleaned_data.get("Response") == "True":
                return self._parse_film_data(cleaned_data)

        # Third attempt: Fuzzy search as a last resort
        print(f"  [OMDb] Exact matches failed. Attempting fuzzy search for '{cleaned_title}'...")
        fuzzy_data = self._fuzzy_search_and_match(cleaned_title, year)
        if fuzzy_data and fuzzy_data.get("Response") == "True":
            return self._parse_film_data(fuzzy_data)

        # If all attempts fail, log the original failure reason if available
        failure_reason = data.get('Error') if data else "Connection error or no match found"
        print(f"  [OMDb] API: Could not find details for '{title}'. Reason: {failure_reason}")
        
        return None

    async def get_film_details_async(self, title: str, year: str = None) -> dict | None:
        """
        Asynchronously fetches film details from OMDb by title.
        """
        from app.utils import clean_film_title # Local import to break circular dependency
        async with httpx.AsyncClient() as client:
            # First attempt with the original title
            data = await self._search_omdb_async(title, year, client)

            if data and data.get("Response") == "True":
                return self._parse_film_data(data)
            
            # If the first attempt fails, try cleaning the title
            cleaned_title = clean_film_title(title)
            
            if cleaned_title.lower() != title.lower():
                print(f"  [OMDb] Initial async search for '{title}' failed. Retrying with cleaned title: '{cleaned_title}'...")
                cleaned_data = await self._search_omdb_async(cleaned_title, year, client)
                if cleaned_data and cleaned_data.get("Response") == "True":
                    return self._parse_film_data(cleaned_data)

        failure_reason = data.get('Error') if data else "Connection error or no match found"
        print(f"  [OMDb] API: Could not find details for '{title}'. Reason: {failure_reason}")
        return None