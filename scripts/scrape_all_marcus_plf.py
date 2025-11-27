#!/usr/bin/env python3
"""
Scrape All Marcus Theaters for PLF Data

Scrapes all Marcus and Movie Tavern theaters for one day to gather
complete PLF format information.

Usage:
    python scripts/scrape_all_marcus_plf.py
"""

import sys
import os
import json
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_all_marcus_theaters():
    """Load all Marcus/Movie Tavern theaters from cache files."""
    theaters = []

    # Check multiple possible cache locations
    cache_paths = [
        'data/Marcus Theatres/markets.json',
        'data/Marcus/markets.json',
        'data/markets.json'
    ]

    for cache_path in cache_paths:
        if os.path.exists(cache_path):
            print(f"Loading from: {cache_path}")
            with open(cache_path, 'r') as f:
                cache = json.load(f)

            # Navigate the nested structure
            def extract_theaters(data, path=""):
                found = []
                if isinstance(data, dict):
                    if 'theaters' in data:
                        for t in data['theaters']:
                            if isinstance(t, dict) and 'name' in t:
                                found.append(t)
                    else:
                        for key, value in data.items():
                            found.extend(extract_theaters(value, f"{path}/{key}"))
                elif isinstance(data, list):
                    for item in data:
                        found.extend(extract_theaters(item, path))
                return found

            theaters.extend(extract_theaters(cache))

    # Remove duplicates based on theater name
    seen = set()
    unique_theaters = []
    for t in theaters:
        if t['name'] not in seen:
            seen.add(t['name'])
            unique_theaters.append(t)

    return unique_theaters


def scrape_theater_formats(theater, date_str):
    """Scrape a single theater and return format data."""
    from app.scraper import Scraper

    scout = Scraper()

    # Build the theater URL if not present
    if 'url' not in theater:
        # Try to construct URL from name
        theater_slug = theater['name'].lower().replace(' ', '-').replace("'", '')
        theater['url'] = f"https://www.fandango.com/{theater_slug}"

    try:
        import asyncio
        # get_all_showings_for_theaters returns a dictionary, so we extract the showings for the specific theater
        results_dict = asyncio.run(scout.get_all_showings_for_theaters([theater], date_str))
        return results_dict.get(theater['name'], [])
    except Exception as e:
        print(f"  Error scraping {theater['name']}: {e}")
        return []


def main():
    """Main function to scrape all theaters and report PLF formats."""
    from collections import defaultdict

    print("=" * 70)
    print("MARCUS THEATERS PLF SCRAPE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # Load all theaters
    theaters = load_all_marcus_theaters()
    print(f"Found {len(theaters)} theaters in cache")

    if not theaters:
        print("No theaters found. Make sure the theater cache exists.")
        return

    # Use tomorrow's date to ensure showtimes are available
    from datetime import timedelta
    target_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Scraping for date: {target_date}")
    print()

    # Track formats by theater
    theater_formats = defaultdict(set)
    total_showings = 0

    for i, theater in enumerate(theaters, 1):
        theater_name = theater['name']
        print(f"[{i}/{len(theaters)}] Scraping: {theater_name}...")

        try:
            showings = scrape_theater_formats(theater, target_date)

            if showings:
                for showing in showings:
                    fmt = showing.get('format', 'Unknown')
                    theater_formats[theater_name].add(fmt)
                    total_showings += 1

                formats = theater_formats[theater_name]
                print(f"    Found {len(showings)} showings, formats: {', '.join(sorted(formats))}")
            else:
                print(f"    No showings found")
        except Exception as e:
            print(f"    Error: {e}")

    # Generate report
    print()
    print("=" * 70)
    print("PLF FORMAT REPORT")
    print("=" * 70)
    print()

    # Collect all unique formats
    all_formats = set()
    for formats in theater_formats.values():
        all_formats.update(formats)

    print(f"All unique formats found: {', '.join(sorted(all_formats))}")
    print()

    # Show PLF theaters
    plf_keywords = ['IMAX', 'UltraScreen', 'Dolby', 'Premium', 'PLF', 'Grand', 'XD',
                    'Big House', 'Superscreen', 'D-BOX', '4DX', 'ScreenX', 'RPX']

    print("THEATERS WITH PLF:")
    print("-" * 70)

    for theater_name, formats in sorted(theater_formats.items()):
        plf_formats = [f for f in formats if any(kw.lower() in f.lower() for kw in plf_keywords)]
        if plf_formats:
            print(f"\n{theater_name}")
            for fmt in sorted(plf_formats):
                print(f"  - {fmt}")

    print()
    print("=" * 70)
    print(f"Total showings scraped: {total_showings}")
    print(f"Theaters with data: {len(theater_formats)}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
