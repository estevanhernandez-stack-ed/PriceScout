# Price Scout - Project Brief

## Project Goal
A Streamlit application that scrapes movie showtimes, ticket prices, and theater information from Fandango for competitive analysis and stores it in a database.

## Current Status
The application is stable and feature-rich, with a robust data architecture that separates showing information from price data. All tests are passing, and the focus has shifted from stabilization to feature enhancement and improving the user experience.

## My Role
As a senior Python developer, my role is to help fix errors, improve the code, and add new features. I will use the existing `pytest` test suite and create new tests where necessary to validate my changes.

## Immediate Objectives
1.  **Enhance Analysis Mode:** Continue building out the "Analysis Mode" with more charts, filters, and summary statistics to provide deeper insights into the historical data.
2.  **Improve User Experience:** Look for opportunities to make the application more intuitive, such as adding summary tables, improving report layouts, and ensuring consistent UI patterns.
3.  **Maintain Stability:** Continue to write tests for all new features to ensure the application remains stable and reliable.
4.  **Test Test Test:** And make tests for new modes as we go along and you notice changes to code save times.

## Key Files
*   `app/price_scout_app.py`: The main Streamlit application file (UI).
*   `app/scraper.py`: Contains the core logic for scraping Fandango.
*   `app/database.py`: Manages the connection and interaction with the database.
*   `app/data_management_v2.py`: Handles data processing and management post-scraping.
*   `tests/`: Contains all the pytests for the application.
*   `app/Scout_Review.md`: Contains notes on issues found during the refactor.

## Commands
*   **Run the application:** `streamlit run app/price_scout_app.py`
*   **Run all tests:** `pytest`
*   **Run tests with coverage report:** `pytest --cov=app --cov-report=term-missing`

---
*This document will be updated as project priorities change.*

---

## Gemini State Summary
*This section is for Gemini Code Assist's internal use. It must be updated at the end of each session to reflect the current project state. Last updated: 2025-09-16*

```
# PROJECT STATE v30.1

status: STABLE
tests: 87/87 PASS

# Core Architecture
db_schema: v2 (showings, prices) # CRITICAL: Separated showings from prices.
data_capture:
  - showings: upsert on discovery (market/compsnipe modes)
  - prices: saved on explicit price scrape
  - play_date: correctly captured.

# Key Features Implemented
features:
  - multi_company_arch
  - data_management:
    - company_onboarding
    - cache_builder (full_scan)
    - db_import_export
    - db_migration_tool (v1_to_v2_schema) # IMPORTANT
    - play_date_backfill_tool (v2 logic)
  - op_hours_mode:
    - manual_scrape
    - weekly_report_auto (thu-thu, comparison, consolidation)
  - analysis_mode:
    - type: "Film" # New workflow
      - summary_report (total_showings, num_theaters, avg_price)
      - theater_drilldown (chart + table)
    - type: "Theater" # Original workflow
      - date_range_selector
      - filters: [Film, Daypart, Format, Ticket Type, "Sold Out?"]
      - charts: [avg_price_bar, price_trend_line, daypart_dist_bar, showtimes_per_day_line]
      - report_formatting: (play_date_first, headers, no_index)
  - ui_ux:
    - theming
    - scrape_timers
    - theater_expander_showtime_count
  - poster_mode:
    - film_selection
    - theater_selection
    - showtime_scraping

# Immediate Objectives
next_objectives:
  - enhance_analysis_mode:
    - add_summary_stats_table
    - add_new_charts (e.g., pie chart for capacity)
  - improve_ux:
    - review report layouts
    - ensure UI consistency
  - maintain_stability:
    - test_new_features
```