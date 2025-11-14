"""
PriceScout SQLite to PostgreSQL Data Migration Script
Version: 1.0.0
Date: November 13, 2025

This script migrates data from the legacy dual SQLite database structure
(users.db + per-company pricing DBs) to the unified PostgreSQL schema.

Usage:
    python migrate_to_postgresql.py --company "AMC Theatres" --sqlite-db "data/AMC Theatres/AMC Theatres.db"
    
    For users.db migration:
    python migrate_to_postgresql.py --migrate-users
    
    For full migration (all companies):
    python migrate_to_postgresql.py --migrate-all

Requirements:
    - PostgreSQL connection string in environment: DATABASE_URL
    - Or use Azure Key Vault: AZURE_KEY_VAULT_URL
"""

import sqlite3
import argparse
import os
import sys
from datetime import datetime
from typing import Optional, Dict, List
import json

try:
    import psycopg2
    from psycopg2.extras import execute_batch
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# Add app to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import PROJECT_DIR


class DatabaseMigrator:
    """Handles migration from SQLite to PostgreSQL"""
    
    def __init__(self, pg_conn_string: str):
        self.pg_conn_string = pg_conn_string
        self.pg_conn = None
        self.stats = {
            'companies': 0,
            'users': 0,
            'scrape_runs': 0,
            'showings': 0,
            'prices': 0,
            'films': 0,
            'operating_hours': 0,
            'unmatched_films': 0,
            'ignored_films': 0,
            'unmatched_ticket_types': 0,
            'errors': []
        }
    
    def connect_postgres(self):
        """Establish PostgreSQL connection"""
        try:
            self.pg_conn = psycopg2.connect(self.pg_conn_string)
            self.pg_conn.autocommit = False
            print(f"✓ Connected to PostgreSQL: {self.pg_conn.info.dbname}")
        except Exception as e:
            print(f"✗ Failed to connect to PostgreSQL: {e}")
            sys.exit(1)
    
    def close_connections(self):
        """Close database connections"""
        if self.pg_conn:
            self.pg_conn.close()
    
    def get_or_create_company(self, company_name: str) -> int:
        """Get company_id or create new company"""
        cursor = self.pg_conn.cursor()
        try:
            # Try to get existing company
            cursor.execute("SELECT company_id FROM companies WHERE company_name = %s", (company_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            
            # Create new company
            cursor.execute(
                "INSERT INTO companies (company_name, is_active, settings) VALUES (%s, %s, %s) RETURNING company_id",
                (company_name, True, json.dumps({}))
            )
            company_id = cursor.fetchone()[0]
            self.pg_conn.commit()
            self.stats['companies'] += 1
            print(f"  → Created company: {company_name} (ID: {company_id})")
            return company_id
        except Exception as e:
            self.pg_conn.rollback()
            self.stats['errors'].append(f"Company creation failed for {company_name}: {e}")
            raise
    
    def migrate_users(self, users_db_path: str = None):
        """Migrate users from users.db to PostgreSQL"""
        if users_db_path is None:
            users_db_path = os.path.join(PROJECT_DIR, "users.db")
        
        if not os.path.exists(users_db_path):
            print(f"✗ Users database not found: {users_db_path}")
            return
        
        print(f"\n📊 Migrating users from: {users_db_path}")
        sqlite_conn = sqlite3.connect(users_db_path)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        cursor = self.pg_conn.cursor()
        
        try:
            # Get all users
            sqlite_cursor.execute("SELECT * FROM users")
            users = sqlite_cursor.fetchall()
            
            for user in users:
                # Get or create company if specified
                company_id = None
                if user['company']:
                    company_id = self.get_or_create_company(user['company'])
                
                default_company_id = None
                if user.get('default_company'):
                    default_company_id = self.get_or_create_company(user['default_company'])
                
                # Parse allowed_modes if it's JSON string
                allowed_modes = user.get('allowed_modes', '[]')
                if isinstance(allowed_modes, str):
                    try:
                        allowed_modes = json.loads(allowed_modes)
                    except:
                        allowed_modes = []
                
                # Insert user
                cursor.execute("""
                    INSERT INTO users (
                        username, password_hash, role, company_id, default_company_id,
                        home_location_type, home_location_value, allowed_modes,
                        is_admin, must_change_password, reset_code, reset_code_expiry, reset_attempts
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        company_id = EXCLUDED.company_id
                """, (
                    user['username'],
                    user['password_hash'],
                    user.get('role', 'user'),
                    company_id,
                    default_company_id,
                    user.get('home_location_type'),
                    user.get('home_location_value'),
                    json.dumps(allowed_modes),
                    bool(user.get('is_admin', 0)),
                    bool(user.get('must_change_password', 0)),
                    user.get('reset_code'),
                    user.get('reset_code_expiry'),
                    user.get('reset_attempts', 0)
                ))
                self.stats['users'] += 1
            
            self.pg_conn.commit()
            print(f"  ✓ Migrated {self.stats['users']} users")
            
        except Exception as e:
            self.pg_conn.rollback()
            self.stats['errors'].append(f"User migration failed: {e}")
            print(f"  ✗ Error: {e}")
        finally:
            sqlite_conn.close()
    
    def migrate_company_data(self, company_name: str, sqlite_db_path: str):
        """Migrate pricing data from company SQLite DB to PostgreSQL"""
        if not os.path.exists(sqlite_db_path):
            print(f"✗ Database not found: {sqlite_db_path}")
            return
        
        print(f"\n📊 Migrating data for company: {company_name}")
        print(f"   Source: {sqlite_db_path}")
        
        # Get or create company
        company_id = self.get_or_create_company(company_name)
        
        sqlite_conn = sqlite3.connect(sqlite_db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        sqlite_conn.row_factory = sqlite3.Row
        
        try:
            # Migrate tables in order (respecting foreign keys)
            self._migrate_scrape_runs(sqlite_conn, company_id)
            self._migrate_films(sqlite_conn, company_id)
            self._migrate_showings(sqlite_conn, company_id)
            self._migrate_prices(sqlite_conn, company_id)
            self._migrate_operating_hours(sqlite_conn, company_id)
            self._migrate_unmatched_films(sqlite_conn, company_id)
            self._migrate_ignored_films(sqlite_conn, company_id)
            self._migrate_unmatched_ticket_types(sqlite_conn, company_id)
            
            self.pg_conn.commit()
            print(f"  ✓ Migration completed for {company_name}")
            
        except Exception as e:
            self.pg_conn.rollback()
            self.stats['errors'].append(f"Company migration failed for {company_name}: {e}")
            print(f"  ✗ Error: {e}")
            raise
        finally:
            sqlite_conn.close()
    
    def _migrate_scrape_runs(self, sqlite_conn, company_id):
        """Migrate scrape_runs table"""
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM scrape_runs")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return
        
        # Create mapping of old run_id to new run_id
        self.run_id_map = {}
        
        for row in rows:
            pg_cursor.execute("""
                INSERT INTO scrape_runs (company_id, run_timestamp, mode)
                VALUES (%s, %s, %s)
                RETURNING run_id
            """, (company_id, row['run_timestamp'], row['mode']))
            new_run_id = pg_cursor.fetchone()[0]
            self.run_id_map[row['run_id']] = new_run_id
            self.stats['scrape_runs'] += 1
        
        print(f"  → Migrated {len(rows)} scrape runs")
    
    def _migrate_films(self, sqlite_conn, company_id):
        """Migrate films table"""
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM films")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return
        
        for row in rows:
            pg_cursor.execute("""
                INSERT INTO films (
                    company_id, film_title, imdb_id, genre, mpaa_rating, director,
                    actors, plot, poster_url, metascore, imdb_rating, release_date,
                    domestic_gross, runtime, opening_weekend_domestic, last_omdb_update
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, film_title) DO UPDATE SET
                    imdb_id = EXCLUDED.imdb_id,
                    last_omdb_update = EXCLUDED.last_omdb_update
            """, (
                company_id, row['film_title'], row.get('imdb_id'), row.get('genre'),
                row.get('mpaa_rating'), row.get('director'), row.get('actors'),
                row.get('plot'), row.get('poster_url'), row.get('metascore'),
                row.get('imdb_rating'), row.get('release_date'), row.get('domestic_gross'),
                row.get('runtime'), row.get('opening_weekend_domestic'), row['last_omdb_update']
            ))
            self.stats['films'] += 1
        
        print(f"  → Migrated {len(rows)} films")
    
    def _migrate_showings(self, sqlite_conn, company_id):
        """Migrate showings table"""
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM showings")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return
        
        # Create mapping of old showing_id to new showing_id
        self.showing_id_map = {}
        
        batch = []
        for row in rows:
            batch.append((
                company_id, row['play_date'], row['theater_name'], row['film_title'],
                row['showtime'], row.get('format'), row.get('daypart'),
                bool(row.get('is_plf', 0)), row.get('ticket_url')
            ))
        
        # Batch insert
        execute_batch(pg_cursor, """
            INSERT INTO showings (
                company_id, play_date, theater_name, film_title, showtime,
                format, daypart, is_plf, ticket_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (company_id, play_date, theater_name, film_title, showtime, format) DO NOTHING
        """, batch, page_size=1000)
        
        self.stats['showings'] += len(rows)
        print(f"  → Migrated {len(rows)} showings")
    
    def _migrate_prices(self, sqlite_conn, company_id):
        """Migrate prices table"""
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM prices")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return
        
        batch = []
        for row in rows:
            # Map old run_id to new run_id
            new_run_id = self.run_id_map.get(row['run_id']) if row.get('run_id') else None
            
            # Note: showing_id mapping is complex due to UNIQUE constraints
            # For now, we'll set showing_id to NULL and rely on play_date
            batch.append((
                company_id, new_run_id, None, row['ticket_type'],
                row['price'], row.get('capacity'), row.get('play_date')
            ))
        
        # Batch insert
        execute_batch(pg_cursor, """
            INSERT INTO prices (
                company_id, run_id, showing_id, ticket_type, price, capacity, play_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, batch, page_size=1000)
        
        self.stats['prices'] += len(rows)
        print(f"  → Migrated {len(rows)} prices")
    
    def _migrate_operating_hours(self, sqlite_conn, company_id):
        """Migrate operating_hours table"""
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM operating_hours")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return
        
        batch = []
        for row in rows:
            new_run_id = self.run_id_map.get(row['run_id']) if row.get('run_id') else None
            batch.append((
                company_id, new_run_id, row.get('market'), row['theater_name'],
                row['scrape_date'], row.get('open_time'), row.get('close_time'),
                row.get('duration_hours')
            ))
        
        execute_batch(pg_cursor, """
            INSERT INTO operating_hours (
                company_id, run_id, market, theater_name, scrape_date,
                open_time, close_time, duration_hours
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, batch, page_size=1000)
        
        self.stats['operating_hours'] += len(rows)
        print(f"  → Migrated {len(rows)} operating hours records")
    
    def _migrate_unmatched_films(self, sqlite_conn, company_id):
        """Migrate unmatched_films table"""
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM unmatched_films")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return
        
        for row in rows:
            pg_cursor.execute("""
                INSERT INTO unmatched_films (company_id, film_title, first_seen)
                VALUES (%s, %s, %s)
                ON CONFLICT (company_id, film_title) DO NOTHING
            """, (company_id, row['film_title'], row['first_seen']))
            self.stats['unmatched_films'] += 1
        
        print(f"  → Migrated {len(rows)} unmatched films")
    
    def _migrate_ignored_films(self, sqlite_conn, company_id):
        """Migrate ignored_films table"""
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM ignored_films")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return
        
        for row in rows:
            pg_cursor.execute("""
                INSERT INTO ignored_films (company_id, film_title)
                VALUES (%s, %s)
                ON CONFLICT (company_id, film_title) DO NOTHING
            """, (company_id, row['film_title']))
            self.stats['ignored_films'] += 1
        
        print(f"  → Migrated {len(rows)} ignored films")
    
    def _migrate_unmatched_ticket_types(self, sqlite_conn, company_id):
        """Migrate unmatched_ticket_types table"""
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM unmatched_ticket_types")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return
        
        for row in rows:
            pg_cursor.execute("""
                INSERT INTO unmatched_ticket_types (
                    company_id, original_description, unmatched_part, first_seen,
                    theater_name, film_title, showtime, format, play_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, unmatched_part, theater_name, film_title, play_date) DO NOTHING
            """, (
                company_id, row.get('original_description'), row['unmatched_part'],
                row['first_seen'], row.get('theater_name'), row.get('film_title'),
                row.get('showtime'), row.get('format'), row.get('play_date')
            ))
            self.stats['unmatched_ticket_types'] += 1
        
        print(f"  → Migrated {len(rows)} unmatched ticket types")
    
    def print_summary(self):
        """Print migration statistics"""
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print(f"Companies:              {self.stats['companies']}")
        print(f"Users:                  {self.stats['users']}")
        print(f"Scrape Runs:            {self.stats['scrape_runs']}")
        print(f"Showings:               {self.stats['showings']}")
        print(f"Prices:                 {self.stats['prices']}")
        print(f"Films:                  {self.stats['films']}")
        print(f"Operating Hours:        {self.stats['operating_hours']}")
        print(f"Unmatched Films:        {self.stats['unmatched_films']}")
        print(f"Ignored Films:          {self.stats['ignored_films']}")
        print(f"Unmatched Ticket Types: {self.stats['unmatched_ticket_types']}")
        print("="*60)
        
        if self.stats['errors']:
            print("\n⚠ ERRORS:")
            for error in self.stats['errors']:
                print(f"  - {error}")
        else:
            print("\n✓ Migration completed successfully!")


def get_postgres_connection_string() -> str:
    """Get PostgreSQL connection string from environment or Azure Key Vault"""
    # Try environment variable first
    conn_string = os.getenv('DATABASE_URL')
    if conn_string:
        return conn_string
    
    # Try Azure Key Vault
    azure_vault_url = os.getenv('AZURE_KEY_VAULT_URL')
    if azure_vault_url:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=azure_vault_url, credential=credential)
            secret = client.get_secret("postgresql-connection-string")
            return secret.value
        except Exception as e:
            print(f"Failed to get connection string from Key Vault: {e}")
    
    # Fallback to user input
    return input("Enter PostgreSQL connection string: ")


def discover_company_databases() -> List[Dict[str, str]]:
    """Find all company SQLite databases in data/ directory"""
    data_dir = os.path.join(PROJECT_DIR, "data")
    companies = []
    
    if not os.path.exists(data_dir):
        return companies
    
    for item in os.listdir(data_dir):
        company_dir = os.path.join(data_dir, item)
        if os.path.isdir(company_dir):
            # Look for [CompanyName].db file
            db_file = os.path.join(company_dir, f"{item}.db")
            if os.path.exists(db_file):
                companies.append({
                    'name': item,
                    'db_path': db_file
                })
    
    return companies


def main():
    parser = argparse.ArgumentParser(description="Migrate PriceScout data from SQLite to PostgreSQL")
    parser.add_argument('--company', help="Company name to migrate")
    parser.add_argument('--sqlite-db', help="Path to company SQLite database")
    parser.add_argument('--migrate-users', action='store_true', help="Migrate users.db")
    parser.add_argument('--migrate-all', action='store_true', help="Migrate all companies")
    parser.add_argument('--pg-conn', help="PostgreSQL connection string (or use DATABASE_URL env var)")
    
    args = parser.parse_args()
    
    # Get PostgreSQL connection string
    pg_conn_string = args.pg_conn or get_postgres_connection_string()
    
    # Create migrator
    migrator = DatabaseMigrator(pg_conn_string)
    migrator.connect_postgres()
    
    try:
        # Migrate users
        if args.migrate_users or args.migrate_all:
            migrator.migrate_users()
        
        # Migrate specific company
        if args.company and args.sqlite_db:
            migrator.migrate_company_data(args.company, args.sqlite_db)
        
        # Migrate all companies
        elif args.migrate_all:
            companies = discover_company_databases()
            print(f"\nFound {len(companies)} company databases")
            for company in companies:
                migrator.migrate_company_data(company['name'], company['db_path'])
        
        # Print summary
        migrator.print_summary()
        
    finally:
        migrator.close_connections()


if __name__ == "__main__":
    main()
