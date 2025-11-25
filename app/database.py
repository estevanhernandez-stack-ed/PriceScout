import sqlite3
import pandas as pd
import datetime
import asyncio
from contextlib import contextmanager
from app import config
from app.omdb_client import OMDbClient

# Register datetime adapters for Python 3.12+ compatibility
# Python 3.12 deprecated the default datetime adapters
def _adapt_datetime_iso(val):
    """Adapt datetime.datetime to ISO 8601 string."""
    return val.isoformat()

def _adapt_date_iso(val):
    """Adapt datetime.date to ISO 8601 string."""
    return val.isoformat()

def _convert_datetime(val):
    """Convert ISO 8601 datetime string to datetime.datetime object."""
    return datetime.datetime.fromisoformat(val.decode())

def _convert_date(val):
    """Convert ISO 8601 date string to datetime.date object."""
    return datetime.date.fromisoformat(val.decode())

# Register the adapters and converters
sqlite3.register_adapter(datetime.datetime, _adapt_datetime_iso)
sqlite3.register_adapter(datetime.date, _adapt_date_iso)
sqlite3.register_converter("timestamp", _convert_datetime)
sqlite3.register_converter("date", _convert_date)

@contextmanager
def _get_db_connection():
    """
    Gets a connection to the database with proper resource cleanup.
    This context manager ensures connections are always closed after use.
    """
    assert config.DB_FILE is not None, "Database path (DB_FILE) has not been configured. It should be set by the main app."
    conn = sqlite3.connect(config.DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """Initializes the SQLite database and creates tables if they don't exist."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrape_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_timestamp DATETIME NOT NULL,
                mode TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS showings (
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
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                price_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                showing_id INTEGER,
                ticket_type TEXT NOT NULL,
                price REAL NOT NULL,
                capacity TEXT,
                play_date DATE,
                FOREIGN KEY (run_id) REFERENCES scrape_runs (run_id),
                FOREIGN KEY (showing_id) REFERENCES showings (showing_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS films (
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
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unmatched_films (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                film_title TEXT NOT NULL UNIQUE,
                first_seen DATETIME NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unmatched_ticket_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_description TEXT,
                unmatched_part TEXT,
                first_seen DATETIME,
                theater_name TEXT,
                film_title TEXT,
                showtime TEXT,
                format TEXT,
                play_date DATE,
                UNIQUE(unmatched_part, theater_name, film_title, play_date)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operating_hours (
                operating_hours_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                market TEXT,
                theater_name TEXT NOT NULL,
                scrape_date DATE NOT NULL,
                open_time TEXT,
                close_time TEXT,
                duration_hours REAL,
                FOREIGN KEY (run_id) REFERENCES scrape_runs (run_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ignored_films (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                film_title TEXT NOT NULL UNIQUE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_operating_hours_theater_date ON operating_hours (theater_name, scrape_date);')
        # --- OPTIMIZATION: Add indexes for faster queries ---
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_showings_theater_date ON showings (theater_name, play_date);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_showings_film_title ON showings (film_title);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_prices_showing_id ON prices (showing_id);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_prices_run_id ON prices (run_id);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_films_title ON films (film_title);')

        conn.commit()

def get_dates_for_theaters(theater_list):
    """Gets the unique dates that the selected theaters have records for."""
    if not theater_list:
        return []
    with _get_db_connection() as conn:
        query = f"""
            SELECT DISTINCT play_date
            FROM showings
            WHERE theater_name IN ({','.join(['?'] * len(theater_list))})
            ORDER BY play_date DESC
        """
        df = pd.read_sql_query(query, conn, params=theater_list)
    return df['play_date'].tolist()

def get_common_films_for_theaters_dates(theater_list, date_list):
    """Gets films that are available for ALL selected theaters on AT LEAST ONE of the selected dates."""
    if not theater_list or not date_list:
        return []
    with _get_db_connection() as conn:
        theater_placeholders = ','.join(['?'] * len(theater_list))
        date_placeholders = ','.join(['?'] * len(date_list))
        
        query = f"""
            SELECT film_title FROM (
                SELECT DISTINCT film_title, theater_name
                FROM showings
                WHERE theater_name IN ({theater_placeholders})
                AND play_date IN ({date_placeholders})
            )
            GROUP BY film_title
            HAVING COUNT(DISTINCT theater_name) = ?
            ORDER BY film_title
        """
        params = theater_list + date_list + [len(theater_list)]
        df = pd.read_sql_query(query, conn, params=params)
    return df['film_title'].tolist()

def get_data_for_trend_report(theater_list, date_list, film_list, daypart_list):
    """Gets all the raw price data needed to build the trend report pivot table."""
    if not all([theater_list, date_list, film_list, daypart_list]):
        return pd.DataFrame()
        
    with _get_db_connection() as conn:
        theater_ph = ','.join(['?'] * len(theater_list))
        date_ph = ','.join(['?'] * len(date_list))
        film_ph = ','.join(['?'] * len(film_list))
        daypart_ph = ','.join(['?'] * len(daypart_list))

        query = f"""
            SELECT 
                s.play_date as scrape_date,
                s.theater_name, 
                s.film_title, 
                s.daypart, 
                p.ticket_type,
                p.price
            FROM prices p
            JOIN showings s ON p.showing_id = s.showing_id
            WHERE s.theater_name IN ({theater_ph})
            AND s.play_date IN ({date_ph})
            AND s.film_title IN ({film_ph})
            AND s.daypart IN ({daypart_ph})
        """
        params = theater_list + date_list + film_list + daypart_list
        df = pd.read_sql_query(query, conn, params=params)
    return df

def update_database_schema():
    """Adds new columns to the database if they don't already exist."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        # Use PRAGMA to check for the column's existence
        cursor.execute("PRAGMA table_info(scrape_runs)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'run_context' not in columns:
            try:
                # Use a try-except block in case of race conditions in a multi-threaded app
                cursor.execute('ALTER TABLE scrape_runs ADD COLUMN run_context TEXT')
                conn.commit()
                print("  [DB] Adding 'run_context' column to scrape_runs table.")
            except sqlite3.OperationalError as e:
                # The column might have been added by another thread between the check and the ALTER
                if "duplicate column name" not in str(e):
                    raise # Re-raise if it's not the expected error
        
        cursor.execute("PRAGMA table_info(prices)")
        prices_columns = [info[1] for info in cursor.fetchall()]
        if 'play_date' not in prices_columns:
            print("  [DB] Adding 'play_date' column to prices table.")
            cursor.execute('ALTER TABLE prices ADD COLUMN play_date DATE')
            conn.commit()
        
        cursor.execute("PRAGMA table_info(prices)")
        prices_columns = [info[1] for info in cursor.fetchall()]
        if 'showing_id' not in prices_columns:
            print("  [DB] Schema is old. Please use the migration tool in Data Management.")
            conn.commit()

        # Add check for box_office_gross in films table
        cursor.execute("PRAGMA table_info(films)")
        films_columns_info = cursor.fetchall()
        films_columns = [info[1] for info in films_columns_info]

        # --- NEW: Robust schema migration for financial columns ---
        if 'domestic_gross' not in films_columns:
            if 'box_office_gross' in films_columns:
                print("  [DB] Renaming 'box_office_gross' to 'domestic_gross'.")
                cursor.execute('ALTER TABLE films RENAME COLUMN box_office_gross TO domestic_gross')
            else:
                print("  [DB] Adding 'domestic_gross' column to films table.")
                cursor.execute('ALTER TABLE films ADD COLUMN domestic_gross INTEGER')
        if 'opening_weekend_domestic' not in films_columns:
            if 'budget' in films_columns:
                print("  [DB] Renaming 'budget' to 'opening_weekend_domestic'.")
                cursor.execute('ALTER TABLE films RENAME COLUMN budget TO opening_weekend_domestic')
            else:
                print("  [DB] Adding 'opening_weekend_domestic' column to films table.")
                cursor.execute('ALTER TABLE films ADD COLUMN opening_weekend_domestic INTEGER')

        if 'runtime' not in films_columns:
            print("  [DB] Adding 'domestic_gross' column to films table.")
            print("  [DB] Adding 'runtime' column to films table.")
            cursor.execute('ALTER TABLE films ADD COLUMN runtime TEXT')
            conn.commit()

        # --- NEW: Add context columns to unmatched_ticket_types ---
        cursor.execute("PRAGMA table_info(unmatched_ticket_types)")
        unmatched_columns = [info[1] for info in cursor.fetchall()]
        context_cols = ['theater_name', 'film_title', 'showtime', 'format', 'play_date']
        for col in context_cols:
            if col not in unmatched_columns:
                print(f"  [DB] Adding '{col}' column to unmatched_ticket_types table.")
                cursor.execute(f'ALTER TABLE unmatched_ticket_types ADD COLUMN {col} TEXT')
        # Drop UNIQUE constraint on unmatched_part if it exists to replace it with a composite one
        # This is complex in SQLite, so for now we rely on the CREATE TABLE statement for new DBs
        # and accept that old DBs might have the old constraint. The INSERT OR IGNORE will still work.

        cursor.execute("PRAGMA table_info(showings)")
        showings_columns = [info[1] for info in cursor.fetchall()]
        if 'is_plf' not in showings_columns:
            print("  [DB] Adding 'is_plf' column to showings table.")
            cursor.execute('ALTER TABLE showings ADD COLUMN is_plf BOOLEAN DEFAULT 0')

def create_scrape_run(mode: str, context: str) -> int:
    """Creates a new entry in the scrape_runs table and returns the run_id."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        run_timestamp = datetime.datetime.now()
        cursor.execute('INSERT INTO scrape_runs (run_timestamp, mode, run_context) VALUES (?, ?, ?)', (run_timestamp, mode, context))
        run_id = cursor.lastrowid
        assert run_id is not None
        conn.commit()
        return run_id

def save_prices(run_id: int, df: pd.DataFrame):
    """Saves a DataFrame of scraped prices to the database for a given run_id."""
    if 'play_date' not in df.columns or df['play_date'].isnull().all():
        print("  [DB] [ERROR] save_prices was called with a DataFrame missing 'play_date' data. Aborting save.")
        return

    with _get_db_connection() as conn:
        # --- OPTIMIZATION: Fetch all showing_ids in one go to avoid N+1 queries ---
        unique_showings_df = df[['play_date', 'Theater Name', 'Film Title', 'Showtime', 'Format']].drop_duplicates().dropna()
        if unique_showings_df.empty:
            print("  [DB] No valid showings in the DataFrame to save prices for.")
            return

        # Build a single large query to fetch all relevant showing_ids
        conditions = " OR ".join(["(play_date = ? AND theater_name = ? AND film_title = ? AND showtime = ? AND format = ?)" for _ in range(len(unique_showings_df))])
        params = [item for sublist in unique_showings_df.to_numpy() for item in sublist]
        query = f"SELECT showing_id, play_date, theater_name, film_title, showtime, format FROM showings WHERE {conditions}"
        
        db_showings_df = pd.read_sql_query(query, conn, params=params)

        # Create a lookup map from a tuple of showing details to its showing_id
        db_showings_df['lookup_key'] = db_showings_df.apply(lambda row: (row['play_date'], row['theater_name'], row['film_title'], row['showtime'], row['format']), axis=1)
        showing_id_map = db_showings_df.set_index('lookup_key')['showing_id'].to_dict()

        # --- NEW: Logic to update formats for unmatched showings ---
        df['lookup_key_with_format'] = df.apply(lambda row: (row['play_date'], row['Theater Name'], row['Film Title'], row['Showtime'], row['Format']), axis=1)
        unmatched_mask = ~df['lookup_key_with_format'].isin(showing_id_map.keys())

        if unmatched_mask.any():
            unmatched_df = df[unmatched_mask].copy()
            unmatched_keys_no_format = unmatched_df[['play_date', 'Theater Name', 'Film Title', 'Showtime']].drop_duplicates()

            if not unmatched_keys_no_format.empty:
                # SECURITY NOTE: This query uses f-strings for dynamic placeholder count, but is SAFE because:
                # 1. All user data goes through parameterized execution (params list below)
                # 2. No user input enters the query structure - only dataframe length determines placeholders
                # 3. The conditions string is built from a fixed pattern, not user input
                # See SECURITY_AUDIT_REPORT.md HIGH-01 for details.
                conditions = " OR ".join(["(play_date = ? AND theater_name = ? AND film_title = ? AND showtime = ?)" for _ in range(len(unmatched_keys_no_format))])
                params = [item for sublist in unmatched_keys_no_format.to_numpy() for item in sublist]
                
                query = f"SELECT showing_id, play_date, theater_name, film_title, showtime FROM showings WHERE format = '2D' AND ({conditions})"
                updatable_showings_df = pd.read_sql_query(query, conn, params=params)

                if not updatable_showings_df.empty:
                    new_format_map = unmatched_df.groupby(['play_date', 'Theater Name', 'Film Title', 'Showtime'])['Format'].apply(lambda x: ", ".join(sorted(list(set(x))))).to_dict()
                    
                    updates_to_make = {}
                    for _, db_row in updatable_showings_df.iterrows():
                        key = (db_row['play_date'], db_row['theater_name'], db_row['film_title'], db_row['showtime'])
                        new_format = new_format_map.get(key)
                        
                        if new_format and new_format != '2D':
                            updates_to_make[db_row['showing_id']] = new_format
                            
                            unmatched_formats_for_key = unmatched_df[(unmatched_df['play_date'] == key[0]) & (unmatched_df['Theater Name'] == key[1]) & (unmatched_df['Film Title'] == key[2]) & (unmatched_df['Showtime'] == key[3])]['Format'].unique()
                            for fmt in unmatched_formats_for_key:
                                showing_id_map[(key[0], key[1], key[2], key[3], fmt)] = db_row['showing_id']

                    if updates_to_make:
                        unique_updates = [(fmt, sid) for sid, fmt in updates_to_make.items()]
                        cursor = conn.cursor()
                        cursor.executemany("UPDATE showings SET format = ? WHERE showing_id = ?", unique_updates)
                        conn.commit()
                        print(f"  [DB] Updated format for {cursor.rowcount} showings from price scrape data.")

        df.drop(columns=['lookup_key_with_format'], inplace=True, errors='ignore')

        # Prepare the data for bulk insertion
        prices_to_insert = []
        for _, row in df.iterrows():
            lookup_key = (row['play_date'], row['Theater Name'], row['Film Title'], row['Showtime'], row['Format'])
            showing_id = showing_id_map.get(lookup_key)
            
            if showing_id:
                try:
                    prices_to_insert.append((
                        run_id,
                        showing_id,
                        row['Ticket Type'],
                        float(row['Price'].replace('$', '')),
                        row['Capacity']
                    ))
                except (ValueError, KeyError) as e:
                    print(f"  [DB] [WARN] Skipping price record due to missing data: {row}. Error: {e}")

        total_inserted = 0
        if prices_to_insert:
            cursor = conn.cursor()
            cursor.executemany("INSERT INTO prices (run_id, showing_id, ticket_type, price, capacity) VALUES (?, ?, ?, ?, ?)", prices_to_insert)
            total_inserted = cursor.rowcount
        conn.commit()
        print(f"  [DB] Saved {total_inserted} price records to database for run ID {run_id}.")

def get_scrape_runs():
    """Fetches all historical scrape runs from the database."""
    with _get_db_connection() as conn:
        query = "SELECT run_id, run_timestamp, mode, run_context FROM scrape_runs ORDER BY run_timestamp DESC"
        df = pd.read_sql_query(query, conn)
    return df

def get_prices_for_run(run_id):
    """Fetches all price data for a specific run_id."""
    with _get_db_connection() as conn:
        query = """
            SELECT s.theater_name, s.film_title, s.showtime, s.format, p.ticket_type, p.price, p.capacity 
            FROM prices p JOIN showings s ON p.showing_id = s.showing_id 
            WHERE p.run_id = ?
        """
        df = pd.read_sql_query(query, conn, params=(run_id,))
    return df

def query_historical_data(start_date, end_date, theaters=None, films=None, genres=None, ratings=None):
    """Queries the database for showing and price records within a date range, with optional filters."""
    with _get_db_connection() as conn:
        query = '''
            SELECT 
                s.theater_name, s.film_title, s.showtime, s.daypart, s.format, 
                p.ticket_type, p.price, p.capacity, s.play_date, r.run_timestamp
            FROM showings s
            LEFT JOIN prices p ON s.showing_id = p.showing_id
            LEFT JOIN scrape_runs r ON p.run_id = r.run_id
        '''
        if genres or ratings:
            query += " JOIN films f ON s.film_title = f.film_title"

        query += " WHERE s.play_date BETWEEN ? AND ?"
        params = [start_date, end_date]

        if theaters:
            query += f" AND s.theater_name IN ({','.join(['?']*len(theaters))})"
            params.extend(theaters)
        if films:
            query += f" AND s.film_title IN ({','.join(['?']*len(films))})"
            params.extend(films)
        if genres:
            genre_clauses = " OR ".join([f"f.genre LIKE ?" for _ in genres])
            if genre_clauses:
                query += f" AND ({genre_clauses})"
                params.extend([f"%{g}%" for g in genres])
        if ratings:
            if len(ratings) > 0:
                query += f" AND f.mpaa_rating IN ({','.join(['?']*len(ratings))})"
                params.extend(ratings)

        query += " ORDER BY r.run_timestamp DESC, s.theater_name, s.film_title"
        df = pd.read_sql_query(query, conn, params=params)
    return df

def get_unique_column_values(column_name):
    """Gets all unique values from a column in the prices table."""
    # Whitelist allowed column names to prevent SQL injection
    allowed_columns = {'ticket_type', 'play_date', 'theater_name', 'film_title', 'showtime', 'format', 'price', 'daypart'}
    if column_name not in allowed_columns:
        raise ValueError(f"Invalid column name: {column_name}. Allowed: {allowed_columns}")

    with _get_db_connection() as conn:
        query = f"SELECT DISTINCT {column_name} FROM prices ORDER BY {column_name}"
        df = pd.read_sql_query(query, conn)
    return df[column_name].tolist()

def get_dates_for_theater(theater_name):
    """Gets the unique dates a specific theater has records for."""
    with _get_db_connection() as conn:
        query = '''
            SELECT DISTINCT play_date
            FROM showings
            WHERE theater_name = ?
            ORDER BY play_date DESC
        '''
        df = pd.read_sql_query(query, conn, params=(theater_name,))
    return df['play_date'].tolist()

def get_films_for_theater_date(theater_name, date):
    """Gets the unique films a specific theater has for a specific date."""
    with _get_db_connection() as conn:
        query = '''
            SELECT DISTINCT film_title
            FROM showings
            WHERE theater_name = ? AND play_date = ?
            ORDER BY film_title
        '''
        df = pd.read_sql_query(query, conn, params=(theater_name, date))
    return df['film_title'].tolist()


def get_final_prices(theater_name, date, film_title, daypart="All"):
    """
    Gets the final price data for the selected drill-down filters,
    with an added optional filter for daypart.
    """
    with _get_db_connection() as conn:
        query = '''
            SELECT s.showtime, s.format, s.daypart, p.ticket_type, p.price, p.capacity, s.play_date, r.run_timestamp
            FROM prices p
            JOIN showings s ON p.showing_id = s.showing_id
            JOIN scrape_runs r ON p.run_id = r.run_id
            WHERE s.theater_name = ? AND s.play_date = ? AND s.film_title = ?
        '''
        params = [theater_name, date, film_title]

        if daypart != "All":
            query += " AND s.daypart = ?"
            params.append(daypart)

        query += " ORDER BY r.run_timestamp DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
    return df



def save_operating_hours(run_id, operating_hours_data, conn):
    """Saves operating hours data to the database using an existing connection."""
    if not operating_hours_data:
        print("  [DB] No operating hours data to save.")
        return

    df = pd.DataFrame(operating_hours_data)
    df['run_id'] = run_id
    
    df_to_save = pd.DataFrame()
    df_to_save['run_id'] = df['run_id']
    df_to_save['market'] = df['Market']
    df_to_save['theater_name'] = df['Theater']
    df_to_save['scrape_date'] = df['Date']
    df_to_save['duration_hours'] = df['Duration (hrs)']
    
    df_to_save['open_time'] = None
    df_to_save['close_time'] = None

    if 'Showtime Range' in df.columns:
        no_showtimes = df['Showtime Range'] == 'No showtimes found'
        df_to_save.loc[no_showtimes, 'open_time'] = None
        df_to_save.loc[no_showtimes, 'close_time'] = None
    
        valid_showtimes = ~no_showtimes
        if valid_showtimes.any():
            df_to_save.loc[valid_showtimes, ['open_time', 'close_time']] = df.loc[valid_showtimes, 'Showtime Range'].str.split(' - ', expand=True).values

    df_to_save.to_sql('operating_hours', conn, if_exists='append', index=False)
    print(f"  [DB] Saved {len(df_to_save)} operating hours records to database for run ID {run_id}.")

def save_full_operating_hours_run(operating_hours_data, context):
    """Manages the full save process for operating hours, including scrape_runs entry."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        run_timestamp = datetime.datetime.now()
        cursor.execute('INSERT INTO scrape_runs (run_timestamp, mode, run_context) VALUES (?, ?, ?)', (run_timestamp, "Operating Hours", context))
        run_id = cursor.lastrowid
        save_operating_hours(run_id, operating_hours_data, conn)
        conn.commit()

def delete_operating_hours(theater_names, scrape_date, conn):
    """Deletes operating hours records for specific theaters on a specific date."""
    if not theater_names:
        return
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(theater_names))
    date_str = scrape_date.strftime('%Y-%m-%d')
    
    sql = f"DELETE FROM operating_hours WHERE theater_name IN ({placeholders}) AND scrape_date = ?"
    params = theater_names + [date_str]
    cursor.execute(sql, params)
    print(f"  [DB] Deleted {cursor.rowcount} old operating hours records for date {date_str}.")

def get_available_films(theaters):
    """Gets a list of films available for a given list of theaters."""
    if not theaters:
        return []
    with _get_db_connection() as conn:
        placeholders = ','.join(['?'] * len(theaters))
        query = f"""
            SELECT DISTINCT film_title
            FROM showings
            WHERE theater_name IN ({placeholders}) AND film_title IS NOT NULL
            ORDER BY film_title
        """
        df = pd.read_sql_query(query, conn, params=theaters)
    return df['film_title'].tolist()

def get_available_dates(theaters, films):
    """Gets the min and max date for a given list of theaters and films."""
    if not theaters or not films:
        return None, None
    with _get_db_connection() as conn:
        theater_placeholders = ','.join(['?'] * len(theaters))
        film_placeholders = ','.join(['?'] * len(films))
        query = f"""
            SELECT MIN(play_date) as min_date, MAX(play_date) as max_date
            FROM showings
            WHERE theater_name IN ({theater_placeholders})
            AND film_title IN ({film_placeholders})
        """
        params = theaters + films
        df = pd.read_sql_query(query, conn, params=params)
        min_date = pd.to_datetime(df['min_date'].iloc[0]) if not pd.isna(df['min_date'].iloc[0]) else None
        max_date = pd.to_datetime(df['max_date'].iloc[0]) if not pd.isna(df['max_date'].iloc[0]) else None
    return min_date, max_date

def get_available_dayparts(theaters, films, start_date, end_date):
    """Gets a list of dayparts available for a given list of theaters, films, and date range."""
    if not theaters or not films or not start_date or not end_date:
        return []
    with _get_db_connection() as conn:
        theater_placeholders = ','.join(['?'] * len(theaters))
        film_placeholders = ','.join(['?'] * len(films))
        query = f"""
            SELECT DISTINCT daypart
            FROM showings
            WHERE theater_name IN ({theater_placeholders})
            AND film_title IN ({film_placeholders})
            AND play_date BETWEEN ? AND ?
            ORDER BY daypart
        """
        params = theaters + films + [start_date, end_date]
        df = pd.read_sql_query(query, conn, params=params)
    return df['daypart'].tolist()

def get_theaters_with_data(data_type):
    """Gets a list of theaters that have data for the selected data type."""
    # Whitelist allowed table names to prevent SQL injection
    table_mapping = {
        "showtimes": "showings",
        "prices": "showings",
        "op_hours": "operating_hours"
    }

    table_name = table_mapping.get(data_type)
    if not table_name:
        return []

    with _get_db_connection() as conn:
        if table_name == "showings":
            # Ensure we only get theaters that actually have price data associated
            query = """
                SELECT DISTINCT s.theater_name FROM showings s
                JOIN prices p ON s.showing_id = p.showing_id
                ORDER BY s.theater_name
            """
        else:
            query = f"SELECT DISTINCT theater_name FROM {table_name} ORDER BY theater_name"
        df = pd.read_sql_query(query, conn)
    return df['theater_name'].tolist()

def get_common_dates_for_theaters(theaters, data_type):
    """Gets a list of common dates for a given list of theaters and data type."""
    if not theaters:
        return []

    table_name = ""
    date_column = ""
    if data_type in ["showtimes", "prices"]:
        table_name = "showings"
        date_column = "play_date"
    elif data_type == "op_hours":
        table_name = "operating_hours"
        date_column = "scrape_date"
    else:
        return []

    with _get_db_connection() as conn:
        placeholders = ','.join(['?'] * len(theaters))
        
        # Inner query to get dates per theater
        inner_query = f"""
            SELECT DISTINCT {date_column} AS play_date, theater_name
            FROM {table_name}
            WHERE theater_name IN ({placeholders}) AND {date_column} IS NOT NULL
        """


        # Outer query to find common dates
        query = f"""
            SELECT play_date
            FROM ({inner_query})
            GROUP BY play_date
            HAVING COUNT(DISTINCT theater_name) = ?
            ORDER BY play_date DESC
        """
        
        params = theaters + [len(theaters)]
        df = pd.read_sql_query(query, conn, params=params)
    return pd.to_datetime(df['play_date']).dt.date.tolist()

def get_operating_hours_for_theaters_and_dates(theater_list, start_date, end_date):
    """
    Fetches operating hours for a list of theaters within a specific date range.
    """
    if not theater_list:
        return pd.DataFrame()
    with _get_db_connection() as conn:
        placeholders = ','.join(['?'] * len(theater_list))
        # --- FIX: Use ROW_NUMBER() to correctly get the latest run for each day per theater ---
        # The previous subquery was flawed and could drop theaters if they shared a latest run_id.
        query = f"""
            WITH RankedRuns AS (
                SELECT 
                    oh.theater_name, 
                    oh.scrape_date,
                    oh.open_time,
                    oh.close_time,
                    ROW_NUMBER() OVER(PARTITION BY oh.theater_name, oh.scrape_date ORDER BY r.run_timestamp DESC) as rn
                FROM operating_hours oh
                JOIN scrape_runs r ON oh.run_id = r.run_id
                WHERE oh.theater_name IN ({placeholders})
                AND oh.scrape_date BETWEEN ? AND ?
            )
            SELECT scrape_date, theater_name, open_time, close_time
            FROM RankedRuns
            WHERE rn = 1;
        """
        params = theater_list + [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]
        df = pd.read_sql_query(query, conn, params=params)
    return df

def calculate_operating_hours_from_showings(theater_list: list[str], start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    """
    [FALLBACK] Calculates operating hours by finding the min/max showtimes
    from the 'showings' table. This is used when no data is in the 'operating_hours' table.
    """
    from app.utils import normalize_time_string # Local import to avoid circular dependency
    if not theater_list:
        return pd.DataFrame()

    with _get_db_connection() as conn:
        placeholders = ','.join(['?'] * len(theater_list))
        query = f"""
            SELECT theater_name, play_date as scrape_date, showtime
            FROM showings
            WHERE theater_name IN ({placeholders})
            AND play_date BETWEEN ? AND ?
        """
        params = theater_list + [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return pd.DataFrame()

    # Convert showtime strings to datetime objects for correct min/max calculation
    df['time_obj'] = df['showtime'].apply(lambda x: datetime.datetime.strptime(normalize_time_string(x), "%I:%M%p").time())

    # Group by theater and date, then find the min and max times
    agg_df = df.groupby(['theater_name', 'scrape_date']).agg(
        open_time=('time_obj', 'min'),
        close_time=('time_obj', 'max')
    ).reset_index()

    # Format times back to strings for consistency with the primary operating_hours table
    agg_df['open_time'] = agg_df['open_time'].apply(lambda x: x.strftime('%I:%M %p').lstrip('0'))
    agg_df['close_time'] = agg_df['close_time'].apply(lambda x: x.strftime('%I:%M %p').lstrip('0'))

    # Ensure column names match the output of get_operating_hours_for_theaters_and_dates
    return agg_df[['scrape_date', 'theater_name', 'open_time', 'close_time']]

def get_all_op_hours_dates(theater_list):
    """Gets all unique dates that the selected theaters have operating hours records for."""
    if not theater_list:
        return []
    with _get_db_connection() as conn:
        placeholders = ','.join(['?'] * len(theater_list))
        query = f"""
            SELECT DISTINCT scrape_date
            FROM operating_hours
            WHERE theater_name IN ({placeholders})
            ORDER BY scrape_date DESC
        """
        df = pd.read_sql_query(query, conn, params=theater_list)
    return pd.to_datetime(df['scrape_date']).dt.date.tolist()

def backfill_play_dates():
    """
    Backfills the 'play_date' column for old records using a more robust assumption.
    - Scrapes before 8 AM are assumed to be for the same day.
    - Scrapes after 8 AM are assumed to be for the next day.
    This is a one-time migration utility.
    """
    with _get_db_connection() as conn:
        cursor = conn.cursor()

        # First, count how many records need updating for user feedback.
        count_query = "SELECT COUNT(*) FROM prices WHERE play_date IS NULL"
        initial_null_count = cursor.execute(count_query).fetchone()[0]

        if initial_null_count == 0:
            return 0, 0 # No records to update

        # This single UPDATE statement is more efficient and robust.
        update_query = """
            UPDATE prices
            SET play_date = (
                SELECT 
                    CASE 
                        WHEN STRFTIME('%H', r.run_timestamp) < '08' THEN DATE(r.run_timestamp)
                        ELSE DATE(r.run_timestamp, '+1 day')
                    END
                FROM scrape_runs r
                WHERE r.run_id = prices.run_id
            )
            WHERE play_date IS NULL
        """
        cursor.execute(update_query)
        updated_count = cursor.rowcount
        conn.commit()
        return -1, updated_count # Return -1 for runs as we didn't count them individually

def upsert_film_details(film_data: dict):
    """Inserts or updates a film's metadata in the database."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        # Use ON CONFLICT to handle both inserts and updates gracefully
        cursor.execute('''
            INSERT INTO films (
                film_title, imdb_id, genre, mpaa_rating, runtime, director, actors, plot, poster_url,
                metascore, imdb_rating, release_date, domestic_gross, opening_weekend_domestic, last_omdb_update
            ) VALUES (
                :film_title, :imdb_id, :genre, :mpaa_rating, :runtime, :director, :actors, :plot, :poster_url,
                :metascore, :imdb_rating, :release_date, :domestic_gross, :opening_weekend_domestic, :last_omdb_update
            ) ON CONFLICT(film_title) DO UPDATE SET
                imdb_id=excluded.imdb_id,
                genre=excluded.genre,
                mpaa_rating=excluded.mpaa_rating,
                runtime=excluded.runtime,
                director=excluded.director,
                actors=excluded.actors,
                plot=excluded.plot,
                poster_url=excluded.poster_url,
                metascore=excluded.metascore,
                imdb_rating=excluded.imdb_rating,
                release_date=excluded.release_date,
                domestic_gross=excluded.domestic_gross,
                opening_weekend_domestic=excluded.opening_weekend_domestic,
                last_omdb_update=excluded.last_omdb_update;
        ''', film_data)
        conn.commit()

def check_film_exists(film_title: str) -> bool:
    """Checks if a film already has metadata in the films table."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM films WHERE film_title = ?", (film_title,))
        exists = cursor.fetchone() is not None
    return exists

def get_film_details(film_title: str) -> dict | None:
    """Retrieves a single film's details from the database."""
    with _get_db_connection() as conn:
        conn.row_factory = sqlite3.Row # Set row_factory to get dict-like rows
        film = conn.execute("SELECT * FROM films WHERE film_title = ?", (film_title,)).fetchone()
    return dict(film) if film else None

def get_all_unique_genres() -> list[str]:
    """Gets a list of all unique genres from the films table."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT genre FROM films WHERE genre IS NOT NULL")
        genres_tuples = cursor.fetchall()
    
    # Genres can be comma-separated, so we need to split and flatten them
    unique_genres = set()
    for row in genres_tuples:
        if row[0]:
            genres = row[0].split(', ')
            unique_genres.update(genres)
        
    return sorted(list(unique_genres))

def get_all_unique_ratings() -> list[str]:
    """Gets a list of all unique MPAA ratings from the films table."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        # Exclude common non-rating values
        cursor.execute("SELECT DISTINCT mpaa_rating FROM films WHERE mpaa_rating IS NOT NULL AND mpaa_rating NOT IN ('N/A', 'Not Rated', 'Unrated')")
        ratings_tuples = cursor.fetchall()
    
    unique_ratings = {row[0] for row in ratings_tuples if row[0]}
    return sorted(list(unique_ratings))

def log_unmatched_film(film_title: str):
    """Logs a new, unique unmatched film title to the database."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO unmatched_films (film_title, first_seen)
            VALUES (?, ?)
        """, (film_title, datetime.datetime.now()))
        conn.commit()

def get_unmatched_films() -> pd.DataFrame:
    """Fetches all unmatched film titles from the database."""
    with _get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM unmatched_films ORDER BY first_seen DESC", conn)
    return df

def delete_unmatched_film(film_title: str):
    """Deletes a processed unmatched film title from the database by its title."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM unmatched_films WHERE film_title = ?", (film_title,))
        conn.commit()

def get_ticket_type_usage_counts() -> pd.DataFrame:
    """Fetches the counts of each ticket_type from the prices table."""
    import json
    import os

    with _get_db_connection() as conn:
        query = "SELECT ticket_type, COUNT(*) as count FROM prices GROUP BY ticket_type"
        df = pd.read_sql_query(query, conn)

    if df.empty:
        return df

    # --- NEW: Consolidate ticket types in memory for accurate reporting ---
    try:
        ticket_types_path = os.path.join(os.path.dirname(__file__), 'ticket_types.json')
        with open(ticket_types_path, 'r') as f:
            ticket_types_data = json.load(f)
        base_type_map = ticket_types_data.get('base_type_map', {})
    except (FileNotFoundError, json.JSONDecodeError):
        # If the file is missing, just return the raw counts.
        return df.sort_values(by='count', ascending=False)

    # Create a reverse map from variation to canonical name
    reverse_map = {}
    for canonical, variations in base_type_map.items():
        # Ensure the canonical name itself also maps to itself
        reverse_map[canonical.lower()] = canonical
        for variation in variations:
            reverse_map[variation.lower()] = canonical

    # Apply the mapping. If a type isn't in the map, it keeps its original name.
    df['canonical_type'] = df['ticket_type'].str.lower().map(reverse_map).fillna(df['ticket_type'])

    # Re-group and sum the counts after consolidation
    consolidated_df = df.groupby('canonical_type')['count'].sum().reset_index().rename(columns={'canonical_type': 'ticket_type'}).sort_values(by='count', ascending=False)
    return consolidated_df

def log_unmatched_ticket_type(original_description: str, unmatched_part: str, showing_details: dict | None = None):
    """Logs a new, unique unmatched ticket type part to the database."""
    context = showing_details or {}
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO unmatched_ticket_types 
            (original_description, unmatched_part, first_seen, theater_name, film_title, showtime, format, play_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (original_description, unmatched_part, datetime.datetime.now(),
              context.get('theater_name'), context.get('film_title'),
              context.get('showtime'), context.get('format'), context.get('play_date')))
        conn.commit()

def get_unmatched_ticket_types() -> pd.DataFrame:
    """Fetches all unmatched ticket types from the database."""
    with _get_db_connection() as conn:
        # Fetch all columns including the new context
        df = pd.read_sql_query("SELECT * FROM unmatched_ticket_types ORDER BY play_date DESC, first_seen DESC", conn)
    return df

def get_films_missing_release_date() -> list[str]:
    """
    Returns a list of film titles that are in the films table but have a NULL or 'N/A' release_date.
    """
    with _get_db_connection() as conn:
        query = """
            SELECT film_title FROM films 
            WHERE release_date IS NULL OR release_date = 'N/A'
        """
        df = pd.read_sql_query(query, conn)
    return df['film_title'].tolist()

def delete_unmatched_ticket_type(unmatched_id: int):
    """Deletes a processed unmatched ticket type from the database by its ID."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM unmatched_ticket_types WHERE id = ?", (unmatched_id,))
        conn.commit()


def get_films_missing_metadata() -> list[str]:
    """
    Returns a list of film titles that are in the showings table
    but do not have an entry in the films table.
    """
    with _get_db_connection() as conn:
        query = """
            SELECT DISTINCT s.film_title
            FROM showings s
            LEFT JOIN films f ON s.film_title = f.film_title
            WHERE f.film_id IS NULL AND s.film_title IS NOT NULL;
        """
        df = pd.read_sql_query(query, conn)
    return df['film_title'].tolist()

def get_films_missing_metadata_for_dates(start_date, end_date) -> list[str]:
    """
    Returns a list of film titles that have showings within a date range
    but do not have an entry in the films table.
    """
    with _get_db_connection() as conn:
        query = """
            SELECT DISTINCT s.film_title
            FROM showings s
            LEFT JOIN films f ON s.film_title = f.film_title
            WHERE f.film_id IS NULL
            AND s.film_title IS NOT NULL
            AND s.play_date BETWEEN ? AND ?;
        """
        params = [start_date, end_date]
        df = pd.read_sql_query(query, conn, params=params)
    return df['film_title'].tolist()

def get_comparable_films(film_title: str, film_genres: list[str]) -> pd.DataFrame:
    """
    Finds other films in the database that share at least one genre.
    Returns a DataFrame with comparable films and their key metrics.
    """
    if not film_genres:
        return pd.DataFrame()

    with _get_db_connection() as conn:
        genre_clauses = " OR ".join(["f.genre LIKE ?" for _ in film_genres])
        query = f"""
            SELECT
                f.film_title AS "Film Title",
                f.domestic_gross AS "Box Office",
                f.genre AS "Genre(s)",
                f.imdb_rating AS "IMDb Rating",
                AVG(p.price) as "Average Price",
                COUNT(DISTINCT s.showing_id) as "Total Showings"
            FROM films f
            JOIN showings s ON f.film_title = s.film_title
            JOIN prices p ON s.showing_id = p.showing_id
            WHERE ({genre_clauses}) AND f.film_title != ?
            GROUP BY f.film_title
            ORDER BY "Total Showings" DESC
            LIMIT 10;
        """
        params = [f"%{g}%" for g in film_genres] + [film_title]
        df = pd.read_sql_query(query, conn, params=params)
    return df

def get_first_play_date_for_all_films() -> dict[str, str]:
    """
    Gets the earliest play_date for every film in the showings table.
    Returns a dictionary mapping film_title to its first play_date.
    """
    with _get_db_connection() as conn:
        query = """
            SELECT film_title, MIN(play_date) as first_play_date
            FROM showings
            GROUP BY film_title
        """
        df = pd.read_sql_query(query, conn)
    return pd.Series(df.first_play_date.values, index=df.film_title).to_dict()

def get_all_films_for_enrichment(as_df=False):
    """Fetches all films from the database, useful for enrichment tasks."""
    with _get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM films ORDER BY release_date DESC, film_title ASC"
        if as_df:
            return pd.read_sql_query(query, conn)
        else:
            films = conn.execute(query).fetchall()
            return [dict(film) for film in films]

def add_film_to_ignore_list(film_title: str):
    """Adds a film title to the ignore list to hide it from the Poster Board."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO ignored_films (film_title) VALUES (?)", (film_title,))
        conn.commit()

def get_ignored_film_titles() -> list[str]:
    """Fetches a list of all film titles in the ignore list."""
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT film_title FROM ignored_films")
        return [row[0] for row in cursor.fetchall()]

def get_theater_comparison_summary(theater_list, start_date, end_date):
    """
    Generates a summary DataFrame for comparing multiple theaters side-by-side.
    """
    if not theater_list:
        return pd.DataFrame()

    with _get_db_connection() as conn:
        placeholders = ",".join(["?"] * len(theater_list))
        
        query = f"""
            SELECT
                s.theater_name,
                COUNT(DISTINCT s.showing_id) as "Total Showings",
                COUNT(DISTINCT s.film_title) as "Unique Films",
                GROUP_CONCAT(DISTINCT s.format) as all_formats
            FROM showings s
            LEFT JOIN prices p ON s.showing_id = p.showing_id
            WHERE s.theater_name IN ({placeholders})
            AND s.play_date BETWEEN ? AND ?
            GROUP BY s.theater_name
        """
        params = theater_list + [start_date, end_date]
        df = pd.read_sql_query(query, conn, params=params)

        # --- NEW: Calculate average price separately with filtering ---
        avg_price_query = f"""
            SELECT s.theater_name, AVG(p.price) as "Overall Avg. Price"
            FROM showings s
            JOIN prices p ON s.showing_id = p.showing_id
            WHERE s.theater_name IN ({placeholders})
            AND s.play_date BETWEEN ? AND ?
            AND p.ticket_type IN ('Adult', 'Senior', 'Child')
            GROUP BY s.theater_name
        """
        avg_price_df = pd.read_sql_query(avg_price_query, conn, params=params)

        if not df.empty and not avg_price_df.empty:
            df = pd.merge(df, avg_price_df, on='theater_name', how='left')

    if not df.empty and 'all_formats' in df.columns:
        def process_formats(format_str):
            """Calculates the number of premium formats and returns a clean string representation."""
            if not format_str:
                return 0, "N/A"
            
            all_formats = set(part.strip() for item in format_str.split(',') for part in item.split(','))
            
            # Premium formats are anything that is not '2D'
            premium_formats = {f for f in all_formats if f != '2D'}
            
            num_premium = len(premium_formats)
            display_str = ", ".join(sorted(list(premium_formats))) if premium_formats else "N/A"
            
            return num_premium, display_str

        # --- REFACTORED: Apply the function and handle the new PLF count ---
        processed_formats_df = df['all_formats'].apply(lambda x: pd.Series(process_formats(x), index=['# Premium Formats', 'Premium Formats']))
        df = pd.concat([df, processed_formats_df], axis=1).drop(columns=['all_formats'])

        # Add a new column for PLF count
        df['PLF Count'] = df['# Premium Formats']

    return df

def get_market_at_a_glance_data(theater_list: list[str], start_date: datetime.date, end_date: datetime.date, films: list[str] | None = None) -> tuple[pd.DataFrame, datetime.date | None]:
    """
    Fetches data for the 'Market At a Glance' report.
    - Gets data from the specified date range.
    - Joins showings and prices to get all necessary details.
    - Returns the DataFrame and the most recent scrape date found.
    """
    if not theater_list:
        return pd.DataFrame(), None

    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    with _get_db_connection() as conn:
        placeholders = ",".join(["?"] * len(theater_list))

        query = f"""
            SELECT
                s.theater_name,
                s.film_title,
                s.daypart,
                f.release_date,
                s.format,
                s.is_plf,
                p.ticket_type,
                p.price,
                r.run_timestamp
            FROM prices p
            JOIN showings s ON p.showing_id = s.showing_id
            LEFT JOIN films f ON s.film_title = f.film_title
            JOIN scrape_runs r ON p.run_id = r.run_id
            WHERE s.theater_name IN ({placeholders})
            AND s.play_date BETWEEN ? AND ?
        """
        params = theater_list + [start_date_str, end_date_str]

        # --- NEW: Add film filter if provided ---
        if films:
            film_placeholders = ",".join(["?"] * len(films))
            query += f" AND s.film_title IN ({film_placeholders})"
            params.extend(films)

        df = pd.read_sql_query(query, conn, params=params)

    latest_scrape_date = None
    if not df.empty and 'run_timestamp' in df.columns:
        latest_scrape_date = pd.to_datetime(df['run_timestamp']).max().date()

    # --- NEW: Consolidate ticket types in memory for accurate reporting ---
    if not df.empty:
        import json
        import os
        try:
            ticket_types_path = os.path.join(os.path.dirname(__file__), 'ticket_types.json')
            with open(ticket_types_path, 'r') as f:
                ticket_types_data = json.load(f)
            base_type_map = ticket_types_data.get('base_type_map', {})
            
            # Create a reverse map from variation to canonical name
            reverse_map = {}
            for canonical, variations in base_type_map.items():
                reverse_map[canonical.lower()] = canonical
                for variation in variations:
                    reverse_map[variation.lower()] = canonical

            # Apply the mapping. If a type isn't in the map, it keeps its original name.
            df['ticket_type'] = df['ticket_type'].str.lower().map(reverse_map).fillna(df['ticket_type'])

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  [DB-WARN] Could not consolidate ticket types for glance report. File missing or corrupt. Error: {e}")
            # Continue with unconsolidated data if the mapping file is missing

    return df, latest_scrape_date

def _get_canonical_mystery_movie_name(title: str) -> str | None:
    """
    Checks if a title matches known 'Mystery Movie' patterns and returns a canonical name.
    This is used to group variations like 'Mystery Movie 10/25' under a single name.
    """
    import re
    mystery_patterns = {
        "Mystery Movie": re.compile(r'^(amc )?mystery movie.*', re.IGNORECASE),
        "Secret Movie": re.compile(r'^secret movie.*', re.IGNORECASE),
        "Secret Screening": re.compile(r'^secret screening.*', re.IGNORECASE),
    }
    for canonical_name, pattern in mystery_patterns.items():
        if pattern.match(title):
            return canonical_name
    return None

def upsert_showings(all_showings, play_date):
    """
    Inserts or ignores showings into the showings table.
    This ensures the schedule is up-to-date without creating duplicates.
    Also triggers on-the-fly film metadata enrichment.
    """
    showings_to_insert = []
    unique_titles_in_batch = set()
    for theater_name, showings in all_showings.items():
        for showing in showings:
            unique_titles_in_batch.add(showing['film_title'])
            showings_to_insert.append((
                play_date.strftime('%Y-%m-%d'),
                theater_name,
                showing['film_title'],
                showing['showtime'],
                showing['format'],
                showing['daypart'],
                showing.get('is_plf', False),
                showing['ticket_url']
            ))

    if not showings_to_insert:
        return

    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT OR IGNORE INTO showings
            (play_date, theater_name, film_title, showtime, format, daypart, is_plf, ticket_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, showings_to_insert)
        conn.commit()
        print(f"  [DB] Upserted {cursor.rowcount} new showings for {play_date.strftime('%Y-%m-%d')}.")

    # --- On-the-fly film metadata enrichment ---
    try:
        if not unique_titles_in_batch:
            return

        # --- OPTIMIZATION: Check for all existing films in one query ---
        placeholders = ','.join(['?'] * len(unique_titles_in_batch))
        with _get_db_connection() as conn:
            query = f"SELECT film_title FROM films WHERE film_title IN ({placeholders})"
            existing_films_df = pd.read_sql_query(query, conn, params=list(unique_titles_in_batch))
        
        existing_films = set(existing_films_df['film_title'])
        new_films_to_enrich = unique_titles_in_batch - existing_films

        if not new_films_to_enrich:
            return # All films in this batch already have metadata

        omdb_client = OMDbClient()
        from app.scraper import Scraper # Local import to avoid circular dependency
        for title in new_films_to_enrich:
            # --- NEW: Proactively check for and handle Mystery Movie patterns ---
            canonical_name = _get_canonical_mystery_movie_name(title)
            if canonical_name:
                print(f"  [Auto-Categorize] Recognized '{title}' as '{canonical_name}'.")
                if not check_film_exists(canonical_name):
                    print(f"  [Auto-Categorize] Creating standard record for '{canonical_name}'.")
                    minimal_details = {
                        "film_title": canonical_name, "mpaa_rating": "N/A", "runtime": "N/A",
                        "genre": "Special Event", "plot": "A special mystery screening event.",
                        "imdb_id": None, "director": None, "actors": None, "poster_url": None,
                        "metascore": None, "imdb_rating": None, "release_date": None,
                        "domestic_gross": None, "opening_weekend_domestic": None,
                        "last_omdb_update": datetime.datetime.now()
                    }
                    upsert_film_details(minimal_details)
                continue # Skip OMDb lookup for this title            
            if canonical_name:
                print(f"  [Auto-Categorize] Recognized '{title}' as '{canonical_name}'.")
                if not check_film_exists(canonical_name):
                    print(f"  [Auto-Categorize] Creating standard record for '{canonical_name}'.")
                    minimal_details = {
                        "film_title": canonical_name, "mpaa_rating": "N/A", "runtime": "N/A",
                        "genre": "Special Event", "plot": "A special mystery screening event.",
                        "imdb_id": None, "director": None, "actors": None, "poster_url": None,
                        "metascore": None, "imdb_rating": None, "release_date": None,
                        "domestic_gross": None, "opening_weekend_domestic": None,
                        "last_omdb_update": datetime.datetime.now()
                    }
                    upsert_film_details(minimal_details)
                continue # Skip OMDb lookup for this title

            film_details = omdb_client.get_film_details(title)
            if film_details:
                film_details['film_title'] = title # Ensure our primary key matches the showing title
                upsert_film_details(film_details)
                print(f"  [OMDb] Successfully saved details for '{title}'.")
            else:
                # --- NEW: Fandango Search Fallback ---
                print(f"  [Fandango Fallback] OMDb failed for '{title}'. Attempting Fandango search...")
                scraper = Scraper()
                fandango_search_results = asyncio.run(scraper.search_fandango_for_film_url(title))

                # Use the first result if it's a high-confidence match
                if fandango_search_results:
                    best_match = fandango_search_results[0]
                    from thefuzz import fuzz
                    # Use a high threshold to avoid incorrect matches
                    if fuzz.ratio(title.lower(), best_match['title'].lower()) > 85:
                        print(f"  [Fandango Fallback] Found match: '{best_match['title']}'. Scraping details...")
                        fandango_details = asyncio.run(scraper.get_film_details_from_fandango_url(best_match['url']))
                        if fandango_details:
                            fandango_details['film_title'] = title # Use original title as key
                            upsert_film_details(fandango_details)
                            print(f"  [Fandango Fallback] Successfully saved details for '{title}'.")
                            continue # Skip to the next film

                # If Fandango fallback also fails, log for manual review.
                # First, check if we have any pre-scraped details from the showtime page.
                if not _try_fandango_prescraped_fallback(title, all_showings):
                    log_unmatched_film(title)
                    print(f"  [Fallback Failed] Could not find details for '{title}' on OMDb or Fandango. Logged for manual review.")
    except Exception as e:
        print(f"  [OMDb] [WARNING] Could not perform OMDb enrichment. Reason: {e}")

def _try_fandango_prescraped_fallback(title: str, all_showings: dict) -> bool:
    """
    A final attempt to use details scraped during the initial showtime discovery.
    Returns True if data was found and saved, False otherwise.
    """
    for showings_list in all_showings.values():
        for showing in showings_list:
            if showing['film_title'] == title and showing.get('fandango_plot') and showing.get('fandango_plot') != 'N/A':
                fandango_fallback_data = {
                    "film_title": title,
                    "mpaa_rating": showing.get('fandango_rating', 'N/A'),
                    "runtime": showing.get('fandango_runtime', 'N/A'),
                    "plot": showing.get('fandango_plot', 'N/A'),
                    "genre": "Special Event",
                    "imdb_id": None, "director": None, "actors": None,
                    "poster_url": None, "metascore": None, "imdb_rating": None,
                    "release_date": None, "domestic_gross": None, "opening_weekend_domestic": None,
                    "last_omdb_update": datetime.datetime.now()
                }
                print(f"  [Fandango Fallback] Using pre-scraped details for '{title}'.")
                upsert_film_details(fandango_fallback_data)
                return True
    return False

def migrate_schema():
    """
    Migrates the database from the old single `prices` table schema to the new
    `showings` and `prices` schema.
    """
    with _get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(prices)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'showing_id' in columns:
            return "Schema is already up-to-date."

        # --- Start Migration ---
        print("  [MIGRATE] Starting database schema migration...")
        
        # 1. Backfill play_dates in the old table first
        backfill_play_dates()

        # 2. Rename old table
        cursor.execute("ALTER TABLE prices RENAME TO prices_old")

        # 3. Create new tables
        init_database()

        # 4. Populate showings table from old prices table
        cursor.execute("""
            INSERT INTO showings (play_date, theater_name, film_title, showtime, format, daypart)
            SELECT DISTINCT play_date, theater_name, film_title, showtime, format, daypart
            FROM prices_old WHERE play_date IS NOT NULL
        """)

        # 5. Populate new prices table by joining old data with new showings table
        cursor.execute("""
            INSERT INTO prices (run_id, showing_id, ticket_type, price, capacity, play_date)
            SELECT p.run_id, s.showing_id, p.ticket_type, p.price, p.capacity, p.play_date
            FROM prices_old p
            JOIN showings s ON 
                p.play_date = s.play_date AND
                p.theater_name = s.theater_name AND
                p.film_title = s.film_title AND
                p.showtime = s.showtime AND
                p.format = s.format
        """)
        
        # 6. Drop the old table
        cursor.execute("DROP TABLE prices_old")
        
        conn.commit()
        return "Successfully migrated database schema."

def consolidate_ticket_types() -> int:
    """
    Updates ticket types in the prices table to their canonical names based on ticket_types.json.
    For example, if 'Child' is the canonical name for ['children', 'kid'], this function
    will update all records where ticket_type is 'children' or 'kid' to be 'Child'.
    Returns the number of rows updated.
    """
    import json
    import os

    ticket_types_path = os.path.join(os.path.dirname(__file__), 'ticket_types.json')
    try:
        with open(ticket_types_path, 'r') as f:
            ticket_types_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("[DB ERROR] Could not load ticket_types.json for consolidation.")
        return 0

    base_type_map = ticket_types_data.get('base_type_map', {})
    total_updated_count = 0

    with _get_db_connection() as conn:
        cursor = conn.cursor()
        for canonical_name, variations in base_type_map.items():
            # --- FIX: Update any variation that is not an exact match for the canonical name ---
            # The previous logic (v.lower() != canonical_name.lower()) would fail to update
            # 'adult' to 'Adult' because their lowercase versions are the same.
            variations_to_update = [v for v in variations if v != canonical_name]
            if variations_to_update:
                # SECURITY NOTE: This query uses f-strings for dynamic placeholder count, but is SAFE because:
                # 1. All values go through parameterized execution (the list passed to execute())
                # 2. No user input enters the query structure - only list length determines placeholders
                # 3. The ticket_type values come from a controlled mapping (ticket_types.json)
                # See SECURITY_AUDIT_REPORT.md HIGH-01 for details.
                placeholders = ','.join(['?'] * len(variations_to_update))
                cursor.execute(f"UPDATE prices SET ticket_type = ? WHERE ticket_type IN ({placeholders})", [canonical_name] + variations_to_update)
                total_updated_count += cursor.rowcount
        conn.commit()
    return total_updated_count
