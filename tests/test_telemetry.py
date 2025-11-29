"""
Test script to verify OpenTelemetry instrumentation is working correctly.

This script will:
1. Initialize OpenTelemetry with console exporter (for local testing)
2. Run a simple scraping operation
3. Display telemetry spans and attributes
"""

import asyncio
import datetime
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

# Import scrapers
from app.scraper import Scraper
from app.box_office_mojo_scraper import BoxOfficeMojoScraper

def setup_telemetry():
    """Setup OpenTelemetry with console exporter for local testing."""
    resource = Resource.create({
        "service.name": "price-scout-test",
        "service.version": "1.0.0",
        "deployment.environment": "local-test"
    })
    
    provider = TracerProvider(resource=resource)
    
    # Use console exporter to see spans in the terminal
    console_exporter = ConsoleSpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(console_exporter))
    
    trace.set_tracer_provider(provider)
    print("✅ OpenTelemetry initialized with console exporter\n")

async def test_scraper_telemetry():
    """Test Fandango scraper telemetry."""
    print("=" * 70)
    print("Testing Fandango Scraper Telemetry")
    print("=" * 70)
    
    scraper = Scraper()
    
    # Create a simple test with mock theater data
    test_theaters = [
        {
            "name": "Test Theater 1",
            "id": "test123",
            "url": "https://www.fandango.com/test-theater-1"
        }
    ]
    
    test_date = datetime.date.today()
    
    print(f"\n📊 Testing get_all_showings_for_theaters...")
    print(f"   Theaters: {len(test_theaters)}")
    print(f"   Date: {test_date}\n")
    
    try:
        # This will create a span with custom attributes
        # Note: It may fail to scrape (test URL), but telemetry should still work
        result = await scraper.get_all_showings_for_theaters(test_theaters, test_date)
        print(f"\n✅ Scraper telemetry test completed")
        print(f"   Result: {len(result)} theaters processed\n")
    except Exception as e:
        print(f"\n⚠️  Scraper test error (expected for test data): {e}")
        print("   Telemetry should still have been captured above\n")

def test_box_office_telemetry():
    """Test Box Office Mojo scraper telemetry."""
    print("\n" + "=" * 70)
    print("Testing Box Office Mojo Scraper Telemetry")
    print("=" * 70)
    
    bom_scraper = BoxOfficeMojoScraper()
    
    print(f"\n📊 Testing discover_films_by_year...")
    print(f"   Year: 2024\n")
    
    try:
        # This will create spans with custom attributes
        # Using 2024 to get recent data
        films = bom_scraper.discover_films_by_year(2024)
        print(f"\n✅ Box Office Mojo telemetry test completed")
        print(f"   Films discovered: {len(films)}\n")
    except Exception as e:
        print(f"\n⚠️  BOM test error: {e}")
        print("   Telemetry should still have been captured above\n")

async def main():
    """Run all telemetry tests."""
    print("\n" + "=" * 70)
    print("🔍 PriceScout OpenTelemetry Instrumentation Test")
    print("=" * 70)
    print("\nThis test verifies that custom telemetry spans are being created")
    print("with proper attributes for business metrics.\n")
    
    # Setup telemetry
    setup_telemetry()
    
    # Test scrapers
    await test_scraper_telemetry()
    
    # Box Office Mojo is synchronous, but we can call it in the async context
    test_box_office_telemetry()
    
    print("\n" + "=" * 70)
    print("✅ Telemetry Test Complete")
    print("=" * 70)
    print("\n📝 Review the console output above to verify:")
    print("   - Spans are being created with proper names")
    print("   - Custom attributes are attached (theater_count, films_discovered, etc.)")
    print("   - Errors are captured in span attributes")
    print("\n💡 In production, these spans will be sent to Application Insights")
    print("   instead of the console.\n")

if __name__ == "__main__":
    asyncio.run(main())
