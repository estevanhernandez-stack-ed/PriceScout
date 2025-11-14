"""
Configuration Test Script for PriceScout
Version: 1.0.0
Date: November 13, 2025

Tests configuration loading and environment detection.
Run this to verify your configuration before deployment.

Usage:
    python test_config.py
    python test_config.py --azure  # Simulate Azure environment
"""

import os
import sys
import argparse

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_section(title):
    """Print formatted section header"""
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)


def print_item(key, value, indent=0):
    """Print formatted configuration item"""
    spaces = "  " * indent
    if value is None:
        value_str = "❌ NOT SET"
    elif isinstance(value, bool):
        value_str = "✓ " + str(value) if value else "✗ " + str(value)
    elif isinstance(value, str) and ('password' in key.lower() or 'secret' in key.lower() or 'key' in key.lower()):
        # Mask sensitive values
        if len(value) > 8:
            value_str = "🔒 " + value[:4] + "..." + value[-4:]
        else:
            value_str = "🔒 ***"
    else:
        value_str = str(value)
    
    print(f"{spaces}{key:35s}: {value_str}")


def test_basic_config():
    """Test basic configuration loading"""
    print_section("1. Basic Configuration")
    
    from app import config
    
    print_item("PROJECT_DIR", config.PROJECT_DIR)
    print_item("SCRIPT_DIR", config.SCRIPT_DIR)
    print_item("DATA_DIR", config.DATA_DIR)
    print_item("DEBUG_DIR", config.DEBUG_DIR)
    print_item("REPORTS_DIR", config.REPORTS_DIR)
    
    return True


def test_environment_detection():
    """Test environment detection"""
    print_section("2. Environment Detection")
    
    from app import config
    
    print_item("is_azure_deployment()", config.is_azure_deployment())
    print_item("is_production()", config.is_production())
    print_item("is_development()", config.is_development())
    print_item("APP_ENVIRONMENT", config.APP_ENVIRONMENT)
    print_item("DEBUG", config.DEBUG)
    
    return True


def test_database_config():
    """Test database configuration"""
    print_section("3. Database Configuration")
    
    from app import config
    from app.db_session import get_current_database_info
    
    db_info = get_current_database_info()
    
    print_item("Database Type", db_info['type'].upper())
    print_item("Database URL", db_info['url'])
    print_item("Engine Active", db_info['engine_active'])
    print_item("Session Factory Active", db_info['session_factory_active'])
    
    if config.DATABASE_URL:
        print_item("DATABASE_URL", config.DATABASE_URL)
    else:
        print("\n  SQLite Configuration:")
        print_item("USER_DB_FILE", config.USER_DB_FILE, indent=1)
        print_item("DB_FILE", config.DB_FILE or "❌ NOT SET (set by app)", indent=1)
    
    return True


def test_database_connection():
    """Test actual database connection"""
    print_section("4. Database Connection Test")
    
    try:
        from app.db_session import get_engine, get_session
        from sqlalchemy import text
        
        # Get engine
        engine = get_engine()
        print_item("Engine Created", "✓ SUCCESS")
        
        # Test connection
        with get_session() as session:
            result = session.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            if row and row[0] == 1:
                print_item("Connection Test", "✓ SUCCESS")
                print_item("Query Result", f"SELECT 1 returned {row[0]}")
                return True
            else:
                print_item("Connection Test", "✗ FAILED - Unexpected result")
                return False
    
    except Exception as e:
        print_item("Connection Test", f"✗ FAILED")
        print(f"\n  Error: {e}")
        return False


def test_azure_services():
    """Test Azure services configuration"""
    print_section("5. Azure Services Configuration")
    
    from app import config
    
    print_item("AZURE_KEY_VAULT_URL", config.AZURE_KEY_VAULT_URL)
    print_item("APPLICATIONINSIGHTS_CONNECTION_STRING", 
               config.APPLICATIONINSIGHTS_CONNECTION_STRING)
    print_item("APPINSIGHTS_INSTRUMENTATION_KEY", 
               config.APPINSIGHTS_INSTRUMENTATION_KEY)
    print_item("AZURE_STORAGE_CONNECTION_STRING", 
               config.AZURE_STORAGE_CONNECTION_STRING)
    
    # Check if Key Vault is accessible (if configured)
    if config.AZURE_KEY_VAULT_URL:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=config.AZURE_KEY_VAULT_URL, credential=credential)
            
            # Try to list secrets (won't show values)
            secret_properties = list(client.list_properties_of_secrets())
            print_item("Key Vault Access", f"✓ SUCCESS - {len(secret_properties)} secrets found")
            return True
        except ImportError:
            print_item("Key Vault Access", "⚠ WARNING - Azure libraries not installed")
            print("  Install with: pip install azure-identity azure-keyvault-secrets")
            return True
        except Exception as e:
            print_item("Key Vault Access", f"✗ FAILED")
            print(f"\n  Error: {e}")
            print("  Hint: Run 'az login' to authenticate")
            return False
    else:
        print("\n  ℹ Key Vault not configured (optional for local development)")
        return True


def test_security_config():
    """Test security configuration"""
    print_section("6. Security Configuration")
    
    from app import config
    
    print_item("SECRET_KEY", config.SECRET_KEY)
    print_item("JWT_SECRET_KEY", config.JWT_SECRET_KEY)
    print_item("SESSION_TIMEOUT_MINUTES", config.SESSION_TIMEOUT_MINUTES)
    
    # Check if using default secret in production
    if config.is_production() and config.SECRET_KEY == 'dev-secret-key-change-in-production':
        print("\n  ⚠ WARNING: Using default SECRET_KEY in production!")
        print("  Generate a secure key: python -c 'import secrets; print(secrets.token_hex(32))'")
        return False
    
    return True


def test_app_settings():
    """Test application settings"""
    print_section("7. Application Settings")
    
    from app import config
    
    print_item("APP_NAME", config.APP_NAME)
    print_item("APP_VERSION", config.APP_VERSION)
    print_item("HOST", config.HOST)
    print_item("PORT", config.PORT)
    print_item("LOG_LEVEL", config.LOG_LEVEL)
    
    return True


def test_scraper_config():
    """Test scraper configuration"""
    print_section("8. Scraper Configuration")
    
    from app import config
    
    print_item("PLAYWRIGHT_TIMEOUT", config.PLAYWRIGHT_TIMEOUT)
    print_item("PLAYWRIGHT_HEADLESS", config.PLAYWRIGHT_HEADLESS)
    print_item("SCRAPER_DELAY_SECONDS", config.SCRAPER_DELAY_SECONDS)
    print_item("SCRAPER_MAX_RETRIES", config.SCRAPER_MAX_RETRIES)
    print_item("OMDB_API_KEY", config.OMDB_API_KEY)
    
    return True


def test_feature_flags():
    """Test feature flags"""
    print_section("9. Feature Flags")
    
    from app import config
    
    print_item("ENABLE_ADMIN_MODE", config.ENABLE_ADMIN_MODE)
    print_item("ENABLE_DATA_EXPORT", config.ENABLE_DATA_EXPORT)
    print_item("ENABLE_BULK_UPLOAD", config.ENABLE_BULK_UPLOAD)
    print_item("ENABLE_DATABASE_RESET", config.ENABLE_DATABASE_RESET)
    print_item("ENABLE_TEST_MODE", config.ENABLE_TEST_MODE)
    
    return True


def test_config_summary():
    """Test configuration summary"""
    print_section("10. Configuration Summary")
    
    from app import config
    
    summary = config.get_config_summary()
    for key, value in summary.items():
        print_item(key, value)
    
    return True


def run_all_tests(skip_connection=False):
    """Run all configuration tests"""
    print("\n" + "="*70)
    print(" PriceScout Configuration Test Suite")
    print(" Version 1.0.0")
    print("="*70)
    
    tests = [
        ("Basic Configuration", test_basic_config),
        ("Environment Detection", test_environment_detection),
        ("Database Configuration", test_database_config),
        ("Database Connection", test_database_connection if not skip_connection else lambda: True),
        ("Azure Services", test_azure_services),
        ("Security Configuration", test_security_config),
        ("Application Settings", test_app_settings),
        ("Scraper Configuration", test_scraper_config),
        ("Feature Flags", test_feature_flags),
        ("Configuration Summary", test_config_summary),
    ]
    
    results = []
    for name, test_func in tests:
        if skip_connection and "Connection" in name:
            print(f"\n⊘ Skipping: {name}")
            continue
        
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test Error in {name}: {e}")
            results.append((name, False))
    
    # Final summary
    print("\n" + "="*70)
    print(" TEST RESULTS SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:8s} {name}")
    
    print("="*70)
    print(f" Total: {passed}/{total} tests passed")
    print("="*70)
    
    return passed == total


def simulate_azure_environment():
    """Simulate Azure environment for testing"""
    print("\n🔧 Simulating Azure environment...")
    os.environ['DEPLOYMENT_ENV'] = 'azure'
    os.environ['WEBSITE_SITE_NAME'] = 'pricescout-app-test'
    os.environ['ENVIRONMENT'] = 'production'
    print("   Set: DEPLOYMENT_ENV=azure")
    print("   Set: WEBSITE_SITE_NAME=pricescout-app-test")
    print("   Set: ENVIRONMENT=production")


def main():
    parser = argparse.ArgumentParser(description="Test PriceScout configuration")
    parser.add_argument('--azure', action='store_true', help="Simulate Azure environment")
    parser.add_argument('--skip-connection', action='store_true', 
                       help="Skip database connection test")
    
    args = parser.parse_args()
    
    if args.azure:
        simulate_azure_environment()
    
    success = run_all_tests(skip_connection=args.skip_connection)
    
    if not success:
        print("\n⚠ Some tests failed. Review configuration before deployment.")
        sys.exit(1)
    else:
        print("\n✓ All tests passed! Configuration is valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
