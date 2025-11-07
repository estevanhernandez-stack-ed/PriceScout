import pytest
import sqlite3
import bcrypt
import time
from app.users import (
    get_db_connection,
    init_database,
    create_user,
    get_user,
    verify_user,
    get_all_users,
    update_user,
    delete_user,
    get_user_role,
    get_user_allowed_modes,
    user_can_access_mode,
    is_admin,
    is_manager,
    change_password,
    force_password_change_required,
    generate_reset_code,
    verify_reset_code,
    reset_password_with_code,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_USER
)

# Strong test passwords that meet security requirements
STRONG_PASSWORD = "TestPass123!"
ADMIN_PASSWORD = "AdminPass456!"
MANAGER_PASSWORD = "ManagerPass789!"


@pytest.fixture
def temp_users_db(monkeypatch):
    """Create an in-memory users database for testing."""
    # Create a persistent in-memory connection that will be reused
    # by patching get_db_connection to return the same connection
    shared_conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
    shared_conn.row_factory = sqlite3.Row
    
    def mock_get_db_connection():
        return shared_conn
    
    # Patch the get_db_connection function
    monkeypatch.setattr('app.users.get_db_connection', mock_get_db_connection)
    
    # Initialize the database
    init_database()
    
    yield shared_conn
    
    # Close connection after tests
    shared_conn.close()


def test_init_database_creates_users_table(temp_users_db):
    """Test that init_database creates the users table."""
    conn = temp_users_db
    cursor = conn.cursor()
    
    # Check table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    assert cursor.fetchone() is not None
    
    # Check columns exist
    cursor.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in cursor.fetchall()}
    assert 'id' in columns
    assert 'username' in columns
    assert 'password_hash' in columns
    assert 'is_admin' in columns
    assert 'company' in columns
    assert 'default_company' in columns


def test_init_database_creates_default_admin(temp_users_db):
    """Test that init_database creates a default admin user."""
    conn = temp_users_db
    cursor = conn.cursor()
    
    # Check admin user exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    admin = cursor.fetchone()
    
    assert admin is not None
    assert admin['username'] == 'admin'
    assert admin['is_admin'] == 1


def test_create_user_success(temp_users_db):
    """Test successful user creation."""
    success, message = create_user('testuser', STRONG_PASSWORD, role=ROLE_USER, company='Test Co')
        
    assert success is True
    assert "successfully" in message
        
    # Verify user was created
    user = get_user('testuser')
    assert user is not None
    assert user['username'] == 'testuser'
    assert user['is_admin'] == 0
    assert user['company'] == 'Test Co'
    assert user['role'] == ROLE_USER
    # New users should be required to change password on first login
    assert user['must_change_password'] == 1


def test_create_user_with_default_company(temp_users_db):
    """Test user creation with default company."""
    success, message = create_user('testuser', STRONG_PASSWORD, role=ROLE_USER, default_company='Default Co')
        
    assert success is True
        
    user = get_user('testuser')
    assert user['default_company'] == 'Default Co'
    # New users should be required to change password
    assert user['must_change_password'] == 1


def test_create_user_duplicate_username(temp_users_db):
    """Test that duplicate usernames are rejected."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
        
    # Try to create duplicate
    success, message = create_user('testuser', 'DifferentPass123!', role=ROLE_USER)
        
    assert success is False
    assert "already exists" in message


def test_create_user_password_is_hashed(temp_users_db):
    """Test that passwords are properly hashed."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
        
    conn = temp_users_db
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = 'testuser'")
    stored_hash = cursor.fetchone()['password_hash']
        
    # Hash should not equal plaintext password
    assert stored_hash != STRONG_PASSWORD
        
    # Hash should be valid bcrypt hash
    assert bcrypt.checkpw(STRONG_PASSWORD.encode('utf-8'), stored_hash.encode('utf-8'))


def test_create_admin_user(temp_users_db):
    """Test creating an admin user."""
    success, message = create_user('admin_user', ADMIN_PASSWORD, role=ROLE_ADMIN)
        
    assert success is True
        
    user = get_user('admin_user')
    assert user['is_admin'] == 1
    assert user['role'] == ROLE_ADMIN


def test_get_user_exists(temp_users_db):
    """Test retrieving an existing user."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
        
    user = get_user('testuser')
        
    assert user is not None
    assert user['username'] == 'testuser'


def test_get_user_not_exists(temp_users_db):
    """Test retrieving a non-existent user."""
    user = get_user('nonexistent')
        
    assert user is None


def test_verify_user_correct_password(temp_users_db):
    """Test user verification with correct password."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
        
    user = verify_user('testuser', STRONG_PASSWORD)
        
    assert user is not None
    assert user['username'] == 'testuser'


def test_verify_user_incorrect_password(temp_users_db):
    """Test user verification with incorrect password."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
        
    user = verify_user('testuser', 'WrongPass123!')
        
    assert user is None


def test_verify_user_nonexistent_user(temp_users_db):
    """Test verification of non-existent user."""
    user = verify_user('nonexistent', STRONG_PASSWORD)
        
    assert user is None


def test_get_all_users(temp_users_db):
    """Test retrieving all users."""
    create_user('user1', STRONG_PASSWORD, role=ROLE_USER)
    create_user('user2', STRONG_PASSWORD, role=ROLE_MANAGER)
    create_user('user3', ADMIN_PASSWORD, role=ROLE_ADMIN)
        
    users = get_all_users()
        
    # Should have 4 users (3 created + default admin)
    assert len(users) >= 4
        
    usernames = [user['username'] for user in users]
    assert 'user1' in usernames
    assert 'user2' in usernames
    assert 'user3' in usernames
    assert 'admin' in usernames


def test_get_all_users_excludes_password_hash(temp_users_db):
    """Test that get_all_users doesn't return password hashes."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
        
    users = get_all_users()
        
    # Check that password_hash is not in returned columns
    for user in users:
        assert 'password_hash' not in dict(user).keys()


def test_update_user(temp_users_db):
    """Test updating user information."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER, company='Old Company')
    user = get_user('testuser')
    user_id = user['id']
        
    # Update user
    update_user(user_id, 'newusername', True, 'New Company', 'Default Co')
        
    # Verify update
    updated_user = get_user('newusername')
    assert updated_user is not None
    assert updated_user['username'] == 'newusername'
    assert updated_user['is_admin'] == 1
    assert updated_user['company'] == 'New Company'
    assert updated_user['default_company'] == 'Default Co'
        
    # Old username should not exist
    old_user = get_user('testuser')
    assert old_user is None


def test_update_user_partial_fields(temp_users_db):
    """Test updating only some user fields."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER, company='Company A')
    user = get_user('testuser')
    user_id = user['id']
        
    # Update only admin status
    update_user(user_id, 'testuser', True, 'Company A', None)
        
    updated_user = get_user('testuser')
    assert updated_user['is_admin'] == 1
    assert updated_user['company'] == 'Company A'


def test_delete_user(temp_users_db):
    """Test deleting a user."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    user = get_user('testuser')
    user_id = user['id']
        
    # Delete user
    delete_user(user_id)
        
    # Verify deletion
    deleted_user = get_user('testuser')
    assert deleted_user is None


def test_delete_user_nonexistent(temp_users_db):
    """Test deleting a non-existent user doesn't raise error."""
    # Should not raise an error
    delete_user(99999)


def test_get_db_connection(temp_users_db):
    """Test database connection."""
    conn = get_db_connection()
        
    assert conn is not None
    assert isinstance(conn, sqlite3.Connection)
    assert conn.row_factory == sqlite3.Row
        
    conn.close()


def test_password_security_uses_bcrypt(temp_users_db):
    """Test that password hashing uses bcrypt."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
        
    conn = temp_users_db
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = 'testuser'")
    hash_str = cursor.fetchone()['password_hash']
        
    # Bcrypt hashes start with $2b$
    assert hash_str.startswith('$2b$')


# ============================================================================
# RBAC (Role-Based Access Control) Tests
# ============================================================================

def test_get_user_role_admin(temp_users_db):
    """Test getting admin user role."""
    create_user('admin_user', ADMIN_PASSWORD, role=ROLE_ADMIN)
    
    role = get_user_role('admin_user')
    assert role == ROLE_ADMIN


def test_get_user_role_manager(temp_users_db):
    """Test getting manager user role."""
    create_user('manager_user', MANAGER_PASSWORD, role=ROLE_MANAGER)
    
    role = get_user_role('manager_user')
    assert role == ROLE_MANAGER


def test_get_user_role_user(temp_users_db):
    """Test getting regular user role."""
    create_user('regular_user', STRONG_PASSWORD, role=ROLE_USER)
    
    role = get_user_role('regular_user')
    assert role == ROLE_USER


def test_get_user_role_nonexistent(temp_users_db):
    """Test getting role for non-existent user."""
    role = get_user_role('nonexistent')
    assert role is None


def test_get_user_allowed_modes_admin(temp_users_db):
    """Test getting allowed modes for admin user."""
    create_user('admin_user', ADMIN_PASSWORD, role=ROLE_ADMIN)
    
    modes = get_user_allowed_modes('admin_user')
    assert isinstance(modes, list)
    assert len(modes) == 8  # Admin has all 8 modes


def test_get_user_allowed_modes_manager(temp_users_db):
    """Test getting allowed modes for manager user."""
    create_user('manager_user', MANAGER_PASSWORD, role=ROLE_MANAGER)
    
    modes = get_user_allowed_modes('manager_user')
    assert isinstance(modes, list)
    assert len(modes) == 5  # Manager has 5 modes


def test_get_user_allowed_modes_user(temp_users_db):
    """Test getting allowed modes for regular user."""
    create_user('regular_user', STRONG_PASSWORD, role=ROLE_USER)
    
    modes = get_user_allowed_modes('regular_user')
    assert isinstance(modes, list)
    assert len(modes) == 3  # User has 3 modes


def test_user_can_access_mode_allowed(temp_users_db):
    """Test permission check for allowed mode."""
    create_user('regular_user', STRONG_PASSWORD, role=ROLE_USER)
    
    can_access = user_can_access_mode('regular_user', 'Market Mode')
    assert can_access is True


def test_user_can_access_mode_denied(temp_users_db):
    """Test permission check for denied mode."""
    create_user('regular_user', STRONG_PASSWORD, role=ROLE_USER)
    
    # Regular users can't access Admin mode
    can_access = user_can_access_mode('regular_user', 'Admin')
    assert can_access is False


def test_is_admin_true(temp_users_db):
    """Test is_admin for admin user."""
    create_user('admin_user', ADMIN_PASSWORD, role=ROLE_ADMIN)
    
    assert is_admin('admin_user') is True


def test_is_admin_false(temp_users_db):
    """Test is_admin for non-admin user."""
    create_user('regular_user', STRONG_PASSWORD, role=ROLE_USER)
    
    assert is_admin('regular_user') is False


def test_is_manager_true(temp_users_db):
    """Test is_manager for manager user."""
    create_user('manager_user', MANAGER_PASSWORD, role=ROLE_MANAGER)
    
    assert is_manager('manager_user') is True


def test_is_manager_false(temp_users_db):
    """Test is_manager for non-manager user."""
    create_user('regular_user', STRONG_PASSWORD, role=ROLE_USER)
    
    assert is_manager('regular_user') is False


def test_init_database_is_idempotent(temp_users_db):
    """Test that calling init_database multiple times is safe."""
    # Call init_database again
    init_database()
        
    # Should still have only one admin user
    conn = temp_users_db
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE username = 'admin'")
    count = cursor.fetchone()['count']
        
    assert count == 1


# ============================================================================
# Password Reset Tests
# ============================================================================

def test_generate_reset_code_success(temp_users_db):
    """Test generating a password reset code."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    
    success, code = generate_reset_code('testuser')
    
    assert success is True
    assert isinstance(code, str)
    assert len(code) == 6
    assert code.isdigit()


def test_generate_reset_code_nonexistent_user(temp_users_db):
    """Test generating reset code for non-existent user."""
    success, message = generate_reset_code('nonexistent')
    
    # Should return false but not reveal that user doesn't exist (security)
    assert success is False
    assert "if this username exists" in message.lower()


def test_verify_reset_code_valid(temp_users_db):
    """Test verifying a valid reset code."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    success, code = generate_reset_code('testuser')
    
    assert success is True
    
    # Verify the code
    valid, message = verify_reset_code('testuser', code)
    
    assert valid is True
    assert "verified" in message.lower() or "reset" in message.lower()


def test_verify_reset_code_invalid(temp_users_db):
    """Test verifying an invalid reset code."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    generate_reset_code('testuser')
    
    # Try wrong code
    valid, message = verify_reset_code('testuser', '999999')
    
    assert valid is False
    assert "invalid" in message.lower() or "attempts" in message.lower()


def test_verify_reset_code_expired(temp_users_db):
    """Test that expired codes are rejected."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    success, code = generate_reset_code('testuser')
    
    assert success is True
    
    # Manually expire the code by setting expiry to past
    conn = temp_users_db
    conn.execute(
        "UPDATE users SET reset_code_expiry = ? WHERE username = ?",
        (int(time.time()) - 1000, 'testuser')
    )
    conn.commit()
    
    # Try to verify expired code
    valid, message = verify_reset_code('testuser', code)
    
    assert valid is False
    assert "expired" in message.lower()


def test_verify_reset_code_max_attempts(temp_users_db):
    """Test that max attempts limit is enforced."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    generate_reset_code('testuser')
    
    # Try wrong code 3 times
    for i in range(3):
        verify_reset_code('testuser', '999999')
    
    # 4th attempt should fail due to max attempts
    valid, message = verify_reset_code('testuser', '999999')
    
    assert valid is False
    assert "maximum" in message.lower() or "attempts" in message.lower()


def test_reset_password_with_code_success(temp_users_db):
    """Test complete password reset flow."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    success, code = generate_reset_code('testuser')
    
    assert success is True
    
    # Reset password
    new_password = "NewStrongPass123!"
    reset_success, message = reset_password_with_code('testuser', code, new_password)
    
    assert reset_success is True
    assert "success" in message.lower() or "reset" in message.lower()
    
    # Verify can login with new password
    user = verify_user('testuser', new_password)
    assert user is not None
    
    # Verify cannot login with old password
    old_user = verify_user('testuser', STRONG_PASSWORD)
    assert old_user is None


def test_reset_password_with_code_invalid_code(temp_users_db):
    """Test password reset with invalid code."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    generate_reset_code('testuser')
    
    # Try to reset with wrong code
    success, message = reset_password_with_code('testuser', '999999', 'NewPass123!')
    
    assert success is False
    assert "invalid" in message.lower() or "code" in message.lower()


def test_reset_password_with_code_weak_password(temp_users_db):
    """Test that password reset enforces password complexity."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    success, code = generate_reset_code('testuser')
    
    assert success is True
    
    # Try to reset with weak password
    weak_password = "weak"
    reset_success, message = reset_password_with_code('testuser', code, weak_password)
    
    assert reset_success is False
    assert "password" in message.lower()


def test_password_complexity_validation(temp_users_db):
    """Test password complexity requirements."""
    # Too short
    success, message = create_user('user1', 'Short1!', role=ROLE_USER)
    assert success is False
    assert "8 characters" in message or "length" in message.lower()
    
    # No uppercase
    success, message = create_user('user2', 'nouppercase123!', role=ROLE_USER)
    assert success is False
    assert "uppercase" in message.lower()
    
    # No lowercase
    success, message = create_user('user3', 'NOLOWERCASE123!', role=ROLE_USER)
    assert success is False
    assert "lowercase" in message.lower()
    
    # No number
    success, message = create_user('user4', 'NoNumbers!', role=ROLE_USER)
    assert success is False
    assert "number" in message.lower()
    
    # No special character
    success, message = create_user('user5', 'NoSpecial123', role=ROLE_USER)
    assert success is False
    assert "special" in message.lower()
    
    # Valid password
    success, message = create_user('user6', STRONG_PASSWORD, role=ROLE_USER)
    assert success is True


def test_create_user_with_home_location(temp_users_db):
    """Test creating a user with home location."""
    success, message = create_user(
        'testuser', 
        STRONG_PASSWORD, 
        role=ROLE_MANAGER, 
        company='Test Co',
        home_location_type='market',
        home_location_value='Midwest > Chicago'
    )
    
    assert success is True
    
    user = get_user('testuser')
    assert user['home_location_type'] == 'market'
    assert user['home_location_value'] == 'Midwest > Chicago'


def test_update_user_home_location(temp_users_db):
    """Test updating a user's home location."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER, company='Test Co')
    user = get_user('testuser')
    user_id = user['id']
    
    # Update with home location
    update_user(
        user_id, 
        'testuser', 
        False, 
        'Test Co', 
        None,
        role=ROLE_USER,
        home_location_type='theater',
        home_location_value='Midwest > Chicago > AMC River East 21'
    )
    
    updated_user = get_user('testuser')
    assert updated_user['home_location_type'] == 'theater'
    assert updated_user['home_location_value'] == 'Midwest > Chicago > AMC River East 21'


def test_force_password_change_for_new_users(temp_users_db):
    """Test that new users are required to change password on first login."""
    create_user('newuser', STRONG_PASSWORD, role=ROLE_USER)
    
    # New user should be forced to change password
    assert force_password_change_required('newuser') is True


def test_password_change_clears_must_change_flag(temp_users_db):
    """Test that changing password clears the must_change_password flag."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    
    # Initially should require password change
    assert force_password_change_required('testuser') is True
    
    # Change password
    success, message = change_password('testuser', STRONG_PASSWORD, 'NewStrongPass123!')
    assert success is True
    
    # Should no longer require password change
    assert force_password_change_required('testuser') is False
    
    # Verify flag is cleared in database
    user = get_user('testuser')
    assert user['must_change_password'] == 0


def test_password_reset_clears_must_change_flag(temp_users_db):
    """Test that password reset clears the must_change_password flag."""
    create_user('testuser', STRONG_PASSWORD, role=ROLE_USER)
    
    # Generate reset code
    success, code = generate_reset_code('testuser')
    assert success is True
    assert code is not None
    
    # Reset password
    success, message = reset_password_with_code('testuser', code, 'NewStrongPass123!')
    assert success is True
    
    # Should no longer require password change
    assert force_password_change_required('testuser') is False
    
    # Verify flag is cleared
    user = get_user('testuser')
    assert user['must_change_password'] == 0


