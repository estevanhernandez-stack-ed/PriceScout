### How the App Works

The PriceScout application is a Streamlit-based web interface designed for competitive price analysis in the movie theater industry. It's a powerful tool that allows users to gather, store, and analyze ticket pricing data from Fandango.

Here's a breakdown of its core components and functionality:

*   **Three Main Modes:**
    *   **Market Mode:** This is the primary mode for analyzing pre-defined markets. Users can select a director, a market (e.g., a city or region), and then specific theaters within that market. They can then choose which movies and showtimes to scrape, generating a live pricing report.
    *   **CompSnipe Mode:** This mode is designed for ad-hoc competitive analysis. Instead of selecting from pre-defined markets, users can search for theaters by ZIP code. This is useful for quickly gathering intelligence on competitors that are not part of the user's primary market.
    *   **Analysis Mode:** This mode provides historical data analysis. Users can query the database of previously scraped prices to identify trends. They can filter by theaters, date ranges, films, and dayparts (e.g., Matinee, Prime) to generate pivot tables that show price evolution over time.

*   **Scraping Engine:**
    *   The scraping logic is encapsulated in the `scraper.py` file.
    *   It uses the `playwright` library to control a headless browser, which allows it to scrape dynamic web pages that rely on JavaScript.
    *   It also uses `BeautifulSoup` for parsing the HTML content.
    *   The scraper is responsible for fetching theater information, movie showtimes, and detailed pricing information for each ticket type.

*   **Database:**
    *   The application uses a SQLite database (`price_scout.db`) to store the scraped data.
    *   The `database.py` file contains all the functions for interacting with the database, including creating the schema, saving new data, and querying historical records.
    *   This historical data is the foundation of the "Analysis Mode".

*   **User Interface:**
    *   The UI is built entirely with Streamlit.
    *   The main application file, `price_scout_app.py`, defines the overall layout and flow of the application.
    *   It uses custom CSS to create a branded look and feel.
    *   The `ui_components.py` file contains reusable UI elements, such as the daypart selector.

*   **Configuration and Utilities:**
    *   `config.py` centralizes all the important file paths and constants, making the application easier to configure.
    *   `utils.py` provides a collection of helper functions for common tasks like running asynchronous operations in a separate thread (to keep the UI responsive), formatting data for display, and managing the application's state.

### Potential Improvements

The application is already quite powerful, but here are some areas where it could be improved:

*   **Code Modularity and Organization:**
    *   The `price_scout_app.py` file is very large and contains the UI logic for all three modes. To improve maintainability, the UI code for each mode should be moved into its respective file in the `app_pages` directory (e.g., `market_mode.py`, `compsnipe_mode.py`, `analysis_mode.py`). The main app file would then be responsible for loading and displaying the appropriate page based on the selected mode.
    *   Similarly, the `scraper.py` file could be broken down into smaller, more specialized modules. For example, all the Fandango-specific scraping logic could be moved into its own class or module. This would make it easier to add new data sources in the future.

*   **Error Handling and Robustness:**
    *   The current error handling is somewhat basic. When a scrape fails, the application often just displays a generic error message. A more robust error handling strategy would be to:
        *   Implement more specific error handling for different types of failures (e.g., network errors, changes in the website's layout).
        *   Provide more informative error messages to the user.
        *   In cases where a single theater fails to scrape, the application could be designed to continue with the remaining theaters and report the failure at the end.

*   **Performance and Caching:**
    *   The use of `playwright` is necessary for scraping dynamic content, but it can be slow. A performance analysis could be done to identify any bottlenecks in the scraping process.
    *   The application could benefit from a more sophisticated caching mechanism. For example, caching the results of film searches for a short period could significantly improve the user experience.

*   **New Features and Enhancements:**
    *   **Support for More Data Sources:** The application currently only supports Fandango. Adding support for other major ticketing platforms (e.g., AMC, Regal, Cinemark) would provide a much more comprehensive view of the competitive landscape.
    *   **Advanced Analytics:** The "Analysis Mode" could be extended with more advanced analytical features, such as:
        *   Price elasticity modeling to understand how price changes affect demand.
        *   A competitor benchmarking dashboard to compare pricing strategies.
        *   Automated anomaly detection to flag unusual pricing patterns.
    *   **User Accounts and Personalization:** Instead of a single password, the application could be enhanced with a full-fledged user authentication system. This would allow for personalized settings, saved reports, and more granular access control.
    *   **Notifications:** The task scheduler is a great feature. It could be made even more useful by adding email or other notification options to alert users when a scheduled scrape is complete or if an error occurs.

### Other Important Considerations

*   **Testing:** The application currently lacks an automated test suite. Adding unit tests for the business logic (especially in `scraper.py` and `database.py`) and integration tests for the UI would significantly improve the code quality and make it easier to maintain and extend in the future.
*   **Security:** The use of `st.secrets` for password management is a good practice. However, if the application is to be deployed in a multi-user environment, a more robust authentication and authorization system should be implemented.
*   **Deployment:** The application is built with Streamlit, which makes it relatively easy to deploy. For a production environment, it would be important to follow best practices for deploying and securing Streamlit applications.
