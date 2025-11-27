# PriceScout API Documentation

**Version:** 0.2.0-alpha  
**Last Updated:** November 27, 2025  
**Status:** Active Development

---

## 📋 Overview

FastAPI-based REST API for PriceScout theater showtime and pricing data. Provides endpoints for report generation, resource queries, and data export in multiple formats (JSON/CSV).

**Total Endpoints:** 12 operational
- ✅ 7 Report endpoints
- ✅ 5 Resource endpoints

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers (for PDF generation)
playwright install chromium

# 3. Setup authentication (first time only)
python manage_api_keys.py create-tables
python manage_api_keys.py generate --client "Development" --tier internal

# 4. Run development server
uvicorn api.main:app --reload --port 8000

# 5. Health check (no auth required)
curl http://localhost:8000/healthz

# 6. Test authenticated endpoint
curl -H "X-API-Key: YOUR_KEY_HERE" \
  http://localhost:8000/api/v1/theaters
```

**⚠️  Note:** Save the API key from step 3 - you'll need it for all requests!

---

## 📚 API Endpoints

### Health & Status

#### `GET /healthz`
Service health check.

**Response:**
```json
{
  "status": "ok"
}
```

---

### Report Endpoints

#### `POST /api/v1/reports/selection-analysis`
Generate showtime selection analysis (pivot table).

**Query Parameters:**
- `format`: `json` | `csv` (default: `json`)

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
curl -X POST "http://localhost:8000/api/v1/reports/selection-analysis?format=csv" \
  -H "Content-Type: application/json" \
  -d '{"selected_showtimes": {...}}' \
  -o analysis.csv
```

---

#### `POST /api/v1/reports/showtime-view/html`
Generate HTML showtime view report.

**Request Body:** Same as selection-analysis

**Response:** HTML bytes (text/html)

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/reports/showtime-view/html" \
  -H "Content-Type: application/json" \
  -d @request.json \
  -o showtime_view.html
```

---

#### `POST /api/v1/reports/showtime-view/pdf`
Generate PDF showtime view report (with HTML fallback).

**Request Body:** Same as selection-analysis

**Response:** PDF bytes (application/pdf) or HTML with 503 if Playwright unavailable

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/reports/showtime-view/pdf" \
  -H "Content-Type: application/json" \
  -d @request.json \
  -o showtime_view.pdf
```

---

#### `GET /api/v1/reports/daily-lineup`
Get daily theater lineup with showtimes.

**Query Parameters:**
- `theater` (required): Theater name (exact match)
- `date` (required): Date in YYYY-MM-DD format
- `format`: `json` | `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8000/api/v1/reports/daily-lineup?\
theater=Marcus%20Ridge%20Cinema&\
date=2025-11-28&\
format=json"
```

**Response:**
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

---

#### `GET /api/v1/reports/operating-hours`
Get derived operating hours (first/last showtime) per theater/date.

**Query Parameters:**
- `theater`: Theater name filter (optional)
- `date`: Date filter YYYY-MM-DD (optional)
- `limit`: Max records (default: 100)
- `format`: `json` | `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8000/api/v1/reports/operating-hours?\
theater=Marcus%20Ridge%20Cinema&\
format=json"
```

**Response:**
```json
{
  "record_count": 4,
  "date_range": {
    "earliest": "2025-11-27",
    "latest": "2025-11-30"
  },
  "operating_hours": [
    {
      "theater_name": "Marcus Ridge Cinema",
      "date": "2025-11-30",
      "opening_time": "10:00AM",
      "closing_time": "9:45PM",
      "total_showtimes": 80
    }
  ]
}
```

---

#### `GET /api/v1/reports/plf-formats`
Get premium large format (PLF) distribution across theaters.

**Query Parameters:**
- `date`: Date filter YYYY-MM-DD (optional)
- `limit`: Max records (default: 100)
- `format`: `json` | `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8000/api/v1/reports/plf-formats?format=json"
```

**Response:**
```json
{
  "theater_count": 75,
  "total_plf_showtimes": 880,
  "theaters": {
    "Marcus Ridge Cinema": [
      {"format": "IMAX", "showtime_count": 15},
      {"format": "Dolby", "showtime_count": 12}
    ]
  }
}
```

---

### Resource Endpoints

#### `GET /api/v1/theaters`
List all theaters with metadata.

**Query Parameters:**
- `active_only`: Filter to active theaters (default: true)
- `date_from`: Filter theaters with showtimes after date (YYYY-MM-DD)
- `format`: `json` | `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8000/api/v1/theaters?format=json"
```

**Response:**
```json
{
  "theater_count": 84,
  "theaters": [
    {
      "theater_name": "Marcus Ridge Cinema",
      "active_dates": 4,
      "total_showtimes": 320,
      "first_date": "2025-11-27",
      "last_date": "2025-11-30",
      "film_count": 25
    }
  ]
}
```

---

#### `GET /api/v1/films`
List films with showtime information.

**Query Parameters:**
- `date`: Filter by specific date (YYYY-MM-DD)
- `theater`: Filter by theater name
- `limit`: Max results (default: 100)
- `format`: `json` | `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8000/api/v1/films?limit=10"
```

**Response:**
```json
{
  "film_count": 10,
  "films": [
    {
      "film_title": "Wicked",
      "showtime_count": 4891,
      "theater_count": 78,
      "date_count": 4,
      "first_date": "2025-11-27",
      "last_date": "2025-11-30"
    }
  ]
}
```

---

#### `GET /api/v1/scrape-runs`
Get recent scrape run history.

**Query Parameters:**
- `limit`: Max results (default: 20)
- `format`: `json` | `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8000/api/v1/scrape-runs?limit=5"
```

**Response:**
```json
{
  "scrape_run_count": 5,
  "scrape_runs": [
    {
      "run_id": 15,
      "status": "completed",
      "run_timestamp": "2025-11-14 01:17:07",
      "mode": "Market Mode",
      "records_scraped": 1450,
      "error_message": null
    }
  ]
}
```

---

#### `GET /api/v1/showtimes/search`
Flexible showtime search with multiple filters.

**Query Parameters:**
- `film`: Film title (partial match)
- `theater`: Theater name (partial match)
- `date_from`: Start date (YYYY-MM-DD)
- `date_to`: End date (YYYY-MM-DD)
- `format_type`: Format filter (IMAX, Dolby, 3D, etc)
- `limit`: Max results (default: 100)
- `format`: `json` | `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8000/api/v1/showtimes/search?\
film=Wicked&\
theater=Marcus&\
format_type=IMAX&\
limit=10"
```

**Response:**
```json
{
  "showtime_count": 10,
  "filters": {
    "film": "Wicked",
    "theater": "Marcus",
    "date_from": null,
    "date_to": null,
    "format_type": "IMAX"
  },
  "showtimes": [
    {
      "film_title": "Wicked",
      "theater_name": "Marcus Ridge Cinema",
      "play_date": "2025-11-28",
      "showtime": "10:00AM",
      "format": "IMAX",
      "daypart": "Matinee",
      "is_plf": true
    }
  ]
}
```

---

#### `GET /api/v1/pricing`
Get ticket pricing data.

**Query Parameters:**
- `theater`: Theater name filter
- `film`: Film title filter
- `date`: Date filter (YYYY-MM-DD)
- `limit`: Max results (default: 100)
- `format`: `json` | `csv` (default: `json`)

**Example:**
```bash
curl "http://localhost:8000/api/v1/pricing?theater=Marcus&limit=20"
```

**Response:**
```json
{
  "price_count": 20,
  "pricing": [
    {
      "film_title": "Wicked",
      "theater_name": "Marcus Ridge Cinema",
      "play_date": "2025-11-28",
      "showtime": "10:00AM",
      "format": "IMAX",
      "ticket_type": "Adult",
      "price": 18.50,
      "scraped_at": "2025-11-27 14:30:00"
    }
  ]
}
```

**Note:** Returns 404 if no pricing data has been scraped yet.

---

## 🧪 Testing

### Run All Tests

```bash
# Test report endpoints
python test_all_endpoints.py

# Test resource endpoints
python test_resource_endpoints.py

# Test specific features
python test_daily_lineup.py
python test_pdf_endpoint.py
```

### Manual Testing with curl

```bash
# Health check
curl http://localhost:8000/healthz

# List theaters
curl http://localhost:8000/api/v1/theaters

# Search for IMAX showtimes
curl "http://localhost:8000/api/v1/showtimes/search?format_type=IMAX&limit=5"

# Export films to CSV
curl "http://localhost:8000/api/v1/films?format=csv" -o films.csv
```

---

## 📊 Response Formats

### JSON
Default format for all endpoints. Returns structured data with metadata.

```json
{
  "record_count": 100,
  "metadata": {...},
  "data": [...]
}
```

### CSV
Available on most endpoints via `?format=csv` query parameter. Returns streaming CSV download with appropriate filename.

```csv
field1,field2,field3
value1,value2,value3
```

---

## 🔒 Security & Authentication

### Current Status: ✅ API Key Authentication Implemented

All API endpoints (except `/healthz`) now require authentication using API keys.

### Getting an API Key

```bash
# Create database tables (first time only)
python manage_api_keys.py create-tables

# Generate a new API key
python manage_api_keys.py generate --client "Your Company" --tier free

# Example output:
# 🔑 API Key: ps_free_abc123def456...
# ⚠️  IMPORTANT: Save this key securely! It cannot be retrieved later.
```

### Using API Keys

Include your API key in the `X-API-Key` header with every request:

```bash
# Example request
curl -H "X-API-Key: ps_free_abc123def456..." \
  http://localhost:8000/api/v1/theaters
```

**PowerShell:**
```powershell
$headers = @{"X-API-Key" = "ps_free_abc123def456..."}
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/theaters" -Headers $headers
```

**Python:**
```python
import requests

headers = {"X-API-Key": "ps_free_abc123def456..."}
response = requests.get("http://localhost:8000/api/v1/theaters", headers=headers)
data = response.json()
```

### API Tiers & Rate Limits

| Tier | Requests/Hour | Requests/Day | Cost | Features |
|------|---------------|--------------|------|----------|
| **Free** | 100 | 1,000 | Free | Basic reports, theaters, films |
| **Premium** | 1,000 | 50,000 | $49/mo | All features + PDF exports |
| **Enterprise** | Unlimited | Unlimited | Custom | All features + priority support |
| **Internal** | Unlimited | Unlimited | N/A | For internal use only |

### Rate Limit Headers

API responses include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1732723200
```

### Authentication Errors

**401 Unauthorized - Missing API Key:**
```json
{
  "detail": "API key required. Include 'X-API-Key' header in your request."
}
```

**401 Unauthorized - Invalid API Key:**
```json
{
  "detail": "Invalid API key. Key not found in database."
}
```

**401 Unauthorized - Expired API Key:**
```json
{
  "detail": "API key expired on 2025-11-01. Contact support."
}
```

**429 Too Many Requests - Rate Limit Exceeded:**
```json
{
  "detail": "Hourly rate limit exceeded (100/100). Upgrade to premium for higher limits."
}
```

### Managing API Keys

```bash
# List all API keys
python manage_api_keys.py list

# Show key details
python manage_api_keys.py show ps_free_abcd

# Deactivate a key
python manage_api_keys.py deactivate ps_free_abcd

# Reactivate a key
python manage_api_keys.py reactivate ps_free_abcd

# View usage statistics
python manage_api_keys.py usage ps_free_abcd --days 30
python manage_api_keys.py usage  # All keys
```

### Security Best Practices

1. **Never commit API keys** - Add them to `.gitignore`
2. **Use environment variables** - Store keys in `.env` files
3. **Rotate keys regularly** - Especially for production
4. **Deactivate unused keys** - Reduce attack surface
5. **Monitor usage** - Track unusual patterns
6. **Use HTTPS in production** - Encrypt keys in transit

### Future Authentication

**Planned (Phase 2):**
- Azure Entra ID (OAuth 2.0)
- Single Sign-On (SSO)
- Multi-tenant support
- API Management (APIM) integration
- Fine-grained permissions

---

## 🏗️ Architecture

- **Framework:** FastAPI 0.111+
- **Server:** uvicorn with standard extras
- **Database:** SQLAlchemy ORM
  - Development: SQLite
  - Production: PostgreSQL
- **PDF Generation:** Playwright (Chromium)
- **Response Formats:** JSON (default), CSV streaming

---

## 📈 Performance

- **Database:** Optimized with 9 composite indexes
- **Query Times:** < 0.05s for most queries
- **Concurrent Requests:** Supports async operations
- **CSV Export:** Streaming responses (no memory limits)

---

## 🐛 Known Issues

1. **PDF Generation:** Requires `playwright install chromium`
   - Falls back to HTML with 503 status if unavailable

2. **Pricing Endpoint:** May return 404 if pricing not yet scraped
   - This is expected behavior for new databases

3. **Theater Names:** Trailing spaces in some theater names (data quality issue)

---

## 🗺️ Roadmap

### Phase 1: Core API (Current)
- ✅ Report endpoints
- ✅ Resource endpoints  
- ✅ Format negotiation (JSON/CSV)
- ✅ Database optimization

### Phase 2: Enhanced Features
- ⏳ Authentication layer
- ⏳ Pagination support
- ⏳ Field filtering (?fields=name,count)
- ⏳ Aggregation endpoints
- ⏳ Webhook notifications

### Phase 3: Production Ready
- ⏳ Azure deployment
- ⏳ APIM integration
- ⏳ Rate limiting
- ⏳ Monitoring & logging
- ⏳ OpenAPI spec export
- ⏳ Postman collection

### Phase 4: Advanced
- ⏳ GraphQL endpoint
- ⏳ WebSocket subscriptions
- ⏳ Batch operations
- ⏳ Analytics dashboard API
- ⏳ ML prediction endpoints

---

## 📝 Migration Notes

This API layer is part of the migration from Streamlit monolith to API-first architecture per Theatre Operations Platform specification.

**Migration Strategy:**
1. Extract report generation logic → API endpoints ✅
2. Add resource query endpoints ✅
3. Implement authentication layer ⏳
4. Deploy alongside Streamlit ⏳
5. Gradually migrate UI to consume API ⏳
6. Deprecate direct database access from UI ⏳

---

## 🤝 Contributing

### Adding New Endpoints

1. Add endpoint function to appropriate router (`reports.py` or `resources.py`)
2. Include query parameter validation
3. Support both JSON and CSV formats
4. Add test case to test suite
5. Update this documentation

### Code Style

- Use type hints
- Include docstrings
- Follow FastAPI best practices
- Handle errors with HTTPException
- Return consistent response structures

---

## 📞 Support

**Documentation:** See `REPORTS_DOCUMENTATION.md` for report specifications

**Issues:** Check `api/README.md` for troubleshooting

**Version:** 0.2.0-alpha

---

**Happy Thanksgiving! 🦃**

Generated with care by GitHub Copilot  
Last updated: November 27, 2025
