import sqlite3
import bcrypt
import json
import os
import secrets
import time
import csv
import io
from datetime import datetime, timedelta
from app import security_config
from app.config import PROJECT_DIR

# Import PostgreSQL support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

DB_FILE = os.path.join(PROJECT_DIR, "users.db")  # Use absolute path to avoid confusion
ROLE_PERMISSIONS_FILE = os.path.join(PROJECT_DIR, "role_permissions.json")

# Reset code settings
RESET_CODE_LENGTH = 6
RESET_CODE_EXPIRY_MINUTES = 15
RESET_CODE_MAX_ATTEMPTS = 3

# Role definitions
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_USER = "user"

VALID_ROLES = [ROLE_ADMIN, ROLE_MANAGER, ROLE_USER]

# All available sidebar modes (from ui_config.json)
ALL_SIDEBAR_MODES = [
    "Market Mode",
    "Operating Hours Mode",
    "CompSnipe Mode",
    "Historical Data and Analysis",
    "Data Management",
    "Theater Matching",
    "Admin",
    "Poster Board"
]

# Default modes by role (can be overridden by role_permissions.json)
ADMIN_DEFAULT_MODES = ALL_SIDEBAR_MODES  # Admin gets everything
MANAGER_DEFAULT_MODES = ["Market Mode", "Operating Hours Mode", "CompSnipe Mode", "Historical Data and Analysis", "Poster Board"]
USER_DEFAULT_MODES = ["Market Mode", "CompSnipe Mode", "Poster Board"]

def load_role_permissions():
    """Load role permissions from JSON file, or return defaults"""
    if os.path.exists(ROLE_PERMISSIONS_FILE):
        try:
            with open(ROLE_PERMISSIONS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    # Return defaults
    return {
        ROLE_ADMIN: ADMIN_DEFAULT_MODES,
        ROLE_MANAGER: MANAGER_DEFAULT_MODES,
        ROLE_USER: USER_DEFAULT_MODES
    }

def save_role_permissions(permissions):
    """Save role permissions to JSON file"""
    with open(ROLE_PERMISSIONS_FILE, 'w') as f:
        json.dump(permissions, f, indent=2)
    security_config.log_security_event("role_permissions_updated", "system", 
                                      {"permissions": permissions})

def _use_postgresql():
    """Check if we should use PostgreSQL instead of SQLite"""
    return POSTGRES_AVAILABLE and os.getenv('DATABASE_URL')

def get_db_connection():
    """Get database connection - PostgreSQL if available, otherwise SQLite"""
    if _use_postgresql():
        # Use PostgreSQL
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        return conn
    else:
        # Use SQLite
        conn = sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn

class DictRow:
    """Wrapper to make PostgreSQL rows work like SQLite rows"""
    def __init__(self, data):
        self._data = data
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __contains__(self, key):
        return key in self._data
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def keys(self):
        return self._data.keys()

def init_database():
    """Initialize database - handles both PostgreSQL and SQLite"""
    if _use_postgresql():
        # PostgreSQL database is already initialized via schema.sql
        # Just verify the connection works
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users;")
                cursor.fetchone()
        except Exception as e:
            print(f"Warning: Could not verify PostgreSQL users table: {e}")
        return
    
    # SQLite initialization (legacy)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0,
                role TEXT DEFAULT 'user',
                allowed_modes TEXT DEFAULT '["User"]'
            )
        """)
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add company column if it doesn't exist
        if 'company' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN company TEXT")
        
        # Add default_company column if it doesn't exist
        if 'default_company' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN default_company TEXT")
        
        # Add home_location columns if they don't exist
        if 'home_location_type' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN home_location_type TEXT")  # 'director', 'market', or 'theater'
        if 'home_location_value' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN home_location_value TEXT")  # The actual director/market/theater name
        
        # Add must_change_password column if it doesn't exist
        if 'must_change_password' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0")
            # Set existing non-admin users to require password change
            cursor.execute("UPDATE users SET must_change_password = 1 WHERE username != 'admin'")
        
        # Add role column if it doesn't exist
        if 'role' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            # Migrate existing users: is_admin=1 → role='admin', is_admin=0 → role='user'
            cursor.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
            cursor.execute("UPDATE users SET role = 'user' WHERE is_admin = 0")
        
        # Add allowed_modes column if it doesn't exist
        if 'allowed_modes' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN allowed_modes TEXT DEFAULT '{}'")
            # Migrate existing users based on their role
            cursor.execute('UPDATE users SET allowed_modes = ? WHERE role = ?', 
                          (json.dumps(ADMIN_DEFAULT_MODES), ROLE_ADMIN))
            cursor.execute('UPDATE users SET allowed_modes = ? WHERE role = ?', 
                          (json.dumps(MANAGER_DEFAULT_MODES), ROLE_MANAGER))
            cursor.execute('UPDATE users SET allowed_modes = ? WHERE role = ?', 
                          (json.dumps(USER_DEFAULT_MODES), ROLE_USER))
        
        # Add password reset columns
        if 'reset_code' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_code TEXT")
        if 'reset_code_expiry' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_code_expiry INTEGER")
        if 'reset_attempts' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_attempts INTEGER DEFAULT 0")

        # Add a default admin user if one doesn't exist
        cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
        if not cursor.fetchone():
            password = b"admin"
            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
            cursor.execute("""
                INSERT INTO users (username, password_hash, is_admin, role, company, allowed_modes) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("admin", hashed_password.decode('utf-8'), 1, ROLE_ADMIN, None, json.dumps(ADMIN_DEFAULT_MODES)))
        conn.commit()

def create_user(username, password, is_admin=False, company=None, default_company=None, role=None, allowed_modes=None, home_location_type=None, home_location_value=None):
    """
    Create a new user with password validation and role-based access control.
    
    Args:
        username: Username for the new user
        password: Plain text password (will be hashed)
        is_admin: Whether user has admin privileges (legacy, use role instead)
        company: Company affiliation
        default_company: Default company for the user
        role: User role ('admin', 'manager', or 'user')
        allowed_modes: List of modes user can access (overrides role default)
        home_location_type: 'director', 'market', or 'theater'
        home_location_value: The actual director/market/theater name
        
    Returns:
        (success, message) tuple
    """
    # Validate password strength
    is_valid, error_msg = security_config.validate_password_strength(password)
    if not is_valid:
        return False, f"Password validation failed: {error_msg}"
    
    # Determine role (prefer explicit role, fall back to is_admin)
    if role is None:
        role = ROLE_ADMIN if is_admin else ROLE_USER
    
    if role not in VALID_ROLES:
        return False, f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}"
    
    # Determine allowed modes based on role if not explicitly provided
    if allowed_modes is None:
        if role == ROLE_ADMIN:
            allowed_modes = ADMIN_DEFAULT_MODES
        elif role == ROLE_MANAGER:
            allowed_modes = MANAGER_DEFAULT_MODES
        else:  # ROLE_USER
            allowed_modes = USER_DEFAULT_MODES
    
    # Ensure is_admin is set correctly for backwards compatibility
    is_admin = (role == ROLE_ADMIN)
    
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            if _use_postgresql():
                # PostgreSQL: Need to get company_id first (default to 1 for System company)
                company_id = 1
                cursor.execute("""
                    INSERT INTO users (username, password_hash, company_id, role, allowed_modes, is_active, must_change_password) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (username, password_hash.decode('utf-8'), company_id, role, json.dumps(allowed_modes), True, True))
            else:
                # SQLite
                cursor.execute("""
                    INSERT INTO users (username, password_hash, is_admin, role, company, default_company, allowed_modes, home_location_type, home_location_value, must_change_password) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (username, password_hash.decode('utf-8'), is_admin, role, company, default_company, json.dumps(allowed_modes), home_location_type, home_location_value, 1))
            
            conn.commit()
            security_config.log_security_event("user_created", username, 
                                              {"role": role, "allowed_modes": allowed_modes})
            return True, "User created successfully."
        except (sqlite3.IntegrityError, Exception) as e:
            return False, f"Error creating user: {str(e)}"

def get_user(username):
    """Get user by username - works with both PostgreSQL and SQLite"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if _use_postgresql():
            # PostgreSQL uses %s placeholders and has different schema
            cursor.execute("""
                SELECT u.*, c.company_name 
                FROM users u 
                LEFT JOIN companies c ON u.company_id = c.company_id 
                WHERE u.username = %s AND u.is_active = true
            """, (username,))
            row = cursor.fetchone()
            if row:
                # Convert to dict-like object and map fields for compatibility
                columns = [desc[0] for desc in cursor.description]
                user_dict = dict(zip(columns, row))
                
                # Map PostgreSQL fields to SQLite-compatible names
                user_dict['is_admin'] = (user_dict.get('role') == 'admin')
                user_dict['company'] = user_dict.get('company_name')
                user_dict['default_company'] = user_dict.get('company_name')
                
                return DictRow(user_dict)
            return None
        else:
            # SQLite uses ? placeholders
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return user

def verify_user(username, password):
    """
    Verifies a user's password with rate limiting protection.
    
    Args:
        username: Username to verify
        password: Password to check
        
    Returns:
        User record if valid, None if invalid or rate limited
        
    Side Effects:
        Records failed login attempts for rate limiting
    """
    # Check rate limiting BEFORE attempting verification
    if not security_config.check_login_attempts(username):
        # User is locked out, return None
        security_config.log_security_event("login_locked", username)
        return None
    
    user = get_user(username)
    if user:
        # Handle password hash - might be string or bytes
        stored_hash = user['password_hash']
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
        
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            # Successful login - reset attempt counter
            security_config.reset_login_attempts(username)
            security_config.log_security_event("login_success", username)
            return user
    
    # Failed login - record attempt
    if user:  # Only record if user exists (don't reveal non-existent users)
        security_config.record_failed_login(username)
        security_config.log_security_event("login_failed", username)
    
    return None

def get_all_users():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if _use_postgresql():
            cursor.execute("""
                SELECT user_id, username, is_admin, role, company_id, default_company_id, 
                       allowed_modes, home_location_type, home_location_value 
                FROM users WHERE is_active = true
            """)
        else:
            cursor.execute("""
                SELECT id, username, is_admin, role, company, default_company, 
                       allowed_modes, home_location_type, home_location_value 
                FROM users
            """)
        return cursor.fetchall()

def update_user(user_id, username, is_admin, company, default_company, role=None, allowed_modes=None, home_location_type=None, home_location_value=None):
    """
    Update user information including role and allowed modes.
    
    Args:
        user_id: User ID to update
        username: New username
        is_admin: Admin flag (for backwards compatibility)
        company: Company affiliation
        default_company: Default company
        role: User role ('admin', 'manager', or 'user')
        allowed_modes: List of allowed modes
        home_location_type: 'director', 'market', or 'theater'
        home_location_value: The actual director/market/theater name
    """
    # Determine role if not provided
    if role is None:
        role = ROLE_ADMIN if is_admin else ROLE_USER
    
    # Ensure role is valid
    if role not in VALID_ROLES:
        role = ROLE_USER
    
    # Determine allowed modes if not provided
    if allowed_modes is None:
        if role == ROLE_ADMIN:
            allowed_modes = ADMIN_DEFAULT_MODES
        elif role == ROLE_MANAGER:
            allowed_modes = MANAGER_DEFAULT_MODES
        else:
            allowed_modes = USER_DEFAULT_MODES
    
    # Sync is_admin with role
    is_admin = (role == ROLE_ADMIN)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if _use_postgresql():
            cursor.execute("""
                UPDATE users 
                SET username = %s, is_admin = %s, role = %s, company_id = %s, default_company_id = %s, 
                    allowed_modes = %s, home_location_type = %s, home_location_value = %s 
                WHERE user_id = %s
            """, (username, is_admin, role, company, default_company, json.dumps(allowed_modes), 
                  home_location_type, home_location_value, user_id))
        else:
            cursor.execute("""
                UPDATE users 
                SET username = ?, is_admin = ?, role = ?, company = ?, default_company = ?, 
                    allowed_modes = ?, home_location_type = ?, home_location_value = ? 
                WHERE id = ?
            """, (username, is_admin, role, company, default_company, json.dumps(allowed_modes), 
                  home_location_type, home_location_value, user_id))
        conn.commit()
        
        security_config.log_security_event("user_updated", username, 
                                          {"role": role, "allowed_modes": allowed_modes})

def delete_user(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if _use_postgresql():
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

def change_password(username, old_password, new_password):
    """
    Change a user's password with validation.
    
    Args:
        username: Username
        old_password: Current password for verification
        new_password: New password to set
        
    Returns:
        (success, message) tuple
    """
    # Verify old password
    user = verify_user(username, old_password)
    if not user:
        return False, "Current password is incorrect."
    
    # Validate new password strength
    is_valid, error_msg = security_config.validate_password_strength(new_password)
    if not is_valid:
        return False, f"New password validation failed: {error_msg}"
    
    # Hash and update password
    new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if _use_postgresql():
            cursor.execute("UPDATE users SET password_hash = %s, must_change_password = false WHERE username = %s", 
                         (new_hash.decode('utf-8'), username))
        else:
            cursor.execute("UPDATE users SET password_hash = ?, must_change_password = 0 WHERE username = ?", 
                         (new_hash.decode('utf-8'), username))
        conn.commit()
    
    security_config.log_security_event("password_changed", username)
    return True, "Password changed successfully."

def is_using_default_password(username):
    """
    Check if user is still using the default password.
    
    Args:
        username: Username to check
        
    Returns:
        True if using default password (admin/admin)
    """
    if username.lower() == "admin":
        user = get_user(username)
        if user:
            # Check if password is "admin"
            return bcrypt.checkpw(b"admin", user['password_hash'].encode('utf-8'))
    return False

def force_password_change_required(username):
    """
    Determine if user must change password before proceeding.
    
    Args:
        username: Username to check
        
    Returns:
        True if password change is required
    """
    # Check if admin is using default password
    if is_using_default_password(username):
        return True
    
    # Check if user has must_change_password flag set
    user = get_user(username)
    if user:
        try:
            if 'must_change_password' in user.keys():
                return bool(user['must_change_password'])
        except (KeyError, TypeError):
            pass
    
    return False

def get_user_role(username):
    """
    Get the role of a user.
    
    Args:
        username: Username to check
        
    Returns:
        User's role string ('admin', 'manager', or 'user'), or None if user doesn't exist
    """
    user = get_user(username)
    if user:
        return user['role'] if 'role' in user.keys() else ROLE_USER
    return None

def get_user_allowed_modes(username):
    """
    Get the list of modes a user is allowed to access.
    Returns modes based on the user's role permissions (from role_permissions.json).
    
    Args:
        username: Username to check
        
    Returns:
        List of allowed mode strings, or empty list if user doesn't exist
    """
    user = get_user(username)
    if user:
        role = user['role'] if 'role' in user.keys() else ROLE_USER
        # Get role-based permissions
        role_perms = load_role_permissions()
        return role_perms.get(role, USER_DEFAULT_MODES)
    return []

def user_can_access_mode(username, mode):
    """
    Check if a user has permission to access a specific mode.
    
    Args:
        username: Username to check
        mode: Mode name ('Corp', 'DD', 'AM', or 'User')
        
    Returns:
        True if user can access the mode, False otherwise
    """
    allowed_modes = get_user_allowed_modes(username)
    return mode in allowed_modes

def is_admin(username):
    """
    Check if user has admin privileges.
    
    Args:
        username: Username to check
        
    Returns:
        True if user is admin
    """
    role = get_user_role(username)
    return role == ROLE_ADMIN

def is_manager(username):
    """
    Check if user has manager privileges.
    
    Args:
        username: Username to check
        
    Returns:
        True if user is manager or admin
    """
    role = get_user_role(username)
    return role in [ROLE_ADMIN, ROLE_MANAGER]

def bulk_import_users(users_data):
    """
    Import multiple users from JSON data.

    Args:
        users_data: Dictionary with 'users' key containing list of user objects

    Returns:
        Tuple of (success_count, error_list)
    """
    if 'users' not in users_data:
        return 0, ["Invalid format: missing 'users' key"]

    success_count = 0
    errors = []

    for idx, user_data in enumerate(users_data['users'], 1):
        try:
            # Validate required fields
            if 'username' not in user_data or 'password' not in user_data:
                errors.append(f"User {idx}: Missing username or password")
                continue

            username = user_data['username']
            password = user_data['password']
            role = user_data.get('role', 'user')
            company = user_data.get('company')
            default_company = user_data.get('default_company')
            home_location_type = user_data.get('home_location_type')
            home_location_value = user_data.get('home_location_value')
            is_admin = (role == ROLE_ADMIN)

            # Normalize empty values
            if company == '':
                company = None
            if default_company == '':
                default_company = None
            if home_location_type in ['', 'none', 'None']:
                home_location_type = None
                home_location_value = None

            # Create user (modes will be determined by role permissions)
            success, message = create_user(
                username, password, is_admin, company, default_company,
                role=role, allowed_modes=None,  # Use role-based permissions
                home_location_type=home_location_type,
                home_location_value=home_location_value
            )

            if success:
                success_count += 1
            else:
                errors.append(f"{username}: {message}")

        except Exception as e:
            errors.append(f"User {idx}: {str(e)}")

    return success_count, errors

def parse_csv_to_users_dict(csv_content):
    """
    Parse CSV content into users dictionary format.

    Args:
        csv_content: String or bytes containing CSV data

    Returns:
        Dictionary with 'users' key containing list of user objects
    """
    # Convert bytes to string if needed
    if isinstance(csv_content, bytes):
        csv_content = csv_content.decode('utf-8')

    # Parse CSV
    csv_reader = csv.DictReader(io.StringIO(csv_content))
    users_list = []

    for row in csv_reader:
        # Skip empty rows
        if not row.get('username') or not row.get('password'):
            continue

        user_data = {
            'username': row.get('username', '').strip(),
            'password': row.get('password', '').strip(),
            'role': row.get('role', 'user').strip().lower(),
            'company': row.get('company', '').strip() or None,
            'default_company': row.get('default_company', '').strip() or None,
            'home_location_type': row.get('home_location_type', '').strip().lower() or None,
            'home_location_value': row.get('home_location_value', '').strip() or None,
        }

        users_list.append(user_data)

    return {'users': users_list}

def generate_reset_code(username):
    """
    Generate a time-limited password reset code for a user.
    
    Args:
        username: Username requesting reset
        
    Returns:
        Tuple of (success: bool, code_or_message: str)
    """
    user = get_user(username)
    if not user:
        # Don't reveal that user doesn't exist
        return False, "If this username exists, a reset code has been generated."
    
    # Generate 6-digit numeric code
    reset_code = ''.join([str(secrets.randbelow(10)) for _ in range(RESET_CODE_LENGTH)])
    
    # Hash the code before storing (same as passwords)
    code_hash = bcrypt.hashpw(reset_code.encode('utf-8'), bcrypt.gensalt())
    
    # Set expiry time
    expiry_timestamp = int((datetime.now() + timedelta(minutes=RESET_CODE_EXPIRY_MINUTES)).timestamp())
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if _use_postgresql():
            cursor.execute("""
                UPDATE users 
                SET reset_code = %s, reset_code_expiry = %s, reset_attempts = 0
                WHERE username = %s
            """, (code_hash.decode('utf-8'), expiry_timestamp, username))
        else:
            cursor.execute("""
                UPDATE users 
                SET reset_code = ?, reset_code_expiry = ?, reset_attempts = 0
                WHERE username = ?
            """, (code_hash.decode('utf-8'), expiry_timestamp, username))
        conn.commit()
    
    security_config.log_security_event("password_reset_requested", username, 
                                      {"expiry_minutes": RESET_CODE_EXPIRY_MINUTES})
    
    return True, reset_code

def verify_reset_code(username, code):
    """
    Verify a password reset code.
    
    Args:
        username: Username attempting reset
        code: Reset code provided by user
        
    Returns:
        Tuple of (valid: bool, message: str)
    """
    user = get_user(username)
    if not user:
        return False, "Invalid username or code."
    
    # Check if code exists
    if not user['reset_code'] or not user['reset_code_expiry']:
        return False, "No active reset code for this account."
    
    # Check attempts
    attempts = user['reset_attempts'] if 'reset_attempts' in user.keys() else 0
    if attempts >= RESET_CODE_MAX_ATTEMPTS:
        # Clear the reset code
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if _use_postgresql():
                cursor.execute("""
                    UPDATE users 
                    SET reset_code = NULL, reset_code_expiry = NULL, reset_attempts = 0
                    WHERE username = %s
                """, (username,))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET reset_code = NULL, reset_code_expiry = NULL, reset_attempts = 0
                    WHERE username = ?
                """, (username,))
            conn.commit()
        security_config.log_security_event("password_reset_max_attempts", username)
        return False, "Too many attempts. Please request a new code."
    
    # Check expiry
    if int(time.time()) > user['reset_code_expiry']:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if _use_postgresql():
                cursor.execute("""
                    UPDATE users 
                    SET reset_code = NULL, reset_code_expiry = NULL, reset_attempts = 0
                    WHERE username = %s
                """, (username,))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET reset_code = NULL, reset_code_expiry = NULL, reset_attempts = 0
                    WHERE username = ?
                """, (username,))
            conn.commit()
        security_config.log_security_event("password_reset_expired", username)
        return False, "Reset code has expired. Please request a new one."
    
    # Verify code
    if bcrypt.checkpw(code.encode('utf-8'), user['reset_code'].encode('utf-8')):
        # Code is valid - clear it
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if _use_postgresql():
                cursor.execute("""
                    UPDATE users 
                    SET reset_code = NULL, reset_code_expiry = NULL, reset_attempts = 0
                    WHERE username = %s
                """, (username,))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET reset_code = NULL, reset_code_expiry = NULL, reset_attempts = 0
                    WHERE username = ?
                """, (username,))
            conn.commit()
        security_config.log_security_event("password_reset_code_verified", username)
        return True, "Code verified. You may now reset your password."
    else:
        # Increment attempts
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if _use_postgresql():
                cursor.execute("""
                    UPDATE users 
                    SET reset_attempts = reset_attempts + 1
                    WHERE username = %s
                """, (username,))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET reset_attempts = reset_attempts + 1
                    WHERE username = ?
                """, (username,))
            conn.commit()
        security_config.log_security_event("password_reset_invalid_code", username)
        return False, f"Invalid code. {RESET_CODE_MAX_ATTEMPTS - attempts - 1} attempts remaining."

def reset_password_with_code(username, code, new_password):
    """
    Reset a user's password using a verified reset code.
    
    Args:
        username: Username
        code: Reset code
        new_password: New password to set
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Verify code first
    valid, message = verify_reset_code(username, code)
    if not valid:
        return False, message
    
    # Validate new password
    is_valid, validation_msg = security_config.validate_password_strength(new_password)
    if not is_valid:
        return False, validation_msg
    
    # Update password
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if _use_postgresql():
            cursor.execute("""
                UPDATE users 
                SET password_hash = %s, must_change_password = false
                WHERE username = %s
            """, (password_hash.decode('utf-8'), username))
        else:
            cursor.execute("""
                UPDATE users 
                SET password_hash = ?, must_change_password = 0
                WHERE username = ?
            """, (password_hash.decode('utf-8'), username))
        conn.commit()
    
    security_config.log_security_event("password_reset_completed", username)
    return True, "Password successfully reset. You may now log in with your new password."
