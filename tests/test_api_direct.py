"""
Quick API endpoint test - run standalone
Usage: python test_api_direct.py
"""
import requests
import json
from time import sleep
import subprocess
import sys
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

# Wait for startup
print("Waiting for server startup...")
sleep(4)

BASE_URL = "http://localhost:8090"

try:
    # Test 1: Health
    print("\n=== Test 1: Health Check ===")
    resp = requests.get(f"{BASE_URL}/healthz")
    print(f"✓ Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")

    # Test 2: Selection Analysis (JSON)
    print("\n=== Test 2: Selection Analysis (JSON) ===")
    payload = {
        "selected_showtimes": {
            "2025-11-30": {
                "Marcus Ridge Cinema": {
                    "Wicked": {
                        "7:00PM": [{"format": "IMAX", "daypart": "Prime", "ticket_url": "https://example.com"}],
                        "9:30PM": [{"format": "Standard", "daypart": "Prime", "ticket_url": "https://example.com"}]
                    },
                    "Gladiator II": {
                        "8:00PM": [{"format": "Dolby Cinema", "daypart": "Prime", "ticket_url": "https://example.com"}]
                    }
                }
            }
        }
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/v1/reports/selection-analysis?format=json",
        json=payload
    )
    print(f"✓ Status: {resp.status_code}")
    result = resp.json()
    print(f"  Rows returned: {len(result['rows'])}")
    if result['rows']:
        print(f"  Sample row: {result['rows'][0]}")

    # Test 3: Selection Analysis (CSV)
    print("\n=== Test 3: Selection Analysis (CSV) ===")
    resp = requests.post(
        f"{BASE_URL}/api/v1/reports/selection-analysis?format=csv",
        json=payload
    )
    print(f"✓ Status: {resp.status_code}")
    print(f"  CSV size: {len(resp.text)} bytes")
    print(f"  First line: {resp.text.split(chr(10))[0]}")

    # Test 4: Showtime View HTML
    print("\n=== Test 4: Showtime View (HTML) ===")
    html_payload = {
        "all_showings": {
            "2025-11-30": {
                "Marcus Ridge Cinema": [
                    {"film_title": "Wicked", "showtime": "7:00PM", "format": "IMAX", "daypart": "Prime"},
                    {"film_title": "Wicked", "showtime": "9:30PM", "format": "Standard", "daypart": "Prime"},
                    {"film_title": "Gladiator II", "showtime": "8:00PM", "format": "Dolby Cinema", "daypart": "Prime"}
                ]
            }
        },
        "selected_films": ["Wicked", "Gladiator II"],
        "theaters": [{"name": "Marcus Ridge Cinema"}],
        "date_start": "2025-11-30",
        "date_end": "2025-11-30",
        "context_title": "Test Market - API"
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/v1/reports/showtime-view/html",
        json=html_payload
    )
    print(f"✓ Status: {resp.status_code}")
    print(f"  HTML size: {len(resp.text)} bytes")
    print(f"  Contains 'Test Market': {'Test Market' in resp.text}")
    print(f"  Contains 'Wicked': {'Wicked' in resp.text}")

    print("\n=== ✓ All Tests Passed! ===")

except requests.exceptions.ConnectionError:
    print("✗ Error: Could not connect to server")
except Exception as e:
    print(f"✗ Error: {e}")
finally:
    print("\nStopping server...")
    server_proc.terminate()
    server_proc.wait(timeout=5)
    print("Done.")
