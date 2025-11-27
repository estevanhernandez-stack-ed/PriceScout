# PriceScout API (Alpha v0.1.0)

FastAPI-based REST API layer for PriceScout report generation.

## Status: Alpha - Active Development

**Working Endpoints:**
- ✅ Health check
- ✅ Selection analysis (CSV/JSON)
- ✅ Showtime view (HTML/PDF)
- ✅ Daily lineup (CSV/JSON with DB queries)

**Known Issues:**
- ⚠️ Operating hours and PLF formats endpoints timeout in API (queries run instantly via CLI - investigating uvicorn/connection pooling)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium   # Required for PDF generation

# Run server
uvicorn api.main:app --reload --port 8080

# Health check
curl http://localhost:8080/healthz
```

## Endpoints

### GET /healthz
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "pricescout-api",
  "version": "0.1.0"
}
```

### POST /api/v1/reports/selection-analysis
Generate selection analysis report (showtime count pivot table).

**Query Parameters:**
- `format`: `json` or `csv` (default: `json`)

**Request Body:**
```json
{
  "selected_showtimes": {
    "2025-11-28": {
      "Marcus Ridge Cinema": {
        "Wicked": {
          "10:00AM": [{"format": "IMAX"}],
          "1:00PM": [{"format": "Standard"}]
        }
      }
    }
  }
}
```

**Example:**
```bash
curl -X POST "http://localhost:8080/api/v1/reports/selection-analysis?format=csv" \
  -H "Content-Type: application/json" \
  -d '{"selected_showtimes": {...}}' \
  -o selection.csv
```

### POST /api/v1/reports/showtime-view/html
Generate HTML showtime view report.

**Request Body:**
```json
{
  "all_showings": {
    "2025-11-30": {
      "Theater A": [
        {"film_title": "Film X", "showtime": "7:00PM", "format": "IMAX"}
      ]
    }
  },
  "selected_films": ["Film X"],
  "theaters": [{"name": "Theater A"}],
  "date_start": "2025-11-30",
  "date_end": "2025-11-30",
  "context_title": "Example Context"
}
```

### POST /api/v1/reports/showtime-view/pdf
Generate PDF showtime view report (with HTML fallback).

**Request Body:** Same as showtime-view/html

**Response:** PDF bytes or 503 with instructions if Playwright browsers missing

### GET /api/v1/reports/daily-lineup
Get daily theater lineup with showtimes.

**Query Parameters:**
- `theater`: Theater name (required, exact match)
- `date`: Date in YYYY-MM-DD format (required)
- `format`: `json` or `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8080/api/v1/reports/daily-lineup?theater=Marcus%20Ridge%20Cinema&date=2025-11-28&format=json"
```

**Response (JSON):**
```json
{
  "theater": "Marcus Ridge Cinema",
  "date": "2025-11-28",
  "showtime_count": 82,
  "showtimes": [
    {
      "film_title": "Wicked",
      "showtime": "10:00AM",
      "format": "IMAX",
      "daypart": "Matinee",
      "runtime": 160
    }
  ]
}
```

### GET /api/v1/reports/operating-hours ⚠️
**Status: Implemented but timing out in API (query runs instantly via CLI)**

Get derived operating hours per theater/date.

**Query Parameters:**
- `theater`: Theater name filter (optional)
- `date`: Date in YYYY-MM-DD format (optional)
- `limit`: Max records (default: 100)
- `format`: `json` or `csv` (default: `json`)

**Known Issue:** Connection/context manager issue causing timeout - under investigation.

### GET /api/v1/reports/plf-formats ⚠️
**Status: Implemented but timing out in API**

Get premium format distribution across theaters.

**Query Parameters:**
- `date`: Date filter YYYY-MM-DD (optional)
- `limit`: Max records (default: 100)
- `format`: `json` or `csv` (default: `json`)

**Known Issue:** Same timeout issue as operating-hours.

## Testing

```bash
# Run all endpoint tests
python test_api_direct.py

# Test daily lineup
python test_daily_lineup.py

# Test PDF generation
python test_pdf_endpoint.py

# Quick diagnostic
python test_operating_hours_quick.py

# Direct query test (bypasses API)
python test_query_direct.py  # Proves queries are fast (0.05s)
```

## Architecture

- **Framework:** FastAPI 0.111+
- **Server:** uvicorn with standard extras
- **Database:** SQLAlchemy ORM (SQLite dev / PostgreSQL prod)
- **PDF Generation:** Playwright (async browser automation)
- **Report Logic:** Reuses existing `app/utils.py` generators

## Database Indexes

Migration applied: `migrations/add_api_indexes.py`

Indexes added for performance:
- `idx_showings_theater_date_agg` - Speeds up operating hours queries
- `idx_showings_theater_format` - Speeds up PLF format queries
- `idx_showings_format` - Speeds up format filtering
- `idx_showings_company_theater` - Speeds up company+theater queries

## Migration Status

This API layer is part of the migration from Streamlit monolith to API-first architecture per Theatre Operations Platform spec.

**Completed:**
- ✅ Core report endpoints (4/7 fully working)
- ✅ Database indexes for aggregation queries
- ✅ Format negotiation (JSON/CSV)
- ✅ Test infrastructure
- ✅ PDF generation via Playwright

**In Progress:**
- 🔄 Debugging aggregation endpoint timeouts
- 🔄 Additional endpoints (pricing capture, etc.)

**Pending:**
- ⏳ Authentication layer (API keys → Entra ID)
- ⏳ Azure APIM integration
- ⏳ OpenAPI spec export
- ⏳ Rate limiting
- ⏳ Deployment to droplet

## Troubleshooting

**"Playwright browsers not found" (PDF endpoint returns HTML):**
```bash
playwright install chromium
```

**Port 8080 already in use:**
```bash
uvicorn api.main:app --port 8090
```

**Aggregation endpoints timeout:**
- Known issue under investigation
- Queries execute instantly outside API (0.05s via `test_query_direct.py`)
- Likely uvicorn worker or SQLAlchemy connection pool configuration
- Workaround: Use daily-lineup endpoint with specific theater/date filters

**Testing connection pooling fix:**
```python
# Try setting pool size in db_session.py
engine = create_engine(db_url, pool_size=5, max_overflow=10)
```

---

**Last Updated:** 2025-11-27  
**Version:** 0.1.0-alpha
