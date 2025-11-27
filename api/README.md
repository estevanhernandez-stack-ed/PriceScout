# PriceScout API (Alpha)

A minimal FastAPI layer exposing report endpoints to begin API-first migration.

## Endpoints
- `GET /healthz` — service health
- `POST /api/v1/reports/selection-analysis?format=csv|json` — accepts `selected_showtimes` JSON, returns CSV (default) or JSON
- `POST /api/v1/reports/showtime-view/html` — returns HTML bytes for the selection view
- `POST /api/v1/reports/showtime-view/pdf` — attempts PDF; returns 503 JSON with guidance if Playwright browsers are missing

## Run (local)
```pwsh
# From repo root
pip install -r requirements.txt
playwright install chromium   # required for PDF endpoint
uvicorn api.main:app --reload --port 8080
```

## Request Examples
Selection Analysis (CSV):
```bash
curl -X POST http://localhost:8080/api/v1/reports/selection-analysis \
  -H "Content-Type: application/json" \
  -d '{"selected_showtimes": {"2025-11-30": {"Theater A": {"Film X": {"7:00PM": [{"format":"IMAX"}]}}}}}' \
  -o selection.csv
```

Showtime View (HTML):
```bash
curl -X POST http://localhost:8080/api/v1/reports/showtime-view/html \
  -H "Content-Type: application/json" \
  -d '{
    "all_showings": {"2025-11-30": {"Theater A": [{"film_title":"Film X","showtime":"7:00PM","format":"IMAX"}]}},
    "selected_films": ["Film X"],
    "theaters": [{"name":"Theater A"}],
    "date_start": "2025-11-30",
    "date_end": "2025-11-30",
    "context_title": "Example Context"
  }' \
  -o view.html
```

## Notes
- This API reuses existing report generation utilities; it is a bridge toward the target .NET API-first architecture.
- Authentication is not wired yet; place behind internal network or gateway while iterating.
