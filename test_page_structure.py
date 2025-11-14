import asyncio
import json
from app.scraper import Scraper
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def test_page_structure():
    # Load theater cache
    with open('app/theater_cache.json', 'r') as f:
        cache = json.load(f)
    
    # Get first market's first theater
    markets = cache.get('markets', {})
    first_market = list(markets.keys())[0]
    theaters = markets[first_market].get('theaters', [])
    test_theater = theaters[0]
    
    print(f"Testing theater: {test_theater['name']}")
    print(f"URL: {test_theater['url']}")
    
    date_str = "2025-11-13"
    full_url = f"{test_theater['url']}?date={date_str}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"\nNavigating to: {full_url}")
        await page.goto(full_url, timeout=60000)
        await page.wait_for_timeout(3000)
        
        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check what we're finding
        print("\n=== CHECKING SELECTORS ===")
        
        fd_panels = soup.select('li.fd-panel')
        print(f"li.fd-panel found: {len(fd_panels)}")
        
        theater_formats = soup.select('div.theater-presenting-formats')
        print(f"div.theater-presenting-formats found: {len(theater_formats)}")
        
        # Try alternative selectors
        movie_containers = soup.select('div.movie-container')
        print(f"div.movie-container found: {len(movie_containers)}")
        
        showtime_sections = soup.select('section.showtimes')
        print(f"section.showtimes found: {len(showtime_sections)}")
        
        # Look for any movie titles
        h2_titles = soup.select('h2')
        print(f"\nh2 elements found: {len(h2_titles)}")
        if h2_titles:
            print("First 3 h2 texts:")
            for h2 in h2_titles[:3]:
                print(f"  - {h2.get_text(strip=True)[:80]}")
        
        # Look for showtime buttons
        showtime_buttons = soup.select('a.showtime-btn')
        print(f"\na.showtime-btn found: {len(showtime_buttons)}")
        
        showtime_links = soup.select('a[href*="jump.aspx"]')
        print(f"a[href*='jump.aspx'] found: {len(showtime_links)}")
        
        # Save HTML for inspection
        with open('debug_page.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"\nSaved full HTML to debug_page.html ({len(html_content)} bytes)")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_page_structure())
