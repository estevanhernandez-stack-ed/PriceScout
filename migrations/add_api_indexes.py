"""
Database Migration: Add indexes for API aggregation queries
Created: 2025-11-27
Purpose: Optimize operating-hours and plf-formats endpoints

Adds composite indexes to speed up GROUP BY queries on:
- theater_name + play_date (for operating hours)
- theater_name + format (for PLF formats)
- format (for PLF filtering)
"""

from sqlalchemy import create_engine, text
import sys
import os
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config

def get_db_url():
    """Get database URL from environment or use SQLite default"""
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url
    # Default SQLite path
    db_path = ROOT / 'pricescout.db'
    return f'sqlite:///{db_path}'

def add_indexes():
    """Add performance indexes for API aggregation queries"""
    
    db_url = get_db_url()
    engine = create_engine(db_url)
    
    indexes_to_add = [
        # For operating hours query (GROUP BY theater_name, play_date)
        ("idx_showings_theater_date_agg", "CREATE INDEX IF NOT EXISTS idx_showings_theater_date_agg ON showings (theater_name, play_date, showtime)"),
        
        # For PLF formats query (GROUP BY theater_name, format WHERE format IN (...))
        ("idx_showings_theater_format", "CREATE INDEX IF NOT EXISTS idx_showings_theater_format ON showings (theater_name, format)"),
        
        # For format filtering
        ("idx_showings_format", "CREATE INDEX IF NOT EXISTS idx_showings_format ON showings (format)"),
        
        # For company + theater + date queries (already exists but verify)
        ("idx_showings_company_theater", "CREATE INDEX IF NOT EXISTS idx_showings_company_theater ON showings (company_id, theater_name)"),
    ]
    
    print("Adding performance indexes to showings table...")
    print(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}\n")
    
    with engine.connect() as conn:
        for idx_name, sql in indexes_to_add:
            try:
                print(f"Creating index: {idx_name}...")
                conn.execute(text(sql))
                conn.commit()
                print(f"  ✓ {idx_name} created successfully")
            except Exception as e:
                print(f"  ⚠ {idx_name}: {str(e)}")
                # Continue with other indexes even if one fails
    
    print("\n✓ Migration complete!")
    print("\nIndexes added:")
    print("  - idx_showings_theater_date_agg: Speeds up operating hours queries")
    print("  - idx_showings_theater_format: Speeds up PLF format queries")
    print("  - idx_showings_format: Speeds up format filtering")
    print("  - idx_showings_company_theater: Speeds up company+theater queries")
    
def verify_indexes():
    """Verify indexes exist"""
    db_url = get_db_url()
    engine = create_engine(db_url)
    
    print("\nVerifying indexes on showings table...")
    
    # SQLite-specific query
    if 'sqlite' in db_url:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='showings'"))
            indexes = [row[0] for row in result]
            print("\nExisting indexes:")
            for idx in sorted(indexes):
                if not idx.startswith('sqlite_'):  # Skip auto-generated indexes
                    print(f"  - {idx}")
    # PostgreSQL-specific query
    elif 'postgresql' in db_url:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename='showings'
                ORDER BY indexname
            """))
            indexes = [row[0] for row in result]
            print("\nExisting indexes:")
            for idx in indexes:
                print(f"  - {idx}")

if __name__ == "__main__":
    try:
        add_indexes()
        verify_indexes()
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)
