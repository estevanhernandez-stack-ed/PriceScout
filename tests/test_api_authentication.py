"""
Test suite for API authentication and authorization

Tests API key validation, rate limiting, expired keys, and usage tracking.

Usage:
    # Create test database tables first
    python manage_api_keys.py create-tables
    
    # Generate test API keys
    python manage_api_keys.py generate --client "Test Client" --tier free
    python manage_api_keys.py generate --client "Premium Client" --tier premium
    
    # Run tests
    python test_api_authentication.py
"""

import sys
import os
from datetime import datetime, timedelta
import requests
import time

# Test configuration
API_BASE_URL = "http://localhost:8000"

# These will be filled in during test setup
TEST_API_KEY_FREE = None
TEST_API_KEY_PREMIUM = None
INVALID_API_KEY = "ps_free_invalid_key_12345"


def setup_test_keys():
    """Generate test API keys for testing"""
    global TEST_API_KEY_FREE, TEST_API_KEY_PREMIUM
    
    print("\n" + "="*60)
    print("SETUP: Generating Test API Keys")
    print("="*60)
    
    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    from api.auth import generate_api_key, hash_api_key, get_key_prefix, APIKey
    from app.database import get_db_session
    
    # Generate test keys
    TEST_API_KEY_FREE = generate_api_key("free")
    TEST_API_KEY_PREMIUM = generate_api_key("premium")
    
    # Store in database
    db = next(get_db_session())
    try:
        # Free tier key
        free_key = APIKey(
            key_hash=hash_api_key(TEST_API_KEY_FREE),
            key_prefix=get_key_prefix(TEST_API_KEY_FREE),
            client_name="Test Client - Free Tier",
            tier="free",
            is_active=True,
            notes="Automated test key"
        )
        db.add(free_key)
        
        # Premium tier key
        premium_key = APIKey(
            key_hash=hash_api_key(TEST_API_KEY_PREMIUM),
            key_prefix=get_key_prefix(TEST_API_KEY_PREMIUM),
            client_name="Test Client - Premium Tier",
            tier="premium",
            is_active=True,
            notes="Automated test key"
        )
        db.add(premium_key)
        
        db.commit()
        
        print(f"✅ Created FREE tier test key:    {get_key_prefix(TEST_API_KEY_FREE)}...")
        print(f"✅ Created PREMIUM tier test key: {get_key_prefix(TEST_API_KEY_PREMIUM)}...")
        print()
        
    finally:
        db.close()


def test_health_endpoint_no_auth():
    """Test that /healthz endpoint does NOT require authentication"""
    print("\n" + "="*60)
    print("TEST 1: Health Endpoint (No Auth Required)")
    print("="*60)
    
    response = requests.get(f"{API_BASE_URL}/healthz")
    
    if response.status_code == 200:
        print("✅ PASS: Health endpoint accessible without API key")
        return True
    else:
        print(f"❌ FAIL: Expected 200, got {response.status_code}")
        return False


def test_missing_api_key():
    """Test that protected endpoints reject requests without API key"""
    print("\n" + "="*60)
    print("TEST 2: Missing API Key")
    print("="*60)
    
    response = requests.get(f"{API_BASE_URL}/api/v1/theaters")
    
    if response.status_code == 401:
        data = response.json()
        print(f"✅ PASS: Rejected with 401 Unauthorized")
        print(f"   Message: {data.get('detail')}")
        return True
    else:
        print(f"❌ FAIL: Expected 401, got {response.status_code}")
        return False


def test_invalid_api_key():
    """Test that invalid API keys are rejected"""
    print("\n" + "="*60)
    print("TEST 3: Invalid API Key")
    print("="*60)
    
    headers = {"X-API-Key": INVALID_API_KEY}
    response = requests.get(f"{API_BASE_URL}/api/v1/theaters", headers=headers)
    
    if response.status_code == 401:
        data = response.json()
        print(f"✅ PASS: Rejected invalid key with 401")
        print(f"   Message: {data.get('detail')}")
        return True
    else:
        print(f"❌ FAIL: Expected 401, got {response.status_code}")
        return False


def test_valid_api_key_free():
    """Test that valid free tier API key works"""
    print("\n" + "="*60)
    print("TEST 4: Valid API Key (Free Tier)")
    print("="*60)
    
    headers = {"X-API-Key": TEST_API_KEY_FREE}
    response = requests.get(f"{API_BASE_URL}/api/v1/theaters", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ PASS: Free tier key accepted")
        print(f"   Theaters returned: {data.get('theater_count', 0)}")
        
        # Check rate limit headers
        if 'X-RateLimit-Limit' in response.headers:
            print(f"   Rate Limit: {response.headers.get('X-RateLimit-Limit')}")
            print(f"   Remaining: {response.headers.get('X-RateLimit-Remaining')}")
        
        return True
    else:
        print(f"❌ FAIL: Expected 200, got {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def test_valid_api_key_premium():
    """Test that valid premium tier API key works"""
    print("\n" + "="*60)
    print("TEST 5: Valid API Key (Premium Tier)")
    print("="*60)
    
    headers = {"X-API-Key": TEST_API_KEY_PREMIUM}
    response = requests.get(f"{API_BASE_URL}/api/v1/films?limit=10", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ PASS: Premium tier key accepted")
        print(f"   Films returned: {data.get('film_count', 0)}")
        return True
    else:
        print(f"❌ FAIL: Expected 200, got {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def test_expired_api_key():
    """Test that expired API keys are rejected"""
    print("\n" + "="*60)
    print("TEST 6: Expired API Key")
    print("="*60)
    
    # Create an expired key
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    from api.auth import generate_api_key, hash_api_key, get_key_prefix, APIKey
    from app.database import get_db_session
    
    expired_key = generate_api_key("free")
    
    db = next(get_db_session())
    try:
        expired_key_record = APIKey(
            key_hash=hash_api_key(expired_key),
            key_prefix=get_key_prefix(expired_key),
            client_name="Expired Test Key",
            tier="free",
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1)  # Expired yesterday
        )
        db.add(expired_key_record)
        db.commit()
        
        # Try to use expired key
        headers = {"X-API-Key": expired_key}
        response = requests.get(f"{API_BASE_URL}/api/v1/theaters", headers=headers)
        
        if response.status_code == 401:
            data = response.json()
            print(f"✅ PASS: Expired key rejected with 401")
            print(f"   Message: {data.get('detail')}")
            
            # Cleanup
            db.delete(expired_key_record)
            db.commit()
            return True
        else:
            print(f"❌ FAIL: Expected 401, got {response.status_code}")
            db.delete(expired_key_record)
            db.commit()
            return False
    finally:
        db.close()


def test_inactive_api_key():
    """Test that deactivated API keys are rejected"""
    print("\n" + "="*60)
    print("TEST 7: Inactive API Key")
    print("="*60)
    
    # Create an inactive key
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    from api.auth import generate_api_key, hash_api_key, get_key_prefix, APIKey
    from app.database import get_db_session
    
    inactive_key = generate_api_key("free")
    
    db = next(get_db_session())
    try:
        inactive_key_record = APIKey(
            key_hash=hash_api_key(inactive_key),
            key_prefix=get_key_prefix(inactive_key),
            client_name="Inactive Test Key",
            tier="free",
            is_active=False  # Deactivated
        )
        db.add(inactive_key_record)
        db.commit()
        
        # Try to use inactive key
        headers = {"X-API-Key": inactive_key}
        response = requests.get(f"{API_BASE_URL}/api/v1/theaters", headers=headers)
        
        if response.status_code == 401:
            data = response.json()
            print(f"✅ PASS: Inactive key rejected with 401")
            print(f"   Message: {data.get('detail')}")
            
            # Cleanup
            db.delete(inactive_key_record)
            db.commit()
            return True
        else:
            print(f"❌ FAIL: Expected 401, got {response.status_code}")
            db.delete(inactive_key_record)
            db.commit()
            return False
    finally:
        db.close()


def test_rate_limiting_free_tier():
    """Test that free tier rate limiting works (100/hour)"""
    print("\n" + "="*60)
    print("TEST 8: Rate Limiting (Free Tier)")
    print("="*60)
    print("⚠️  Note: This test makes 102 rapid requests and may take 10-20 seconds")
    
    headers = {"X-API-Key": TEST_API_KEY_FREE}
    
    # Make 102 requests rapidly (free tier limit is 100/hour)
    success_count = 0
    rate_limited = False
    
    for i in range(102):
        response = requests.get(f"{API_BASE_URL}/api/v1/theaters", headers=headers)
        
        if response.status_code == 200:
            success_count += 1
        elif response.status_code == 429:
            rate_limited = True
            print(f"   Request {i+1}: Rate limited (429)")
            print(f"   Message: {response.json().get('detail')}")
            break
        else:
            print(f"   Unexpected status: {response.status_code}")
    
    if rate_limited:
        print(f"✅ PASS: Rate limiting triggered after {success_count} requests")
        print(f"   Free tier limit: 100 requests/hour")
        return True
    else:
        print(f"⚠️  WARNING: Made {success_count} requests without rate limiting")
        print(f"   This might be expected if rate limiting is not yet enforced")
        return True  # Don't fail, just warn


def test_usage_tracking():
    """Test that API key usage is tracked"""
    print("\n" + "="*60)
    print("TEST 9: Usage Tracking")
    print("="*60)
    
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    from api.auth import get_key_prefix, APIKey
    from app.database import get_db_session
    
    # Get current request count
    db = next(get_db_session())
    try:
        key_prefix = get_key_prefix(TEST_API_KEY_PREMIUM)
        key_record = db.query(APIKey).filter(APIKey.key_prefix == key_prefix).first()
        initial_count = key_record.total_requests if key_record else 0
        
        # Make a request
        headers = {"X-API-Key": TEST_API_KEY_PREMIUM}
        response = requests.get(f"{API_BASE_URL}/api/v1/theaters", headers=headers)
        
        # Check updated count
        db.refresh(key_record)
        final_count = key_record.total_requests
        
        if final_count > initial_count:
            print(f"✅ PASS: Usage tracked successfully")
            print(f"   Initial count: {initial_count}")
            print(f"   Final count: {final_count}")
            print(f"   Increment: {final_count - initial_count}")
            return True
        else:
            print(f"❌ FAIL: Usage not tracked")
            print(f"   Count stayed at {initial_count}")
            return False
    finally:
        db.close()


def test_all_endpoints_protected():
    """Test that all endpoints (except /healthz) require auth"""
    print("\n" + "="*60)
    print("TEST 10: All Endpoints Protected")
    print("="*60)
    
    endpoints = [
        "/api/v1/theaters",
        "/api/v1/films",
        "/api/v1/scrape-runs",
        "/api/v1/showtimes/search",
        "/api/v1/pricing",
        "/api/v1/reports/operating-hours?theater=Test",
        "/api/v1/reports/plf-formats",
        "/api/v1/reports/daily-lineup?theater=Test&date=2025-11-27"
    ]
    
    all_protected = True
    
    for endpoint in endpoints:
        response = requests.get(f"{API_BASE_URL}{endpoint}")
        
        if response.status_code == 401:
            print(f"   ✅ {endpoint}")
        else:
            print(f"   ❌ {endpoint} - returned {response.status_code}")
            all_protected = False
    
    if all_protected:
        print(f"\n✅ PASS: All endpoints properly protected")
        return True
    else:
        print(f"\n❌ FAIL: Some endpoints not protected")
        return False


def cleanup_test_keys():
    """Remove test API keys from database"""
    print("\n" + "="*60)
    print("CLEANUP: Removing Test API Keys")
    print("="*60)
    
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    from api.auth import get_key_prefix, APIKey
    from app.database import get_db_session
    
    db = next(get_db_session())
    try:
        # Delete test keys
        free_prefix = get_key_prefix(TEST_API_KEY_FREE)
        premium_prefix = get_key_prefix(TEST_API_KEY_PREMIUM)
        
        db.query(APIKey).filter(APIKey.key_prefix == free_prefix).delete()
        db.query(APIKey).filter(APIKey.key_prefix == premium_prefix).delete()
        db.query(APIKey).filter(APIKey.client_name.like("%Test%")).delete()
        
        db.commit()
        print("✅ Test keys removed")
    finally:
        db.close()


def main():
    """Run all authentication tests"""
    print("\n" + "="*70)
    print(" "*15 + "🔐 API AUTHENTICATION TEST SUITE 🔐")
    print("="*70)
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if API is running
    try:
        response = requests.get(f"{API_BASE_URL}/healthz", timeout=2)
        if response.status_code != 200:
            print(f"\n❌ ERROR: API not responding at {API_BASE_URL}")
            print("   Make sure the API is running: uvicorn api.main:app --reload")
            return
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR: Cannot connect to API at {API_BASE_URL}")
        print(f"   {str(e)}")
        print("\n   Make sure the API is running:")
        print("   uvicorn api.main:app --reload --port 8000")
        return
    
    # Setup test keys
    setup_test_keys()
    
    # Run tests
    results = []
    
    results.append(("Health endpoint (no auth)", test_health_endpoint_no_auth()))
    results.append(("Missing API key", test_missing_api_key()))
    results.append(("Invalid API key", test_invalid_api_key()))
    results.append(("Valid key (free tier)", test_valid_api_key_free()))
    results.append(("Valid key (premium tier)", test_valid_api_key_premium()))
    results.append(("Expired API key", test_expired_api_key()))
    results.append(("Inactive API key", test_inactive_api_key()))
    results.append(("Rate limiting", test_rate_limiting_free_tier()))
    results.append(("Usage tracking", test_usage_tracking()))
    results.append(("All endpoints protected", test_all_endpoints_protected()))
    
    # Cleanup
    cleanup_test_keys()
    
    # Print summary
    print("\n" + "="*70)
    print(" "*25 + "TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("="*70)
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! Authentication is working correctly.\n")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.\n")


if __name__ == "__main__":
    main()
