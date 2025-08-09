# scraper.py - The Standalone Data Scraping Engine (DEFINITIVE VERSION)

import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import re
import datetime
import json
import os

# --- Helper Functions ---
def clean_ticket_type(description: str) -> str:
    """Shortens the ticket type description to a standard format."""
    desc_lower = description.lower()
    if 'adult' in desc_lower: return 'Adult'
    if 'senior' in desc_lower: return 'Senior'
    if 'child' in desc_lower: return 'Child'
    return description.split('(')[0].strip()

def classify_daypart(showtime_str: str) -> str:
    """Classifies a showtime string (e.g., '3:25p') into a daypart."""
    try:
        normalized_time = showtime_str.lower().replace('p', 'PM').replace('a', 'AM')
        time_obj = datetime.datetime.strptime(normalized_time, "%I:%M%p").time()
        if time_obj < datetime.time(16, 0): return "Matinee"
        elif time_obj <= datetime.time(21, 0): return "Prime"
        else: return "Late Night"
    except ValueError: return "Unknown"

# --- Advanced Scraper Functions ---
async def get_theaters_from_zip_page(page, zip_code, date):
    """Extracts theater list directly from the page's hydrated JavaScript object."""
    url = f"https://www.fandango.com/{zip_code}_movietimes?date={date}"
    print(f"Navigating to theater list: {url}")
    await page.goto(url, timeout=60000)
    try:
        await page.locator('#onetrust-accept-btn-handler').click(timeout=5000)
        print("Cookie consent banner handled.")
    except:
        print("No cookie consent banner found, continuing...")
    
    js_condition = "() => window.Fandango && window.Fandango.pageDetails && window.Fandango.pageDetails.localTheaters"
    print("Waiting for theater data to hydrate...")
    await page.wait_for_function(js_condition, timeout=20000)
    print("Theater data found. Extracting directly from page memory...")
    
    theaters_data = await page.evaluate('() => window.Fandango.pageDetails.localTheaters')
    
    theaters = []
    for theater_data in theaters_data:
        name = theater_data.get('name')
        url_path = theater_data.get('theaterPageUrl')
        if name and url_path:
            theaters.append({'name': name, 'url': "https://www.fandango.com" + url_path})
            
    print(f"-> Success! Found {len(theaters)} theaters.")
    return theaters

async def get_movies_from_theater_page(page, theater_url, date):
    """Extracts movie and showtime info directly from a theater page's JavaScript object."""
    full_url = f"{theater_url}?date={date}"
    print(f"Navigating to theater: {full_url}")
    await page.goto(full_url, timeout=60000)
    
    # Assumption: Theater pages use a similar hydration mechanism. We wait for the movie data object.
    js_condition = "() => window.__PRELOADED_STATE__ && window.__PRELOADED_STATE__.movies"
    print("  Waiting for movie data to hydrate...")
    await page.wait_for_function(js_condition, timeout=20000)
    print("  Movie data found. Extracting directly...")

    page_data = await page.evaluate('() => window.__PRELOADED_STATE__')
    movies_data = page_data.get('movies', {}).get('movies', [])
    
    showings = []
    for movie in movies_data:
        film_title = movie.get('title')
        for variant in movie.get('variants', []):
            for showtime_group in variant.get('showtimeGroups', []):
                for showtime in showtime_group.get('showtimes', []):
                    time_str = showtime.get('time')
                    ticket_url = showtime.get('ticketingUrl')
                    if film_title and time_str and ticket_url:
                        showings.append({
                            "film_title": film_title,
                            "showtime": time_str,
                            "daypart": classify_daypart(time_str),
                            "ticket_url": ticket_url
                        })
    print(f"  -> Success! Found {len(showings)} showtimes across all movies.")
    return showings

# Price scraping function remains the same as it was generally reliable
async def get_prices_for_showtime(page, showtime_url):
    await page.goto(showtime_url, timeout=60000)
    prices = {}
    try:
        await page.wait_for_selector('div#SeatPicker, div.ticket-selection-overlay__header', timeout=15000)
        for ticket_row in await page.locator('div.ticket-type-row').all():
            type_text = await ticket_row.locator('div.ticket-type-name').inner_text()
            price_text = await ticket_row.locator('div.ticket-price').inner_text()
            ticket_type = clean_ticket_type(type_text)
            prices[ticket_type] = price_text.split(' ')[0]
        print(f"    -> Success: Scraped {len(prices)} price points.")
    except Exception:
        print(f"    -> Warning: Could not get prices for this showtime. Trying fallback...")
        try:
            for row in await page.locator('li.section__block[data-ticket-type-id]').all():
                desc_elem = await row.locator('h3.ticket-qty-btns__descr').inner_text()
                price_elem = await row.locator('div.ticket-qty-btns__price').inner_text()
                ticket_type = clean_ticket_type(desc_elem)
                prices[ticket_type] = price_elem.split('+')[0].strip()
            print(f"    -> Success (Fallback): Scraped {len(prices)} price points.")
        except Exception as e:
            print(f"    -> ERROR: Price scraping failed for {showtime_url}. {e}")
    return prices

async def main():
    import sys
    if len(sys.argv) > 1:
        scrape_date = sys.argv[1]
    else:
        scrape_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    
    zip_code = "76107"
    all_price_data = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        try:
            theaters = await get_theaters_from_zip_page(page, zip_code, scrape_date)
            await page.close()

            if not theaters:
                return

            for theater in theaters[:3]: # Limit to 3 theaters for speed
                page = await context.new_page()
                showings = await get_movies_from_theater_page(page, theater['url'], scrape_date)
                await page.close()

                for showing in showings[:4]: # Limit to 4 showings per theater
                    print(f"--- Getting prices for {theater['name']} - {showing['film_title']} @ {showing['showtime']}")
                    page = await context.new_page()
                    price_dict = await get_prices_for_showtime(page, showing['ticket_url'])
                    await page.close()

                    for ticket_type, price in price_dict.items():
                        all_price_data.append({
                            "Theater Name": theater['name'], "Film Title": showing['film_title'],
                            "Showtime": showing['showtime'], "Daypart": showing['daypart'],
                            "Ticket Type": ticket_type, "Price": price
                        })
        except Exception as e:
            print(f"A critical error occurred during the main process: {e}")
        finally:
            await browser.close()

    if all_price_data:
        df = pd.DataFrame(all_price_data)
        df.to_csv('live_report.csv', index=False)
        print(f"\n--- SCRAPE COMPLETE: Data for {scrape_date} saved to live_report.csv ---")
    else:
        print("\n--- SCRAPE FAILED: No data collected. ---")

if __name__ == '__main__':
    asyncio.run(main())