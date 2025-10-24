import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.scraper import Scraper
import datetime
from playwright.async_api import Page

@pytest.mark.asyncio
async def test_scrape_details_concurrent_behavior():
    # Mock the Scraper instance and its dependencies
    scraper = Scraper(headless=True, devtools=False)

    # Mock _get_prices_and_capacity to simulate price fetching
    # This mock will be called concurrently for each showing
    mock_get_prices_and_capacity = AsyncMock()
    scraper._get_prices_and_capacity = mock_get_prices_and_capacity

    # Configure the mock to return different data for different showings
    # We'll use a side_effect to return specific data based on the call order
    mock_get_prices_and_capacity.side_effect = [
        # Showing 1: Film A, 10:00am
        {"tickets": [{"type": "Adult", "price": "$15.00", "amenities": []}], "capacity": "Available", "error": None},
        # Showing 2: Film B, 11:00am
        {"tickets": [{"type": "Child", "price": "$10.00", "amenities": ["3D"]}], "capacity": "Available", "error": None},
        # Showing 3: Film C, 01:00pm
        {"tickets": [{"type": "Senior", "price": "$12.00", "amenities": []}], "capacity": "Available", "error": None},
        # Showing 4: Film D, 02:00pm
        {"tickets": [{"type": "Adult", "price": "$18.00", "amenities": ["IMAX"]}], "capacity": "Available", "error": None},
    ]

    # Mock Playwright components
    # Each call to new_page should return a distinct mock page
    mock_page = AsyncMock(spec=Page)
    
    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    
    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    # Patch async_playwright to return our mock
    # --- FIX: Patch the async context manager correctly ---
    mock_playwright_cm = AsyncMock()
    mock_playwright_cm.__aenter__.return_value = mock_playwright
    with patch('app.scraper.async_playwright', return_value=mock_playwright_cm), \
         patch('app.scraper.logger'): # Patch logger to suppress output
        
        # Define input data
        theaters = [{"name": "Test Theater", "url": "http://example.com/test-theater"}]
        selected_showtimes = {
            "2025-01-01": {
                "Test Theater": {
                    "Film A": {
                        "10:00am": [{"ticket_url": "http://example.com/ticket1", "film_title": "Film A", "showtime": "10:00am", "daypart": "Matinee", "format": "2D"}]
                    },
                    "Film B": {
                        "11:00am": [{"ticket_url": "http://example.com/ticket2", "film_title": "Film B", "showtime": "11:00am", "daypart": "Matinee", "format": "3D"}]
                    }
                }
            },
            "2025-01-02": {
                "Test Theater": {
                    "Film C": {
                        "01:00pm": [{"ticket_url": "http://example.com/ticket3", "film_title": "Film C", "showtime": "01:00pm", "daypart": "Matinee", "format": "2D"}]
                    },
                    "Film D": {
                        "02:00pm": [{"ticket_url": "http://example.com/ticket4", "film_title": "Film D", "showtime": "02:00pm", "daypart": "Matinee", "format": "IMAX"}]
                    }
                }
            }
        }
        status_container = ["Initializing..."]

        # Call the function under test
        all_price_data, showings_attempted = await scraper.scrape_details(theaters, selected_showtimes, status_container)

        # Assertions
        # 1. Verify Playwright components were called correctly
        mock_playwright.chromium.launch.assert_called_once_with(headless=True, devtools=False)
        mock_browser.new_context.assert_called_once()
        # new_page should be called once for each concurrent task (4 showings in this case)
        assert mock_context.new_page.call_count == 4
        mock_browser.close.assert_called_once()
        # The worker function doesn't close the page, so we don't assert that.

        # 2. Verify _get_prices_and_capacity was called for all showings
        assert mock_get_prices_and_capacity.call_count == 4
        
        # 3. Verify the output data structure and content
        assert len(all_price_data) == 4
        assert len(showings_attempted) == 4

        # Check a sample of the processed data
        film_a_data = next(item for item in all_price_data if item['Film Title'] == 'Film A')
        assert film_a_data['Price'] == '$15.00'
        assert film_a_data['Format'] == '2D' # Original format was 2D, no amenities added

        film_b_data = next(item for item in all_price_data if item['Film Title'] == 'Film B')
        assert film_b_data['Price'] == '$10.00'
        assert film_b_data['Format'] == '3D' # Original format was 3D, no amenities added

        film_d_data = next(item for item in all_price_data if item['Film Title'] == 'Film D')
        assert film_d_data['Price'] == '$18.00'
        assert film_d_data['Format'] == 'IMAX' # Original format was IMAX, no amenities added

        # 4. Verify status container updates (at least the last one)
        assert "Scraping showing" in status_container[0]

        # 5. Verify that the showings_attempted list contains the correct details
        expected_showings_attempted_titles = {"Film A", "Film B", "Film C", "Film D"}
        actual_showings_attempted_titles = {s['film_title'] for s in showings_attempted}
        assert actual_showings_attempted_titles == expected_showings_attempted_titles

@pytest.mark.asyncio
async def test_scrape_details_concurrent_error_handling():
    """
    Tests that `scrape_details` handles errors gracefully when one of the
    concurrent `_get_prices_and_capacity` calls fails.
    """
    # Mock the Scraper instance and its dependencies
    scraper = Scraper(headless=True, devtools=False)

    # Mock _get_prices_and_capacity to simulate a mix of success and failure
    mock_get_prices_and_capacity = AsyncMock()
    scraper._get_prices_and_capacity = mock_get_prices_and_capacity

    mock_get_prices_and_capacity.side_effect = [
        # Showing 1: Success
        {"tickets": [{"type": "Adult", "price": "$15.00", "amenities": []}], "capacity": "Available", "error": None},
        # Showing 2: Failure
        {"tickets": [], "capacity": "N/A", "error": "Simulated scrape failure"},
        # Showing 3: Success
        {"tickets": [{"type": "Senior", "price": "$12.00", "amenities": []}], "capacity": "Available", "error": None},
    ]

    # Mock Playwright components
    mock_page = AsyncMock(spec=Page)
    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    # Patch async_playwright and the logger to capture error logs
    # --- FIX: Patch the async context manager correctly ---
    mock_playwright_cm = AsyncMock()
    mock_playwright_cm.__aenter__.return_value = mock_playwright
    with patch('app.scraper.async_playwright', return_value=mock_playwright_cm), \
         patch('app.scraper.logger') as mock_logger:
        
        # Define input data for 3 showings
        theaters = [{"name": "Test Theater", "url": "http://example.com/test-theater"}]
        selected_showtimes = {
            "2025-01-01": {
                "Test Theater": {
                    "Film A": {"10:00am": [{"ticket_url": "url1", "film_title": "Film A", "showtime": "10:00am", "daypart": "Matinee"}]},
                    "Film B": {"11:00am": [{"ticket_url": "url2", "film_title": "Film B", "showtime": "11:00am", "daypart": "Matinee"}]},
                    "Film C": {"01:00pm": [{"ticket_url": "url3", "film_title": "Film C", "showtime": "01:00pm", "daypart": "Matinee"}]}
                }
            }
        }
        status_container = ["Initializing..."]

        # Call the function under test
        all_price_data, showings_attempted = await scraper.scrape_details(theaters, selected_showtimes, status_container)

        # Assertions
        # 1. Verify Playwright components were still called for all tasks
        assert mock_context.new_page.call_count == 3
        mock_browser.close.assert_called_once()

        # 2. Verify _get_prices_and_capacity was called for all 3 showings
        assert mock_get_prices_and_capacity.call_count == 3

        # 3. Verify the logger was called with an error for the failed showing
        mock_logger.error.assert_called_once()
        log_message = mock_logger.error.call_args[0][0]
        assert "Scraping Film B at Test Theater: Simulated scrape failure" in log_message

        # 4. Verify the output data contains only the successful scrapes
        assert len(all_price_data) == 2 # Only Film A and Film C should be in the results
        
        # 5. Verify the list of attempted showings includes all of them
        assert len(showings_attempted) == 3

        # 6. Check the content of the successful results
        film_a_data = next((item for item in all_price_data if item['Film Title'] == 'Film A'), None)
        film_c_data = next((item for item in all_price_data if item['Film Title'] == 'Film C'), None)
        film_b_data = next((item for item in all_price_data if item['Film Title'] == 'Film B'), None)

        assert film_a_data is not None
        assert film_c_data is not None
        assert film_b_data is None # The failed showing should not be in the final data

        assert film_a_data['Price'] == '$15.00'
        assert film_c_data['Price'] == '$12.00'