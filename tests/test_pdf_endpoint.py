"""
Test PDF endpoint (requires Playwright browsers installed)
Usage: python test_pdf_endpoint.py
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
    print("\n=== Test: Showtime View (PDF) ===")
    payload = {
        "all_showings": {
            "2025-11-30": {
                "Marcus Ridge Cinema": [
                    {"film_title": "Wicked", "showtime": "7:00PM", "format": "IMAX", "daypart": "Prime"},
                    {"film_title": "Wicked", "showtime": "9:30PM", "format": "Standard", "daypart": "Prime"}
                ]
            }
        },
        "selected_films": ["Wicked"],
        "theaters": [{"name": "Marcus Ridge Cinema"}],
        "date_start": "2025-11-30",
        "date_end": "2025-11-30",
        "context_title": "PDF Test"
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/v1/reports/showtime-view/pdf",
        json=payload
    )
    
    if resp.status_code == 200:
        print(f"✓ PDF generated successfully")
        print(f"  Size: {len(resp.content)} bytes")
        print(f"  Content-Type: {resp.headers.get('content-type')}")
        
        # Save to file
        output_path = Path("test_output.pdf")
        output_path.write_bytes(resp.content)
        print(f"  Saved to: {output_path.absolute()}")
        
    elif resp.status_code == 503:
        print(f"⚠ PDF generation failed (expected if Playwright not installed)")
        error = resp.json()
        print(f"  Error: {error.get('error')}")
        print(f"  Detail: {error.get('detail')}")
    else:
        print(f"✗ Unexpected status: {resp.status_code}")
        print(f"  Response: {resp.text[:200]}")

except Exception as e:
    print(f"✗ Error: {e}")
finally:
    print("\nStopping server...")
    server_proc.terminate()
    server_proc.wait(timeout=5)
    print("Done.")
