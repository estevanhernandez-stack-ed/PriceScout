import pytest
from app.scraper import Scraper
from unittest.mock import MagicMock, AsyncMock
import asyncio

class MockResponse:
    def __init__(self, status_code):
        self.status = status_code

def test_classify_daypart():
    """Tests the _classify_daypart method with various time inputs."""
    scraper = Scraper()
    assert scraper._classify_daypart("10:00am") == "Matinee"
    assert scraper._classify_daypart("3:59pm") == "Matinee"
    assert scraper._classify_daypart("4:00pm") == "Twilight"
    assert scraper._classify_daypart("5:59pm") == "Twilight"
    assert scraper._classify_daypart("6:00pm") == "Prime"
    assert scraper._classify_daypart("9:00pm") == "Prime"
    assert scraper._classify_daypart("9:01pm") == "Late Night"
    assert scraper._classify_daypart("11:59pm") == "Late Night"
    assert scraper._classify_daypart("12:00am") == "Late Night"
    assert scraper._classify_daypart("1:00am") == "Late Night"
    assert scraper._classify_daypart("Invalid Time") == "Unknown"

def test_strip_common_terms():
    """Tests the _strip_common_terms method to ensure it correctly cleans theater names."""
    scraper = Scraper()
    assert scraper._strip_common_terms("AMC DINE-IN South Barrington 24 with IMAX, Dolby, Prime") == "south barrington 24 with prime"
    assert scraper._strip_common_terms("Cinemark Cantera Warrenville and XD") == "cantera warrenville and"
    assert scraper._strip_common_terms("Marcus Crosswoods Cinema with UltraScreen") == "crosswoods with"
    assert scraper._strip_common_terms("Regal Edwards Big Newport & RPX") == "edwards big newport & rpx"
    assert scraper._strip_common_terms("Movie Tavern by Marcus at College Square") == "at college square"
    assert scraper._strip_common_terms("B&B Theatres Omaha Oakview Plaza 14 w/ Grand Screens, MX4D & Screen-X") == "omaha oakview plaza 14 w/ grand screens mx4d & screen-x"

@pytest.mark.asyncio
async def test_check_url_status(mocker):
    """Tests the check_url_status method with various mock responses."""
    scraper = Scraper()
    mock_response = MockResponse(200)
    mock_page = mocker.AsyncMock()
    mock_page.request.head.return_value = mock_response

    mock_browser = mocker.AsyncMock()
    mock_browser.new_page.return_value = mock_page

    # The original mock was incorrect. launch() returns the browser, not a context manager.
    mock_playwright_instance = mocker.AsyncMock()
    mock_playwright_instance.chromium.launch.return_value = mock_browser

    # This is the async context manager for `async with async_playwright() as p:`
    mock_playwright_cm = mocker.AsyncMock()
    mock_playwright_cm.__aenter__.return_value = mock_playwright_instance

    mocker.patch('app.scraper.async_playwright', return_value=mock_playwright_cm)

    # Test case 1: URL is active (200 OK)
    mock_response.status = 200
    assert await scraper.check_url_status("http://valid.com") is True

    # Test case 2: URL is not active (404 Not Found)
    mock_response.status = 404
    assert await scraper.check_url_status("http://invalid.com") is False
