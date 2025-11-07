"""
Security Feature Testing Suite
Tests all implemented security features for Price Scout application.

Usage:
    python scripts/test_security_features.py
    python scripts/test_security_features.py --verbose
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import json
from app import users, security_config
from datetime import datetime, timedelta
import tempfile

# Test results tracking
test_results = []

def log_test(name, passed, message=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": name, "passed": passed, "message": message})
    print(f"{status} - {name}")
    if message:
        print(f"     {message}")

def test_rate_limiting():
    """Test login rate limiting (5 attempts, 15min lockout)"""
    print("\n=== Testing Rate Limiting ===")
    
    test_username = "rate_limit_test_user"
    
    # Create test user
    users.create_user(test_username, "ValidPass123!", role='user')
    
    # Test 1: First 5 attempts should be allowed
    for i in range(5):
        result = security_config.check_login_attempts(test_username)
        if result:
            security_config.record_failed_login(test_username)
        log_test(f"Rate Limit - Attempt {i+1} allowed", result, f"Attempt {i+1}/5 should be allowed")
    
    # Test 2: 6th attempt should be blocked
    blocked = not security_config.check_login_attempts(test_username)
    log_test("Rate Limit - 6th attempt blocked", blocked, "User should be locked out after 5 failed attempts")
    
    # Test 3: Reset should work
    security_config.reset_login_attempts(test_username)
    allowed_after_reset = security_config.check_login_attempts(test_username)
    log_test("Rate Limit - Reset works", allowed_after_reset, "Should be allowed after manual reset")
    
    # Cleanup
    users.delete_user_by_username(test_username)

def test_session_timeout():
    """Test 30-minute session timeout"""
    print("\n=== Testing Session Timeout ===")
    
    # This test verifies the timeout logic exists
    # Actual timeout testing requires 30 minutes, so we verify the code paths
    
    # Test 1: Check timeout function exists
    has_timeout_check = hasattr(security_config, 'check_session_timeout')
    log_test("Session Timeout - Function exists", has_timeout_check)
    
    # Test 2: Check timeout constant is set correctly
    timeout_correct = security_config.SESSION_TIMEOUT_MINUTES == 30
    log_test("Session Timeout - 30 minute timeout configured", timeout_correct, 
             f"Configured: {security_config.SESSION_TIMEOUT_MINUTES} minutes")
    
    # Test 3: Verify forced password change function exists
    has_force_change = hasattr(users, 'force_password_change_required')
    log_test("Session Timeout - Force password change function exists", has_force_change)

def test_file_upload_validation():
    """Test file upload size limits and JSON validation"""
    print("\n=== Testing File Upload Validation ===")
    
    # Test 1: File size limit check
    max_size = security_config.MAX_FILE_SIZE_MB
    log_test("File Upload - Size limit configured", max_size == 50, 
             f"Max upload size: {max_size}MB")
    
    # Test 2: JSON depth constant
    max_depth = security_config.MAX_JSON_DEPTH
    log_test("File Upload - JSON depth limit configured", max_depth == 10,
             f"Max JSON depth: {max_depth}")
    
    # Test 3: Test get_json_depth function
    deep_json = {"a": {"b": {"c": {"d": {"e": {"f": "deep"}}}}}}
    depth = security_config.get_json_depth(deep_json)
    log_test("File Upload - Deep JSON depth calculated", depth == 6,
             f"Calculated depth: {depth}")
    
    # Test 4: Shallow JSON
    shallow_json = {"a": "value", "b": {"c": "nested"}}
    depth = security_config.get_json_depth(shallow_json)
    log_test("File Upload - Shallow JSON depth calculated", depth == 2,
             f"Calculated depth: {depth}")
    
    #Test 5: File size validation function exists
    has_validate = hasattr(security_config, 'validate_uploaded_file')
    log_test("File Upload - Validation function exists", has_validate)

def test_password_requirements():
    """Test password complexity requirements"""
    print("\n=== Testing Password Requirements ===")
    
    test_passwords = [
        ("short", False, "Too short (< 8 chars)"),
        ("nouppercase123!", False, "No uppercase letter"),
        ("NOLOWERCASE123!", False, "No lowercase letter"),
        ("NoNumbers!", False, "No number"),
        ("NoSpecial123", False, "No special character"),
        ("ValidPass123!", True, "Meets all requirements"),
        ("AnotherGood1@", True, "Another valid password"),
    ]
    
    for password, should_pass, description in test_passwords:
        is_valid, msg = security_config.validate_password_strength(password)
        log_test(f"Password - {description}", is_valid == should_pass, 
                 f"'{password}' - {msg}")

def test_rbac_mode_restrictions():
    """Test role-based mode access"""
    print("\n=== Testing RBAC Mode Restrictions ===")
    
    # Create test users with different roles
    admin_user = "test_admin_rbac"
    manager_user = "test_manager_rbac"
    regular_user = "test_user_rbac"
    
    users.create_user(admin_user, "AdminPass123!", is_admin=True, role='admin')
    users.create_user(manager_user, "ManagerPass123!", role='manager')
    users.create_user(regular_user, "UserPass123!", role='user')
    
    # Test 1: Admin has all modes
    admin_modes = users.get_user_allowed_modes(admin_user)
    has_all_modes = len(admin_modes) == len(users.ALL_SIDEBAR_MODES)
    log_test("RBAC - Admin has all 8 modes", has_all_modes, 
             f"Admin modes: {len(admin_modes)}/8")
    
    # Test 2: Manager has correct default modes
    manager_modes = users.get_user_allowed_modes(manager_user)
    manager_perms = users.load_role_permissions()
    correct_manager_modes = set(manager_modes) == set(manager_perms.get('manager', []))
    log_test("RBAC - Manager has role-based modes", correct_manager_modes,
             f"Manager modes: {len(manager_modes)}")
    
    # Test 3: User has correct default modes
    user_modes = users.get_user_allowed_modes(regular_user)
    user_perms = users.load_role_permissions()
    correct_user_modes = set(user_modes) == set(user_perms.get('user', []))
    log_test("RBAC - User has role-based modes", correct_user_modes,
             f"User modes: {len(user_modes)}")
    
    # Test 4: Permission check function works
    can_access = users.user_can_access_mode(regular_user, "Market Mode")
    log_test("RBAC - Permission check works", can_access,
             "User should be able to access Market Mode")
    
    # Test 5: Admin check works
    is_admin = users.is_admin(admin_user)
    log_test("RBAC - Admin check works", is_admin,
             "Admin user should be identified as admin")
    
    # Cleanup
    users.delete_user_by_username(admin_user)
    users.delete_user_by_username(manager_user)
    users.delete_user_by_username(regular_user)

def test_password_reset_flow():
    """Test password reset code generation and verification"""
    print("\n=== Testing Password Reset Flow ===")
    
    test_user = "reset_test_user"
    users.create_user(test_user, "OldPass123!", role='user')
    
    # Test 1: Generate reset code
    success, code = users.generate_reset_code(test_user)
    log_test("Password Reset - Code generation", success,
             f"Generated code: {code}")
    
    # Test 2: Code is 6 digits
    is_six_digits = len(code) == 6 and code.isdigit()
    log_test("Password Reset - Code is 6 digits", is_six_digits,
             f"Code length: {len(code)}, all digits: {code.isdigit()}")
    
    # Test 3: Valid code verification
    valid, msg = users.verify_reset_code(test_user, code)
    log_test("Password Reset - Valid code accepted", valid, msg)
    
    # Test 4: Generate new code for failed attempt test
    success, new_code = users.generate_reset_code(test_user)
    
    # Test 5: Invalid code rejection
    invalid, msg = users.verify_reset_code(test_user, "999999")
    log_test("Password Reset - Invalid code rejected", not invalid, msg)
    
    # Test 6: Generate new code for max attempts test
    success, test_code = users.generate_reset_code(test_user)
    
    # Use up all 3 attempts
    for i in range(3):
        users.verify_reset_code(test_user, "000000")
    
    # 4th attempt should be blocked
    blocked, msg = users.verify_reset_code(test_user, test_code)
    log_test("Password Reset - Max attempts enforced", not blocked,
             "Should block after 3 failed attempts")
    
    # Cleanup
    users.delete_user_by_username(test_user)

def delete_user_by_username(username):
    """Helper to delete user by username"""
    user = users.get_user(username)
    if user:
        users.delete_user(user['id'])

# Monkey patch for cleanup
users.delete_user_by_username = delete_user_by_username

def print_summary():
    """Print test summary"""
    print("\n" + "="*60)
    print("SECURITY TESTING SUMMARY")
    print("="*60)
    
    total = len(test_results)
    passed = sum(1 for t in test_results if t['passed'])
    failed = total - passed
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if failed > 0:
        print("\n🚨 Failed Tests:")
        for test in test_results:
            if not test['passed']:
                print(f"  - {test['name']}: {test['message']}")
    
    print("\n" + "="*60)
    return failed == 0

if __name__ == "__main__":
    print("="*60)
    print("PRICE SCOUT - SECURITY FEATURE TESTING")
    print("="*60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Testing implemented security features...\n")
    
    # Run all tests
    test_rate_limiting()
    test_session_timeout()
    test_file_upload_validation()
    test_password_requirements()
    test_rbac_mode_restrictions()
    test_password_reset_flow()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)
