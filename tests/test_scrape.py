import asyncio
import json
from app.scraper import PriceScoutScraper

async def test_scrape():
    # Load theater cache
    with open('app/theater_cache.json', 'r') as f:
        cache = json.load(f)
    
    # Get first market's first theater
    markets = cache.get('markets', {})
    if not markets:
        print("ERROR: No markets in cache!")
        return
    
    first_market = list(markets.keys())[0]
    theaters = markets[first_market].get('theaters', [])
    
    if not theaters:
        print(f"ERROR: No theaters in market {first_market}!")
        return
    
    test_theater = theaters[0]
    print(f"Testing theater: {test_theater['name']}")
    print(f"URL: {test_theater['url']}")
    
    # Test scrape
    scraper = PriceScoutScraper(headless=True)
    date_str = "2025-11-13"
    
    print(f"\nScraping for date: {date_str}")
    result = await scraper.get_all_showings_for_theaters([test_theater], date_str)
    
    print(f"\nResult type: {type(result)}")
    print(f"Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
    
    if result and test_theater['name'] in result:
        showings = result[test_theater['name']]
        print(f"\nFound {len(showings)} showings")
        if showings:
            print("\nFirst 3 showings:")
            for showing in showings[:3]:
                print(f"  - {showing}")
    else:
        print("\nNo showings found!")

if __name__ == "__main__":
    asyncio.run(test_scrape())
