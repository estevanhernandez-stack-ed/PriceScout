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

PriceScout is a production-oriented competitive intelligence and ticket pricing analysis platform for theatrical exhibitors. It supports multiple scrape modes (Market Mode, CompSnipe, Poster, Operating Hours), role-based access control, theater matching, operating hours derivation, and pricing history analytics. The data layer is currently being migrated from a legacy SQLite implementation to a multi‑tenant PostgreSQL + SQLAlchemy architecture. Recent work includes adapting to a breaking change in Fandango's DOM structure, refactoring operating hours persistence, and hardening user / admin workflows. Export, reporting, and film metadata enrichment (OMDb) remain integral features.

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
17. [x] Update imports to use `db_adapter` instead of legacy `database.py`
18. [x] Add company context initialization on login (multi-tenancy)
19. [x] Fix column name mismatches (`is_active`, `company_name`, FK ids)
20. [x] Replace invalid bcrypt seed & normalize password change workflow
21. [x] Refactor operating hours save to ORM (list/dict format support)
22. [x] Repair admin user management functions (PostgreSQL-safe queries)
23. [x] Adapt scraper to new Fandango DOM (`li.shared-movie-showtimes`, `aria-label` time parsing)
24. [x] Add debug instrumentation for scrape run creation & showings persistence
25. [x] Fix IndentationError / import hygiene in `utils.py`

**Pending / next steps:**
26. [ ] Re-enable full price scrape flow (remove stray kwargs, ensure `selected_showtimes` session population)
27. [ ] Persist scrape run context (add separate context/metadata table or JSON field)
28. [ ] Add migration scripts (Alembic) for future schema evolution
29. [ ] Harden error surfacing (surface async thread exceptions in UI status blocks)
30. [ ] Rebuild failing / outdated tests (admin + theming) for PostgreSQL path
31. [ ] Implement async batch scraping (parallel theater contexts) for performance
32. [ ] Add observability (structured logs + optional Application Insights key)
33. [ ] Resume pricing history backfill under new schema
34. [ ] Security pass: rotate SECRET_KEY & vault-managed credentials
35. [ ] Improve PDF report rendering (film grouping, page breaks)
36. [ ] Add market-level aggregate dashboards (median price, PLF penetration)
37. [ ] Optional: Introduce caching layer (Redis) for repeated theater lookups

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
- `theater_cache.json` – cached theater + market structure
- `scheduler_service.py` – background / future cron tasks
- `tests/` – suite (needs PostgreSQL updates for some cases)

---

## 📝 Additional Notes
**Recent architectural change log (summary):**
- Migrated core persistence from raw SQLite calls to SQLAlchemy (supports PostgreSQL in production, keeps lightweight SQLite fallback).
- Introduced multi-tenancy via `company_id` & `set_current_company()` at login.
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
**Key Modules:** `db_adapter.py`, `db_models.py`, `price_scout_app.py`, modes (`market_mode.py`, `analysis_mode.py`, etc.)
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
**Export Date:** 11/13/2025, 9:45:44 PM
**https://project-626labs.web.app**
