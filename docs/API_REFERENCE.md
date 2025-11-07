# 📚 Price Scout API Reference

**Version:** 1.0.0  
**Last Updated:** October 26, 2025  
**Target Audience:** Developers and Contributors

---

## Table of Contents

1. [Overview](#overview)
2. [Core Modules](#core-modules)
3. [Scraper Module](#scraper-module)
4. [Database Module](#database-module)
5. [OMDb Client Module](#omdb-client-module)
6. [Users Module](#users-module)
7. [Utils Module](#utils-module)
8. [UI Components Module](#ui-components-module)
9. [Mode Modules](#mode-modules)
10. [Configuration](#configuration)
11. [Data Structures](#data-structures)
12. [Testing Utilities](#testing-utilities)

---

## Overview

Price Scout is built on a modular architecture with clear separation of concerns:

- **Scraping Layer** - `scraper.py` handles web scraping via Playwright
- **Data Layer** - `database.py` manages SQLite persistence
- **API Layer** - `omdb_client.py` integrates external film metadata
- **Auth Layer** - `users.py` handles authentication and authorization
- **UI Layer** - Streamlit-based interface with mode-specific modules
- **Utilities** - `utils.py` provides shared helper functions

### Import Patterns

```python
# Core modules
from app.scraper import Scraper
from app import database
from app.omdb_client import OMDbClient
from app import users
from app import utils
from app import config

# Mode modules
from app.modes import market_mode
from app.modes import analysis_mode
from app.modes import poster_mode
from app.modes import operating_hours_mode
from app.modes import compsnipe_mode

# UI components
from app import ui_components
from app import theming
```

---

## Core Modules

### Module Hierarchy

```
app/
├── __init__.py
├── scraper.py          # Web scraping engine
├── database.py         # Data persistence
├── omdb_client.py      # Film metadata API
├── users.py            # User management
├── utils.py            # Utility functions
├── config.py           # Configuration constants
├── state.py            # Streamlit session state
├── theming.py          # UI theme management
├── ui_components.py    # Reusable UI widgets
├── price_scout_app.py  # Main application
└── modes/              # Feature modules
    ├── __init__.py
    ├── market_mode.py
    ├── analysis_mode.py
    ├── poster_mode.py
    ├── operating_hours_mode.py
    └── compsnipe_mode.py
```

### Dependencies

**External Packages:**
- `streamlit` - Web UI framework
- `playwright` - Browser automation
- `pandas` - Data manipulation
- `bcrypt` - Password hashing
- `beautifulsoup4` - HTML parsing
- `thefuzz` - Fuzzy string matching
- `httpx` - HTTP client
- `openpyxl` - Excel file generation

**Python Standard Library:**
- `sqlite3` - Database
- `asyncio` - Async operations
- `logging` - Logging framework
- `datetime` - Date/time handling
- `json` - JSON parsing
- `re` - Regular expressions

---

## Scraper Module

**File:** `app/scraper.py`  
**Purpose:** Web scraping engine using Playwright to extract showtime and pricing data from Fandango.

### Class: `Scraper`

Main class for web scraping operations.

#### Constructor

```python
def __init__(self, headless=True, devtools=False):
    """
    Initializes the Scraper with browser configuration.
    
    Args:
        headless (bool): Run browser in headless mode (no visible window)
        devtools (bool): Open browser DevTools for debugging
        
    Attributes:
        ticket_types_data (dict): Loaded from ticket_types.json
        headless (bool): Browser visibility setting
        devtools (bool): DevTools enabled flag
        capture_html (bool): Save HTML on failures
        amenity_map_re (dict): Precompiled regex for amenity detection
        base_type_map_re (dict): Precompiled regex for ticket types
        plf_formats (set): Premium Large Format identifiers
        ignored_amenities (set): Amenity terms to skip
    """
```

**Example Usage:**

```python
from app.scraper import Scraper

# Production mode (headless)
scout = Scraper(headless=True, devtools=False)

# Debug mode (visible browser with DevTools)
scout = Scraper(headless=False, devtools=True)

# Enable HTML capture for failures
scout.capture_html = True
```

#### Key Methods

##### `get_all_showings_for_theaters`

```python
async def get_all_showings_for_theaters(
    self, 
    theaters: dict, 
    date_str: str, 
    page=None
) -> tuple[str, dict | str, str, dict | None]:
    """
    Scrapes showtimes for multiple theaters on a specific date.
    
    Args:
        theaters (dict): Theater data {name: {name, url}}
        date_str (str): Date in 'YYYY-MM-DD' format
        page (Page, optional): Existing Playwright page object
        
    Returns:
        tuple: (status, result, log, metadata)
            status (str): 'success' or 'error'
            result (dict | str): Showings data or error message
            log (str): Detailed execution log
            metadata (dict | None): Scrape metrics
            
    Data Structure (on success):
        {
            'YYYY-MM-DD': {
                'Theater Name': {
                    'Film Title': {
                        'HH:MM AM/PM': [
                            {
                                'url': 'https://...',
                                'format': 'IMAX',
                                'ticket_info': {...},
                                'theater_name': 'Theater Name',
                                'play_date': 'YYYY-MM-DD'
                            }
                        ]
                    }
                }
            }
        }
    """
```

**Example:**

```python
import asyncio
from app.scraper import Scraper

async def main():
    scout = Scraper()
    
    theaters = {
        "AMC Mesquite 30": {
            "name": "AMC Mesquite 30",
            "url": "https://www.fandango.com/amc-mesquite-30-aabcd"
        }
    }
    
    status, result, log, metadata = await scout.get_all_showings_for_theaters(
        theaters, 
        "2025-12-25"
    )
    
    if status == 'success':
        for date, theaters in result.items():
            for theater, films in theaters.items():
                for film, showtimes in films.items():
                    print(f"{theater} - {film}: {len(showtimes)} showtimes")
    else:
        print(f"Error: {result}")

asyncio.run(main())
```

##### `get_prices`

```python
async def get_prices(
    self, 
    showing_urls: list[dict], 
    page=None
) -> tuple[str, list[dict] | str, str]:
    """
    Scrapes pricing information for specific showtimes.
    
    Args:
        showing_urls (list[dict]): List of showing objects with URLs
        page (Page, optional): Existing Playwright page
        
    Returns:
        tuple: (status, result, log)
            status (str): 'success' or 'error'
            result (list[dict] | str): Price data or error message
            log (str): Execution log
            
    Price Data Structure:
        [
            {
                'theater_name': 'Theater Name',
                'play_date': 'YYYY-MM-DD',
                'film_title': 'Film Title',
                'showtime': 'HH:MM AM/PM',
                'format': 'IMAX',
                'daypart': 'Evening',
                'ticket_url': 'https://...',
                'prices': [
                    {
                        'ticket_type': 'Adult',
                        'price': 16.99,
                        'capacity': '50/150'
                    }
                ]
            }
        ]
    """
```

**Example:**

```python
showings_to_price = [
    {
        'url': 'https://www.fandango.com/...',
        'theater_name': 'AMC Mesquite 30',
        'play_date': '2025-12-25',
        'film_title': 'Wicked',
        'showtime': '7:00 PM',
        'format': 'IMAX'
    }
]

status, prices, log = await scout.get_prices(showings_to_price)

if status == 'success':
    for showing in prices:
        for price_entry in showing['prices']:
            print(f"{price_entry['ticket_type']}: ${price_entry['price']}")
```

##### `live_search_by_zip`

```python
async def live_search_by_zip(
    self, 
    zip_code: str, 
    date_str: str, 
    page=None
) -> tuple[str, dict | str, str, None]:
    """
    Searches for theaters near a ZIP code with showtimes on a date.
    
    Args:
        zip_code (str): 5-digit US ZIP code
        date_str (str): Date in 'YYYY-MM-DD' format
        page (Page, optional): Existing Playwright page
        
    Returns:
        tuple: (status, result, log, None)
            status (str): 'success' or 'error'
            result (dict | str): Theater data or error message
            log (str): Execution log
            
    Theater Data Structure:
        {
            'Theater Name': {
                'name': 'Theater Name',
                'url': 'https://www.fandango.com/...'
            }
        }
    """
```

**Example:**

```python
# Find theaters near ZIP code 75001 on Christmas
status, theaters, log, _ = await scout.live_search_by_zip(
    "75001", 
    "2025-12-25"
)

if status == 'success':
    print(f"Found {len(theaters)} theaters:")
    for name, data in theaters.items():
        print(f"  - {name}: {data['url']}")
```

##### `get_operating_hours`

```python
async def get_operating_hours(
    self, 
    theaters: dict, 
    date_str: str, 
    page=None
) -> tuple[str, dict | str, str, dict | None]:
    """
    Scrapes theater operating hours for a specific date.
    
    Args:
        theaters (dict): Theater data {name: {name, url}}
        date_str (str): Date in 'YYYY-MM-DD' format
        page (Page, optional): Existing Playwright page
        
    Returns:
        tuple: (status, result, log, metadata)
            status (str): 'success' or 'error'
            result (dict | str): Hours data or error message
            log (str): Execution log
            metadata (dict | None): Scrape metrics
            
    Hours Data Structure:
        {
            'YYYY-MM-DD': {
                'Theater Name': {
                    'name': 'Theater Name',
                    'hours': '10:00 AM - 11:00 PM'
                }
            }
        }
    """
```

**Example:**

```python
status, hours, log, _ = await scout.get_operating_hours(
    theaters, 
    "2025-12-25"
)

if status == 'success':
    for date, theater_hours in hours.items():
        for theater, data in theater_hours.items():
            print(f"{theater}: {data['hours']}")
```

#### Helper Methods

##### `_parse_ticket_description`

```python
def _parse_ticket_description(
    self, 
    description: str, 
    showing_details: dict | None = None
) -> dict:
    """
    Parses ticket description to extract type and amenities.
    
    Args:
        description (str): Raw ticket description from website
        showing_details (dict, optional): Context (format, theater, etc.)
        
    Returns:
        dict: {
            'base_type': 'Adult' | 'Senior' | 'Child' | etc.,
            'amenities': ['Recliner', 'Reserved Seating', ...]
        }
    """
```

##### `_find_amenities_in_string`

```python
def _find_amenities_in_string(self, text: str) -> list[str]:
    """
    Extracts amenities from text using regex patterns.
    
    Args:
        text (str): Text to analyze
        
    Returns:
        list[str]: Unique amenities found
    """
```

##### `_strip_common_terms`

```python
def _strip_common_terms(self, name: str) -> str:
    """
    Removes common cinema brand names for fuzzy matching.
    
    Args:
        name (str): Theater name
        
    Returns:
        str: Cleaned name
    """
```

---

## Database Module

**File:** `app/database.py`  
**Purpose:** SQLite database operations for persistent data storage.

### Database Schema

#### Table: `scrape_runs`

Tracks scraping sessions.

```sql
CREATE TABLE scrape_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp DATETIME NOT NULL,
    mode TEXT NOT NULL
);
```

#### Table: `showings`

Stores individual showtimes.

```sql
CREATE TABLE showings (
    showing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    play_date DATE NOT NULL,
    theater_name TEXT NOT NULL,
    film_title TEXT NOT NULL,
    showtime TEXT NOT NULL,
    format TEXT,
    daypart TEXT,
    is_plf BOOLEAN DEFAULT 0,
    ticket_url TEXT,
    UNIQUE(play_date, theater_name, film_title, showtime, format)
);
```

#### Table: `prices`

Stores ticket pricing data.

```sql
CREATE TABLE prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    showing_id INTEGER,
    ticket_type TEXT NOT NULL,
    price REAL NOT NULL,
    capacity TEXT,
    play_date DATE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs (run_id),
    FOREIGN KEY (showing_id) REFERENCES showings (showing_id)
);
```

#### Table: `films`

Stores film metadata from OMDb.

```sql
CREATE TABLE films (
    film_id INTEGER PRIMARY KEY AUTOINCREMENT,
    film_title TEXT NOT NULL UNIQUE,
    imdb_id TEXT,
    genre TEXT,
    mpaa_rating TEXT,
    director TEXT,
    actors TEXT,
    plot TEXT,
    poster_url TEXT,
    metascore INTEGER,
    imdb_rating REAL,
    release_date TEXT,
    domestic_gross INTEGER,
    runtime TEXT,
    opening_weekend_domestic INTEGER,
    last_omdb_update DATETIME NOT NULL
);
```

#### Table: `operating_hours`

Stores theater operating hours.

```sql
CREATE TABLE operating_hours (
    operating_hours_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    market TEXT,
    theater_name TEXT NOT NULL,
    date DATE NOT NULL,
    opening_time TEXT,
    closing_time TEXT,
    FOREIGN KEY (run_id) REFERENCES scrape_runs (run_id)
);
```

### Key Functions

#### `init_database`

```python
def init_database() -> None:
    """
    Initializes the SQLite database and creates tables if they don't exist.
    Must be called before any database operations.
    
    Raises:
        AssertionError: If config.DB_FILE is not set
    """
```

**Example:**

```python
from app import database, config

# Set database path
config.DB_FILE = "data/Marcus/price_scout.db"

# Initialize database
database.init_database()
```

#### `save_scrape_run`

```python
def save_scrape_run(
    data: list[dict], 
    mode: str, 
    timestamp: datetime.datetime | None = None
) -> int:
    """
    Saves a scraping session to the database.
    
    Args:
        data (list[dict]): Price data from scraper
        mode (str): Mode name ('Market Mode', 'CompSnipe', etc.)
        timestamp (datetime, optional): Run timestamp (defaults to now)
        
    Returns:
        int: run_id of created scrape run
        
    Data Format:
        [
            {
                'theater_name': 'Theater',
                'play_date': 'YYYY-MM-DD',
                'film_title': 'Film',
                'showtime': 'HH:MM AM/PM',
                'format': 'IMAX',
                'daypart': 'Evening',
                'ticket_url': 'https://...',
                'prices': [
                    {'ticket_type': 'Adult', 'price': 16.99, 'capacity': '50/150'}
                ]
            }
        ]
    """
```

**Example:**

```python
import datetime
from app import database

price_data = [
    {
        'theater_name': 'AMC Mesquite 30',
        'play_date': '2025-12-25',
        'film_title': 'Wicked',
        'showtime': '7:00 PM',
        'format': 'IMAX',
        'daypart': 'Evening',
        'ticket_url': 'https://...',
        'prices': [
            {'ticket_type': 'Adult', 'price': 16.99, 'capacity': '100/150'},
            {'ticket_type': 'Senior', 'price': 14.99, 'capacity': '100/150'}
        ]
    }
]

run_id = database.save_scrape_run(price_data, 'Market Mode')
print(f"Saved run_id: {run_id}")
```

#### `get_all_showings_df`

```python
def get_all_showings_df(
    start_date: str | None = None, 
    end_date: str | None = None
) -> pd.DataFrame:
    """
    Retrieves all showings within a date range as a DataFrame.
    
    Args:
        start_date (str, optional): Start date 'YYYY-MM-DD'
        end_date (str, optional): End date 'YYYY-MM-DD'
        
    Returns:
        pd.DataFrame: Showing data with columns:
            - showing_id
            - play_date
            - theater_name
            - film_title
            - showtime
            - format
            - daypart
            - is_plf
            - ticket_url
    """
```

**Example:**

```python
from app import database

# Get all showings in December
df = database.get_all_showings_df('2025-12-01', '2025-12-31')

# Analyze by film
film_counts = df.groupby('film_title').size().sort_values(ascending=False)
print(film_counts.head(10))
```

#### `get_prices_for_showings`

```python
def get_prices_for_showings(
    showing_ids: list[int]
) -> pd.DataFrame:
    """
    Retrieves pricing data for specific showings.
    
    Args:
        showing_ids (list[int]): List of showing_id values
        
    Returns:
        pd.DataFrame: Price data with columns:
            - price_id
            - run_id
            - showing_id
            - ticket_type
            - price
            - capacity
            - play_date
    """
```

#### `get_all_films`

```python
def get_all_films() -> list[dict]:
    """
    Retrieves all films from the database.
    
    Returns:
        list[dict]: Film records with all metadata fields
    """
```

#### `save_or_update_film`

```python
def save_or_update_film(film_data: dict) -> None:
    """
    Inserts or updates film metadata in the database.
    
    Args:
        film_data (dict): Film metadata from OMDb client
            Required: 'film_title'
            Optional: All other OMDb fields
    """
```

**Example:**

```python
from app import database
from app.omdb_client import OMDbClient

# Fetch and save film metadata
omdb = OMDbClient()
film_data = omdb.get_film_by_title("Wicked", year="2024")

if film_data:
    database.save_or_update_film(film_data)
    print(f"Saved: {film_data['film_title']}")
```

#### `save_operating_hours`

```python
def save_operating_hours(
    hours_data: list[dict], 
    run_id: int, 
    market: str
) -> None:
    """
    Saves theater operating hours to database.
    
    Args:
        hours_data (list[dict]): Operating hours records
        run_id (int): Associated scrape run ID
        market (str): Market name
        
    Data Format:
        [
            {
                'theater_name': 'Theater',
                'date': 'YYYY-MM-DD',
                'opening_time': '10:00 AM',
                'closing_time': '11:00 PM'
            }
        ]
    """
```

#### `merge_external_database`

```python
def merge_external_database(external_db_path: str) -> dict:
    """
    Merges data from an external Price Scout database.
    
    Args:
        external_db_path (str): Path to external .db file
        
    Returns:
        dict: Merge statistics
            {
                'runs_added': int,
                'showings_added': int,
                'prices_added': int,
                'films_added': int
            }
            
    Raises:
        sqlite3.Error: On database errors
    """
```

**Example:**

```python
from app import database, config

config.DB_FILE = "data/Marcus/price_scout.db"
database.init_database()

stats = database.merge_external_database("backup_2025_10_25.db")
print(f"Merged {stats['runs_added']} runs, {stats['showings_added']} showings")
```

---

## OMDb Client Module

**File:** `app/omdb_client.py`  
**Purpose:** Integration with Open Movie Database API for film metadata.

### Class: `OMDbClient`

Handles OMDb API requests and data parsing.

#### Constructor

```python
def __init__(self):
    """
    Initializes OMDb client with API key from Streamlit secrets.
    
    Raises:
        ValueError: If API key not found in st.secrets['omdb_api_key']
        
    Attributes:
        api_key (str): OMDb API key
        API_URL (str): 'http://www.omdbapi.com/'
    """
```

**Configuration:**

```toml
# .streamlit/secrets.toml
omdb_api_key = "your_api_key_here"
```

**Example:**

```python
from app.omdb_client import OMDbClient

# Initialize (requires secrets.toml)
omdb = OMDbClient()
```

#### `get_film_by_title`

```python
def get_film_by_title(
    self, 
    title: str, 
    year: str | None = None
) -> dict | None:
    """
    Fetches film metadata from OMDb by title.
    
    Args:
        title (str): Film title (can include year in parentheses)
        year (str, optional): Release year for disambiguation
        
    Returns:
        dict | None: Film metadata or None if not found
        
    Return Structure:
        {
            'film_title': str,
            'imdb_id': str,
            'genre': str,
            'mpaa_rating': str,
            'runtime': str,
            'director': str,
            'actors': str,
            'plot': str,
            'poster_url': str,
            'metascore': int | None,
            'imdb_rating': float | None,
            'release_date': str,  # 'YYYY-MM-DD'
            'domestic_gross': int | None,
            'opening_weekend_domestic': None,
            'last_omdb_update': datetime
        }
    """
```

**Example:**

```python
from app.omdb_client import OMDbClient

omdb = OMDbClient()

# Simple title search
film = omdb.get_film_by_title("Wicked")

# With year for disambiguation
film = omdb.get_film_by_title("Dune", year="2021")

# Title with year in parentheses
film = omdb.get_film_by_title("Dune (2021)")

if film:
    print(f"{film['film_title']} ({film['mpaa_rating']})")
    print(f"Genre: {film['genre']}")
    print(f"Rating: {film['imdb_rating']}/10")
else:
    print("Film not found")
```

#### `search_films`

```python
def search_films(
    self, 
    query: str, 
    year: str | None = None
) -> list[dict]:
    """
    Searches for films matching a query.
    
    Args:
        query (str): Search term
        year (str, optional): Filter by release year
        
    Returns:
        list[dict]: List of film results (simplified data)
        
    Result Structure:
        [
            {
                'Title': str,
                'Year': str,
                'imdbID': str,
                'Type': 'movie' | 'series',
                'Poster': str
            }
        ]
    """
```

**Example:**

```python
results = omdb.search_films("Star Wars")

for film in results:
    print(f"{film['Title']} ({film['Year']}) - {film['imdbID']}")
```

#### Helper Methods

##### `_parse_title_and_year`

```python
def _parse_title_and_year(
    self, 
    full_title: str
) -> tuple[str, str | None]:
    """
    Extracts title and year from string.
    
    Args:
        full_title (str): 'Movie Title (2025)' or 'Movie Title'
        
    Returns:
        tuple: (title, year) where year may be None
    """
```

##### `_parse_film_data`

```python
def _parse_film_data(self, api_response: dict) -> dict:
    """
    Transforms OMDb API response to internal format.
    
    Args:
        api_response (dict): Raw API response
        
    Returns:
        dict: Standardized film data
    """
```

---

## Users Module

**File:** `app/users.py`  
**Purpose:** User authentication and authorization.

### Database

Separate SQLite database: `users.db`

**Schema:**

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT 0,
    company TEXT,
    default_company TEXT
);
```

### Functions

#### `init_database`

```python
def init_database() -> None:
    """
    Initializes user database and creates default admin account.
    
    Default Admin:
        Username: 'admin'
        Password: 'admin'
        
    ⚠️ Change default password immediately in production!
    """
```

#### `create_user`

```python
def create_user(
    username: str, 
    password: str, 
    is_admin: bool = False, 
    company: str | None = None, 
    default_company: str | None = None
) -> tuple[bool, str]:
    """
    Creates a new user account.
    
    Args:
        username (str): Unique username
        password (str): Plain text password (will be hashed)
        is_admin (bool): Grant admin privileges
        company (str, optional): Assigned company
        default_company (str, optional): Default company selection
        
    Returns:
        tuple: (success, message)
            success (bool): True if created
            message (str): Success or error message
    """
```

**Example:**

```python
from app import users

users.init_database()

# Create standard user
success, msg = users.create_user(
    "john.smith", 
    "SecurePass123!", 
    is_admin=False, 
    company="Marcus Theatres"
)

if success:
    print(f"User created: {msg}")
else:
    print(f"Error: {msg}")

# Create admin user
success, msg = users.create_user(
    "admin2", 
    "AdminPass456!", 
    is_admin=True
)
```

#### `verify_user`

```python
def verify_user(
    username: str, 
    password: str
) -> sqlite3.Row | None:
    """
    Authenticates a user.
    
    Args:
        username (str): Username
        password (str): Plain text password
        
    Returns:
        Row | None: User record if valid, None if invalid
        
    User Record Fields:
        - id
        - username
        - password_hash
        - is_admin
        - company
        - default_company
    """
```

**Example:**

```python
from app import users

user = users.verify_user("john.smith", "SecurePass123!")

if user:
    print(f"Welcome {user['username']}")
    print(f"Admin: {user['is_admin']}")
    print(f"Company: {user['company']}")
else:
    print("Invalid credentials")
```

#### `get_user`

```python
def get_user(username: str) -> sqlite3.Row | None:
    """
    Retrieves user by username.
    
    Args:
        username (str): Username to lookup
        
    Returns:
        Row | None: User record or None
    """
```

#### `get_all_users`

```python
def get_all_users() -> list[sqlite3.Row]:
    """
    Retrieves all users (for admin user management).
    
    Returns:
        list[Row]: All user records (password_hash excluded)
    """
```

#### `update_user`

```python
def update_user(
    user_id: int, 
    username: str, 
    is_admin: bool, 
    company: str, 
    default_company: str
) -> None:
    """
    Updates user account details.
    
    Args:
        user_id (int): User ID to update
        username (str): New username
        is_admin (bool): Admin status
        company (str): Assigned company
        default_company (str): Default company
        
    Note: Does not update password (use separate function)
    """
```

#### `delete_user`

```python
def delete_user(user_id: int) -> None:
    """
    Deletes a user account.
    
    Args:
        user_id (int): User ID to delete
        
    ⚠️ Permanent action - cannot be undone!
    """
```

### Password Security

**Hashing:**
- Uses BCrypt with automatic salt generation
- Configurable work factor (default: 12 rounds)
- Passwords never stored in plain text

**Best Practices:**
```python
import bcrypt

# Hash password
password = b"user_password"
hashed = bcrypt.hashpw(password, bcrypt.gensalt())

# Verify password
is_valid = bcrypt.checkpw(password, hashed)
```

---

## Utils Module

**File:** `app/utils.py`  
**Purpose:** Shared utility functions used across the application.

### Async Utilities

#### `run_async_in_thread`

```python
def run_async_in_thread(coro, *args, **kwargs):
    """
    Runs an async coroutine in a background thread.
    
    Args:
        coro: Async coroutine function
        *args: Positional arguments for coroutine
        **kwargs: Keyword arguments for coroutine
        
    Returns:
        tuple: (thread, result_func)
            thread: Thread object (call .join() to wait)
            result_func: Callable that returns (status, result, log, metadata)
            
    Used for running Playwright scraping in Streamlit.
    """
```

**Example:**

```python
from app.scraper import Scraper
from app.utils import run_async_in_thread

scout = Scraper()
theaters = {...}

# Start async operation in thread
thread, result_func = run_async_in_thread(
    scout.get_all_showings_for_theaters,
    theaters,
    "2025-12-25"
)

# Wait for completion
thread.join()

# Get results
status, showings, log, metadata = result_func()
```

### Data Formatting

#### `format_price_change`

```python
def format_price_change(
    old_price: float, 
    new_price: float
) -> str:
    """
    Formats price change with arrow and amount.
    
    Args:
        old_price (float): Previous price
        new_price (float): Current price
        
    Returns:
        str: '▲ +$2.00' or '▼ -$1.50' or '―'
    """
```

**Example:**

```python
from app.utils import format_price_change

change = format_price_change(14.99, 16.99)
print(change)  # '▲ +$2.00'

change = format_price_change(16.99, 14.99)
print(change)  # '▼ -$2.00'

change = format_price_change(14.99, 14.99)
print(change)  # '―'
```

#### `format_time_to_human_readable`

```python
def format_time_to_human_readable(seconds: float) -> str:
    """
    Converts seconds to human-readable duration.
    
    Args:
        seconds (float): Duration in seconds
        
    Returns:
        str: '2 minutes 30 seconds' or '1 hour 15 minutes'
    """
```

**Example:**

```python
from app.utils import format_time_to_human_readable

print(format_time_to_human_readable(125))  # '2 minutes 5 seconds'
print(format_time_to_human_readable(3665))  # '1 hour 1 minute 5 seconds'
```

### Data Conversion

#### `to_excel`

```python
def to_excel(df: pd.DataFrame) -> bytes:
    """
    Converts DataFrame to Excel bytes for download.
    
    Args:
        df (pd.DataFrame): Data to export
        
    Returns:
        bytes: Excel file content
    """
```

**Example:**

```python
import streamlit as st
from app.utils import to_excel

df = get_report_data()
excel_bytes = to_excel(df)

st.download_button(
    "Download Excel",
    data=excel_bytes,
    file_name="report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
```

#### `to_csv`

```python
def to_csv(df: pd.DataFrame) -> str:
    """
    Converts DataFrame to CSV string.
    
    Args:
        df (pd.DataFrame): Data to export
        
    Returns:
        str: CSV content
    """
```

#### `to_excel_multi_sheet`

```python
def to_excel_multi_sheet(report_data: list[dict]) -> bytes:
    """
    Creates multi-sheet Excel workbook.
    
    Args:
        report_data (list[dict]): List of sheet definitions
            [
                {
                    'sheet_name': 'Sheet 1',
                    'data': pd.DataFrame
                }
            ]
            
    Returns:
        bytes: Excel file with multiple sheets
    """
```

### String Utilities

#### `clean_film_title`

```python
def clean_film_title(title: str) -> str:
    """
    Normalizes film title for matching.
    
    Args:
        title (str): Raw film title
        
    Returns:
        str: Cleaned title
        
    Transformations:
        - Removes year in parentheses
        - Converts to title case
        - Strips extra whitespace
        - Removes special characters
    """
```

**Example:**

```python
from app.utils import clean_film_title

print(clean_film_title("the batman (2022)"))  # "The Batman"
print(clean_film_title("DUNE: PART TWO"))     # "Dune Part Two"
```

#### `normalize_time_string`

```python
def normalize_time_string(time_str: str) -> str:
    """
    Normalizes time format to 'HH:MM AM/PM'.
    
    Args:
        time_str (str): Time in various formats
        
    Returns:
        str: Standardized time string
    """
```

**Example:**

```python
from app.utils import normalize_time_string

print(normalize_time_string("7:00pm"))      # "7:00 PM"
print(normalize_time_string("12:30 p.m.")) # "12:30 PM"
```

### Cache Management

#### `check_cache_status`

```python
def check_cache_status() -> tuple[bool, str, str | None]:
    """
    Checks theater cache file status.
    
    Returns:
        tuple: (exists, status, last_updated)
            exists (bool): Cache file exists
            status (str): 'fresh' | 'stale' | 'missing'
            last_updated (str | None): Last modified date
    """
```

**Example:**

```python
from app.utils import check_cache_status

exists, status, updated = check_cache_status()

if status == 'stale':
    print(f"Cache is old (last updated: {updated})")
    print("Recommend rebuilding cache")
```

### Logging

#### `log_runtime`

```python
def log_runtime(
    mode: str, 
    num_theaters: int, 
    num_showings: int, 
    duration: float
) -> None:
    """
    Logs scrape runtime metrics to CSV.
    
    Args:
        mode (str): Mode name
        num_theaters (int): Number of theaters scraped
        num_showings (int): Number of showings found
        duration (float): Time in seconds
        
    Log File: data/[Company]/reports/runtime_log.csv
    """
```

### Session State

#### `clear_workflow_state`

```python
def clear_workflow_state() -> None:
    """
    Clears workflow-specific session state variables.
    
    Preserves: logged_in, user_name, is_admin, company, search_mode
    Clears: all_showings, selected_films, selected_showtimes, etc.
    """
```

#### `reset_session`

```python
def reset_session() -> None:
    """
    Resets entire session state and reruns app.
    
    ⚠️ User remains logged in, mode preserved
    """
```

---

## UI Components Module

**File:** `app/ui_components.py`  
**Purpose:** Reusable Streamlit UI components.

### Functions

#### `render_theater_buttons`

```python
def render_theater_buttons(
    theaters: list[str],
    selected_theaters: list[str],
    columns: int = 4
) -> list[str]:
    """
    Renders clickable theater buttons in a grid.
    
    Args:
        theaters (list[str]): Theater names
        selected_theaters (list[str]): Currently selected
        columns (int): Number of columns
        
    Returns:
        list[str]: Updated selected theaters
    """
```

#### `render_film_selector`

```python
def render_film_selector(
    films: list[dict],
    multi: bool = True
) -> list[str]:
    """
    Renders film selection interface.
    
    Args:
        films (list[dict]): Film data
        multi (bool): Allow multiple selection
        
    Returns:
        list[str]: Selected film titles
    """
```

---

## Mode Modules

Mode modules handle specific features. Each follows similar patterns:

### Standard Mode Structure

```python
# app/modes/example_mode.py

def render(scout, markets_data, cache_data, all_theaters, is_disabled):
    """
    Main entry point for mode.
    
    Args:
        scout (Scraper): Scraper instance
        markets_data (dict): Market configuration
        cache_data (dict): Theater cache
        all_theaters (list): All available theaters
        is_disabled (bool): UI disabled flag
    """
    # Mode-specific UI and logic
    pass
```

### Available Modes

- **market_mode.py** - Market comparisons
- **analysis_mode.py** - Historical data analysis
- **poster_mode.py** - Poster/schedule generation
- **operating_hours_mode.py** - Operating hours tracking
- **compsnipe_mode.py** - Competitive intelligence

---

## Configuration

**File:** `app/config.py`

```python
import os

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, 'theater_cache.json')
DEBUG_DIR = os.path.join(SCRIPT_DIR, 'debug')

# Database
DB_FILE = None  # Set by main app based on company

# Cache settings
CACHE_EXPIRATION_DAYS = 7

# Scraping settings
DEFAULT_TIMEOUT = 30000  # milliseconds
MAX_RETRIES = 3
```

---

## Data Structures

### Showings Data Structure

```python
{
    'YYYY-MM-DD': {
        'Theater Name': {
            'Film Title': {
                'HH:MM AM/PM': [
                    {
                        'url': 'https://...',
                        'format': 'IMAX',
                        'ticket_info': {...},
                        'theater_name': 'Theater Name',
                        'play_date': 'YYYY-MM-DD'
                    }
                ]
            }
        }
    }
}
```

### Price Data Structure

```python
[
    {
        'theater_name': 'Theater',
        'play_date': 'YYYY-MM-DD',
        'film_title': 'Film',
        'showtime': 'HH:MM AM/PM',
        'format': 'IMAX',
        'daypart': 'Evening',
        'ticket_url': 'https://...',
        'prices': [
            {
                'ticket_type': 'Adult',
                'price': 16.99,
                'capacity': '50/150'
            }
        ]
    }
]
```

### Markets JSON Structure

```json
{
  "Company Name": {
    "Region": {
      "Market": {
        "Theater Name": {
          "name": "Theater Name",
          "url": "https://www.fandango.com/..."
        }
      }
    }
  }
}
```

---

## Testing Utilities

### Fixtures

Located in `tests/conftest.py`:

```python
@pytest.fixture
def mock_scraper():
    """Returns a mock Scraper instance."""
    
@pytest.fixture
def sample_showings_data():
    """Returns sample showings structure."""
    
@pytest.fixture
def sample_price_data():
    """Returns sample price data."""
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific module
pytest tests/test_database.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest tests/test_scraper.py::test_parse_ticket_description -v
```

---

## Best Practices

### Error Handling

```python
try:
    status, result, log, meta = await scout.get_all_showings_for_theaters(...)
    if status == 'success':
        # Process result
        pass
    else:
        # Handle error
        st.error(f"Scraping failed: {result}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    st.error("An unexpected error occurred")
```

### Database Connections

```python
# Always use context manager
from app import database

with database._get_db_connection() as conn:
    cursor = conn.cursor()
    # Perform operations
    conn.commit()
# Connection automatically closed
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Detailed debug information")
logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error occurred")
```

---

## API Versioning

**Current Version:** 28.0

### Version History

- **v28.0** (October 2025)
  - Fixed duplicate showing bug
  - Removed dev mode
  - Improved CompSnipe UX
  - Standardized error messages
  - Enhanced documentation

- **v27.0** (January 2025)
  - Initial comprehensive testing
  - 244 tests, 40% coverage
  - Production-ready baseline

---

## Support

**Documentation:**
- README.md - Installation and quick start
- USER_GUIDE.md - End-user instructions
- ADMIN_GUIDE.md - Administrator guide
- API_REFERENCE.md - This document

**Testing:**
- Test suite: `tests/`
- Coverage: `htmlcov/index.html`

**Contributing:**
- Follow existing patterns
- Write tests for new features
- Update documentation
- Run linter before committing

---

**API Reference Version:** 28.0  
**Last Updated:** October 2025  
**Status:** Production Ready
