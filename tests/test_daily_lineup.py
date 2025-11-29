"""
Test Daily Lineup endpoint
Usage: python test_daily_lineup.py

Requires: Database with showings data
"""
import requests
import subprocess
import sys
from time import sleep
from pathlib import Path
from datetime import date, timedelta

# Start server
print("Starting FastAPI server on port 8090...")
server_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api.main:app", "--port", "8090"],
    cwd=Path(__file__).parent,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

sleep(4)

BASE_URL = "http://localhost:8090"

try:
    # You'll need to adjust these based on your actual database content
    # Use a recent date and theater name from your database
    
    # Tomorrow's date as a common test case
    test_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    test_theater = "Marcus Ridge Cinema"  # Change this to match your DB
    
    print(f"\nTesting with theater: {test_theater}, date: {test_date}")
    print("(Update these values in test_daily_lineup.py if no data exists)")
    
    # Test 1: JSON format
    print("\n=== Test 1: Daily Lineup (JSON) ===")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v1/reports/daily-lineup",
            params={
                "theater": test_theater,
                "date": test_date,
                "format": "json"
            }
        )
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"✓ Status: {resp.status_code}")
            print(f"  Theater: {data['theater']}")
            print(f"  Date: {data['date']}")
            print(f"  Showtime count: {data['showtime_count']}")
            
            if data['showtimes']:
                print(f"  First showtime: {data['showtimes'][0]}")
        elif resp.status_code == 404:
            print(f"⚠ No data found (404) - this is expected if no showtimes exist")
            print(f"  Response: {resp.json()}")
        else:
            print(f"✗ Unexpected status: {resp.status_code}")
            print(f"  Response: {resp.json()}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 2: CSV format
    print("\n=== Test 2: Daily Lineup (CSV) ===")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v1/reports/daily-lineup",
            params={
                "theater": test_theater,
                "date": test_date,
                "format": "csv"
            }
        )
        
        if resp.status_code == 200:
            print(f"✓ Status: {resp.status_code}")
            print(f"  CSV size: {len(resp.text)} bytes")
            lines = resp.text.split('\n')
            print(f"  Header: {lines[0]}")
            if len(lines) > 1:
                print(f"  First row: {lines[1]}")
                
            # Save to file
            output_file = Path("test_lineup_output.csv")
            output_file.write_text(resp.text)
            print(f"  Saved to: {output_file.absolute()}")
        elif resp.status_code == 404:
            print(f"⚠ No data found (404)")
            print(f"  Response: {resp.json()}")
        else:
            print(f"✗ Unexpected status: {resp.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 3: Invalid date format
    print("\n=== Test 3: Invalid Date Format ===")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v1/reports/daily-lineup",
            params={
                "theater": test_theater,
                "date": "invalid-date",
                "format": "json"
            }
        )
        
        if resp.status_code == 400:
            print(f"✓ Correctly rejected invalid date (400)")
            print(f"  Error: {resp.json()['detail']}")
        else:
            print(f"✗ Expected 400, got {resp.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n=== Tests Complete ===")
    print("\nNote: Update test_theater and test_date variables if 404 errors occur.")
    print("Check your database for available theaters and dates.")

except Exception as e:
    print(f"✗ Fatal error: {e}")
finally:
    print("\nStopping server...")
    server_proc.terminate()
    server_proc.wait(timeout=5)
    print("Done.")
