import asyncio
from app.box_office_mojo_scraper import BoxOfficeMojoScraper

async def main():
    scraper = BoxOfficeMojoScraper()

    # Test film discovery
    print("--- Testing Film Discovery ---")
    films = scraper.discover_films_by_year(2023)
    if films:
        print(f"Discovered {len(films)} films.")
        # Test financial data scraping for the first film
        if films:
            first_film = films[0]
            print(f"--- Testing Financial Data Scraping for: {first_film['title']} ---")
            financials = await scraper.get_film_financials_async(first_film['bom_url'])
            if financials:
                print(f"Financials for {first_film['title']}: {financials}")
            else:
                print(f"Could not retrieve financials for {first_film['title']}.")
    else:
        print("No films discovered for 2023.")

if __name__ == "__main__":
    asyncio.run(main())