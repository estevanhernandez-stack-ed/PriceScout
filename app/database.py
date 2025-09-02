import sqlite3
import pandas as pd
import datetime
from config import DB_FILE

def init_database():
    """Initializes the SQLite database and creates tables if they don't exist."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrape_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_timestamp DATETIME NOT NULL,
                mode TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                price_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                theater_name TEXT NOT NULL,
                film_title TEXT NOT NULL,
                showtime TEXT NOT NULL,
                daypart TEXT,
                format TEXT,
                ticket_type TEXT NOT NULL,
                price REAL NOT NULL,
                capacity TEXT,
                FOREIGN KEY (run_id) REFERENCES scrape_runs (run_id)
            )
        ''')
        conn.commit()

def get_dates_for_theaters(theater_list):
    """Gets the unique dates that the selected theaters have records for."""
    if not theater_list:
        return []
    with sqlite3.connect(DB_FILE) as conn:
        placeholders = ','.join(['?'] * len(theater_list))
        query = f"""
            SELECT DISTINCT DATE(r.run_timestamp) as scrape_date
            FROM prices p
            JOIN scrape_runs r ON p.run_id = r.run_id
            WHERE p.theater_name IN ({placeholders})
            ORDER BY scrape_date DESC
        """
        df = pd.read_sql_query(query, conn, params=theater_list)
    return df['scrape_date'].tolist()

def get_common_films_for_theaters_dates(theater_list, date_list):
    """Gets films that are available for ALL selected theaters on AT LEAST ONE of the selected dates."""
    if not theater_list or not date_list:
        return []
    with sqlite3.connect(DB_FILE) as conn:
        theater_placeholders = ','.join(['?'] * len(theater_list))
        date_placeholders = ','.join(['?'] * len(date_list))
        
        query = f"""
            SELECT film_title FROM (
                SELECT DISTINCT film_title, theater_name
                FROM prices p
                JOIN scrape_runs r ON p.run_id = r.run_id
                WHERE p.theater_name IN ({theater_placeholders})
                AND DATE(r.run_timestamp) IN ({date_placeholders})
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
        
    with sqlite3.connect(DB_FILE) as conn:
        theater_ph = ','.join(['?'] * len(theater_list))
        date_ph = ','.join(['?'] * len(date_list))
        film_ph = ','.join(['?'] * len(film_list))
        daypart_ph = ','.join(['?'] * len(daypart_list))

        query = f"""
            SELECT 
                DATE(r.run_timestamp) as scrape_date,
                p.theater_name, 
                p.film_title, 
                p.daypart, 
                p.ticket_type,
                p.price
            FROM prices p
            JOIN scrape_runs r ON p.run_id = r.run_id
            WHERE p.theater_name IN ({theater_ph})
            AND DATE(r.run_timestamp) IN ({date_ph})
            AND p.film_title IN ({film_ph})
            AND p.daypart IN ({daypart_ph})
        """
        params = theater_list + date_list + film_list + daypart_list
        df = pd.read_sql_query(query, conn, params=params)
    return df

def update_database_schema():
    """Adds new columns to the database if they don't already exist."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(scrape_runs)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'run_context' not in columns:
            print("  [DB] Adding 'run_context' column to scrape_runs table.")
            cursor.execute('ALTER TABLE scrape_runs ADD COLUMN run_context TEXT')
            conn.commit()

def save_to_database(df, mode, context):
    """Saves a DataFrame of scraped prices to the database."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        run_timestamp = datetime.datetime.now()
        cursor.execute('INSERT INTO scrape_runs (run_timestamp, mode, run_context) VALUES (?, ?, ?)', (run_timestamp, mode, context))
        run_id = cursor.lastrowid
        
        df_to_save = df.copy()
        df_to_save['run_id'] = run_id
        df_to_save['Price'] = df_to_save['Price'].replace({'\$': ''}, regex=True).astype(float)
        
        df_to_save = df_to_save.rename(columns={
            'Brand': 'brand', 'Theater Name': 'theater_name', 'Film Title': 'film_title',
            'Showtime': 'showtime', 'Daypart': 'daypart',
            'Format': 'format', 'Ticket Type': 'ticket_type',
            'Price': 'price', 'Capacity': 'capacity'
        })

        db_cols = [desc[1] for desc in cursor.execute("PRAGMA table_info(prices)").fetchall()]
        df_cols_to_save = [col for col in df_to_save.columns if col in db_cols]
        
        df_to_save[df_cols_to_save].to_sql(
            'prices', conn, if_exists='append', index=False
        )
        conn.commit()
        print(f"  [DB] Saved {len(df_to_save)} records to database for run ID {run_id}.")

def get_scrape_runs():
    """Fetches all historical scrape runs from the database."""
    with sqlite3.connect(DB_FILE) as conn:
        query = "SELECT run_id, run_timestamp, mode, run_context FROM scrape_runs ORDER BY run_timestamp DESC"
        df = pd.read_sql_query(query, conn)
    return df

def get_prices_for_run(run_id):
    """Fetches all price data for a specific run_id."""
    with sqlite3.connect(DB_FILE) as conn:
        query = f"SELECT theater_name, film_title, showtime, format, ticket_type, price, capacity FROM prices WHERE run_id = {run_id}"
        df = pd.read_sql_query(query, conn)
    return df

def query_historical_data(start_date, end_date, theaters=None, films=None):
    """Queries the database for price records within a date range, with optional filters."""
    with sqlite3.connect(DB_FILE) as conn:
        query = '''
            SELECT p.theater_name, p.film_title, p.showtime, p.format, p.ticket_type, p.price, r.run_timestamp
            FROM prices p
            JOIN scrape_runs r ON p.run_id = r.run_id
            WHERE DATE(r.run_timestamp) BETWEEN ? AND ?
        '''
        params = [start_date, end_date]
        if theaters:
            query += f" AND p.theater_name IN ({','.join(['?']*len(theaters))})"
            params.extend(theaters)
        if films:
            query += f" AND p.film_title IN ({','.join(['?']*len(films))})"
            params.extend(films)
        query += " ORDER BY r.run_timestamp DESC, p.theater_name, p.film_title"
        df = pd.read_sql_query(query, conn, params=params)
    return df

def get_unique_column_values(column_name):
    """Gets all unique values from a column in the prices table."""
    with sqlite3.connect(DB_FILE) as conn:
        query = f"SELECT DISTINCT {column_name} FROM prices ORDER BY {column_name}"
        df = pd.read_sql_query(query, conn)
    return df[column_name].tolist()

def get_dates_for_theater(theater_name):
    """Gets the unique dates a specific theater has records for."""
    with sqlite3.connect(DB_FILE) as conn:
        query = '''
            SELECT DISTINCT DATE(r.run_timestamp) as scrape_date
            FROM prices p
            JOIN scrape_runs r ON p.run_id = r.run_id
            WHERE p.theater_name = ?
            ORDER BY scrape_date DESC
        '''
        df = pd.read_sql_query(query, conn, params=(theater_name,))
    return df['scrape_date'].tolist()

def get_films_for_theater_date(theater_name, date):
    """Gets the unique films a specific theater has for a specific date."""
    with sqlite3.connect(DB_FILE) as conn:
        query = '''
            SELECT DISTINCT p.film_title
            FROM prices p
            JOIN scrape_runs r ON p.run_id = r.run_id
            WHERE p.theater_name = ? AND DATE(r.run_timestamp) = ?
            ORDER BY p.film_title
        '''
        df = pd.read_sql_query(query, conn, params=(theater_name, date))
    return df['film_title'].tolist()


def get_final_prices(theater_name, date, film_title, daypart="All"):
    """
    Gets the final price data for the selected drill-down filters,
    with an added optional filter for daypart.
    """
    with sqlite3.connect(DB_FILE) as conn:
        query = '''
            SELECT p.showtime, p.format, p.daypart, p.ticket_type, p.price, p.capacity, r.run_timestamp
            FROM prices p
            JOIN scrape_runs r ON p.run_id = r.run_id
            WHERE p.theater_name = ? AND DATE(r.run_timestamp) = ? AND p.film_title = ?
        '''
        params = [theater_name, date, film_title]

        if daypart != "All":
            query += " AND p.daypart = ?"
            params.append(daypart)

        query += " ORDER BY r.run_timestamp DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
    return df
