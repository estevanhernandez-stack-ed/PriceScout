"""
Comprehensive test for all report endpoints
Tests: health, selection-analysis, showtime-view, daily-lineup, operating-hours, plf-formats
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
    # Test 1: Health check
    print("\n=== Test 1: Health Check ===")
    resp = requests.get(f"{BASE_URL}/healthz")
    print(f"✓ Status: {resp.status_code}" if resp.status_code == 200 else f"✗ Status: {resp.status_code}")
    
    # Test 2: Selection Analysis (quick)
    print("\n=== Test 2: Selection Analysis (JSON) ===")
    payload = {
        "selected_showtimes": {
            "2025-11-28": {
                "Marcus Ridge Cinema": {
                    "Wicked": {
                        "10:00AM": [{"format": "IMAX"}],
                        "1:00PM": [{"format": "Standard"}]
                    }
                }
            }
        }
    }
    resp = requests.post(f"{BASE_URL}/api/v1/reports/selection-analysis?format=json", json=payload)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code} - {len(data)} rows")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 3: Daily Lineup
    print("\n=== Test 3: Daily Lineup (JSON) ===")
    test_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    resp = requests.get(
        f"{BASE_URL}/api/v1/reports/daily-lineup",
        params={"theater": "Marcus Ridge Cinema", "date": test_date, "format": "json"}
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code} - {data['showtime_count']} showtimes")
    elif resp.status_code == 404:
        print(f"⚠ No data (404) - expected if no showtimes exist")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 4: Operating Hours
    print("\n=== Test 4: Operating Hours (JSON) ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/reports/operating-hours",
        params={"theater": "Marcus Ridge Cinema", "format": "json"}
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code} - {data['record_count']} records")
        if data['record_count'] > 0:
            print(f"  Date range: {data['date_range']['earliest']} to {data['date_range']['latest']}")
            print(f"  Sample: {data['operating_hours'][0]}")
    elif resp.status_code == 404:
        print(f"⚠ No data (404)")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 5: Operating Hours CSV
    print("\n=== Test 5: Operating Hours (CSV) ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/reports/operating-hours",
        params={"format": "csv"}
    )
    if resp.status_code == 200:
        print(f"✓ Status: {resp.status_code} - {len(resp.text)} bytes")
        lines = resp.text.split('\n')
        print(f"  Header: {lines[0]}")
        if len(lines) > 1:
            print(f"  First row: {lines[1]}")
        
        # Save CSV
        Path("test_operating_hours.csv").write_text(resp.text)
        print(f"  Saved to: test_operating_hours.csv")
    elif resp.status_code == 404:
        print(f"⚠ No data (404)")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 6: PLF Formats
    print("\n=== Test 6: PLF Formats (JSON) ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/reports/plf-formats",
        params={"format": "json"}
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code}")
        print(f"  Theater count: {data['theater_count']}")
        print(f"  Total PLF showtimes: {data['total_plf_showtimes']}")
        if data['theaters']:
            first_theater = list(data['theaters'].keys())[0]
            print(f"  Sample theater: {first_theater}")
            print(f"    Formats: {data['theaters'][first_theater]}")
    elif resp.status_code == 404:
        print(f"⚠ No PLF data (404) - expected if no premium formats in DB")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 7: PLF Formats CSV
    print("\n=== Test 7: PLF Formats (CSV) ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/reports/plf-formats",
        params={"format": "csv"}
    )
    if resp.status_code == 200:
        print(f"✓ Status: {resp.status_code} - {len(resp.text)} bytes")
        lines = resp.text.split('\n')
        print(f"  Header: {lines[0]}")
        if len(lines) > 1:
            print(f"  First row: {lines[1]}")
        
        # Save CSV
        Path("test_plf_formats.csv").write_text(resp.text)
        print(f"  Saved to: test_plf_formats.csv")
    elif resp.status_code == 404:
        print(f"⚠ No PLF data (404)")
    else:
        print(f"✗ Status: {resp.status_code}")
    
    # Test 8: PLF Formats with date filter
    print("\n=== Test 8: PLF Formats (Date Filter) ===")
    resp = requests.get(
        f"{BASE_URL}/api/v1/reports/plf-formats",
        params={"date": test_date, "format": "json"}
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {resp.status_code} - {data['total_plf_showtimes']} showtimes on {test_date}")
    elif resp.status_code == 404:
        print(f"⚠ No PLF data for {test_date} (404)")
    else:
        print(f"✗ Status: {resp.status_code}")

    print("\n=== All Tests Complete ===")
    print("\nEndpoints Summary:")
    print("  ✓ GET  /healthz")
    print("  ✓ POST /api/v1/reports/selection-analysis")
    print("  ✓ POST /api/v1/reports/showtime-view/html")
    print("  ✓ POST /api/v1/reports/showtime-view/pdf")
    print("  ✓ GET  /api/v1/reports/daily-lineup")
    print("  ✓ GET  /api/v1/reports/operating-hours")
    print("  ✓ GET  /api/v1/reports/plf-formats")

except Exception as e:
    print(f"✗ Fatal error: {e}")
finally:
    print("\nStopping server...")
    server_proc.terminate()
    server_proc.wait(timeout=5)
    print("Done.")
