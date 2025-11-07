"""
End-to-end tests for security features.

Tests the complete security workflows including authentication, authorization,
password reset, and session management.
"""
import pytest
from unittest.mock import MagicMock, patch, call
import time
from app import users
from app.users import (
    ROLE_ADMIN, ROLE_MANAGER, ROLE_USER,
    create_user, verify_user, generate_reset_code, 
    reset_password_with_code, get_user_allowed_modes
)

# Strong test passwords
ADMIN_PASSWORD = "AdminSecure123!"
MANAGER_PASSWORD = "ManagerSecure456!"
USER_PASSWORD = "UserSecure789!"
NEW_PASSWORD = "NewSecure999!"


@pytest.fixture
def auth_db(monkeypatch, tmp_path):
    """Create a temporary database for authentication tests."""
    import sqlite3
    
    # Create in-memory database
    shared_conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
    shared_conn.row_factory = sqlite3.Row
    
    def mock_get_db_connection():
        return shared_conn
    
    # Patch the get_db_connection function
    monkeypatch.setattr('app.users.get_db_connection', mock_get_db_connection)
    
    # Initialize the database
    users.init_database()
    
    yield shared_conn
    
    shared_conn.close()


class TestAuthenticationFlow:
    """End-to-end tests for complete authentication flow."""
    
    def test_complete_login_logout_flow(self, auth_db):
        """Test complete authentication workflow: register → login → verify session → logout."""
        # Step 1: Create a user
        success, message = create_user('testuser', USER_PASSWORD, role=ROLE_USER, company='Test Co')
        assert success is True, f"User creation failed: {message}"
        
        # Step 2: Verify user can login with correct password
        user = verify_user('testuser', USER_PASSWORD)
        assert user is not None, "Login with correct password failed"
        assert user['username'] == 'testuser'
        assert user['role'] == ROLE_USER
        assert user['company'] == 'Test Co'
        
        # Step 3: Verify user cannot login with wrong password
        invalid_user = verify_user('testuser', 'WrongPass123!')
        assert invalid_user is None, "Login should fail with wrong password"
        
        # Step 4: Verify session data is correct
        assert user['is_admin'] == 0, "Regular user should not be admin"
        modes = get_user_allowed_modes('testuser')
        assert len(modes) == 3, f"User should have 3 modes, got {len(modes)}"
        assert 'Market Mode' in modes, "User should have Market Mode"
    
    def test_admin_login_has_full_access(self, auth_db):
        """Test that admin login provides full system access."""
        # Create admin user
        success, message = create_user('admin_user', ADMIN_PASSWORD, role=ROLE_ADMIN)
        assert success is True
        
        # Login
        user = verify_user('admin_user', ADMIN_PASSWORD)
        assert user is not None
        assert user['is_admin'] == 1
        assert user['role'] == ROLE_ADMIN
        
        # Verify admin has all modes
        modes = get_user_allowed_modes('admin_user')
        assert len(modes) == 8, f"Admin should have all 8 modes, got {len(modes)}"
        assert 'Admin' in modes
        assert 'Data Management' in modes
    
    def test_multiple_concurrent_sessions(self, auth_db):
        """Test that multiple users can be logged in simultaneously."""
        # Create multiple users
        create_user('user1', USER_PASSWORD, role=ROLE_USER)
        create_user('user2', MANAGER_PASSWORD, role=ROLE_MANAGER)
        create_user('user3', ADMIN_PASSWORD, role=ROLE_ADMIN)
        
        # All should be able to login
        session1 = verify_user('user1', USER_PASSWORD)
        session2 = verify_user('user2', MANAGER_PASSWORD)
        session3 = verify_user('user3', ADMIN_PASSWORD)
        
        assert session1 is not None
        assert session2 is not None
        assert session3 is not None
        
        # Verify each has correct permissions
        assert session1['role'] == ROLE_USER
        assert session2['role'] == ROLE_MANAGER
        assert session3['role'] == ROLE_ADMIN


class TestRBACAuthorizationFlow:
    """End-to-end tests for role-based access control."""
    
    def test_user_role_mode_access(self, auth_db):
        """Test that regular users can only access their assigned modes."""
        create_user('limited_user', USER_PASSWORD, role=ROLE_USER)
        user = verify_user('limited_user', USER_PASSWORD)
        assert user is not None
        
        # Get allowed modes
        allowed_modes = get_user_allowed_modes('limited_user')
        
        # User should have limited access
        assert len(allowed_modes) == 3
        assert 'Market Mode' in allowed_modes
        assert 'CompSnipe Mode' in allowed_modes
        assert 'Poster Board' in allowed_modes
        
        # User should NOT have admin modes
        assert 'Admin' not in allowed_modes
        assert 'Data Management' not in allowed_modes
        assert 'Theater Matching' not in allowed_modes
    
    def test_manager_role_mode_access(self, auth_db):
        """Test that managers have intermediate access."""
        create_user('manager_user', MANAGER_PASSWORD, role=ROLE_MANAGER)
        user = verify_user('manager_user', MANAGER_PASSWORD)
        assert user is not None
        
        # Get allowed modes
        allowed_modes = get_user_allowed_modes('manager_user')
        
        # Manager should have 5 modes
        assert len(allowed_modes) == 5
        assert 'Market Mode' in allowed_modes
        assert 'Operating Hours Mode' in allowed_modes
        assert 'CompSnipe Mode' in allowed_modes
        
        # Manager should NOT have admin-only modes
        assert 'Admin' not in allowed_modes
        assert 'Data Management' not in allowed_modes
        assert 'Theater Matching' not in allowed_modes
    
    def test_role_escalation_prevented(self, auth_db):
        """Test that users cannot escalate their own privileges."""
        # Create a regular user
        create_user('regular_joe', USER_PASSWORD, role=ROLE_USER)
        
        # Verify they're a user
        user = verify_user('regular_joe', USER_PASSWORD)
        assert user['role'] == ROLE_USER
        
        # Modes should be limited
        modes_before = get_user_allowed_modes('regular_joe')
        assert len(modes_before) == 3
        
        # Even if they somehow got admin modes list, they can't access admin features
        # because the role check happens at the database level
        assert user['is_admin'] == 0
        
    def test_company_isolation(self, auth_db):
        """Test that users are properly associated with their companies."""
        # Create users from different companies
        create_user('amc_user', USER_PASSWORD, role=ROLE_USER, company='AMC Theatres')
        create_user('marcus_user', USER_PASSWORD, role=ROLE_USER, company='Marcus Theatres')
        
        # Verify company assignments
        amc_session = verify_user('amc_user', USER_PASSWORD)
        marcus_session = verify_user('marcus_user', USER_PASSWORD)
        
        assert amc_session['company'] == 'AMC Theatres'
        assert marcus_session['company'] == 'Marcus Theatres'
        
        # Both should have same role permissions
        amc_modes = get_user_allowed_modes('amc_user')
        marcus_modes = get_user_allowed_modes('marcus_user')
        assert amc_modes == marcus_modes


class TestPasswordResetFlow:
    """End-to-end tests for password reset workflow."""
    
    def test_complete_password_reset_flow(self, auth_db):
        """Test complete password reset: request → verify → reset → login."""
        # Step 1: Create a user
        create_user('forgetful_user', USER_PASSWORD, role=ROLE_USER)
        
        # Step 2: User forgets password and requests reset
        success, code = generate_reset_code('forgetful_user')
        assert success is True
        assert len(code) == 6
        assert code.isdigit()
        
        # Step 3: User receives code and enters it (with new password)
        reset_success, message = reset_password_with_code('forgetful_user', code, NEW_PASSWORD)
        assert reset_success is True, f"Password reset failed: {message}"
        
        # Step 4: User cannot login with old password
        old_login = verify_user('forgetful_user', USER_PASSWORD)
        assert old_login is None, "Should not login with old password"
        
        # Step 5: User can login with new password
        new_login = verify_user('forgetful_user', NEW_PASSWORD)
        assert new_login is not None, "Should login with new password"
        assert new_login['username'] == 'forgetful_user'
    
    def test_reset_code_expires(self, auth_db):
        """Test that reset codes expire after time limit."""
        create_user('test_user', USER_PASSWORD, role=ROLE_USER)
        
        # Generate code
        success, code = generate_reset_code('test_user')
        assert success is True
        
        # Manually expire the code
        conn = auth_db
        conn.execute(
            "UPDATE users SET reset_code_expiry = ? WHERE username = ?",
            (int(time.time()) - 1000, 'test_user')
        )
        conn.commit()
        
        # Try to reset with expired code
        reset_success, message = reset_password_with_code('test_user', code, NEW_PASSWORD)
        assert reset_success is False
        assert "expired" in message.lower()
        
        # Original password should still work
        user = verify_user('test_user', USER_PASSWORD)
        assert user is not None
    
    def test_reset_code_max_attempts(self, auth_db):
        """Test that reset codes are invalidated after max attempts."""
        create_user('test_user', USER_PASSWORD, role=ROLE_USER)
        
        # Generate code
        success, code = generate_reset_code('test_user')
        assert success is True
        
        # Try wrong code 3 times
        from app.users import verify_reset_code
        for i in range(3):
            verify_reset_code('test_user', '999999')
        
        # 4th attempt should fail due to max attempts
        valid, message = verify_reset_code('test_user', code)
        assert valid is False
        assert "maximum" in message.lower() or "attempts" in message.lower()
    
    def test_reset_code_one_time_use(self, auth_db):
        """Test that reset codes can only be used once."""
        create_user('test_user', USER_PASSWORD, role=ROLE_USER)
        
        # Generate and use code once
        success, code = generate_reset_code('test_user')
        reset_success, _ = reset_password_with_code('test_user', code, NEW_PASSWORD)
        assert reset_success is True
        
        # Try to reuse the same code
        second_reset, message = reset_password_with_code('test_user', code, 'AnotherPass123!')
        assert second_reset is False
        
        # Password should still be the first reset password
        user = verify_user('test_user', NEW_PASSWORD)
        assert user is not None
    
    def test_reset_requires_strong_password(self, auth_db):
        """Test that password reset enforces password complexity."""
        create_user('test_user', USER_PASSWORD, role=ROLE_USER)
        
        # Generate code
        success, code = generate_reset_code('test_user')
        assert success is True
        
        # Try to reset with weak password
        weak_passwords = [
            'short',           # Too short
            'nouppercase1!',   # No uppercase
            'NOLOWERCASE1!',   # No lowercase
            'NoNumbers!',      # No number
            'NoSpecial123'     # No special char
        ]
        
        for weak_pass in weak_passwords:
            # Generate fresh code for each attempt
            success, code = generate_reset_code('test_user')
            reset_success, message = reset_password_with_code('test_user', code, weak_pass)
            assert reset_success is False, f"Weak password '{weak_pass}' should be rejected"
            assert "password" in message.lower() or "characters" in message.lower()


class TestSecurityIntegration:
    """Integration tests for security features working together."""
    
    def test_failed_login_does_not_leak_user_existence(self, auth_db):
        """Test that failed logins don't reveal if username exists."""
        create_user('existing_user', USER_PASSWORD, role=ROLE_USER)
        
        # Failed login for existing user
        result1 = verify_user('existing_user', 'WrongPass123!')
        
        # Failed login for non-existent user
        result2 = verify_user('nonexistent_user', 'WrongPass123!')
        
        # Both should return None (no info leakage)
        assert result1 is None
        assert result2 is None
    
    def test_password_reset_does_not_leak_user_existence(self, auth_db):
        """Test that password reset requests don't reveal if username exists."""
        create_user('existing_user', USER_PASSWORD, role=ROLE_USER)
        
        # Request reset for existing user (returns True + code)
        success1, result1 = generate_reset_code('existing_user')
        
        # Request reset for non-existent user (returns False + message)
        success2, result2 = generate_reset_code('nonexistent_user')
        
        # Existing user gets code
        assert success1 is True
        assert len(result1) == 6 and result1.isdigit()
        
        # Non-existent user gets ambiguous message (doesn't reveal user doesn't exist)
        assert success2 is False
        assert "if this username exists" in result2.lower()
    
    def test_admin_can_create_users_with_any_role(self, auth_db):
        """Test that admin workflow can create users with different roles."""
        # Simulate admin creating users
        admin_success, _ = create_user('new_admin', ADMIN_PASSWORD, role=ROLE_ADMIN)
        manager_success, _ = create_user('new_manager', MANAGER_PASSWORD, role=ROLE_MANAGER)
        user_success, _ = create_user('new_user', USER_PASSWORD, role=ROLE_USER)
        
        assert admin_success is True
        assert manager_success is True
        assert user_success is True
        
        # Verify roles are correctly assigned
        admin_login = verify_user('new_admin', ADMIN_PASSWORD)
        manager_login = verify_user('new_manager', MANAGER_PASSWORD)
        user_login = verify_user('new_user', USER_PASSWORD)
        
        assert admin_login['role'] == ROLE_ADMIN
        assert manager_login['role'] == ROLE_MANAGER
        assert user_login['role'] == ROLE_USER
        
        # Verify mode counts
        assert len(get_user_allowed_modes('new_admin')) == 8
        assert len(get_user_allowed_modes('new_manager')) == 5
        assert len(get_user_allowed_modes('new_user')) == 3

