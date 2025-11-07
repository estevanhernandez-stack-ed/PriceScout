import pytest
from playwright.async_api import async_playwright

@pytest.mark.asyncio
async def test_simple_navigation_manual():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com")
        assert "Google" in await page.title()
        await browser.close()