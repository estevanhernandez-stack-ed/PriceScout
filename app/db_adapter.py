"""
Database Adapter Layer for PriceScout
Version: 1.0.0
Date: November 13, 2025

This module provides a compatibility layer between legacy sqlite3 code and SQLAlchemy ORM.
It maintains the same function signatures as database.py while using SQLAlchemy underneath.

Usage:
    # Drop-in replacement for old database.py imports
    from app.db_adapter import get_dates_for_theaters, get_data_for_trend_report
    
    # Works exactly like before
    dates = get_dates_for_theaters(['Theater 1', 'Theater 2'])
"""

import pandas as pd
from datetime import datetime
from contextlib import contextmanager
from sqlalchemy import text, and_, or_, func
from app.db_session import get_session, get_engine, legacy_db_connection
from app.db_models import (
    Company, User, ScrapeRun, Showing, Price, Film,
    OperatingHours, UnmatchedFilm, IgnoredFilm, UnmatchedTicketType
)
from app import config


# ============================================================================
# COMPATIBILITY LAYER: Legacy function implementations using SQLAlchemy
# ============================================================================

@contextmanager
def _get_db_connection():
    """
    Legacy compatibility: context manager for database connections.
    Now uses SQLAlchemy underneath.
    """
    with legacy_db_connection() as conn:
        yield conn


def init_database():
    """Initialize database schema (SQLAlchemy version)"""
    from app.db_session import init_database as sa_init_database
    sa_init_database()


def get_dates_for_theaters(theater_list):
    """Gets the unique dates that the selected theaters have records for."""
    if not theater_list:
        return []
    
    with get_session() as session:
        # Get company_id from config (set by main app)
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Showing.play_date).distinct()
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        query = query.filter(Showing.theater_name.in_(theater_list))
        query = query.order_by(Showing.play_date.desc())
        
        results = query.all()
        return [row[0] for row in results]


def get_common_films_for_theaters_dates(theater_list, date_list):
    """Gets films that are available for ALL selected theaters on AT LEAST ONE of the selected dates."""
    if not theater_list or not date_list:
        return []
    
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        # Subquery: distinct film_title, theater_name combinations
        subquery = session.query(
            Showing.film_title,
            Showing.theater_name
        ).distinct()
        
        if company_id:
            subquery = subquery.filter(Showing.company_id == company_id)
        
        subquery = subquery.filter(
            and_(
                Showing.theater_name.in_(theater_list),
                Showing.play_date.in_(date_list)
            )
        )
        
        # Group by film and count distinct theaters
        query = session.query(Showing.film_title).select_from(
            subquery.subquery()
        ).group_by(Showing.film_title).having(
            func.count(func.distinct(Showing.theater_name)) == len(theater_list)
        ).order_by(Showing.film_title)
        
        results = query.all()
        return [row[0] for row in results]


def get_theater_comparison_summary(theater_list, start_date, end_date):
    """
    Generates a summary DataFrame for comparing multiple theaters side-by-side.
    """
    if not theater_list:
        return pd.DataFrame()

    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)

        # Query for main stats
        query = session.query(
            Showing.theater_name,
            func.count(func.distinct(Showing.showing_id)).label('Total Showings'),
            func.count(func.distinct(Showing.film_title)).label('Unique Films'),
            func.group_concat(func.distinct(Showing.format)).label('all_formats')
        ).outerjoin(
            Price, Showing.showing_id == Price.showing_id
        ).filter(
            Showing.theater_name.in_(theater_list),
            Showing.play_date.between(start_date, end_date)
        )

        if company_id:
            query = query.filter(Showing.company_id == company_id)

        df = pd.read_sql(query.group_by(Showing.theater_name).statement, session.bind)

        # Query for average price
        avg_price_query = session.query(
            Showing.theater_name,
            func.avg(Price.price).label('Overall Avg. Price')
        ).join(
            Price, Showing.showing_id == Price.showing_id
        ).filter(
            Showing.theater_name.in_(theater_list),
            Showing.play_date.between(start_date, end_date),
            Price.ticket_type.in_(['Adult', 'Senior', 'Child'])
        )

        if company_id:
            avg_price_query = avg_price_query.filter(Showing.company_id == company_id)

        avg_price_df = pd.read_sql(avg_price_query.group_by(Showing.theater_name).statement, session.bind)

        if not df.empty and not avg_price_df.empty:
            df = pd.merge(df, avg_price_df, on='theater_name', how='left')

    if not df.empty and 'all_formats' in df.columns:
        def process_formats(format_str):
            if not format_str:
                return 0, "N/A"
            
            all_formats = set(part.strip() for item in format_str.split(',') for part in item.split(','))
            premium_formats = {f for f in all_formats if f != '2D'}
            num_premium = len(premium_formats)
            display_str = ", ".join(sorted(list(premium_formats))) if premium_formats else "N/A"
            return num_premium, display_str

        processed_formats_df = df['all_formats'].apply(lambda x: pd.Series(process_formats(x), index=['# Premium Formats', 'Premium Formats']))
        df = pd.concat([df, processed_formats_df], axis=1).drop(columns=['all_formats'])
        df['PLF Count'] = df['# Premium Formats']

    return df

from typing import Optional

def get_market_at_a_glance_data(theater_list: list[str], start_date: datetime.date, end_date: datetime.date, films: Optional[list[str]] = None) -> tuple[pd.DataFrame, Optional[datetime.date]]:
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

def calculate_operating_hours_from_showings(theater_list: list[str], start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    """
    [FALLBACK] Calculates operating hours by finding the min/max showtimes
    from the 'showings' table. This is used when no data is in the 'operating_hours' table.
    """
    from app.utils import normalize_time_string # Local import to avoid circular dependency
    if not theater_list:
        return pd.DataFrame()

    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(
            Showing.theater_name,
            Showing.play_date.label('scrape_date'),
            Showing.showtime
        ).filter(
            Showing.theater_name.in_(theater_list),
            Showing.play_date.between(start_date, end_date)
        )
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)

        df = pd.read_sql(query.statement, session.bind)

    if df.empty:
        return pd.DataFrame()

    # Convert showtime strings to datetime objects for correct min/max calculation
    df['time_obj'] = df['showtime'].apply(lambda x: datetime.strptime(normalize_time_string(x), "%I:%M%p").time())

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
    
def update_database_schema():
    """
    Legacy compatibility: Schema updates now handled by SQLAlchemy migrations.
    This is a no-op for backward compatibility.
    """
    print("[DB] Schema updates handled by SQLAlchemy. Use migrations for changes.")


# ============================================================================
# FILM MANAGEMENT: OMDB integration
# ============================================================================

def get_all_film_titles():
    """Get all unique film titles from showings"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Showing.film_title).distinct()
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        results = query.all()
        return [row[0] for row in results]


def get_film_metadata(film_title):
    """Get film metadata from films table"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Film).filter(Film.film_title == film_title)
        
        if company_id:
            query = query.filter(Film.company_id == company_id)
        
        film = query.first()
        
        if not film:
            return None
        
        # Convert to dict for backward compatibility
        return {
            'film_title': film.film_title,
            'imdb_id': film.imdb_id,
            'genre': film.genre,
            'mpaa_rating': film.mpaa_rating,
            'director': film.director,
            'actors': film.actors,
            'plot': film.plot,
            'poster_url': film.poster_url,
            'metascore': film.metascore,
            'imdb_rating': float(film.imdb_rating) if film.imdb_rating else None,
            'release_date': film.release_date,
            'domestic_gross': film.domestic_gross,
            'runtime': film.runtime,
            'opening_weekend_domestic': film.opening_weekend_domestic,
            'last_omdb_update': film.last_omdb_update
        }


def save_film_metadata(film_data):
    """Save or update film metadata"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set in config")
        
        # Check if film exists
        film = session.query(Film).filter(
            and_(
                Film.company_id == company_id,
                Film.film_title == film_data['film_title']
            )
        ).first()
        
        if film:
            # Update existing
            for key, value in film_data.items():
                if hasattr(film, key):
                    setattr(film, key, value)
            film.last_omdb_update = datetime.utcnow()
        else:
            # Create new
            film = Film(
                company_id=company_id,
                last_omdb_update=datetime.utcnow(),
                **film_data
            )
            session.add(film)


def get_unmatched_films():
    """Get list of films that couldn't be matched to OMDB"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(UnmatchedFilm)
        
        if company_id:
            query = query.filter(UnmatchedFilm.company_id == company_id)
        
        results = query.all()
        return [{'film_title': row.film_title, 'first_seen': row.first_seen} for row in results]


def add_unmatched_film(film_title):
    """Add or update unmatched film"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set in config")
        
        # Check if exists
        film = session.query(UnmatchedFilm).filter(
            and_(
                UnmatchedFilm.company_id == company_id,
                UnmatchedFilm.film_title == film_title
            )
        ).first()
        
        if film:
            # Update occurrence
            film.last_seen = datetime.utcnow()
            film.occurrence_count += 1
        else:
            # Create new
            film = UnmatchedFilm(
                company_id=company_id,
                film_title=film_title,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                occurrence_count=1
            )
            session.add(film)


def get_ignored_films():
    """Get list of films that are ignored"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(IgnoredFilm.film_title)
        
        if company_id:
            query = query.filter(IgnoredFilm.company_id == company_id)
        
        results = query.all()
        return [row[0] for row in results]


def add_ignored_film(film_title, reason=None):
    """Add film to ignored list"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set in config")
        
        # Check if exists
        existing = session.query(IgnoredFilm).filter(
            and_(
                IgnoredFilm.company_id == company_id,
                IgnoredFilm.film_title == film_title
            )
        ).first()
        
        if not existing:
            film = IgnoredFilm(
                company_id=company_id,
                film_title=film_title,
                reason=reason
            )
            session.add(film)


def remove_ignored_film(film_title):
    """Remove film from ignored list"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(IgnoredFilm).filter(
            IgnoredFilm.film_title == film_title
        )
        
        if company_id:
            query = query.filter(IgnoredFilm.company_id == company_id)
        
        film = query.first()
        if film:
            session.delete(film)


# ============================================================================
# SCRAPE RUN MANAGEMENT
# ============================================================================

def create_scrape_run(mode, context=None, user_id=None):
    """Create a new scrape run and return its ID"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set in config")
        
        # Get current user ID from session state if not provided
        if user_id is None:
            try:
                import streamlit as st
                if hasattr(st, 'session_state') and 'user' in st.session_state:
                    user_dict = st.session_state.user
                    # Handle both dict formats: {'id': ...} or {'user_id': ...}
                    user_id = user_dict.get('user_id') or user_dict.get('id')
                    print(f"  [DB] Got user_id from session: {user_id}")
            except Exception as e:
                print(f"  [DB] Could not get user_id from session: {e}")
                user_id = None
        
        print(f"  [DB] Creating scrape run - mode: {mode}, user_id: {user_id}, context: {context}")
        
        run = ScrapeRun(
            company_id=company_id,
            run_timestamp=datetime.utcnow(),
            mode=mode,
            user_id=user_id,
            status='running'
        )
        session.add(run)
        session.flush()  # Get the ID before commit
        print(f"  [DB] Created scrape run with ID: {run.run_id}")
        return run.run_id


def update_scrape_run_status(run_id, status, records_scraped=0, error_message=None):
    """Update scrape run status"""
    with get_session() as session:
        run = session.query(ScrapeRun).filter(ScrapeRun.run_id == run_id).first()
        if run:
            run.status = status
            run.records_scraped = records_scraped
            run.error_message = error_message


# ============================================================================
# RAW SQL SUPPORT: For complex queries not yet migrated
# ============================================================================

def execute_raw_sql(query, params=None):
    """
    Execute raw SQL query and return DataFrame.
    Use this for complex queries during migration period.
    """
    with get_session() as session:
        if params:
            result = session.execute(text(query), params)
        else:
            result = session.execute(text(query))
        
        # Try to convert to DataFrame if possible
        try:
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        except:
            return result


def execute_raw_sql_pandas(query, params=None):
    """
    Execute raw SQL and return pandas DataFrame.
    Maintains compatibility with pd.read_sql_query usage.
    """
    engine = get_engine()
    return pd.read_sql_query(text(query), engine, params=params)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_all_theaters():
    """Get list of all theater names"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Showing.theater_name).distinct()
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        query = query.order_by(Showing.theater_name)
        
        results = query.all()
        return [row[0] for row in results]


def get_all_markets():
    """Get list of all market names"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(OperatingHours.market).distinct()
        
        if company_id:
            query = query.filter(OperatingHours.company_id == company_id)
        
        query = query.filter(OperatingHours.market.isnot(None))
        query = query.order_by(OperatingHours.market)
        
        results = query.all()
        return [row[0] for row in results]


def get_theaters_by_market(market):
    """Get theaters in a specific market"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(OperatingHours.theater_name).distinct()
        
        if company_id:
            query = query.filter(OperatingHours.company_id == company_id)
        
        query = query.filter(OperatingHours.market == market)
        query = query.order_by(OperatingHours.theater_name)
        
        results = query.all()
        return [row[0] for row in results]


# ============================================================================
# MIGRATION HELPERS: Functions to ease transition
# ============================================================================

def set_current_company(company_name):
    """
    Set the current company context for all database operations.
    This should be called at app startup after user login.
    """
    with get_session() as session:
        company = session.query(Company).filter(Company.company_name == company_name).first()
        
        if company:
            config.CURRENT_COMPANY_ID = company.company_id
            print(f"[DB] Set current company: {company_name} (ID: {company.company_id})")
        else:
            # Create company if it doesn't exist
            company = Company(company_name=company_name, is_active=True)
            session.add(company)
            session.flush()
            config.CURRENT_COMPANY_ID = company.company_id
            print(f"[DB] Created company: {company_name} (ID: {company.company_id})")


def get_current_company():
    """Get the current company context"""
    company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
    if not company_id:
        return None
    
    with get_session() as session:
        company = session.query(Company).filter(Company.company_id == company_id).first()
        return company.company_name if company else None


# Expose legacy connection manager for backward compatibility
get_db_connection = _get_db_connection


# ============================================================================
# SCRAPING: Core functions for saving scraped data
# ============================================================================

def save_prices(run_id: int, df: pd.DataFrame):
    """Save scraped prices to database"""
    if 'play_date' not in df.columns or df['play_date'].isnull().all():
        print("  [DB] [ERROR] save_prices called with missing 'play_date'. Aborting.")
        return
    
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set")
        
        # Get showing IDs for all prices
        for _, row in df.iterrows():
            showing = session.query(Showing).filter(
                and_(
                    Showing.company_id == company_id,
                    Showing.play_date == row['play_date'],
                    Showing.theater_name == row['Theater Name'],
                    Showing.film_title == row['Film Title'],
                    Showing.showtime == row['Showtime'],
                    Showing.format == row['Format']
                )
            ).first()
            
            if showing:
                try:
                    price_value = float(str(row['Price']).replace('$', ''))
                    price = Price(
                        company_id=company_id,
                        run_id=run_id,
                        showing_id=showing.showing_id,
                        ticket_type=row['Ticket Type'],
                        price=price_value,
                        capacity=row.get('Capacity'),
                        play_date=row['play_date']
                    )
                    session.add(price)
                except (ValueError, KeyError) as e:
                    print(f"  [DB] [WARN] Skipping price: {e}")
        
        session.flush()
        print(f"  [DB] Saved prices for run ID {run_id}.")


def upsert_showings(all_showings, play_date):
    """Insert or update showings in database"""
    import datetime

    # Ensure play_date is a date object, not a string
    if isinstance(play_date, str):
        play_date = datetime.datetime.strptime(play_date, '%Y-%m-%d').date()
    elif isinstance(play_date, datetime.datetime):
        play_date = play_date.date()

    if not all_showings:
        print(f"  [DB] [WARN] No showings to upsert")
        return

    try:
        with get_session() as session:
            company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
            if not company_id:
                raise ValueError("CURRENT_COMPANY_ID not set")
            
            showing_count = 0
            for theater_name, showings in all_showings.items():
                print(f"  [DB] Processing {len(showings)} showings for {theater_name}")
                for showing_data in showings:
                    # Remove play_date from showing_data if present (we pass it separately)
                    showing_data.pop('play_date', None)

                    # Check if showing exists
                    existing = session.query(Showing).filter(
                        and_(
                            Showing.company_id == company_id,
                            Showing.play_date == play_date,
                            Showing.theater_name == theater_name,
                            Showing.film_title == showing_data['film_title'],
                            Showing.showtime == showing_data['showtime'],
                            Showing.format == showing_data['format']
                        )
                    ).first()

                    if not existing:
                        showing = Showing(
                            company_id=company_id,
                            play_date=play_date,
                            theater_name=theater_name,
                            film_title=showing_data['film_title'],
                            showtime=showing_data['showtime'],
                            format=showing_data['format'],
                            daypart=showing_data['daypart'],
                            is_plf=showing_data.get('is_plf', False),
                            ticket_url=showing_data.get('ticket_url')
                        )
                        session.add(showing)
                        showing_count += 1

            try:
                session.flush()
                print(f"  [DB] Upserted {showing_count} showings for {play_date.strftime('%Y-%m-%d')}.")
            except Exception as e:
                # Handle duplicate constraint errors gracefully
                print(f"  [DB] [WARN] Some showings may already exist: {e}")
                session.rollback()
                # Try inserting one at a time to skip duplicates
                for theater_name, showings in all_showings.items():
                    for showing_data in showings:
                        showing_data.pop('play_date', None)
                        try:
                            existing = session.query(Showing).filter(
                                and_(
                                    Showing.company_id == company_id,
                                    Showing.play_date == play_date,
                                    Showing.theater_name == theater_name,
                                    Showing.film_title == showing_data['film_title'],
                                    Showing.showtime == showing_data['showtime'],
                                    Showing.format == showing_data['format']
                                )
                            ).first()
                            if not existing:
                                showing = Showing(
                                    company_id=company_id,
                                    play_date=play_date,
                                    theater_name=theater_name,
                                    film_title=showing_data['film_title'],
                                    showtime=showing_data['showtime'],
                                    format=showing_data['format'],
                                    daypart=showing_data['daypart'],
                                    is_plf=showing_data.get('is_plf', False),
                                    ticket_url=showing_data.get('ticket_url')
                                )
                                session.add(showing)
                                session.commit()
                        except:
                            session.rollback()
                print(f"  [DB] Finished upserting showings for {play_date.strftime('%Y-%m-%d')} (some may have been skipped as duplicates).")
    except Exception as e:
        print(f"  [DB] [ERROR] Failed to upsert showings: {e}")
        import traceback
        traceback.print_exc()
        raise


# ============================================================================
# HISTORICAL DATA QUERIES
# ============================================================================

def get_scrape_runs():
    """Get all scrape runs"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(ScrapeRun).order_by(ScrapeRun.run_timestamp.desc())
        
        if company_id:
            query = query.filter(ScrapeRun.company_id == company_id)
        
        runs = query.all()
        return [{
            'run_id': r.run_id,
            'run_timestamp': r.run_timestamp,
            'mode': r.mode,
            'status': r.status,
            'records_scraped': r.records_scraped
        } for r in runs]


def get_prices_for_run(run_id):
    """Get all prices for a specific scrape run"""
    with get_session() as session:
        query = session.query(
            Price.price,
            Price.ticket_type,
            Showing.play_date,
            Showing.theater_name,
            Showing.film_title,
            Showing.showtime,
            Showing.format,
            Showing.daypart
        ).join(
            Showing, Price.showing_id == Showing.showing_id
        ).filter(Price.run_id == run_id)
        
        df = pd.read_sql(query.statement, session.bind)
        return df


def query_historical_data(start_date, end_date, theaters=None, films=None, genres=None, ratings=None):
    """Query historical price data with filters"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(
            Showing.play_date,
            Showing.theater_name,
            Showing.film_title,
            Showing.showtime,
            Showing.format,
            Showing.daypart,
            Price.ticket_type,
            Price.price,
            Film.genre,
            Film.mpaa_rating
        ).join(
            Price, Price.showing_id == Showing.showing_id
        ).outerjoin(
            Film, and_(
                Film.film_title == Showing.film_title,
                Film.company_id == Showing.company_id
            )
        )
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        query = query.filter(
            and_(
                Showing.play_date >= start_date,
                Showing.play_date <= end_date
            )
        )
        
        if theaters:
            query = query.filter(Showing.theater_name.in_(theaters))
        
        if films:
            query = query.filter(Showing.film_title.in_(films))
        
        if genres:
            query = query.filter(Film.genre.in_(genres))
        
        if ratings:
            query = query.filter(Film.mpaa_rating.in_(ratings))
        
        df = pd.read_sql(query.statement, session.bind)
        return df


# ============================================================================
# UTILITY QUERIES
# ============================================================================

def get_unique_column_values(column_name):
    """Get unique values for a column"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        if column_name == 'theater_name':
            query = session.query(Showing.theater_name).distinct()
            if company_id:
                query = query.filter(Showing.company_id == company_id)
        elif column_name == 'film_title':
            query = session.query(Showing.film_title).distinct()
            if company_id:
                query = query.filter(Showing.company_id == company_id)
        else:
            return []
        
        results = query.all()
        return sorted([r[0] for r in results if r[0]])


def get_dates_for_theater(theater_name):
    """Get all dates with data for a theater"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Showing.play_date).distinct()
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        query = query.filter(Showing.theater_name == theater_name)
        query = query.order_by(Showing.play_date.desc())
        
        results = query.all()
        return [r[0] for r in results]


def get_films_for_theater_date(theater_name, date):
    """Get all films for a theater on a specific date"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Showing.film_title).distinct()
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        query = query.filter(
            and_(
                Showing.theater_name == theater_name,
                Showing.play_date == date
            )
        )
        query = query.order_by(Showing.film_title)
        
        results = query.all()
        return [r[0] for r in results]


def get_final_prices(theater_name, date, film_title, daypart="All"):
    """Get prices for a specific showing"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(
            Showing.showtime,
            Showing.format,
            Price.ticket_type,
            Price.price
        ).join(
            Price, Price.showing_id == Showing.showing_id
        )
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        filters = [
            Showing.theater_name == theater_name,
            Showing.play_date == date,
            Showing.film_title == film_title
        ]
        
        if daypart != "All":
            filters.append(Showing.daypart == daypart)
        
        query = query.filter(and_(*filters))
        
        df = pd.read_sql(query.statement, session.bind)
        return df


# ============================================================================
# OPERATING HOURS MANAGEMENT
# ============================================================================

def save_operating_hours(run_id, operating_hours_data, conn=None):
    """Save operating hours data (compatibility wrapper)"""
    # conn parameter ignored in SQLAlchemy version
    save_full_operating_hours_run(operating_hours_data, f"run_{run_id}")


def save_full_operating_hours_run(operating_hours_data, context):
    """Save complete operating hours data"""
    if not operating_hours_data:
        return
    
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set")
        
        # Handle both list format (from utils.py) and dict format (legacy)
        if isinstance(operating_hours_data, list):
            # List format: [{"Date": "...", "Theater": "...", "Market": "...", "Showtime Range": "...", "Duration (hrs)": ...}]
            for hours_record in operating_hours_data:
                # Parse showtime range to get open_time and close_time
                showtime_range = hours_record.get('Showtime Range', '')
                if showtime_range and showtime_range != "No valid showtimes found":
                    # Format: "9:00am - 11:00pm" or similar
                    if ' - ' in showtime_range:
                        open_time, close_time = showtime_range.split(' - ')
                    else:
                        open_time = close_time = None
                else:
                    open_time = close_time = None
                
                # Parse date
                scrape_date = datetime.strptime(hours_record['Date'], '%Y-%m-%d').date()
                
                # Get duration from record
                duration_hours = hours_record.get('Duration (hrs)', 0.0)
                
                op_hours = OperatingHours(
                    company_id=company_id,
                    theater_name=hours_record['Theater'],
                    market=hours_record.get('Market'),
                    scrape_date=scrape_date,
                    open_time=open_time,
                    close_time=close_time,
                    duration_hours=duration_hours
                )
                session.add(op_hours)
        else:
            # Dict format: {theater_name: [{...}, {...}]}
            for theater_name, hours_list in operating_hours_data.items():
                for hours in hours_list:
                    op_hours = OperatingHours(
                        company_id=company_id,
                        theater_name=theater_name,
                        market=hours.get('market'),
                        scrape_date=hours['scrape_date'],
                        open_time=hours.get('opens_at') or hours.get('open_time'),
                        close_time=hours.get('closes_at') or hours.get('close_time'),
                        duration_hours=hours.get('duration_hours')
                    )
                    session.add(op_hours)
        
        session.flush()
        print(f"  [DB] Saved operating hours for context: {context}")


def delete_operating_hours(theater_names, scrape_date, conn=None):
    """Delete operating hours for theaters on date"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(OperatingHours).filter(
            OperatingHours.scrape_date == scrape_date
        )
        
        if company_id:
            query = query.filter(OperatingHours.company_id == company_id)
        
        if theater_names:
            query = query.filter(OperatingHours.theater_name.in_(theater_names))
        
        count = query.delete()
        print(f"  [DB] Deleted {count} operating hours records")


def get_operating_hours_for_theaters_and_dates(theater_list, start_date, end_date):
    """Get operating hours for theaters in date range"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(OperatingHours)
        
        if company_id:
            query = query.filter(OperatingHours.company_id == company_id)
        
        query = query.filter(
            and_(
                OperatingHours.theater_name.in_(theater_list),
                OperatingHours.scrape_date >= start_date,
                OperatingHours.scrape_date <= end_date
            )
        )
        
        df = pd.read_sql(query.statement, session.bind)
        return df


def get_all_op_hours_dates(theater_list):
    """Get all dates with operating hours data"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(OperatingHours.scrape_date).distinct()
        
        if company_id:
            query = query.filter(OperatingHours.company_id == company_id)
        
        if theater_list:
            query = query.filter(OperatingHours.theater_name.in_(theater_list))
        
        query = query.order_by(OperatingHours.scrape_date.desc())
        
        results = query.all()
        return [r[0] for r in results]


# ============================================================================
# FILM METADATA ENRICHMENT
# ============================================================================

def upsert_film_details(film_data: dict):
    """Save or update film metadata"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set")
        
        film = session.query(Film).filter(
            and_(
                Film.company_id == company_id,
                Film.film_title == film_data['film_title']
            )
        ).first()
        
        if film:
            # Update existing
            for key, value in film_data.items():
                if hasattr(film, key) and key != 'film_id':
                    setattr(film, key, value)
            film.last_omdb_update = datetime.utcnow()
        else:
            # Create new
            film = Film(
                company_id=company_id,
                last_omdb_update=datetime.utcnow(),
                **{k: v for k, v in film_data.items() if k != 'film_id'}
            )
            session.add(film)
        
        session.flush()


def check_film_exists(film_title: str) -> bool:
    """Check if film metadata exists"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Film).filter(Film.film_title == film_title)
        
        if company_id:
            query = query.filter(Film.company_id == company_id)
        
        return query.first() is not None


def get_film_details(film_title: str) -> dict | None:
    """Get film metadata"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Film).filter(Film.film_title == film_title)
        
        if company_id:
            query = query.filter(Film.company_id == company_id)
        
        film = query.first()
        
        if not film:
            return None
        
        return {
            'film_title': film.film_title,
            'imdb_id': film.imdb_id,
            'genre': film.genre,
            'mpaa_rating': film.mpaa_rating,
            'director': film.director,
            'actors': film.actors,
            'plot': film.plot,
            'poster_url': film.poster_url,
            'metascore': film.metascore,
            'imdb_rating': float(film.imdb_rating) if film.imdb_rating else None,
            'release_date': film.release_date,
            'domestic_gross': film.domestic_gross,
            'runtime': film.runtime,
            'opening_weekend_domestic': film.opening_weekend_domestic,
            'last_omdb_update': film.last_omdb_update
        }


def get_all_unique_genres() -> list[str]:
    """Get all unique genres"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Film.genre).distinct()
        
        if company_id:
            query = query.filter(Film.company_id == company_id)
        
        query = query.filter(Film.genre.isnot(None))
        
        results = query.all()
        return sorted([r[0] for r in results if r[0]])


def get_all_unique_ratings() -> list[str]:
    """Get all unique MPAA ratings"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Film.mpaa_rating).distinct()
        
        if company_id:
            query = query.filter(Film.company_id == company_id)
        
        query = query.filter(Film.mpaa_rating.isnot(None))
        
        results = query.all()
        return sorted([r[0] for r in results if r[0]])


def log_unmatched_film(film_title: str):
    """Log film that couldn't be matched"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set")
        
        film = session.query(UnmatchedFilm).filter(
            and_(
                UnmatchedFilm.company_id == company_id,
                UnmatchedFilm.film_title == film_title
            )
        ).first()
        
        if film:
            film.last_seen = datetime.utcnow()
            film.occurrence_count += 1
        else:
            film = UnmatchedFilm(
                company_id=company_id,
                film_title=film_title,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                occurrence_count=1
            )
            session.add(film)
        
        session.flush()


def delete_unmatched_film(film_title: str):
    """Remove film from unmatched list"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(UnmatchedFilm).filter(
            UnmatchedFilm.film_title == film_title
        )
        
        if company_id:
            query = query.filter(UnmatchedFilm.company_id == company_id)
        
        film = query.first()
        if film:
            session.delete(film)
            session.flush()


# ============================================================================
# TICKET TYPE MANAGEMENT
# ============================================================================

def get_ticket_type_usage_counts() -> pd.DataFrame:
    """Get usage counts for each ticket type"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(
            Price.ticket_type,
            func.count(Price.price_id).label('count')
        ).group_by(Price.ticket_type)
        
        if company_id:
            query = query.filter(Price.company_id == company_id)
        
        query = query.order_by(func.count(Price.price_id).desc())
        
        df = pd.read_sql(query.statement, session.bind)
        return df


def log_unmatched_ticket_type(original_description: str, unmatched_part: str, showing_details: dict | None = None):
    """Log unmatched ticket type"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        if not company_id:
            raise ValueError("CURRENT_COMPANY_ID not set")
        
        ticket_type = UnmatchedTicketType(
            company_id=company_id,
            original_description=original_description,
            unmatched_part=unmatched_part,
            first_seen=datetime.utcnow()
        )
        
        if showing_details:
            ticket_type.theater_name = showing_details.get('theater_name')
            ticket_type.film_title = showing_details.get('film_title')
            ticket_type.showtime = showing_details.get('showtime')
        
        session.add(ticket_type)
        session.flush()


def get_unmatched_ticket_types() -> pd.DataFrame:
    """Get all unmatched ticket types"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(UnmatchedTicketType)
        
        if company_id:
            query = query.filter(UnmatchedTicketType.company_id == company_id)
        
        df = pd.read_sql(query.statement, session.bind)
        return df


def delete_unmatched_ticket_type(unmatched_id: int):
    """Delete unmatched ticket type"""
    with get_session() as session:
        ticket_type = session.query(UnmatchedTicketType).filter(
            UnmatchedTicketType.unmatched_id == unmatched_id
        ).first()
        
        if ticket_type:
            session.delete(ticket_type)
            session.flush()


# ============================================================================
# ADDITIONAL UTILITY FUNCTIONS
# ============================================================================

def get_films_missing_release_date() -> list[str]:
    """Get films without release dates"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Film.film_title).filter(
            or_(Film.release_date.is_(None), Film.release_date == '')
        )
        
        if company_id:
            query = query.filter(Film.company_id == company_id)
        
        results = query.all()
        return [r[0] for r in results]


def get_films_missing_metadata() -> list[str]:
    """Get films without complete metadata"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        # Get films in showings that don't have metadata
        query = session.query(Showing.film_title).distinct().outerjoin(
            Film, and_(
                Film.film_title == Showing.film_title,
                Film.company_id == Showing.company_id
            )
        ).filter(Film.film_id.is_(None))
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        results = query.all()
        return [r[0] for r in results]


def get_all_films_for_enrichment(as_df=False):
    """Get all films for metadata enrichment"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Film.film_title)
        
        if company_id:
            query = query.filter(Film.company_id == company_id)
        
        if as_df:
            return pd.read_sql(query.statement, session.bind)
        else:
            results = query.all()
            return [r[0] for r in results]


# Stub functions for complex queries - can be implemented as needed
def get_available_films(theaters):
    """Get films available at theaters"""
    return get_common_films_for_theaters_dates(theaters, get_dates_for_theaters(theaters))


def get_available_dates(theaters, films):
    """Get dates with data for theaters and films"""
    dates = get_dates_for_theaters(theaters)
    return dates


def get_available_dayparts(theaters, films, start_date, end_date):
    """Get available dayparts"""
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
        
        query = session.query(Showing.daypart).distinct()
        
        if company_id:
            query = query.filter(Showing.company_id == company_id)
        
        query = query.filter(
            and_(
                Showing.theater_name.in_(theaters),
                Showing.film_title.in_(films),
                Showing.play_date >= start_date,
                Showing.play_date <= end_date
            )
        )
        
        results = query.all()
        return [r[0] for r in results if r[0]]


def get_theaters_with_data(data_type):
    """Get theaters with specific data type"""
    if data_type == 'operating_hours':
        with get_session() as session:
            company_id = getattr(config, 'CURRENT_COMPANY_ID', None)
            
            query = session.query(OperatingHours.theater_name).distinct()
            
            if company_id:
                query = query.filter(OperatingHours.company_id == company_id)
            
            results = query.all()
            return [r[0] for r in results]
    else:
        return get_all_theaters()


def get_common_dates_for_theaters(theaters, data_type):
    """Get dates common to all theaters"""
    return get_dates_for_theaters(theaters)


def backfill_play_dates():
    """Legacy migration function - no-op in PostgreSQL"""
    pass


def migrate_schema():
    """Legacy migration function - no-op in PostgreSQL"""
    return "Schema managed by SQLAlchemy migrations"


def consolidate_ticket_types() -> int:
    """Consolidate ticket type variations"""
    # TODO: Implement ticket type consolidation
    return 0
