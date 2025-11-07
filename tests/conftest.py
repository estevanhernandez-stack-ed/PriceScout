"""
Pytest configuration and fixtures.
"""
import sys
from pathlib import Path
import sqlite3
import warnings

# Add the project root to Python path so tests can import from app
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Suppress ResourceWarnings about unclosed databases during tests
warnings.filterwarnings("ignore", category=ResourceWarning)

# Enable strict cleanup of database connections
def pytest_configure(config):
    """Configure pytest to enable strict resource cleanup."""
    sqlite3.enable_callback_tracebacks(True)
