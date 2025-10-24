# Price Scout - Test Failure Report

**Overall Status:** 34 out of 127 tests are failing.

---

#### **High Priority Issues**

These issues are critical and likely impact the core functionality of the application.

1.  **Ticket Information Parsing (`test_ticket_parsing.py`):**
    *   **Issue:** 16 different tests related to parsing ticket descriptions are failing. The function responsible for identifying the base ticket type (e.g., "Adult", "Child") and amenities (e.g., "IMAX", "3D") from a string is not working correctly.
    *   **Impact:** This is a critical failure. If the app cannot correctly parse ticket descriptions, the collected price data will be miscategorized or incomplete, making any subsequent analysis unreliable. For example, it's incorrectly identifying "Adult with D-BOX" as having a "With" amenity.

2.  **Live Fandango Scraping (`test_scraper_async.py`):**
    *   **Issue:** Live tests that attempt to scrape actual data from Fandango are failing. The scraper is not extracting ticket prices or seating capacity information.
    *   **Impact:** This indicates that the scraper is likely broken for live data. The structure of the Fandango website may have changed, rendering the current scraping logic obsolete.

3.  **Core Scraper Unit Tests (`app/test_scraper_unit.py`):**
    *   **Issue:** Unit tests for the scraper's price and capacity extraction logic are failing. The tests indicate that the scraper cannot find the necessary data in the provided mock HTML.
    *   **Impact:** This points to a fundamental problem in the scraping logic itself, separate from any live website changes.

4.  **Database and Data Management (`test_data_management.py`):**
    *   **Issue:** Tests for merging external databases and saving film details are failing. The database merge test shows an incorrect number of rows being added, and the film upsert test is failing due to a missing parameter (`:domestic_gross`).
    *   **Impact:** The application may not be able to correctly import data from other sources or save new film information, which is crucial for data analysis.

---

#### **Medium Priority Issues**

These issues represent significant bugs that affect application features but may not be as critical as the high-priority items.

1.  **Concurrent Scraping (`app/test_scraper_concurrent.py`):**
    *   **Issue:** Tests for concurrent scraping are failing because the underlying Playwright functions are not being called as expected in the mocked environment.
    *   **Impact:** The concurrency feature, which is important for performance, may not be working as intended.

2.  **Analysis and Reporting (`test_analysis_mode.py`, `test_app_workflow.py`):**
    *   **Issue:** Tests for generating analysis reports are failing. One test produces an empty report, and another indicates that the UI is not behaving as expected. The weekly operating hours report is also not being saved correctly.
    *   **Impact:** The data analysis and reporting features of the application are likely unreliable.

3.  **End-to-End and Market Mode Workflows (`test_end_to_end.py`, `test_market_mode.py`):**
    *   **Issue:** The end-to-end test for the market mode workflow is failing because the scraping function is being called multiple times when it should only be called once. A related failure shows that the `REPORTS_DIR` is not configured during the test run.
    *   **Impact:** This suggests a potential logic flaw in the UI workflow that could lead to unintended behavior and repeated scraping.

---

#### **Low Priority Issues**

These are minor issues or problems in non-critical areas.

1.  **OMDb Client (`test_omdb_client.py`):**
    *   **Issue:** The tests are failing with a `KeyError: 'box_office_gross'`. This means the OMDb API is no longer returning data in the format the application expects.
    *   **Impact:** This affects the enrichment of film data with financial information but does not break the core scraping functionality.

2.  **Utility Functions (`test_utils.py`):**
    *   **Issue:** The `estimate_scrape_time_by_theaters` function is returning an incorrect value.
    *   **Impact:** The UI may display an inaccurate time estimate to the user, which is a minor usability issue.
