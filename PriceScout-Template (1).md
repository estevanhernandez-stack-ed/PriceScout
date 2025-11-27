# 📋 Project Brief - 626 Labs

**Instructions:** This template contains your current project data. You can print and edit it, then upload it back to update your project.

---

## 🏷️ Project Name
**PriceScout**

---

## 📂 Project Type
**Check one:**
- [x] Software Application (web, mobile, desktop)
- [ ] Research Project (academic, market research, investigation)
- [ ] Physical Build (PC build, car restoration, home renovation)
- [ ] Creative Project (design, art, music, writing)
- [ ] Business Project (startup, product launch, marketing campaign)
- [ ] Personal Goal (learning, fitness, travel)
- [ ] Custom/Other: _________________

---

## 📝 Project Brief
**What is this project about? (updated)**

PriceScout is a production-oriented competitive intelligence and ticket pricing analysis platform for theatrical exhibitors. It supports multiple scrape modes (Market Mode, CompSnipe, Poster, Operating Hours), role-based access control, theater matching, operating hours derivation, and pricing history analytics. The data layer is currently being migrated from a legacy SQLite implementation to a multi‑tenant PostgreSQL + SQLAlchemy architecture. A new data management module, `data_management_v2.py`, has been introduced to handle all CRUD operations, replacing the previous ad-hoc data handling. Recent work includes adapting to a breaking change in Fandango's DOM structure, refactoring operating hours persistence, and hardening user / admin workflows. Export, reporting, and film metadata enrichment (OMDb) remain integral features.

---

## 🎯 Project Status
**Check one:**
- [ ] Not Started
- [x] In Progress *(post-migration stabilization)*
- [ ] Completed
- [ ] On Hold

---

## 📊 Project Category
**Check one:**
- [x] Software (apps, websites, tools)
- [ ] Research (studies, investigations)
- [ ] Physical (builds, constructions)
- [ ] Creative (art, design, content)
- [ ] Business (ventures, operations)
- [ ] Personal (self-improvement, hobbies)

---

## ✅ Tasks / Roadmap (Historical & Current)
**Legacy foundation (completed):**
1. [x] Initial Streamlit UI (multi-mode scaffolding)
2. [x] Playwright integration for headless scraping
3. [x] Legacy SQLite schema for pricing & showtimes
4. [x] Basic price extraction (adult / child / senior)
5. [x] CSV export & report generation
6. [x] BCrypt authentication & session handling
7. [x] RBAC (admin / manager / user)
8. [x] Operating Hours derivation (first implementation)
9. [x] Theater Matching Tool (competitor mapping)
10. [x] Film Analysis / historical comparison view
11. [x] Test suite baseline (≈391 tests)
12. [x] Documentation suite (deployment, security, RBAC, testing)
13. [x] v1.0.0 deployment (SQLite based)

**Migration & stabilization (recent / ongoing):**
14. [x] Introduce SQLAlchemy ORM models (multi‑tenant via company_id)
15. [x] Implement `db_session` context manager & engine auto‑detection
16. [x] Create `db_adapter.py` (compatibility layer) – showings, prices, films, operating hours, ticket type logging
17. [x] Introduce `data_management_v2.py` for centralized data operations.
18. [x] Update imports to use `db_adapter` instead of legacy `database.py`
19. [x] Add company context initialization on login (multi-tenancy)
20. [x] Fix column name mismatches (`is_active`, `company_name`, FK ids)
21. [x] Replace invalid bcrypt seed & normalize password change workflow
22. [x] Refactor operating hours save to ORM (list/dict format support)
23. [x] Repair admin user management functions (PostgreSQL-safe queries)
24. [x] Adapt scraper to new Fandango DOM (`li.shared-movie-showtimes`, `aria-label` time parsing)
25. [x] Add debug instrumentation for scrape run creation & showings persistence
26. [x] Fix IndentationError / import hygiene in `utils.py`
27. [x] Fix Streamlit download button regression (pin to v1.38.0 – see Known Issues)
28. [x] Add Daily Lineup mode with Excel/CSV export, out-time calculation, and time format options

**Pending / next steps:**
29. [ ] Refactor existing data handling logic to use `data_management_v2.py`.
30. [ ] Re-enable full price scrape flow (remove stray kwargs, ensure `selected_showtimes` session population)
31. [ ] Persist scrape run context (add separate context/metadata table or JSON field)
32. [ ] Add migration scripts (Alembic) for future schema evolution
33. [ ] Harden error surfacing (surface async thread exceptions in UI status blocks)
34. [ ] Rebuild failing / outdated tests (admin + theming) for PostgreSQL path
35. [ ] Implement async batch scraping (parallel theater contexts) for performance
36. [ ] Add observability (structured logs + optional Application Insights key)
37. [ ] Resume pricing history backfill under new schema
38. [ ] Security pass: rotate SECRET_KEY & vault-managed credentials
39. [ ] Improve PDF report rendering (film grouping, page breaks)
40. [ ] Add market-level aggregate dashboards (median price, PLF penetration)
41. [ ] Optional: Introduce caching layer (Redis) for repeated theater lookups
42. [ ] Monitor Streamlit releases for download_button proxy fix (test versions >1.38.0)

**Deferred / idea backlog:**
- [ ] Headless vs headed mode toggle in UI for diagnostics
- [ ] Synthetic regression snapshots (HTML capture diffing)
- [ ] Rate limiting / circuit breaker for external site changes

---

## 💰 Budget Estimate
**Total Budget:** $__________

**Major Cost Items:**
- ________________: $__________
- ________________: $__________
- ________________: $__________

---

## 📅 Timeline / Deadlines
**Start Date:** __________
**Target Completion:** __________

**Key Milestones:**
- [ ] Milestone 1: ________________ (Due: ______)
- [ ] Milestone 2: ________________ (Due: ______)
- [ ] Milestone 3: ________________ (Due: ______)

---

## 🏷️ Tags / Keywords
**Add tags to help organize (comma-separated):**

competitive-intelligence, theater-industry, web-scraping, streamlit, python, pricing-analysis, business-intelligence, saas, automation, data-analytics, playwright, real-time, enterprise

---

---

## 📎 Attachments / Files (Selected)
- `db_adapter.py` – compatibility layer for legacy calls
- `db_models.py` – authoritative ORM schema
- `data_management_v2.py` – centralized data operations
- `theater_cache.json` – cached theater + market structure
- `scheduler_service.py` – background / future cron tasks
- `tests/` – suite (needs PostgreSQL updates for some cases)

---

## 📝 Additional Notes
**Recent architectural change log (summary):**
- Migrated core persistence from raw SQLite calls to SQLAlchemy (supports PostgreSQL in production, keeps lightweight SQLite fallback).
- Introduced multi-tenancy via `company_id` & `set_current_company()` at login.
- Introduced `data_management_v2.py` to centralize all CRUD operations, refactoring away from ad-hoc data handling.
- Patched failing admin flows (user listing / updates) due to `conn.execute()` remnants.
- Resolved invalid bcrypt hash & unified password update semantics.
- Repaired Operating Hours persistence (data shape & column name alignment).
- Adapted scraper to Fandango structural changes (DOM selectors & time parsing from `aria-label`).
- Added debug verbosity for showings & scrape run creation to aid migration QA.
- Identified remaining blockers: price scrape invocation mismatch (extra kwarg), scrape run context storage, test suite PostgreSQL alignment.

**Key constraints / risks:**
- Upstream DOM volatility (Fandango) necessitates resilient selector abstraction.
- Threaded async wrapper currently swallows TypeErrors; needs surfaced exception handling.
- No Alembic migrations yet – manual schema drift risk.
- Secret management pending (STATIC `SECRET_KEY` warning in logs).

**Known Issues (version pinning):**
- **Streamlit pinned to v1.38.0** (2025-11-26): Versions 1.39+ have a regression where `st.download_button` behind nginx proxy causes files to download with UUID/hash filenames (e.g., `592c389120823a6813fd...xlsx`) instead of the specified filename. This affects all download functionality (CSV, Excel, PDF). Root cause appears to be changes in how Streamlit handles Content-Disposition headers through reverse proxies.
  - **Workaround:** Pin `streamlit==1.38.0` in `requirements.txt`
  - **Test newer versions:** Check if downloads produce correct filenames (e.g., `daily_lineup_Theater_2025-11-26.xlsx`)
  - **Track upstream:** https://github.com/streamlit/streamlit/issues (search "download filename proxy")

**Near-term priorities:** Stabilize price scrape end-to-end, add structured error reporting, then parallelize theater scrapes for performance.

---

## 🔗 Related Projects
**Is this connected to any other projects?**

- Parent Project: ________________
- Related Projects: ________________

---

## 🎨 Special Fields (Optional)

### For Software Projects:
**Tech Stack:** Python 3.11, Streamlit, Playwright (Chromium), SQLAlchemy, PostgreSQL (prod) / SQLite (dev fallback), bcrypt, Pandas, BeautifulSoup, Docker
**Repository URL:** (private) – Provided locally (`PriceScout` repository)
**Key Modules:** `db_adapter.py`, `db_models.py`, `data_management_v2.py`, `price_scout_app.py`, modes (`market_mode.py`, `analysis_mode.py`, etc.)
**Security:** BCrypt hashing, RBAC, pending SECRET_KEY rotation
**Observability (planned):** Structured logging + optional App Insights

### For Research Projects:
**Research Question:** ________________
**Data Sources:** ________________

### For Physical Builds (PC, Car, etc.):
**Component List:**
- Component 1: ________________
- Component 2: ________________

### For Creative Projects:
**Creative Brief:** ________________
**Inspiration:** ________________

---

## 📤 Re-Uploading This Template

### Method 1: Print & Handwriting
1. Print this template
2. Fill out changes by hand
3. In project worksheet, click "Upload Template"
4. Choose "Merge" mode to add to existing data
5. Or choose "Replace" mode to overwrite completely

### Method 2: Edit Digitally
1. Edit this file in any text editor
2. Save changes
3. In project worksheet, click "Upload Template"
4. Select this file

---

**Generated by 626 Labs - Project Management Reimagined**
**Export Date:** 11/26/2025 (updated)
**https://project-626labs.web.app**
