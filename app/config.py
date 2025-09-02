import os

# --- Dynamically Define File Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DEBUG_DIR = os.path.join(PROJECT_DIR, 'debug_snapshots') # Directory for HTML snapshots

# --- Constants ---
DATA_DIR = os.path.join(PROJECT_DIR, 'data', 'Marcus')
CACHE_FILE = os.path.join(SCRIPT_DIR, 'theater_cache.json')
MARKETS_FILE = os.path.join(DATA_DIR, 'markets.json')
CACHE_EXPIRATION_DAYS = 3
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')
RUNTIME_LOG_FILE = os.path.join(REPORTS_DIR, 'runtime_log.csv')
DB_FILE = os.path.join(DATA_DIR, 'price_scout.db')
SCHEDULED_TASKS_DIR = os.path.join(DATA_DIR, 'scheduled_tasks')
