import pytest
import re
from app.scraper import Scraper
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

import datetime

class TestLiveScraper:
    """
    Groups tests that perform live scrapes against the Fandango website.
    These tests are essential for detecting when the website's structure changes.
    """
    @pytest.mark.asyncio
    async def test_live_search_by_zip_success(self):
        scraper = Scraper()
        logger.info("Starting test_live_search_by_zip_success")
        theaters = await scraper.live_search_by_zip("76107", "2025-08-24")
        logger.info(f"Theaters found: {theaters}")
        assert "AMC Palace 9" in theaters
        assert "https://www.fandango.com/amc-palace-9-aadcs/theater-page" == theaters["AMC Palace 9"]["url"]
        logger.info("Finished test_live_search_by_zip_success")

    @pytest.mark.asyncio
    async def test_live_search_by_name_success(self):
        scraper = Scraper()
        logger.info("Starting test_live_search_by_name_success")
        theaters = await scraper.live_search_by_name("AMC Palace 9")
        assert any("AMC Palace 9" in name for name in theaters.keys())
        logger.info("Finished test_live_search_by_name_success")

    @pytest.mark.asyncio
    async def test_get_movies_from_theater_page_success(self):
        scraper = Scraper()
        logger.info("Starting test_get_movies_from_theater_page_success")
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        date_str = tomorrow.strftime('%Y-%m-%d')
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            theater = {"name": "AMC Palace 9", "url": "https://www.fandango.com/amc-palace-9-aadcs/theater-page"}
            movies = await scraper._get_movies_from_theater_page(page, theater, date_str)
            assert len(movies) > 0
            await browser.close()
        logger.info("Finished test_get_movies_from_theater_page_success")

    @pytest.mark.asyncio
    async def test_get_prices_and_capacity_success(self):
        scraper = Scraper()
        logger.info("Starting test_get_prices_and_capacity_success")
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        date_str = tomorrow.strftime('%Y-%m-%d')
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            theater = {"name": "AMC Palace 9", "url": "https://www.fandango.com/amc-palace-9-aadcs/theater-page"}
            movies = await scraper._get_movies_from_theater_page(page, theater, date_str)
            assert len(movies) > 0
            showing = movies[0]
            prices = await scraper._get_prices_and_capacity(page, showing)
            assert len(prices["tickets"]) > 0
            await browser.close()
        logger.info("Finished test_get_prices_and_capacity_success")

    @pytest.mark.asyncio
    async def test_get_capacity_success(self):
        scraper = Scraper()
        logger.info("Starting test_get_capacity_success")
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        date_str = tomorrow.strftime('%Y-%m-%d')
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            # This theater and movie are known to have capacity info
            theater = {"name": "AMC DINE-IN Clearfork 8", "url": "https://www.fandango.com/amc-dine-in-clearfork-8-aayjv/theater-page"}
            movies = await scraper._get_movies_from_theater_page(page, theater, date_str)
            assert len(movies) > 0
            # Find a showing that is likely to have reserved seating
            showing_with_url = next((s for s in movies if s.get('ticket_url')), None)
            assert showing_with_url is not None, "No showing with a ticket URL found to test capacity"

            prices = await scraper._get_prices_and_capacity(page, showing_with_url)
            assert prices['capacity'] in ["Available", "Sold Out"]
            await browser.close()
        logger.info("Finished test_get_capacity_success")

    @pytest.mark.asyncio
    async def test_scraper_with_devtools_enabled(self):
        """
        Tests that the scraper can be initialized with devtools=True.
        This is a functional test; when run, it should open a visible browser
        window with the DevTools panel open. The test passes if the operation
        completes without errors.
        """
        # Initialize the scraper in "dev mode"
        scraper = Scraper(headless=False, devtools=True)
        logger.info("Starting test_scraper_with_devtools_enabled")
        theaters = await scraper.live_search_by_name("AMC")
        assert theaters, "Live search should return some results for 'AMC'"
        logger.info("Finished test_scraper_with_devtools_enabled")