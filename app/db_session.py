"""
SQLAlchemy Session Management for PriceScout
Version: 1.0.0
Date: November 13, 2025

This module handles database connections and session management.
Supports SQLite (local), PostgreSQL, and Azure SQL (MSSQL) with automatic detection.

Usage:
    from app.db_session import get_session, get_engine
    
    # Context manager (recommended)
    with get_session() as session:
        users = session.query(User).all()
    
    # Manual session management
    session = get_session()
    try:
        users = session.query(User).all()
        session.commit()
    finally:
        session.close()
"""

import os
from urllib.parse import urlparse, quote_plus
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool, NullPool
from app import config

# Global engine and session factory
_engine = None
_SessionFactory = None


def _detect_database_type():
    """
    Detect which database to use based on configuration.
    Returns: 'postgresql', 'mssql', or 'sqlite'
    """
    # Explicit override if provided
    explicit = os.getenv('DB_TYPE')
    if explicit in {'postgresql', 'postgres', 'mssql', 'sqlite'}:
        return 'postgresql' if explicit in {'postgresql', 'postgres'} else explicit

    db_url = os.getenv('DATABASE_URL')
    if db_url:
        try:
            scheme = urlparse(db_url).scheme.lower()
            if scheme.startswith('postgres'):
                return 'postgresql'
            if scheme.startswith('mssql'):
                return 'mssql'
        except Exception:
            # If parsing fails, fall back to heuristics below
            pass

    # Default to SQLite for local development
    return 'sqlite'


def _get_database_url():
    """
    Get the appropriate database URL based on environment.
    Returns: SQLAlchemy connection string
    """
    db_type = _detect_database_type()
    
    if db_type == 'postgresql':
        # Try environment variable first
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            # Fix Azure's postgres:// prefix (should be postgresql://)
            if db_url.startswith('postgres://'):
                db_url = db_url.replace('postgres://', 'postgresql://', 1)
            return db_url
        
        # Try Azure Key Vault (requires azure_secrets.py)
        try:
            from app.azure_secrets import get_secret
            # Prefer generic secret name if present
            db_url = get_secret('DATABASE-URL') or get_secret('postgresql-connection-string')
            if db_url:
                return db_url
        except (ImportError, Exception) as e:
            print(f"Warning: Could not load PostgreSQL credentials from Key Vault: {e}")
        
        # Fallback: construct from components
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        database = os.getenv('POSTGRES_DB', 'pricescout_db')
        user = os.getenv('POSTGRES_USER', 'pricescout_app')
        password = os.getenv('POSTGRES_PASSWORD', '')
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode=prefer"
    elif db_type == 'mssql':
        # Try environment variable first
        db_url = os.getenv('DATABASE_URL')
        if db_url and urlparse(db_url).scheme.lower().startswith('mssql'):
            return db_url

        # Try Azure Key Vault (generic name recommended)
        try:
            from app.azure_secrets import get_secret
            db_url = get_secret('DATABASE-URL') or get_secret('mssql-connection-string')
            if db_url:
                return db_url
        except (ImportError, Exception) as e:
            print(f"Warning: Could not load MSSQL credentials from Key Vault: {e}")

        # Fallback: construct URL for Azure SQL / MSSQL with ODBC Driver 18
        host = os.getenv('SQLSERVER_HOST', 'localhost')
        port = os.getenv('SQLSERVER_PORT', '1433')
        database = os.getenv('SQLSERVER_DATABASE', 'pricescout_db')
        user = os.getenv('SQLSERVER_USER', 'pricescout_app')
        password = os.getenv('SQLSERVER_PASSWORD', '')
        driver = os.getenv('SQLSERVER_DRIVER', 'ODBC Driver 18 for SQL Server')

        user_q = quote_plus(user)
        pass_q = quote_plus(password)
        driver_q = driver.replace(' ', '+')
        return (
            f"mssql+pyodbc://{user_q}:{pass_q}@{host}:{port}/{database}"
            f"?driver={driver_q}&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30"
        )
    
    else:  # SQLite
        # Use config.DB_FILE if set (per-company database)
        if config.DB_FILE:
            db_path = config.DB_FILE
        else:
            # Fallback to default database location
            from app.config import PROJECT_DIR
            db_path = os.path.join(PROJECT_DIR, "pricescout.db")
        
        return f"sqlite:///{db_path}"


def get_engine(echo=False):
    """
    Get or create the SQLAlchemy engine.
    
    Args:
        echo (bool): If True, log all SQL statements (for debugging)
    
    Returns:
        sqlalchemy.engine.Engine
    """
    global _engine
    
    if _engine is None:
        db_url = _get_database_url()
        db_type = _detect_database_type()
        
        # Configure engine based on database type
        if db_type == 'postgresql':
            _engine = create_engine(
                db_url,
                echo=echo,
                pool_size=10,              # Connection pool size
                max_overflow=20,           # Max overflow connections
                pool_pre_ping=True,        # Verify connections before using
                pool_recycle=3600,         # Recycle connections after 1 hour
                connect_args={
                    'connect_timeout': 10,
                    'application_name': 'PriceScout'
                }
            )
        elif db_type == 'mssql':
            _engine = create_engine(
                db_url,
                echo=echo,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                fast_executemany=True
            )
        else:  # SQLite
            _engine = create_engine(
                db_url,
                echo=echo,
                connect_args={
                    'check_same_thread': False,  # Allow multi-threaded access
                    'timeout': 30                 # Longer timeout for concurrent writes
                },
                poolclass=StaticPool           # Single connection for SQLite
            )
            
            # Enable foreign keys for SQLite
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        
        print(f"[DB] Initialized {db_type.upper()} engine: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    
    return _engine


def get_session_factory():
    """
    Get or create the session factory.
    
    Returns:
        sqlalchemy.orm.sessionmaker
    """
    global _SessionFactory
    
    if _SessionFactory is None:
        engine = get_engine()
        _SessionFactory = scoped_session(
            sessionmaker(
                bind=engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False  # Prevent lazy-load errors after commit
            )
        )
    
    return _SessionFactory


@contextmanager
def get_session():
    """
    Context manager for database sessions with automatic cleanup.
    
    Usage:
        with get_session() as session:
            users = session.query(User).all()
            # Automatic commit on success, rollback on exception
    
    Yields:
        sqlalchemy.orm.Session
    """
    SessionFactory = get_session_factory()
    session = SessionFactory()
    
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[DB] Session error: {e}")
        raise
    finally:
        session.close()


def get_scoped_session():
    """
    Get a thread-local scoped session (for Streamlit multi-page apps).
    
    Usage:
        session = get_scoped_session()
        users = session.query(User).all()
        # Remember to call session.remove() when done
    
    Returns:
        sqlalchemy.orm.scoped_session
    """
    return get_session_factory()


def init_database():
    """
    Initialize database schema (create all tables if they don't exist).
    Safe to call multiple times.
    """
    from app.db_models import Base, create_all_tables
    
    engine = get_engine()
    create_all_tables(engine)
    print("[DB] Database schema initialized")


def reset_database():
    """
    Drop and recreate all tables (for testing only!).
    WARNING: This will DELETE ALL DATA.
    """
    from app.db_models import Base, drop_all_tables, create_all_tables
    
    engine = get_engine()
    
    # Safety check
    db_url = _get_database_url()
    if 'prod' in db_url or 'production' in db_url:
        raise RuntimeError("Cannot reset production database!")
    
    confirm = input("⚠ WARNING: This will DELETE ALL DATA. Type 'DELETE' to confirm: ")
    if confirm != 'DELETE':
        print("Database reset cancelled.")
        return
    
    drop_all_tables(engine)
    create_all_tables(engine)
    print("[DB] Database reset complete")


def close_engine():
    """Close the database engine and cleanup connections"""
    global _engine, _SessionFactory
    
    if _SessionFactory:
        _SessionFactory.remove()
        _SessionFactory = None
    
    if _engine:
        _engine.dispose()
        _engine = None
        print("[DB] Database engine closed")


# ============================================================================
# BACKWARD COMPATIBILITY: Legacy database.py integration
# ============================================================================

def get_legacy_connection():
    """
    Get a raw database connection for legacy code that uses sqlite3 directly.
    This is a temporary compatibility layer during migration.
    
    Returns:
        For SQLite: sqlite3.Connection
        For PostgreSQL: psycopg2.connection (via SQLAlchemy)
    """
    engine = get_engine()
    return engine.raw_connection()


@contextmanager
def legacy_db_connection():
    """
    Context manager for legacy database connections.
    Mimics the old _get_db_connection() behavior.
    
    Usage:
        with legacy_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
    """
    conn = get_legacy_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================================
# TESTING UTILITIES
# ============================================================================

def is_using_postgresql():
    """Check if currently using PostgreSQL"""
    return _detect_database_type() == 'postgresql'


def is_using_mssql():
    """Check if currently using MSSQL (Azure SQL)"""
    return _detect_database_type() == 'mssql'


def is_using_sqlite():
    """Check if currently using SQLite"""
    return _detect_database_type() == 'sqlite'


def get_current_database_info():
    """Get information about the current database connection"""
    db_type = _detect_database_type()
    db_url = _get_database_url()
    
    # Mask password in URL
    if '@' in db_url:
        parts = db_url.split('@')
        user_pass = parts[0].split('//')[-1]
        if ':' in user_pass:
            user, _ = user_pass.rsplit(':', 1)
            masked_url = db_url.replace(user_pass, f"{user}:***")
        else:
            masked_url = db_url
    else:
        masked_url = db_url
    
    return {
        'type': db_type,
        'url': masked_url,
        'engine_active': _engine is not None,
        'session_factory_active': _SessionFactory is not None
    }


if __name__ == "__main__":
    # Test database connection
    print("="*60)
    print("PriceScout Database Connection Test")
    print("="*60)
    
    info = get_current_database_info()
    print(f"\nDatabase Type: {info['type'].upper()}")
    print(f"Database URL:  {info['url']}")
    
    try:
        # Test connection
        engine = get_engine(echo=False)
        
        # Try to query something
        with get_session() as session:
            from sqlalchemy import text
            result = session.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            if row and row[0] == 1:
                print("\n✓ Database connection successful!")
            else:
                print("\n✗ Unexpected query result")
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
    finally:
        close_engine()
    
    print("="*60)
