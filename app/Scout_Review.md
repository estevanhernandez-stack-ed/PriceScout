# Price Scout Application Review

**Version:** v30.1
**Review Date:** 2025-09-28

## 1. Executive Summary

Price Scout is a robust and feature-rich Streamlit application for scraping and analyzing movie ticket pricing data from Fandango. The application is well-structured, leveraging a modular design that separates concerns effectively. A recent major refactoring of the database architecture has made the application's data handling more resilient and powerful. The application is stable, fully tested, and ready for further feature enhancements.

The core scraping logic is powerful, utilizing `playwright` for dynamic content and `BeautifulSoup` for parsing, with intelligent error handling and data extraction techniques. The application is in a strong state, and the following review provides recommendations for polishing and ensuring long-term stability.

## 2. Architecture and Design

The application follows a well-defined, multi-layered architecture.

-   **Presentation Layer (UI):** `price_scout_app.py` serves as the main entry point, with UI components abstracted into `ui_components.py`. The use of different "modes" (`market_mode.py`, `compsnipe_mode.py`, etc.) is an excellent choice for separating the logic of different application features.
-   **Business Logic Layer (Scraping & Data Processing):** The `scraper.py` module encapsulates the core web scraping functionality. This is a clean separation that allows the UI to be independent of the scraping implementation. Data processing and utility functions are correctly placed in `utils.py`.
-   **Data Access Layer:** The `database.py` module provides a clear and concise API for all database interactions, abstracting the SQL queries from the rest of the application. The use of an SQLite database is appropriate for this type of application.
-   **Configuration:** Application-level constants and paths are centralized in `config.py`, which is a best practice.

**Strengths:**

*   **Modularity:** The separation of concerns between UI, scraping logic, and data persistence is excellent.
*   **State Management:** The application makes effective use of Streamlit's session state to manage user interactions and workflow.
*   **Asynchronous Operations:** The use of `asyncio` and `threading` to run long-running scraping tasks without blocking the UI is a critical and well-implemented feature.
*   **Code Reusability:** Functions are well-factored into modules like `utils.py` and `ui_components.py`.

**Recommendations:**

*   **(Future Consideration) Configuration Management:** For even greater robustness, consider using a library like `pydantic` for settings management, which can provide validation and type hinting for configuration values.

## 3. Code Quality and Maintainability

The code is generally clean, readable, and well-organized.

**Strengths:**
*   **Readability:** The code is well-formatted and uses clear variable and function names.
*   **Modularity:** The codebase is broken down into logical modules, which makes it easier to navigate and understand.
*   **Refactoring:** The codebase shows a clear commitment to continuous improvement, with complex logic being consistently broken down into smaller, more manageable functions.

**Recommendations:**

*   **Docstrings and Comments:** **(Good)** The data and scraping layers have good docstrings. As the UI logic in the `modes` directory continues to evolve, adding more comments to explain complex state interactions will be beneficial for long-term maintenance.
*   **Error Handling:** **(Good)** The application correctly handles specific errors like `TimeoutError` and `JSONDecodeError` in the scraping layer and provides user-friendly feedback. This is a best practice that should be continued.

## 4. Testing

The test suite is comprehensive and stable, with all tests passing. This provides a solid foundation of reliability for the application. The suite covers:
*   **Unit Tests:** For individual functions in `scraper.py`, `utils.py`, and `data_management_v2.py`.
*   **Integration Tests:** To verify module interactions and database operations.
*   **Component Logic Tests:** For UI and data parsing logic in the various application modes.

**Recommendations:**

*   **Maintain and Expand Test Coverage:** As new features are added, continue to write corresponding tests to maintain the stability of the application. The current structure provides an excellent template for future tests.

## 5. UI/UX and Feature Polish

The application is in a great state. The UI is consistent and provides good user feedback.

*   **Loading Spinners & User Guidance:** The application uses `st.spinner` effectively for all long-running tasks and provides helpful `st.info` and `st.warning` messages to guide the user, especially for empty data states or time-sensitive scrapes.
*   **Consistent Styling:** The `theming.py` module and custom CSS provide a consistent and polished look and feel across all application modes.

## 6. Core Technologies and Implementation

This section details the key Python libraries and tools used in Price Scout and how they are integrated to create a cohesive and powerful application.

*   **Streamlit (Web Framework):**
    *   **Implementation:** Streamlit is the backbone of the user interface. The main application file, `price_scout_app.py`, orchestrates the UI, manages application-wide state via `st.session_state`, and dispatches rendering to different "mode" modules (e.g., `market_mode.py`, `analysis_mode.py`). These modules use a wide range of Streamlit components (`st.button`, `st.dataframe`, `st.spinner`, etc.) to create an interactive and responsive user experience.

*   **Playwright (Browser Automation):**
    *   **Implementation:** Playwright is the engine behind the data collection, managed within `scraper.py`. It launches a headless browser to navigate Fandango's dynamic, JavaScript-heavy pages, which a simpler library like `requests` could not handle. It is used to perform searches, click on elements to reveal showtimes, and extract the page source for parsing.

*   **BeautifulSoup (HTML/XML Parser):**
    *   **Implementation:** Once Playwright retrieves the page content, `scraper.py` uses BeautifulSoup to parse the HTML. It navigates the document tree to find specific elements by their tags, classes, and attributes, extracting raw data like film titles, showtimes, and ticketing URLs.

*   **Pandas (Data Manipulation):**
    *   **Implementation:** Pandas is used extensively throughout the application for data handling. In `analysis_mode.py`, it's used to aggregate, pivot, and calculate statistics for generating reports and charts. In `database.py`, it's used to read SQL query results into DataFrames for easier manipulation. It is the primary tool for transforming raw scraped data into structured formats for display and download.

*   **Asyncio & Threading (Concurrency):**
    *   **Implementation:** The application uses a sophisticated concurrency model to prevent the UI from freezing during long-running scrapes. The `run_async_in_thread` function in `utils.py` is a key component. It runs the `asyncio`-based Playwright scraping code in a separate `threading.Thread`, allowing the Streamlit front-end to remain responsive and display progress updates.

*   **SQLite3 (Database):**
    *   **Implementation:** The application uses Python's built-in `sqlite3` module for data persistence. All database logic is abstracted into the `database.py` module, which handles creating the schema, inserting new records (`showings`, `prices`), and executing complex queries to retrieve data for the analysis modes.

*   **Altair (Declarative Visualization):**
    *   **Implementation:** In `analysis_mode.py`, Altair is used to create interactive data visualizations. It takes Pandas DataFrames as input and generates charts like bar charts, line charts, and scatter plots to help users visually analyze trends in the historical data.

*   **Pytest (Testing Framework):**
    *   **Implementation:** The `tests/` directory contains a comprehensive suite of tests built with `pytest`. It uses mocking (`unittest.mock`) to isolate components and test individual functions (unit tests) as well as the interaction between different parts of the application (integration tests), ensuring code reliability and stability.

## 7. Key Features and Recent Enhancements
This section highlights the key features and recent improvements that make Price Scout a powerful analysis tool.

*   **Multi-Modal Analysis:** The application is divided into distinct modes for different analysis tasks:
    *   **Market Mode:** For broad scrapes across defined markets.
    *   **CompSnipe Mode:** For targeted, live searches by ZIP code or theater name.
    *   **Poster Board:** For visually discovering and selecting films to analyze.
    *   **Operating Hours Mode:** For analyzing and comparing theater operation schedules.
    *   **Historical Analysis Mode:** For deep-diving into the collected data with filters and charts.

*   **Robust Data Management:** A dedicated "Data Management" area provides tools for:
    *   **Theater Cache Management:** Building and rebuilding the cache of Fandango theater names and URLs.
    *   **Data Quality:** Reviewing and correcting unmatched film titles and ticket types.
    *   **Database Tools:** Backfilling historical data, enriching film metadata from OMDb and Box Office Mojo, and merging external databases.

*   **"Market At a Glance" Report:** A sophisticated, automatic report in "Analysis Mode" that provides a summary of core ticket prices (Matinee/Evening for Adult/Senior/Child) for each theater in a selected market. It intelligently identifies potential surcharge pricing, provides context for new releases, and prompts the user to re-scrape if the market's data is outdated.

*   **Concurrent Scraping and Enrichment:** Film discovery and data enrichment processes run concurrently using `asyncio`, dramatically speeding up data collection and providing a more responsive user experience.

*   **Task Scheduling and Automation:** The application features a Task Scheduler for automating data collection. Users can define, manage, and schedule scrapes to run at specific times, turning Price Scout into an autonomous monitoring platform.