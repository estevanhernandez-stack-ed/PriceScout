import pytest
import json
from unittest.mock import AsyncMock, patch
from app.scraper import Scraper
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

# Sample HTML content mimicking the Fandango ticketing page structure
SAMPLE_HTML_TEMPLATE = """
<html>
<head><title>Tickets</title></head>
<body>
    <h1>Buy Tickets</h1>
    <script>
        // Some other javascript
        var someVar = 'hello';
    </script>
    <script>
        window.Commerce.models = {json_payload}
        // Some other code
        console.log('init');
    </script>
</body>
</html>
"""

# A valid JSON payload for the test
VALID_JSON_PAYLOAD = """
{
    "tickets": {
        "seatingAreas": [
            {
                "isSoldOut": false,
                "ticketTypes": [
                    {
                        "description": "Adult Ticket",
                        "price": 15.50
                    },
                    {
                        "description": "Child (with 3D)",
                        "price": 12.00
                    }
                ]
            }
        ]
    }
}
"""

SOLD_OUT_JSON_PAYLOAD = """
{
    "tickets": {
        "seatingAreas": [
            {
                "isSoldOut": true,
                "ticketTypes": []
            }
        ]
    }
}
"""

@pytest.fixture
def scraper_instance():
    """Provides a Scraper instance for tests."""
    return Scraper(headless=True)

@pytest.mark.asyncio
async def test_get_prices_and_capacity_success(scraper_instance):
    """
    Tests successful extraction of prices and capacity from a standard HTML structure.
    """
    # --- Setup ---
    mock_page = AsyncMock()
    # Configure the mock to return the sample HTML when page.content() is called
    html_with_valid_json = SAMPLE_HTML_TEMPLATE.format(json_payload=VALID_JSON_PAYLOAD)
    mock_page.content.return_value = html_with_valid_json
    mock_page.query_selector_all.return_value = [AsyncMock(inner_html=AsyncMock(return_value=f'window.Commerce.models = {VALID_JSON_PAYLOAD}'))]
    
    showing_details = {'ticket_url': 'http://example.com/ticket'}

    # --- Execution ---
    result = await scraper_instance._get_prices_and_capacity(mock_page, showing_details)

    # --- Assertions ---
    mock_page.goto.assert_called_once_with('http://example.com/ticket', timeout=60000)
    # Verify the results are parsed correctly
    assert result['error'] is None
    assert result['capacity'] == "Available"
    assert len(result['tickets']) == 2
    
    # Check ticket details
    adult_ticket = next(t for t in result['tickets'] if t['type'] == 'Adult')
    child_ticket = next(t for t in result['tickets'] if t['type'] == 'Child')
    
    assert adult_ticket['price'] == '$15.50'
    assert adult_ticket['amenities'] == ['Ticket']
    assert child_ticket['price'] == '$12.00'
    assert '3D' in child_ticket['amenities']

@pytest.mark.asyncio
async def test_get_prices_and_capacity_sold_out(scraper_instance):
    """
    Tests that 'Sold Out' capacity is correctly identified.
    """
    mock_page = AsyncMock()
    html_with_sold_out_json = SAMPLE_HTML_TEMPLATE.format(json_payload=SOLD_OUT_JSON_PAYLOAD)
    mock_page.content.return_value = html_with_sold_out_json
    mock_page.query_selector_all.return_value = [AsyncMock(inner_html=AsyncMock(return_value=f'window.Commerce.models = {SOLD_OUT_JSON_PAYLOAD}'))]
    
    result = await scraper_instance._get_prices_and_capacity(mock_page, {'ticket_url': 'url'})
    
    assert result['error'] is None
    assert result['capacity'] == "Sold Out"
    assert len(result['tickets']) == 0

@pytest.mark.asyncio
async def test_get_prices_and_capacity_no_json_object(scraper_instance):
    """
    Tests the function's behavior when the 'window.Commerce.models' object is not found.
    """
    mock_page = AsyncMock()
    # HTML is missing the 'window.Commerce.models' assignment
    html_without_json = "<html><body><script>var x = 1;</script></body></html>"
    mock_page.content.return_value = html_without_json
    mock_page.query_selector_all.return_value = [AsyncMock(inner_html=AsyncMock(return_value="var x = 1;"))]
    
    result = await scraper_instance._get_prices_and_capacity(mock_page, {'ticket_url': 'url'})
    
    assert result['error'] == "Could not find 'window.Commerce.models' in any script tag."
    assert result['capacity'] == "N/A"
    assert len(result['tickets']) == 0

@pytest.mark.asyncio
async def test_get_prices_and_capacity_timeout_error(scraper_instance):
    """
    Tests the function's behavior when page.goto() raises a TimeoutError.
    """
    mock_page = AsyncMock()
    mock_page.goto.side_effect = PlaywrightTimeoutError("Page load timed out")
    
    result = await scraper_instance._get_prices_and_capacity(mock_page, {'ticket_url': 'url'})
    
    assert result['error'] == 'Scraping timed out.'
    assert result['capacity'] == "N/A"
    assert len(result['tickets']) == 0

@pytest.mark.asyncio
@patch('app.scraper.logger')
@patch('app.scraper.os.makedirs')
@patch('builtins.open')
async def test_get_prices_and_capacity_saves_html_on_failure(mock_open, mock_makedirs, mock_logger, scraper_instance):
    """Tests that the failing HTML is saved for debugging when an unexpected error occurs."""
    mock_page = AsyncMock()
    mock_page.content.return_value = "<html></html>"
    # Simulate a JSON parsing error
    mock_page.goto.side_effect = Exception("Simulated general error")

    await scraper_instance._get_prices_and_capacity(mock_page, {'ticket_url': 'url'})

    mock_makedirs.assert_called_once()
    mock_open.assert_called_once()
    mock_logger.debug.assert_called()
    assert "Saved failing HTML" in mock_logger.debug.call_args[0][0]