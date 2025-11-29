"""
Debug script to fetch and analyze Fandango ticket page HTML structure.
This helps us see what changed in their pricing page layout.
"""
import asyncio
from playwright.async_api import async_playwright
import json

async def debug_fandango_ticket_page(ticket_url):
    """Fetches a Fandango ticket page and analyzes the HTML structure for pricing data."""
    print(f"\n{'='*80}")
    print(f"Debugging Fandango ticket page:")
    print(f"URL: {ticket_url}")
    print(f"{'='*80}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Set to False to see the browser
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print("Loading page...")
            await page.goto(ticket_url, timeout=60000)
            await page.wait_for_timeout(3000)  # Wait 3 seconds for dynamic content

            print("\n1. Searching for 'window.Commerce.models' in page scripts...")
            scripts = await page.query_selector_all('script')
            found_commerce_models = False

            for i, script in enumerate(scripts):
                content = await script.inner_html()
                if content and 'window.Commerce.models' in content:
                    found_commerce_models = True
                    print(f"\n[+] Found in script #{i}")

                    # Extract the JSON object
                    start_text = 'window.Commerce.models = '
                    start_index = content.find(start_text)
                    if start_index != -1:
                        json_start = content.find('{', start_index)
                        open_braces, json_end = 0, -1
                        for j in range(json_start, len(content)):
                            if content[j] == '{': open_braces += 1
                            elif content[j] == '}': open_braces -= 1
                            if open_braces == 0:
                                json_end = j + 1
                                break

                        if json_end != -1:
                            json_str = content[json_start:json_end]
                            try:
                                data = json.loads(json_str)
                                print("\n[+] Successfully parsed JSON!")
                                print(f"\nKeys in window.Commerce.models: {list(data.keys())}")

                                # Check for pricing data
                                if 'tickets' in data:
                                    print(f"\n[+] 'tickets' key found!")
                                    tickets_data = data['tickets']
                                    print(f"  Keys in tickets: {list(tickets_data.keys())}")

                                    if 'seatingAreas' in tickets_data:
                                        seating_areas = tickets_data['seatingAreas']
                                        print(f"\n  [+] Found {len(seating_areas)} seating area(s)")

                                        if seating_areas:
                                            first_area = seating_areas[0]
                                            print(f"  Keys in first seating area: {list(first_area.keys())}")

                                            if 'ticketTypes' in first_area:
                                                ticket_types = first_area['ticketTypes']
                                                print(f"\n  [+] Found {len(ticket_types)} ticket type(s)")
                                                print(f"\n  Sample ticket types:")
                                                for tt in ticket_types[:3]:
                                                    print(f"    - {tt.get('description', 'N/A')}: ${tt.get('price', 'N/A')}")
                                            else:
                                                print("\n  [-] No 'ticketTypes' found in seating area")
                                    else:
                                        print("\n  [-] No 'seatingAreas' in tickets")
                                else:
                                    print("\n[-] No 'tickets' key in window.Commerce.models")
                                    print(f"Available keys: {list(data.keys())}")

                                # Check for seating/capacity data
                                if 'seating' in data:
                                    seating_info = data['seating']
                                    print(f"\n[+] 'seating' key found!")
                                    print(f"  Total seats: {seating_info.get('totalSeats', 'N/A')}")
                                    print(f"  Available seats: {seating_info.get('availableSeats', 'N/A')}")
                                else:
                                    print("\n[-] No 'seating' key found")

                                # Save full JSON to file for inspection
                                with open('fandango_debug_output.json', 'w') as f:
                                    json.dump(data, f, indent=2)
                                print(f"\n[+] Full JSON saved to 'fandango_debug_output.json'")

                            except json.JSONDecodeError as e:
                                print(f"\n[-] Failed to parse JSON: {e}")
                                print(f"\nFirst 500 chars of JSON string:\n{json_str[:500]}")
                        else:
                            print("\n[-] Could not find end of JSON object")
                    else:
                        print("\n[-] Could not find '{' after 'window.Commerce.models ='")

            if not found_commerce_models:
                print("\n[-] 'window.Commerce.models' NOT found in any script tags!")
                print("\nSearching for alternative data sources...")

                # Look for other potential data sources
                all_content = await page.content()

                if 'window.Commerce' in all_content:
                    print("\n  [+] Found 'window.Commerce' (but not 'window.Commerce.models')")
                else:
                    print("\n  [-] No 'window.Commerce' found at all")

                if 'price' in all_content.lower():
                    print("  [+] Found 'price' text in page (pricing may use different structure)")
                else:
                    print("  [-] No 'price' text found in page")

                # Save full HTML for manual inspection
                with open('fandango_debug_page.html', 'w', encoding='utf-8') as f:
                    f.write(all_content)
                print(f"\n[+] Full HTML saved to 'fandango_debug_page.html' for manual inspection")

        except Exception as e:
            print(f"\n[-] Error during debugging: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()
            print(f"\n{'='*80}")
            print("Debug complete!")
            print(f"{'='*80}\n")


if __name__ == "__main__":
    # You'll need to provide a valid Fandango ticket URL
    # Example format: https://tickets.fandango.com/transaction/ticketing/mobile/jump.aspx?sdate=...

    print("\n" + "="*80)
    print("FANDANGO HTML DEBUG SCRIPT")
    print("="*80)
    print("\nThis script will:")
    print("  1. Load a Fandango ticket page")
    print("  2. Search for pricing data in JavaScript")
    print("  3. Save output files for inspection")
    print("  4. Show what changed in their HTML structure")
    print("\nPlease provide a ticket URL from your recent scrape attempt.")
    print("You can find this in the database or by running a test scrape.")
    print("="*80 + "\n")

    ticket_url = input("Enter Fandango ticket URL: ").strip()

    if ticket_url:
        asyncio.run(debug_fandango_ticket_page(ticket_url))
    else:
        print("No URL provided. Exiting.")
