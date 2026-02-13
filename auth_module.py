"""
============================================================================
AUTHENTICATION & SECURITY MODULE
Smart Portfolio Monitor - Multi-User System
============================================================================
"""

import hashlib
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
import mysql.connector
from mysql.connector import Error
from passlib.hash import bcrypt
import streamlit as st

# ============================================================================
# CONFIGURATION
# ============================================================================

# Password Requirements
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_DIGIT = True
PASSWORD_REQUIRE_SPECIAL = True

# Security Settings
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCK_DURATION_MINUTES = 30
SESSION_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_HOURS = 1

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_connection():
    """
    Create MySQL database connection
    Returns: connection object or None
    """
    try:
        connection = mysql.connector.connect(
            host=st.secrets.get("MYSQL_HOST", "localhost"),
            port=st.secrets.get("MYSQL_PORT", 3306),
            user=st.secrets.get("MYSQL_USER", "root"),
            password=st.secrets.get("MYSQL_PASSWORD", ""),
            database=st.secrets.get("MYSQL_DATABASE", "portfolio_db"),
            autocommit=False
        )
        return connection
    except Error as e:
        st.error(f"❌ Database connection failed: {e}")
        return None

# ============================================================================
# PASSWORD UTILITIES
# ============================================================================

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt
    Args:
        password: Plain text password
    Returns:
        Hashed password string
    """
    return bcrypt.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash
    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hash
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password meets security requirements
    Returns: (is_valid, error_message)
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
    
    if PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if PASSWORD_REQUIRE_DIGIT and not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""


def validate_email(email: str) -> bool:
    """
    Basic email validation
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username: str) -> Tuple[bool, str]:
    """
    Validate username format
    Returns: (is_valid, error_message)
    """
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 50:
        return False, "Username must be less than 50 characters"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"
    
    return True, ""


# ============================================================================
# USER REGISTRATION
# ============================================================================

def register_user(username: str, email: str, password: str, 
                 connection=None) -> Tuple[bool, str, Optional[int]]:
    """
    Register a new user
    Returns: (success, message, user_id)
    """
    close_connection = False
    if connection is None:
        connection = get_db_connection()
        close_connection = True
    
    if not connection:
        return False, "Database connection failed", None
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Validate username
        valid, msg = validate_username(username)
        if not valid:
            return False, msg, None
        
        # Validate email
        if not validate_email(email):
            return False, "Invalid email format", None
        
        # Validate password strength
        valid, msg = validate_password_strength(password)
        if not valid:
            return False, msg, None
        
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return False, "Username already exists", None
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return False, "Email already registered", None
        
        # Hash password
        password_hash = hash_password(password)
        
        # Insert new user
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (%s, %s, %s)
            """,
            (username, email, password_hash)
        )
        
        user_id = cursor.lastrowid
        connection.commit()
        
        # Log registration
        log_audit_action(user_id, "USER_REGISTERED", connection=connection)
        
        return True, "Registration successful", user_id
    
    except Error as e:
        connection.rollback()
        return False, f"Registration failed: {str(e)}", None
    
    finally:
        cursor.close()
        if close_connection:
            connection.close()


# ============================================================================
# USER LOGIN
# ============================================================================

def check_account_locked(username: str, connection) -> Tuple[bool, Optional[datetime]]:
    """
    Check if account is locked due to failed login attempts
    Returns: (is_locked, locked_until)
    """
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute(
            """
            SELECT locked_until, failed_login_attempts 
            FROM users 
            WHERE username = %s
            """,
            (username,)
        )
        
        result = cursor.fetchone()
        
        if not result:
            return False, None
        
        locked_until = result['locked_until']
        
        if locked_until and locked_until > datetime.now():
            return True, locked_until
        
        # If lock expired, reset
        if locked_until:
            cursor.execute(
                """
                UPDATE users 
                SET failed_login_attempts = 0, locked_until = NULL 
                WHERE username = %s
                """,
                (username,)
            )
            connection.commit()
        
        return False, None
    
    finally:
        cursor.close()


def increment_failed_login(username: str, connection):
    """
    Increment failed login attempts and lock account if needed
    """
    cursor = connection.cursor()
    
    try:
        cursor.execute(
            """
            UPDATE users 
            SET failed_login_attempts = failed_login_attempts + 1 
            WHERE username = %s
            """,
            (username,)
        )
        
        # Check if should lock account
        cursor.execute(
            "SELECT failed_login_attempts FROM users WHERE username = %s",
            (username,)
        )
        
        result = cursor.fetchone()
        
        if result and result[0] >= MAX_LOGIN_ATTEMPTS:
            lock_until = datetime.now() + timedelta(minutes=ACCOUNT_LOCK_DURATION_MINUTES)
            cursor.execute(
                """
                UPDATE users 
                SET locked_until = %s 
                WHERE username = %s
                """,
                (lock_until, username)
            )
        
        connection.commit()
    
    finally:
        cursor.close()


def reset_failed_login(username: str, connection):
    """
    Reset failed login attempts on successful login
    """
    cursor = connection.cursor()
    
    try:
        cursor.execute(
            """
            UPDATE users 
            SET failed_login_attempts = 0, 
                locked_until = NULL,
                last_login = %s
            WHERE username = %s
            """,
            (datetime.now(), username)
        )
        connection.commit()
    
    finally:
        cursor.close()


def login_user(username: str, password: str, 
              connection=None) -> Tuple[bool, str, Optional[Dict]]:
    """
    Authenticate user
    Returns: (success, message, user_data_dict)
    """
    close_connection = False
    if connection is None:
        connection = get_db_connection()
        close_connection = True
    
    if not connection:
        return False, "Database connection failed", None
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Check if account is locked
        is_locked, locked_until = check_account_locked(username, connection)
        
        if is_locked:
            remaining = (locked_until - datetime.now()).seconds // 60
            return False, f"Account locked. Try again in {remaining} minutes", None
        
        # Fetch user
        cursor.execute(
            """
            SELECT id, username, email, password_hash, is_active 
            FROM users 
            WHERE username = %s
            """,
            (username,)
        )
        
        user = cursor.fetchone()
        
        if not user:
            return False, "Invalid username or password", None
        
        # Check if account is active
        if not user['is_active']:
            return False, "Account is disabled. Contact support", None
        
        # Verify password
        if not verify_password(password, user['password_hash']):
            increment_failed_login(username, connection)
            return False, "Invalid username or password", None
        
        # Success - reset failed attempts
        reset_failed_login(username, connection)
        
        # Create session token
        token = create_session_token(user['id'], connection)
        
        # Log login
        log_audit_action(user['id'], "USER_LOGIN", connection=connection)
        
        user_data = {
            'user_id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'session_token': token
        }
        
        return True, "Login successful", user_data
    
    except Error as e:
        return False, f"Login failed: {str(e)}", None
    
    finally:
        cursor.close()
        if close_connection:
            connection.close()


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def create_session_token(user_id: int, connection) -> str:
    """
    Create a secure session token
    """
    cursor = connection.cursor()
    
    try:
        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)
        
        # Clean up old tokens for this user
        cursor.execute(
            "DELETE FROM session_tokens WHERE user_id = %s",
            (user_id,)
        )
        
        # Insert new token
        cursor.execute(
            """
            INSERT INTO session_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, token, expires_at)
        )
        
        connection.commit()
        return token
    
    finally:
        cursor.close()


def validate_session_token(token: str, connection=None) -> Optional[int]:
    """
    Validate session token and return user_id
    Returns: user_id or None if invalid
    """
    close_connection = False
    if connection is None:
        connection = get_db_connection()
        close_connection = True
    
    if not connection:
        return None
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute(
            """
            SELECT user_id, expires_at 
            FROM session_tokens 
            WHERE token = %s
            """,
            (token,)
        )
        
        result = cursor.fetchone()
        
        if not result:
            return None
        
        if result['expires_at'] < datetime.now():
            # Token expired
            cursor.execute("DELETE FROM session_tokens WHERE token = %s", (token,))
            connection.commit()
            return None
        
        # Update last_used
        cursor.execute(
            """
            UPDATE session_tokens 
            SET last_used = %s 
            WHERE token = %s
            """,
            (datetime.now(), token)
        )
        connection.commit()
        
        return result['user_id']
    
    finally:
        cursor.close()
        if close_connection:
            connection.close()


def logout_user(token: str, connection=None):
    """
    Invalidate session token
    """
    close_connection = False
    if connection is None:
        connection = get_db_connection()
        close_connection = True
    
    if not connection:
        return
    
    cursor = connection.cursor()
    
    try:
        cursor.execute("DELETE FROM session_tokens WHERE token = %s", (token,))
        connection.commit()
    
    finally:
        cursor.close()
        if close_connection:
            connection.close()


# ============================================================================
# AUDIT LOGGING
# ============================================================================

def log_audit_action(user_id: int, action_type: str, ticker: str = None,
                     details: str = None, connection=None):
    """
    Log user action to audit trail
    """
    close_connection = False
    if connection is None:
        connection = get_db_connection()
        close_connection = True
    
    if not connection:
        return
    
    cursor = connection.cursor()
    
    try:
        cursor.execute(
            """
            INSERT INTO audit_log (user_id, action_type, ticker, details)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, action_type, ticker, details)
        )
        connection.commit()
    
    except Error as e:
        print(f"Audit log error: {e}")
    
    finally:
        cursor.close()
        if close_connection:
            connection.close()


# ============================================================================
# PASSWORD RESET
# ============================================================================

def create_password_reset_token(email: str, connection=None) -> Tuple[bool, str, Optional[str]]:
    """
    Create password reset token
    Returns: (success, message, token)
    """
    close_connection = False
    if connection is None:
        connection = get_db_connection()
        close_connection = True
    
    if not connection:
        return False, "Database connection failed", None
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            # Don't reveal if email exists
            return True, "If email exists, reset link sent", None
        
        user_id = user['id']
        
        # Generate token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=PASSWORD_RESET_EXPIRY_HOURS)
        
        # Insert token
        cursor.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, token, expires_at)
        )
        
        connection.commit()
        
        return True, "Reset token created", token
    
    except Error as e:
        return False, f"Failed to create reset token: {str(e)}", None
    
    finally:
        cursor.close()
        if close_connection:
            connection.close()


def reset_password_with_token(token: str, new_password: str, 
                              connection=None) -> Tuple[bool, str]:
    """
    Reset password using reset token
    """
    close_connection = False
    if connection is None:
        connection = get_db_connection()
        close_connection = True
    
    if not connection:
        return False, "Database connection failed"
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Validate password
        valid, msg = validate_password_strength(new_password)
        if not valid:
            return False, msg
        
        # Check token
        cursor.execute(
            """
            SELECT user_id, expires_at, used 
            FROM password_reset_tokens 
            WHERE token = %s
            """,
            (token,)
        )
        
        result = cursor.fetchone()
        
        if not result:
            return False, "Invalid reset token"
        
        if result['used']:
            return False, "Reset token already used"
        
        if result['expires_at'] < datetime.now():
            return False, "Reset token expired"
        
        user_id = result['user_id']
        
        # Update password
        password_hash = hash_password(new_password)
        cursor.execute(
            """
            UPDATE users 
            SET password_hash = %s,
                failed_login_attempts = 0,
                locked_until = NULL
            WHERE id = %s
            """,
            (password_hash, user_id)
        )
        
        # Mark token as used
        cursor.execute(
            """
            UPDATE password_reset_tokens 
            SET used = TRUE 
            WHERE token = %s
            """,
            (token,)
        )
        
        connection.commit()
        
        # Log action
        log_audit_action(user_id, "PASSWORD_RESET", connection=connection)
        
        return True, "Password reset successful"
    
    except Error as e:
        connection.rollback()
        return False, f"Password reset failed: {str(e)}"
    
    finally:
        cursor.close()
        if close_connection:
            connection.close()
