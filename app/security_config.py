"""
Security Configuration and Utilities for Price Scout

This module provides centralized security configuration, rate limiting,
session management, and input validation for the Price Scout application.

Created: October 26, 2025
Version: 2.8.0
"""

import streamlit as st
from datetime import datetime, timedelta
import re
import json
import logging

# ============================================================================
# SECURITY CONSTANTS
# ============================================================================

# Authentication & Session Security
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
SESSION_TIMEOUT_MINUTES = 30
MIN_PASSWORD_LENGTH = 8
REQUIRE_PASSWORD_COMPLEXITY = True

# File Upload Security
MAX_FILE_SIZE_MB = 50
MAX_JSON_DEPTH = 10
ALLOWED_UPLOAD_EXTENSIONS = {".json", ".db"}

# Logging Security
LOG_LEVEL_PRODUCTION = "INFO"
LOG_LEVEL_DEVELOPMENT = "DEBUG"
SENSITIVE_KEYS = {"password", "api_key", "token", "secret", "auth"}

# ============================================================================
# RATE LIMITING
# ============================================================================

def check_login_attempts(username: str) -> bool:
    """
    Rate limit login attempts to prevent brute force attacks.
    
    Args:
        username: Username attempting to log in
        
    Returns:
        True if login attempt allowed, False if account is locked
        
    Side Effects:
        Updates st.session_state with attempt tracking
    """
    key = f"login_attempts_{username}"
    
    # Initialize tracking if not exists
    if key not in st.session_state:
        st.session_state[key] = {
            "count": 0,
            "locked_until": None,
            "last_attempt": None
        }
    
    attempts = st.session_state[key]
    
    # Check if account is currently locked
    if attempts["locked_until"]:
        if datetime.now() < attempts["locked_until"]:
            remaining_seconds = (attempts["locked_until"] - datetime.now()).seconds
            remaining_minutes = remaining_seconds // 60
            st.error(
                f"🔒 **Account Locked**\n\n"
                f"Too many failed login attempts. Please try again in "
                f"**{remaining_minutes} minutes and {remaining_seconds % 60} seconds**.\n\n"
                f"This is a security measure to protect your account."
            )
            return False
        else:
            # Lockout period expired, reset counter
            attempts["count"] = 0
            attempts["locked_until"] = None
    
    # Check if we've exceeded max attempts
    if attempts["count"] >= MAX_LOGIN_ATTEMPTS:
        attempts["locked_until"] = datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        st.error(
            f"⚠️ **Security Alert: Account Locked**\n\n"
            f"Too many failed login attempts ({MAX_LOGIN_ATTEMPTS}).\n\n"
            f"Your account has been locked for **{LOCKOUT_DURATION_MINUTES} minutes** "
            f"as a security precaution.\n\n"
            f"_If you believe this is an error, please contact your administrator._"
        )
        return False
    
    return True


def record_failed_login(username: str):
    """
    Record a failed login attempt.
    
    Args:
        username: Username that failed to log in
        
    Side Effects:
        Increments failed login counter in st.session_state
        Logs security event
    """
    key = f"login_attempts_{username}"
    
    if key in st.session_state:
        st.session_state[key]["count"] += 1
        st.session_state[key]["last_attempt"] = datetime.now()
        
        attempts_remaining = MAX_LOGIN_ATTEMPTS - st.session_state[key]["count"]
        
        if attempts_remaining > 0:
            st.warning(
                f"⚠️ Invalid credentials. "
                f"You have **{attempts_remaining}** attempt(s) remaining before lockout."
            )
        
        # Log security event (don't log password)
        logging.warning(
            f"Failed login attempt for user '{username}' "
            f"(Attempt {st.session_state[key]['count']}/{MAX_LOGIN_ATTEMPTS})"
        )


def reset_login_attempts(username: str):
    """
    Reset login attempt counter after successful login.
    
    Args:
        username: Username that successfully logged in
    """
    key = f"login_attempts_{username}"
    if key in st.session_state:
        del st.session_state[key]


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def check_session_timeout() -> bool:
    """
    Check if session has timed out due to inactivity.
    
    Returns:
        True if session is valid, False if timed out
        
    Side Effects:
        Clears session state if timeout occurred
        Updates last_activity timestamp
    """
    # Initialize last activity if not set
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = datetime.now()
        return True
    
    # Calculate idle time
    idle_time = datetime.now() - st.session_state.last_activity
    
    # Check if session expired
    if idle_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        # Clear session
        st.session_state.clear()
        st.warning(
            f"⏱️ **Session Expired**\n\n"
            f"Your session has timed out after {SESSION_TIMEOUT_MINUTES} minutes of inactivity.\n\n"
            f"Please log in again to continue."
        )
        return False
    
    # Warn if session is about to expire (5 minutes before timeout)
    warning_threshold = timedelta(minutes=SESSION_TIMEOUT_MINUTES - 5)
    if idle_time > warning_threshold:
        remaining_minutes = SESSION_TIMEOUT_MINUTES - (idle_time.seconds // 60)
        if remaining_minutes > 0:
            st.info(
                f"ℹ️ Your session will expire in **{remaining_minutes} minute(s)** "
                f"due to inactivity."
            )
    
    # Update last activity
    st.session_state.last_activity = datetime.now()
    return True


# ============================================================================
# PASSWORD VALIDATION
# ============================================================================

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets complexity requirements.
    
    Args:
        password: Password to validate
        
    Returns:
        (is_valid, error_message) tuple
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
    
    if REQUIRE_PASSWORD_COMPLEXITY:
        # Check for uppercase
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        # Check for lowercase
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        # Check for digit
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character (!@#$%^&*...)"
    
    return True, ""


def is_default_password(username: str, password: str) -> bool:
    """
    Check if user is using the default password.
    
    Args:
        username: Username to check
        password: Password to check
        
    Returns:
        True if default password is detected
    """
    # Default admin credentials (should be changed on first login)
    if username.lower() == "admin" and password == "admin":
        return True
    
    return False


# ============================================================================
# FILE UPLOAD VALIDATION
# ============================================================================

def validate_uploaded_file(
    uploaded_file,
    expected_type: str,
    max_size_mb: int = MAX_FILE_SIZE_MB
) -> tuple[bool, str]:
    """
    Validate uploaded file for security.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        expected_type: Expected file type ("json" or "db")
        max_size_mb: Maximum file size in megabytes
        
    Returns:
        (is_valid, error_message) tuple
    """
    try:
        # Check file size
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            return False, (
                f"File too large: {file_size_mb:.2f}MB "
                f"(maximum: {max_size_mb}MB)"
            )
        
        # Validate JSON files
        if expected_type == "json":
            try:
                data = json.loads(uploaded_file.getvalue())
                
                # Check JSON depth to prevent DoS
                depth = get_json_depth(data)
                if depth > MAX_JSON_DEPTH:
                    return False, (
                        f"JSON structure too deeply nested "
                        f"(depth: {depth}, maximum: {MAX_JSON_DEPTH})"
                    )
                
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON file: {str(e)}"
        
        # Validate SQLite database files
        elif expected_type == "db":
            # Check magic bytes (SQLite files start with "SQLite format 3")
            magic = uploaded_file.getvalue()[:16]
            if not magic.startswith(b"SQLite format 3"):
                return False, "Invalid database file format (not a valid SQLite database)"
        
        return True, ""
        
    except Exception as e:
        return False, f"File validation error: {str(e)}"


def get_json_depth(data, depth=0):
    """
    Recursively calculate JSON nesting depth.
    
    Args:
        data: JSON data structure
        depth: Current depth (internal use)
        
    Returns:
        Maximum depth of nested structures
    """
    if isinstance(data, dict):
        if not data:
            return depth
        return max([get_json_depth(v, depth + 1) for v in data.values()])
    elif isinstance(data, list):
        if not data:
            return depth
        return max([get_json_depth(v, depth + 1) for v in data])
    return depth


# ============================================================================
# LOGGING SANITIZATION
# ============================================================================

def sanitize_log_data(data):
    """
    Remove sensitive information before logging.
    
    Args:
        data: Data to sanitize (dict, string, or other)
        
    Returns:
        Sanitized data with sensitive values redacted
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Redact sensitive keys
            if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
                sanitized[key] = "***REDACTED***"
            else:
                # Recursively sanitize nested dicts
                sanitized[key] = sanitize_log_data(value)
        return sanitized
    
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    
    elif isinstance(data, str):
        # Redact potential API keys or tokens in strings
        # Pattern: alphanumeric strings longer than 20 chars
        if len(data) > 20 and data.isalnum():
            return f"{data[:4]}...{data[-4:]}"
        return data
    
    return data


# ============================================================================
# INPUT SANITIZATION
# ============================================================================

def sanitize_sql_like_pattern(user_input: str) -> str:
    """
    Escape special characters in SQL LIKE patterns.
    
    Args:
        user_input: User-provided search string
        
    Returns:
        Escaped string safe for SQL LIKE queries
    """
    # Escape special LIKE characters
    escaped = user_input.replace('%', r'\%').replace('_', r'\_')
    return escaped


def sanitize_filename(filename: str) -> str:
    """
    Remove potentially dangerous characters from filenames.
    
    Args:
        filename: User-provided filename
        
    Returns:
        Sanitized filename
    """
    # Remove path traversal characters
    sanitized = filename.replace('..', '').replace('/', '').replace('\\', '')
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>:"|?*]', '', sanitized)
    
    return sanitized


# ============================================================================
# SECURITY MONITORING
# ============================================================================

def log_security_event(event_type: str, username: str, details: dict = None):
    """
    Log security-relevant events.
    
    Args:
        event_type: Type of security event (login, upload, admin_action, etc.)
        username: User associated with the event
        details: Additional event details (will be sanitized)
    """
    sanitized_details = sanitize_log_data(details) if details else {}
    
    logging.info(
        f"SECURITY EVENT | Type: {event_type} | User: {username} | "
        f"Details: {sanitized_details}"
    )


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_security_config() -> dict:
    """
    Get current security configuration.
    
    Returns:
        Dictionary of security settings
    """
    return {
        "max_login_attempts": MAX_LOGIN_ATTEMPTS,
        "lockout_duration_minutes": LOCKOUT_DURATION_MINUTES,
        "session_timeout_minutes": SESSION_TIMEOUT_MINUTES,
        "min_password_length": MIN_PASSWORD_LENGTH,
        "require_password_complexity": REQUIRE_PASSWORD_COMPLEXITY,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "max_json_depth": MAX_JSON_DEPTH,
    }


if __name__ == "__main__":
    # Test password validation
    print("Testing password validation...")
    
    test_passwords = [
        "admin",  # Too short, no complexity
        "Password123",  # Missing special char
        "Password123!",  # Valid
        "short",  # Too short
    ]
    
    for pwd in test_passwords:
        is_valid, msg = validate_password_strength(pwd)
        print(f"'{pwd}': {'✅ Valid' if is_valid else f'❌ {msg}'}")
    
    # Test JSON depth
    print("\nTesting JSON depth...")
    shallow = {"a": 1, "b": 2}
    deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": 1}}}}}}}}}}}
    
    print(f"Shallow depth: {get_json_depth(shallow)}")
    print(f"Deep depth: {get_json_depth(deep)}")
    
    # Test log sanitization
    print("\nTesting log sanitization...")
    sensitive_data = {
        "username": "admin",
        "password": "secret123",
        "api_key": "sk-1234567890abcdef",
        "email": "user@example.com"
    }
    print(f"Original: {sensitive_data}")
    print(f"Sanitized: {sanitize_log_data(sensitive_data)}")
