import os

# --- Dynamically Define File Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DEBUG_DIR = os.path.join(PROJECT_DIR, 'debug_snapshots') # Directory for HTML snapshots

# --- Constants ---
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
CACHE_FILE = os.path.join(SCRIPT_DIR, 'theater_cache.json')
CACHE_EXPIRATION_DAYS = 7
USER_DB_FILE = os.path.join(PROJECT_DIR, 'user_data.db') # New user database file

# --- Dynamic Paths (to be set in the app) ---
DB_FILE = None
REPORTS_DIR = None
RUNTIME_LOG_FILE = None
SCHEDULED_TASKS_DIR = None
