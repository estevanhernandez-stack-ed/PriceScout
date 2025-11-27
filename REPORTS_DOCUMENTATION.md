# PriceScout Report Catalog & Specification

> Version: v2 branch (azure) • Date: 2025-11-26
> Scope: Documents all current report outputs, their generation sources, schemas, file naming conventions, and future roadmap alignment.

---
## 1. Report Catalog Overview
| Report Name | Type | Generation Function / Module | Primary Use | Output Formats |
|-------------|------|------------------------------|-------------|----------------|
| Live Pricing Report (Market Mode) | Aggregated Showtimes + Pricing (Pending full pricing flow re-enable) | Market Mode UI (button) / future API | Snapshot of selected showtimes for pricing extraction | (Planned) CSV, PDF | 
| Showtime Selection Analysis | Pivot summary of selected showtimes | `generate_selection_analysis_report` (`app/utils.py`) | Quantify scope of a scrape (films × theaters × date) | CSV | 
| Showtime View (PDF/HTML) | Rendered hierarchical view of selection (films per theater/day) | `generate_showtime_pdf_report` / `generate_showtime_html_report` (`app/utils.py`) | Printable visual reference of scope & format distribution | PDF (primary), HTML fallback |
| Sniper Report (CompSnipe) | Targeted competitive showtimes (future pricing addition) | `render_compsnipe_mode` -> (Pending internal generation function) | Rapid comparison of competitor formats & times | PDF planned, CSV (selection analysis) | 
| Daily Lineup | Chronological per-theater schedule with optional out-times | `generate_daily_lineup` (`app/modes/daily_lineup_mode.py`) | Print-friendly operations schedule | CSV, XLSX (formatted) | 
| Operating Hours (Derived) | Open/close span per theater per date | `save_operating_hours_from_all_showings` (`app/utils.py`) | Operating window derivation & audit | DB persistence (table), future CSV export | 
| PLF Format Report | Listing of premium formats by theater (Marcus/Movie Tavern) | `scripts/scrape_all_marcus_plf.py` | PLF penetration analysis | Console + implied text output | 
| Film Runtime Assisted Lineup | Daily Lineup augmented with runtime-calculated out times | Same as Daily Lineup | More accurate labor / turnover planning | CSV, XLSX |
| Historical Pricing (Planned) | Time-series of ticket prices | (Future module) | Trend analysis, elasticity, competitive moves | CSV, API JSON |
| Market Aggregate Dashboard (Planned) | Aggregates (median price, PLF %, showtime density) | (Future aggregation service) | Executive/strategy snapshot | Web dashboard, CSV export |

---
## 2. Detailed Specifications
### 2.1 Showtime Selection Analysis (CSV)
Source: `generate_selection_analysis_report(selected_showtimes)`
Input Shape: `selected_showtimes = { date: { theater_name: { film_title: { showtime: [showing_objects] }}}}`
Schema (Columns):
- `Date` (YYYY-MM-DD)
- `Theater Name`
- `Film Title` (as columns in pivot) -> numeric counts of selected showtimes for that film
- `Total Showings Per Day` (sum across films for that theater/date)
File Naming: `Showtime_Selection_Analysis_{timestamp}.csv`
Notes:
- Only counts selected showtimes (not total possible) — acts as scope bill-of-materials.
- Empty selection returns empty DataFrame.
Improvement Opportunities:
- Add column for unique film count.
- Add per-film earliest/latest time range.
- API endpoint: `GET /api/v1/reports/showtime-selection?date=...&theater=...` (planned).

### 2.2 Showtime View (PDF / HTML fallback)
Source: `generate_showtime_pdf_report` (async Playwright) / `generate_showtime_html_report`
Context Inputs:
- `all_showings` (dict keyed by date → theater → showings list)
- `selected_films` (list)
- `theaters` (list of theater objects)
- `scrape_date_range` (tuple `(start_date, end_date)`)
- Optional `context_title` injected by mode (Director / ZIP / Market label)
HTML Structure Highlights:
- Date section wrappers
- Theater sections with computed time range: min/max showtime + span duration (hrs)
- Film sections listing each distinct showtime
Rendered Data Points:
- Film Title
- Number of showtimes (per film per theater per date)
- Format decorations (non-2D formats appended)
File Naming (UI): `Showtime_View_{YYYYMMDD_HHMM}.pdf` / `.html`
Fallback Trigger:
- Any exception in PDF generation (missing Playwright browsers) produces HTML bytes.
Enhancement Ideas:
- Pagination & page breaks per date.
- Format grouping (PLF vs Standard).
- Add summary banner (total theaters × films × showtimes).
- API endpoint for HTML clean export.

### 2.3 Daily Lineup (CSV / XLSX)
Source: `generate_daily_lineup()`
Inputs:
- Theater name
- Date
- Options: `compact_titles`, `remove_articles`, `max_words`, `show_outtime`, `use_military_time`, `show_ampm`
Data Query:
- SQLAlchemy query joining `Showing` ← `Film` for runtime
Processing:
- Time parsing & chronological sort via `_sort_time`
- Out-Time calculation: showtime + runtime minutes (if available)
- Premium Format Indicator appended (`[IMAX]`, `[Dolby]`, etc.)
Schema (variable based on options):
- `Theater #` (manual fill placeholder)
- `Film` (possibly compacted)
- `In-Time` (formatted)
- `Out-Time` (optional; blank if runtime missing)
File Naming:
- CSV: `daily_lineup_{safe_theater_name}_{YYYY-MM-DD}.csv`
- XLSX: `daily_lineup_{safe_theater_name}_{YYYY-MM-DD}.xlsx`
Excel Formatting:
- Header rows with theater & date
- Styled header (color fill, bold font)
- Potential future conditional formatting (e.g., highlight PLF)
Enhancement Ideas:
- Include auditorium assignment algorithm.
- Add turnover gap calculation (Out-Time of previous vs In-Time of next).
- Add occupancy projection overlay (future integration).

### 2.4 Operating Hours (Derived Persistence)
Source: `save_operating_hours_from_all_showings(daily_showings, theaters_list, scrape_date, market, duration)`
Purpose:
- Derives first showtime → opening & last showtime → closing per theater/date.
Storage:
- Saved to DB (operating hours table) with context metadata.
Data Points (inferred typical):
- `theater_name`, `play_date`, `first_showtime`, `last_showtime`, `span_hours`, `market`, `calculation_context`.
Enhancement Ideas:
- Export UI action (CSV batch dump).
- API endpoint: `GET /api/v1/operating-hours?date=...&theaterId=...`.
- Confidence score (based on completeness of film data).

### 2.5 PLF Format Report (Script)
Source: `scripts/scrape_all_marcus_plf.py`
Flow:
- Loads cached theater list(s)
- Runs showtime scrape for target date (tomorrow)
- Aggregates `format` strings per theater
Outputs:
- Console listing of PLF formats per theater
- Summary of unique formats
PLF Keyword Set:
- `['IMAX','UltraScreen','Dolby','Premium','PLF','Grand','XD','Big House','Superscreen','D-BOX','4DX','ScreenX','RPX']`
Enhancement Ideas:
- Persist to `plf_inventory` table with timestamp
- Report as CSV: columns = Theater | Formats | PLF Count | Non-PLF Count
- Dashboard (%) PLF penetration per market

### 2.6 Sniper Report (CompSnipe Mode)
Current State:
- UI triggers film & showtime selection for targeted theaters (ZIP/name search).
- PDF generation shares logic with Market Mode (same fallback mechanism).
Gaps:
- Pricing extraction integration (currently focusing on showtimes and formats).
- Distinct Sniper-specific report schema not yet formalized.
Recommended Schema (Proposed):
| Column | Description |
|--------|-------------|
| Date | Play date |
| Theater | Theater name |
| Film | Film title |
| Showtime | Local time |
| Format | Unified format label |
| PLF Flag | Boolean |
| Ticket URL | Deep link |
| Market | Derived or searched region |
| ZIP | Input ZIP (if used) |

### 2.7 Live Pricing Report (Pending Reactivation)
Currently Placeholder:
- Button in Market Mode UI.
Gaps:
- Pricing scrape path disabled by migration issues (stray kwargs, session population).
Planned Data Points:
| Column | Description |
|--------|-------------|
| Date | Play date |
| Theater | Theater name |
| Film | Film title |
| Showtime | Confirmed start |
| Base Price | Standard adult ticket price |
| Senior | Senior price (if available) |
| Child | Child price |
| Format | Format label |
| PLF Flag | Pre-calculated |
| Daypart | Derived (Matinee/Twilight/Prime/Late Night) |
| Ticket URL | Source link |
| Capture Timestamp | When scraped |

### 2.8 Film Runtime Assisted Lineup
Same as Daily Lineup with enhanced runtime mapping.
Enhancement Ideas:
- Flag anomalies (runtime missing).
- Add multi-day generation (weekpack).

---
## 3. File Naming & Retention Conventions
| Report | Pattern | Retention Recommendation |
|--------|---------|--------------------------|
| Selection Analysis CSV | `Showtime_Selection_Analysis_{YYYYMMDD_HHMM}.csv` | Keep 90 days (scope audit) |
| Showtime View PDF | `Showtime_View_{YYYYMMDD_HHMM}.pdf` | Keep 30 days (operational reference) |
| Daily Lineup CSV/XLSX | `daily_lineup_{theater}_{YYYY-MM-DD}.(csv|xlsx)` | Keep 14 days (operational) |
| PLF Format Script Output | Console / future `plf_formats_{YYYY-MM-DD}.csv` | Keep 180 days (trend) |
| Operating Hours | DB rows | Indefinite (analytics) |
| Future Pricing Report | `pricing_capture_{YYYYMMDD_HHMM}.csv` | Keep 1 year (trend) |

---
## 4. Data Quality & Validation
| Aspect | Current State | Improvement |
|--------|---------------|------------|
| Showtimes Uniqueness | Consolidated by time per film per theater | Add duplicate detection alert |
| Format Normalization | Raw strings aggregated; PLF flagged | Introduce canonical format taxonomy table |
| Daypart Assignment | Derived during auto-selection | Persist in showings for audit |
| Runtime Integrity | Optional join; missing for some films | Backfill via OMDb enrichment job |
| Market Attribution | Derived via cache mapping | Add audit field (source, timestamp) |

---
## 5. API-First Migration Targets
| Report | Proposed Endpoint | Method | Status |
|--------|-------------------|--------|--------|
| Selection Analysis | `/api/v1/reports/selection-analysis` | POST (payload of selected_showtimes) | Planned |
| Showtime View | `/api/v1/reports/showtime-view` | POST → returns HTML/PDF link | Planned |
| Daily Lineup | `/api/v1/reports/daily-lineup?theater=...&date=...` | GET | Planned |
| Operating Hours | `/api/v1/operating-hours?date=...` | GET | Planned |
| PLF Formats | `/api/v1/reports/plf-formats?date=...` | GET | Planned |
| Pricing Capture | `/api/v1/reports/pricing-live` | POST (scrape job) | Planned |

---
## 6. Security & Compliance Considerations
- Current reports contain no PCI or PII beyond potential user session metadata.
- Future pricing history may include derived competitive analytics — ensure role-based filtering persists.
- Introduce audit logging: report generation events → `report_audit` table (timestamp, user, report_type, scope_metrics).
- Ensure download endpoints enforce authenticated JWT + RBAC (manager/admin for sensitive pricing).

---
## 7. Performance & Scalability Notes
| Concern | Current Mitigation | Future Optimization |
|---------|--------------------|---------------------|
| Websocket Payload Size | Collapsed expanders for >20 theaters | Move to API pagination + client-side virtualization |
| PDF Generation Latency | Playwright headless single-thread | Pre-render async queue + caching (Service Bus) |
| Large Lineup Exports | On-demand generation single theater | Batch multi-theater lineup job endpoint |
| PLF Scan Full Set | Sequential theater scraping | Parallel async workers; rate limit upstream |

---
## 8. Future Report Roadmap
| Feature | Description | Priority |
|---------|-------------|----------|
| Pricing History Report | Time-series price changes with delta styling | High |
| Market Aggregates Dashboard | KPIs: PLF %, Avg Price, Showtime Density | High |
| Out-Time Gap Analysis | Adds turnover metrics to lineups | Medium |
| Multi-day Lineup Pack | Weekly PDF export per theater | Medium |
| Premium Format Saturation Trend | PLF formats over time per market | Medium |
| Selection Consistency Score | Cross-day film presence index | Low |
| Auditorium Assignment Optimizer | Suggest mapping based on runtime overlaps | Low |
| API Report Tokens | Pre-signed short-lived URLs for automated pulls | Medium |

---
## 9. Known Gaps
| Gap | Impact | Path to Resolution |
|-----|--------|-------------------|
| No unified report audit trail | Limited traceability | Add `report_audit` table + logging decorator |
| Pricing scrape paused | Incomplete pricing reports | Fix kwargs + session showtime population; re-enable | 
| HTML/PDF lacks summary header | Harder quick scope assessment | Inject aggregate metrics pre-body |
| No RLS on report data | Potential cross-tenant leakage risk | Implement DB row-level policies by `company_id` |
| Format taxonomy inconsistencies | Reporting fragmentation | Normalize & map formats to canonical categories |

---
## 10. Glossary (Report Context)
| Term | Definition |
|------|------------|
| PLF | Premium Large Format (IMAX, Dolby, XD, etc.) |
| Daypart | Operational time bucket (Matinee, Twilight, Prime, Late Night) |
| Out-Time | Calculated end time: In-Time + runtime |
| Scope Metrics | Aggregates describing size of selection (theaters × films × showtimes) |
| Lineup | Ordered chronological list of film start times for a theater |

---
## 11. Proposed Immediate Enhancements (Quick Wins)
1. Add aggregate summary (total theaters, films, selected showtimes) to Showtime View HTML.
2. Introduce `GET /api/v1/reports/daily-lineup` stub (FastAPI or .NET) returning JSON.
3. Persist PLF Format Report output to DB for trend analysis.
4. Add audit logging wrapper to report generators.
5. Re-enable pricing scrape path and attach to Live Pricing Report.

---
## 12. Alignment with Theatre Operations Platform Architecture
| Platform Principle | Current Report State | Alignment Action |
|--------------------|----------------------|------------------|
| API-First | UI-coupled generation | Externalize endpoints for each report |
| Shared Platform | Local-only, no APIM | Publish OpenAPI specs; integrate APIM |
| Monitoring | Basic logging only | Instrument report generation via App Insights |
| Identity | Bcrypt sessions | Entra ID JWT + RBAC claim filters |
| Schema Separation | Single schema multi-tenant | Partition reporting tables (e.g., `competitive.reports`) |

---
## 13. Change Log (This Document)
| Date | Author | Change |
|------|--------|--------|
| 2025-11-26 | System (AI Assistant) | Initial creation of comprehensive report catalog |

---
## 14. Next Steps Checklist
- [ ] Add report audit decorator
- [ ] Implement first API endpoint (daily lineup JSON)
- [ ] Normalize format taxonomy mapping
- [ ] Re-enable pricing scrape & define pricing report spec JSON
- [ ] Add summary metrics to PDF/HTML showtime view

---
*End of REPORTS_DOCUMENTATION.md*
