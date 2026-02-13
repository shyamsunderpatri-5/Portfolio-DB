"""
============================================================================
STREAMLIT AUTHENTICATION UI COMPONENTS
Multi-User Interface for Smart Portfolio Monitor
============================================================================
"""

import streamlit as st
from datetime import datetime
import time
import logging

# Import the authentication module (choose one based on your backend)
# For MySQL:
from auth_module import (
    register_user, login_user, logout_user,
    validate_session_token, log_audit_action
)

logger = logging.getLogger(__name__)


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def init_auth_session_state():
    """Initialize authentication session state variables"""
    
    if 'is_logged_in' not in st.session_state:
        st.session_state.is_logged_in = False
    
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    
    if 'username' not in st.session_state:
        st.session_state.username = None
    
    if 'email' not in st.session_state:
        st.session_state.email = None
    
    if 'session_token' not in st.session_state:
        st.session_state.session_token = None
    
    if 'login_time' not in st.session_state:
        st.session_state.login_time = None
    
    if 'is_refreshing' not in st.session_state:
        st.session_state.is_refreshing = False
    
    if 'last_session_check' not in st.session_state:
        st.session_state.last_session_check = None


# ============================================================================
# AUTO-LOGIN WITH SESSION TOKEN
# ============================================================================

def check_existing_session():
    """
    Check if user has valid session token
    Auto-login if valid
    Designed to handle Streamlit reruns safely
    """
    try:
        # FIRST CHECK: If we're already logged in with all necessary data, trust it
        # (Unless it's been a long time)
        if st.session_state.get('is_logged_in') and st.session_state.get('user_id'):
            # Check if we need to re-validate with database
            last_check = st.session_state.get('last_session_check')
            if last_check:
                from datetime import timedelta as td
                time_since_check = datetime.now() - last_check
                # Re-validate every 10 minutes
                if time_since_check < td(minutes=10):
                    logger.info(f"✅ Using cached session for user {st.session_state.get('username')} (checked {time_since_check.seconds}s ago)")
                    return True
        
        # SECOND CHECK: Try to restore session with token
        session_token = st.session_state.get('session_token')
        if not session_token or not isinstance(session_token, str):
            return False
        
        logger.info(f"🔐 Validating session token from database...")
        
        # Validate token with database
        user_data = validate_session_token(session_token)
        st.session_state.last_session_check = datetime.now()
        
        if user_data and isinstance(user_data, dict):
            # Valid session - restore all session state
            st.session_state.is_logged_in = True
            st.session_state.user_id = user_data.get('user_id')
            st.session_state.username = user_data.get('username')
            st.session_state.email = user_data.get('email')
            st.session_state.session_token = session_token
            
            if 'login_time' not in st.session_state or not st.session_state.login_time:
                st.session_state.login_time = datetime.now()
            
            logger.info(f"✅ Session restored for user: {user_data.get('username')}")
            return True
        else:
            logger.warning("⚠️ Session token validation failed")
            clear_session()
            return False
    
    except Exception as e:
        logger.error(f"❌ Error in session check: {str(e)}", exc_info=True)
        # If there's an error and user claims to be logged in, trust them (might be temp DB issue)
        if st.session_state.get('is_logged_in'):
            logger.warning(f"⚠️ DB error but keeping user logged in (will retry on next check)")
            return True
        clear_session()
        return False


def clear_session():
    """Clear all session data"""
    st.session_state.is_logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.email = None
    st.session_state.session_token = None
    st.session_state.login_time = None


# ============================================================================
# LOGIN PAGE
# ============================================================================

def render_login_page():
    """
    Render the login interface
    """
    st.markdown("""
    <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; border-radius: 10px; margin-bottom: 30px;'>
        <h1 style='margin: 0;'>🧠 Smart Portfolio Monitor</h1>
        <p style='margin: 10px 0 0 0; font-size: 1.1em;'>Multi-User Trading Platform</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    # =========================================================================
    # LOGIN TAB
    # =========================================================================
    with tab1:
        st.markdown("### Login to Your Account")
        
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="login_username"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password"
            )
            
            remember_me = st.checkbox("Remember me", value=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                submit_button = st.form_submit_button(
                    "🔐 Login",
                    use_container_width=True,
                    type="primary"
                )
            
            with col2:
                forgot_password = st.form_submit_button(
                    "🔑 Forgot Password?",
                    use_container_width=True
                )
        
        if submit_button:
            if not username or not password:
                st.error("❌ Please enter both username and password")
            else:
                with st.spinner("Authenticating..."):
                    success, message, user_data = login_user(username, password)
                    
                    if success:
                        # Set session state
                        st.session_state.is_logged_in = True
                        st.session_state.user_id = user_data['user_id']
                        st.session_state.username = user_data['username']
                        st.session_state.email = user_data['email']
                        st.session_state.session_token = user_data['session_token']
                        st.session_state.login_time = datetime.now()
                        st.session_state.last_session_check = datetime.now()
                        
                        st.success(f"✅ {message}")
                        st.balloons()
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        if forgot_password:
            st.info("🔑 Password reset feature - Contact admin or check your email")
    
    # =========================================================================
    # REGISTER TAB
    # =========================================================================
    with tab2:
        st.markdown("### Create New Account")
        
        with st.form("register_form", clear_on_submit=True):
            new_username = st.text_input(
                "Username",
                placeholder="Choose a username (3-50 characters)",
                key="register_username",
                help="Only letters, numbers, and underscores allowed"
            )
            
            new_email = st.text_input(
                "Email",
                placeholder="your.email@example.com",
                key="register_email"
            )
            
            new_password = st.text_input(
                "Password",
                type="password",
                placeholder="Create a strong password",
                key="register_password"
            )
            
            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Re-enter your password",
                key="confirm_password"
            )
            
            # Password strength indicator
            if new_password:
                strength_score = 0
                requirements = []
                
                if len(new_password) >= 8:
                    strength_score += 1
                    requirements.append("✅ At least 8 characters")
                else:
                    requirements.append("❌ At least 8 characters")
                
                if any(c.isupper() for c in new_password):
                    strength_score += 1
                    requirements.append("✅ One uppercase letter")
                else:
                    requirements.append("❌ One uppercase letter")
                
                if any(c.islower() for c in new_password):
                    strength_score += 1
                    requirements.append("✅ One lowercase letter")
                else:
                    requirements.append("❌ One lowercase letter")
                
                if any(c.isdigit() for c in new_password):
                    strength_score += 1
                    requirements.append("✅ One digit")
                else:
                    requirements.append("❌ One digit")
                
                if any(c in '!@#$%^&*(),.?":{}|<>' for c in new_password):
                    strength_score += 1
                    requirements.append("✅ One special character")
                else:
                    requirements.append("❌ One special character")
                
                # Display strength
                if strength_score < 3:
                    st.warning("🔴 Weak password")
                elif strength_score < 5:
                    st.info("🟡 Medium password")
                else:
                    st.success("🟢 Strong password")
                
                with st.expander("Password Requirements"):
                    for req in requirements:
                        st.caption(req)
            
            terms_accepted = st.checkbox(
                "I agree to the Terms of Service and Privacy Policy",
                key="terms_checkbox"
            )
            
            register_button = st.form_submit_button(
                "📝 Create Account",
                use_container_width=True,
                type="primary"
            )
        
        if register_button:
            # Validation
            if not new_username or not new_email or not new_password:
                st.error("❌ Please fill in all fields")
            
            elif new_password != confirm_password:
                st.error("❌ Passwords do not match")
            
            elif not terms_accepted:
                st.error("❌ Please accept the Terms of Service")
            
            else:
                with st.spinner("Creating your account..."):
                    success, message, user_id = register_user(
                        new_username,
                        new_email,
                        new_password
                    )
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.success("🎉 You can now login with your credentials!")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")


# ============================================================================
# LOGOUT BUTTON (Sidebar)
# ============================================================================

def render_logout_button():
    """
    Render logout button and user info in sidebar
    Only shows if user is logged in
    """
    if not st.session_state.get('is_logged_in', False):
        return
    
    st.sidebar.divider()
    
    # User info display with safety checks
    username = st.session_state.get('username', 'User')
    email = st.session_state.get('email', 'N/A')
    user_id = st.session_state.get('user_id', 'N/A')
    
    st.sidebar.markdown(f"""
    <div style='background: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center;'>
        <h4 style='margin: 0; color: #667eea;'>👤 {username}</h4>
        <p style='margin: 5px 0; font-size: 0.9em; color: #666;'>{email}</p>
        <p style='margin: 5px 0; font-size: 0.8em; color: #999;'>ID: {user_id}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.caption("")
    
    # Session info
    login_time = st.session_state.get('login_time')
    if login_time:
        session_duration = datetime.now() - login_time
        hours = session_duration.seconds // 3600
        minutes = (session_duration.seconds % 3600) // 60
        st.sidebar.caption(f"⏱️ Session: {hours}h {minutes}m")
    
    # Logout button
    if st.sidebar.button("🚪 Logout", use_container_width=True, type="secondary"):
        # Log the logout
        if st.session_state.get('user_id'):
            log_audit_action(st.session_state.user_id, "USER_LOGOUT")
        
        # Invalidate token
        if st.session_state.get('session_token'):
            logout_user(st.session_state.session_token)
        
        # Clear session
        clear_session()
        
        st.success("✅ Logged out successfully")
        time.sleep(1)
        st.rerun()


# ============================================================================
# USER PROFILE SECTION (Optional)
# ============================================================================

def render_user_profile():
    """
    Render user profile management
    """
    with st.expander("👤 User Profile", expanded=False):
        st.markdown("### Account Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Username", st.session_state.username)
            st.metric("Email", st.session_state.email)
        
        with col2:
            st.metric("User ID", st.session_state.user_id)
            if st.session_state.login_time:
                st.metric("Last Login", st.session_state.login_time.strftime('%Y-%m-%d %H:%M'))
        
        st.divider()
        
        st.markdown("#### Change Password")
        
        with st.form("change_password_form"):
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_new_password = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("🔐 Update Password"):
                if new_password != confirm_new_password:
                    st.error("❌ New passwords do not match")
                else:
                    st.info("Password update feature - Coming soon!")


# ============================================================================
# AUTHENTICATION GATEKEEPER
# ============================================================================

def require_authentication():
    """
    Main authentication gatekeeper
    Returns True if authenticated, False otherwise
    
    Usage in main():
        if not require_authentication():
            return  # Stop execution
        
        # Continue with authenticated app...
    """
    # Initialize session state
    init_auth_session_state()
    
    # Check for existing session
    if check_existing_session():
        return True
    
    # Not logged in - show login page
    render_login_page()
    
    # Show footer
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #666; font-size: 0.8em;'>"
        "Smart Portfolio Monitor v6.0 - Secure Multi-User Platform<br>"
        "© 2024 | <a href='#'>Privacy Policy</a> | <a href='#'>Terms of Service</a>"
        "</p>",
        unsafe_allow_html=True
    )
    
    return False


# ============================================================================
# DEMO MODE (for testing without auth)
# ============================================================================

def enable_demo_mode():
    """
    Enable demo mode for testing (bypass authentication)
    WARNING: Remove this in production!
    """
    st.session_state.is_logged_in = True
    st.session_state.user_id = "demo"
    st.session_state.username = "demo_user"
    st.session_state.email = "demo@example.com"
    st.session_state.session_token = "demo_token"
    st.session_state.login_time = datetime.now()
