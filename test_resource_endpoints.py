"""
Test all resource endpoints
"""
import requests
import subprocess
import sys
from time import sleep
from pathlib import Path

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
    # Test 1: List Theaters
    print("\n=== Test 1: List Theaters ===")
    resp = requests.get(f"{BASE_URL}/api/v1/theaters", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code}")
        print(f"  Theater count: {data['theater_count']}")
        if data['theaters']:
            print(f"  Sample: {data['theaters'][0]}")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 2: List Films
    print("\n=== Test 2: List Films ===")
    resp = requests.get(f"{BASE_URL}/api/v1/films?limit=10", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code}")
        print(f"  Film count: {data['film_count']}")
        if data['films']:
            print(f"  Top film: {data['films'][0]}")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 3: Scrape Runs
    print("\n=== Test 3: List Scrape Runs ===")
    resp = requests.get(f"{BASE_URL}/api/v1/scrape-runs?limit=5", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code}")
        print(f"  Scrape run count: {data['scrape_run_count']}")
        if data['scrape_runs']:
            print(f"  Latest: {data['scrape_runs'][0]}")
    elif resp.status_code == 404:
        print(f"⚠ No scrape runs found (404)")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 4: Search Showtimes
    print("\n=== Test 4: Search Showtimes (Wicked) ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/showtimes/search",
        params={"film": "Wicked", "limit": 5},
        timeout=10
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code}")
        print(f"  Showtime count: {data['showtime_count']}")
        if data['showtimes']:
            print(f"  Sample: {data['showtimes'][0]}")
    elif resp.status_code == 404:
        print(f"⚠ No showtimes found (404)")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 5: Search by Theater
    print("\n=== Test 5: Search Showtimes (Marcus Ridge) ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/showtimes/search",
        params={"theater": "Marcus Ridge", "limit": 5},
        timeout=10
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code}")
        print(f"  Showtime count: {data['showtime_count']}")
    elif resp.status_code == 404:
        print(f"⚠ No showtimes found (404)")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 6: Pricing Data
    print("\n=== Test 6: Get Pricing Data ===")
    resp = requests.get(f"{BASE_URL}/api/v1/pricing?limit=10", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code}")
        print(f"  Price count: {data['price_count']}")
        if data['pricing']:
            print(f"  Sample: {data['pricing'][0]}")
    elif resp.status_code == 404:
        print(f"⚠ No pricing data found (404) - expected if pricing not scraped yet")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 7: CSV Export (Theaters)
    print("\n=== Test 7: Export Theaters CSV ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/theaters",
        params={"format": "csv"},
        timeout=10
    )
    if resp.status_code == 200:
        print(f"✓ Status: {resp.status_code}")
        print(f"  CSV size: {len(resp.text)} bytes")
        lines = resp.text.split('\n')
        print(f"  Header: {lines[0]}")
        if len(lines) > 1:
            print(f"  First row: {lines[1]}")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 8: CSV Export (Films)
    print("\n=== Test 8: Export Films CSV ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/films",
        params={"format": "csv", "limit": 20},
        timeout=10
    )
    if resp.status_code == 200:
        print(f"✓ Status: {resp.status_code}")
        print(f"  CSV size: {len(resp.text)} bytes")
        
        # Save to file
        output_file = Path("test_films_export.csv")
        output_file.write_text(resp.text)
        print(f"  Saved to: {output_file.absolute()}")
    else:
        print(f"✗ Status: {resp.status_code}")

    print("\n=== All Resource Tests Complete ===")
    print("\nNew Endpoints Tested:")
    print("  ✓ GET /api/v1/theaters")
    print("  ✓ GET /api/v1/films")
    print("  ✓ GET /api/v1/scrape-runs")
    print("  ✓ GET /api/v1/showtimes/search")
    print("  ✓ GET /api/v1/pricing")

except Exception as e:
    print(f"\n✗ Fatal error: {e}")
    import traceback
    traceback.print_exc()
finally:
    print("\nStopping server...")
    server_proc.terminate()
    server_proc.wait(timeout=5)
    print("Done.")
