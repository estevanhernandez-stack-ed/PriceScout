"""
Quick diagnostic test for operating-hours endpoint
Tests with timeout to avoid hanging
"""
import requests
import subprocess
import sys
from time import sleep
from pathlib import Path

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
    resp = requests.get(f"{BASE_URL}/healthz", timeout=5)
    print(f"✓ Status: {resp.status_code}")
    
    # Test 2: Operating Hours with specific theater (should be faster)
    print("\n=== Test 2: Operating Hours (Single Theater, JSON) ===")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v1/reports/operating-hours",
            params={"theater": "Marcus Ridge Cinema", "format": "json"},
            timeout=10  # 10 second timeout
        )
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"✓ Status: {resp.status_code}")
            print(f"  Record count: {data['record_count']}")
            print(f"  Date range: {data['date_range']}")
            if data['operating_hours']:
                print(f"  First record: {data['operating_hours'][0]}")
        elif resp.status_code == 404:
            print(f"⚠ No data (404)")
        else:
            print(f"✗ Status: {resp.status_code}")
            print(f"  Response: {resp.text[:200]}")
    except requests.exceptions.Timeout:
        print(f"✗ Request timed out after 10 seconds")
        print(f"  Issue: Query likely too slow - may need optimization")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 3: PLF Formats (should be faster due to format filter)
    print("\n=== Test 3: PLF Formats (JSON) ===")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v1/reports/plf-formats",
            params={"format": "json"},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"✓ Status: {resp.status_code}")
            print(f"  Theater count: {data['theater_count']}")
            print(f"  Total PLF showtimes: {data['total_plf_showtimes']}")
        elif resp.status_code == 404:
            print(f"⚠ No PLF data (404)")
        else:
            print(f"✗ Status: {resp.status_code}")
    except requests.exceptions.Timeout:
        print(f"✗ Request timed out after 10 seconds")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n=== Tests Complete ===")

except Exception as e:
    print(f"✗ Fatal error: {e}")
finally:
    print("\nStopping server...")
    server_proc.terminate()
    server_proc.wait(timeout=5)
    print("Done.")
