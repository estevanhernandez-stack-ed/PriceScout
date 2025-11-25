# SQLAlchemy Migration Guide

**Status**: Phase 1 - Task 2 Complete  
**Date**: November 13, 2025  
**Version**: 1.0.0

## Overview

This guide explains how to migrate from direct `sqlite3` usage to SQLAlchemy ORM while maintaining backward compatibility.

## New Files Created

### 1. `app/db_models.py`
SQLAlchemy ORM model definitions for all database tables:
- **Company**: Multi-tenant company isolation
- **User**: Authentication and RBAC
- **AuditLog**: Security tracking
- **ScrapeRun**: Data collection sessions
- **Showing**: Theater screenings
- **Price**: Ticket pricing
- **Film**: Movie metadata
- **OperatingHours**: Theater schedules
- **UnmatchedFilm, IgnoredFilm, UnmatchedTicketType**: Error tracking

**Features**:
- Supports both SQLite and PostgreSQL
- Relationships between models
- JSON field helpers (settings_dict, allowed_modes_list)
- Indexes for performance
- Constraints for data integrity

### 2. `app/db_session.py`
Session management and database connection handling:
- **get_engine()**: Get/create SQLAlchemy engine
- **get_session()**: Context manager for transactions
- **init_database()**: Create all tables
- **_detect_database_type()**: Auto-detect SQLite vs PostgreSQL
- **_get_database_url()**: Build connection string from environment

**Environment Detection**:
- PostgreSQL: If `DATABASE_URL`, `DEPLOYMENT_ENV=azure`, or `AZURE_KEY_VAULT_URL` set
- SQLite: Default for local development

### 3. `app/db_adapter.py`
Backward compatibility layer - drop-in replacement for `database.py`:
- Maintains same function signatures as legacy code
- Uses SQLAlchemy underneath
- Supports `config.CURRENT_COMPANY_ID` for multi-tenancy
- All legacy functions work without code changes

**Key Functions**:
- `get_dates_for_theaters()`
- `get_common_films_for_theaters_dates()`
- `get_data_for_trend_report()`
- `get_film_metadata()`, `save_film_metadata()`
- `create_scrape_run()`, `update_scrape_run_status()`
- `set_current_company()`, `get_current_company()`

## Migration Strategy

### Phase 1: Dual Mode (Current)
Both `database.py` and SQLAlchemy work simultaneously:

```python
# OLD CODE (still works)
from app import database
conn = database._get_db_connection()
# ... sqlite3 code ...

# NEW CODE (preferred)
from app.db_adapter import get_dates_for_theaters
dates = get_dates_for_theaters(theater_list)
```

### Phase 2: Gradual Migration
Replace imports one file at a time:

```python
# BEFORE
from app.database import get_dates_for_theaters, get_common_films_for_theaters_dates

# AFTER
from app.db_adapter import get_dates_for_theaters, get_common_films_for_theaters_dates
```

### Phase 3: Pure SQLAlchemy (Future)
Direct ORM usage for new features:

```python
from app.db_session import get_session
from app.db_models import User, Company

with get_session() as session:
    users = session.query(User).filter_by(role='admin').all()
    for user in users:
        print(f"{user.username} - {user.company.company_name}")
```

## Usage Examples

### 1. Basic Query (Legacy Compatible)

```python
from app.db_adapter import get_all_theaters, get_dates_for_theaters

# Get all theaters
theaters = get_all_theaters()

# Get dates for specific theaters
dates = get_dates_for_theaters(['Theater 1', 'Theater 2'])
```

### 2. ORM Query (New Style)

```python
from app.db_session import get_session
from app.db_models import Showing
from sqlalchemy import and_

with get_session() as session:
    showings = session.query(Showing).filter(
        and_(
            Showing.company_id == 1,
            Showing.play_date == '2025-11-13',
            Showing.theater_name == 'AMC Empire 25'
        )
    ).all()
    
    for showing in showings:
        print(f"{showing.film_title} at {showing.showtime}")
```

### 3. Company Context Setup

```python
from app.db_adapter import set_current_company

# At app startup (after user login)
set_current_company('AMC Theatres')

# All subsequent queries automatically filter by this company
from app.db_adapter import get_all_theaters
theaters = get_all_theaters()  # Only AMC Theatres' theaters
```

### 4. Creating Records

```python
from app.db_session import get_session
from app.db_models import Film
from datetime import datetime

with get_session() as session:
    film = Film(
        company_id=1,
        film_title='Dune: Part Two',
        imdb_id='tt15239678',
        genre='Sci-Fi, Adventure',
        mpaa_rating='PG-13',
        imdb_rating=8.6,
        last_omdb_update=datetime.utcnow()
    )
    session.add(film)
    # Automatic commit on context exit
```

### 5. Raw SQL (When Needed)

```python
from app.db_adapter import execute_raw_sql_pandas

# Complex query not yet migrated
query = """
    SELECT 
        theater_name,
        COUNT(DISTINCT film_title) as film_count,
        AVG(price) as avg_price
    FROM showings s
    JOIN prices p ON s.showing_id = p.showing_id
    WHERE play_date = :date
    GROUP BY theater_name
"""
df = execute_raw_sql_pandas(query, params={'date': '2025-11-13'})
```

## Database Configuration

### Local Development (SQLite)

```python
# No configuration needed - auto-detected
# Uses: sqlite:///[PROJECT_DIR]/pricescout.db or config.DB_FILE
```

### PostgreSQL (Local)

```powershell
# Set environment variable
$env:DATABASE_URL = "postgresql://username:password@localhost:5432/pricescout_db"

# Or use individual components
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "pricescout_db"
$env:POSTGRES_USER = "pricescout_app"
$env:POSTGRES_PASSWORD = "your_password"
```

### Azure PostgreSQL (Production)

```powershell
# Option 1: Connection string
$env:DATABASE_URL = "postgresql://user@server:pass@server.postgres.database.azure.com:5432/pricescout_db?sslmode=require"

# Option 2: Azure Key Vault (automatic)
$env:AZURE_KEY_VAULT_URL = "https://pricescout-kv-prod.vault.azure.net/"
$env:DEPLOYMENT_ENV = "azure"
# Connection string fetched automatically from Key Vault
```

## Testing the Migration

### 1. Test Database Connection

```bash
python app/db_session.py
```

Expected output:
```
============================================================
PriceScout Database Connection Test
============================================================

Database Type: SQLITE
Database URL:  sqlite:///C:/Users/.../Price Scout/pricescout.db

✓ Database connection successful!
============================================================
```

### 2. Initialize Schema

```python
from app.db_session import init_database

init_database()
# Creates all tables if they don't exist
```

### 3. Test Legacy Compatibility

```python
# This should work without changes
from app.db_adapter import get_all_theaters

theaters = get_all_theaters()
print(f"Found {len(theaters)} theaters")
```

### 4. Run Existing Tests

```bash
pytest tests/ -v
# All tests should pass (uses SQLite by default)
```

## Migration Checklist for Each File

When migrating a file from `database.py` to SQLAlchemy:

- [ ] Identify all `database.` imports
- [ ] Check if function exists in `db_adapter.py`
  - ✓ Yes: Change import to `from app.db_adapter import ...`
  - ✗ No: Add function to `db_adapter.py` or use ORM directly
- [ ] Test functionality with SQLite
- [ ] Test functionality with PostgreSQL (if available)
- [ ] Update any direct `sqlite3` usage to use `get_session()`
- [ ] Ensure `config.CURRENT_COMPANY_ID` is set if using company-scoped queries

## Files Requiring Migration

### High Priority (Core Functionality)
1. ✅ `app/database.py` - Compatibility layer created
2. ⏳ `app/users.py` - User management (8 sqlite3.connect calls)
3. ⏳ `app/data_management_v2.py` - Data import/export (2 calls)
4. ⏳ `app/modes/*.py` - Application modes (may use database.py)

### Medium Priority (Admin Features)
5. ⏳ `app/admin.py` - Admin interface
6. ⏳ `app/theater_matching_tool.py` - Theater matching
7. ⏳ Test files - Update mocks to use SQLAlchemy

### Low Priority (Optional)
8. ⏳ Scripts in `scripts/` directory
9. ⏳ Debug utilities in `debug/`

## Common Pitfalls

### 1. Missing Company Context

**Error**: No results returned, or wrong company's data shown

**Fix**:
```python
from app.db_adapter import set_current_company
set_current_company('Your Company Name')  # Set at app startup
```

### 2. Session Not Closed

**Error**: Database locked (SQLite) or connection pool exhausted (PostgreSQL)

**Fix**: Always use context manager
```python
# BAD
session = get_session()
users = session.query(User).all()
# Session never closed!

# GOOD
with get_session() as session:
    users = session.query(User).all()
# Automatic cleanup
```

### 3. Lazy Loading After Commit

**Error**: `DetachedInstanceError` when accessing relationships

**Fix**: Use `expire_on_commit=False` (already set) or eager loading
```python
with get_session() as session:
    user = session.query(User).filter_by(username='admin').first()
    company_name = user.company.company_name  # Works now
```

### 4. Date/DateTime Types

**Error**: String comparison issues with dates

**Fix**: Use proper date types
```python
from datetime import date

# BAD
showing = session.query(Showing).filter(Showing.play_date == '2025-11-13').first()

# GOOD
showing = session.query(Showing).filter(Showing.play_date == date(2025, 11, 13)).first()
```

## Performance Considerations

### 1. Batch Inserts
```python
from app.db_session import get_session
from app.db_models import Showing

with get_session() as session:
    showings = [
        Showing(company_id=1, theater_name=t, film_title=f, ...)
        for t, f in data
    ]
    session.bulk_save_objects(showings)
    # Much faster than individual inserts
```

### 2. Query Optimization
```python
# BAD: N+1 queries
with get_session() as session:
    users = session.query(User).all()
    for user in users:
        print(user.company.company_name)  # Separate query each time!

# GOOD: Eager loading
from sqlalchemy.orm import joinedload

with get_session() as session:
    users = session.query(User).options(joinedload(User.company)).all()
    for user in users:
        print(user.company.company_name)  # Already loaded!
```

### 3. Connection Pooling
```python
# Already configured in db_session.py
# PostgreSQL: pool_size=10, max_overflow=20
# SQLite: StaticPool (single connection)
```

## Rollback Plan

If issues arise, you can temporarily revert:

1. Keep `app/database.py` unchanged
2. Don't update imports in application code
3. SQLAlchemy files are additive - no breaking changes

To completely disable SQLAlchemy:
```python
# Rename db_adapter.py to db_adapter.py.disabled
# Continue using database.py as before
```

## Next Steps

After completing this task:

1. **Task 3**: Update `app/config.py` for environment variables
2. **Task 4**: Create Dockerfile with PostgreSQL support
3. **Test Migration**: Run `migrations/migrate_to_postgresql.py`
4. **Update Tests**: Modify test fixtures to use SQLAlchemy
5. **Gradual Adoption**: Replace imports in `users.py`, `data_management_v2.py`

## Support

For questions or issues:
- Review SQLAlchemy docs: https://docs.sqlalchemy.org/
- Check migration script: `migrations/migrate_to_postgresql.py`
- Test connection: `python app/db_session.py`
- Verify schema: `python -c "from app.db_models import Base; print(Base.metadata.tables.keys())"`
