"""
Authentication Module
Handles user login, registration, and session management
"""
import streamlit as st
import re
from database import get_db

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength
    Returns: (is_valid, message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Password is strong"

def validate_username(username: str) -> tuple[bool, str]:
    """Validate username"""
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 20:
        return False, "Username must be less than 20 characters"
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"
    return True, "Username is valid"

def show_login_page():
    """Display login page"""
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <h1 style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                   -webkit-background-clip: text;
                   -webkit-text-fill-color: transparent;
                   font-size: 3rem;'>
            🧠 Smart Portfolio Monitor
        </h1>
        <p style='color: #666; font-size: 1.2rem;'>Login to manage your portfolio</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Login")
        
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
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                submit = st.form_submit_button(
                    "🚀 Login",
                    use_container_width=True,
                    type="primary"
                )
            
            with col_b:
                register = st.form_submit_button(
                    "📝 Register",
                    use_container_width=True
                )
        
        if submit:
            if not username or not password:
                st.error("❌ Please enter both username and password")
            else:
                db = get_db()
                success, user_data = db.login_user(username, password)
                
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_data['user_id']
                    st.session_state.username = user_data['username']
                    st.session_state.email = user_data['email']
                    st.session_state.full_name = user_data.get('full_name')
                    
                    st.success(f"✅ Welcome back, {user_data['username']}!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
        
        if register:
            st.session_state.show_register = True
            st.rerun()
        
        # Demo credentials
        with st.expander("💡 Demo Credentials", expanded=False):
            st.info("""
            **Quick Login:**
            - Username: `demo`
            - Password: `Demo@123`
            
            Or register a new account!
            """)

def show_registration_page():
    """Display registration page"""
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <h1 style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                   -webkit-background-clip: text;
                   -webkit-text-fill-color: transparent;
                   font-size: 3rem;'>
            🧠 Smart Portfolio Monitor
        </h1>
        <p style='color: #666; font-size: 1.2rem;'>Create your account</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 📝 Registration")
        
        with st.form("register_form", clear_on_submit=False):
            full_name = st.text_input(
                "Full Name (Optional)",
                placeholder="John Doe"
            )
            
            username = st.text_input(
                "Username *",
                placeholder="Choose a unique username",
                help="3-20 characters, letters, numbers, and underscores only"
            )
            
            email = st.text_input(
                "Email Address *",
                placeholder="your.email@example.com"
            )
            
            password = st.text_input(
                "Password *",
                type="password",
                placeholder="Create a strong password",
                help="Min 8 characters with uppercase, lowercase, and number"
            )
            
            confirm_password = st.text_input(
                "Confirm Password *",
                type="password",
                placeholder="Re-enter your password"
            )
            
            st.caption("* Required fields")
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                submit = st.form_submit_button(
                    "✅ Register",
                    use_container_width=True,
                    type="primary"
                )
            
            with col_b:
                back = st.form_submit_button(
                    "← Back to Login",
                    use_container_width=True
                )
        
        if submit:
            # Validation
            errors = []
            
            if not username or not email or not password or not confirm_password:
                errors.append("❌ Please fill in all required fields")
            
            if username:
                valid, msg = validate_username(username)
                if not valid:
                    errors.append(f"❌ {msg}")
            
            if email and not validate_email(email):
                errors.append("❌ Invalid email format")
            
            if password:
                valid, msg = validate_password(password)
                if not valid:
                    errors.append(f"❌ {msg}")
            
            if password != confirm_password:
                errors.append("❌ Passwords do not match")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Register user
                db = get_db()
                success, message = db.register_user(username, email, password, full_name)
                
                if success:
                    st.success("✅ " + message)
                    st.info("You can now login with your credentials!")
                    st.balloons()
                    
                    # Auto-switch to login after 2 seconds
                    import time
                    time.sleep(2)
                    st.session_state.show_register = False
                    st.rerun()
                else:
                    st.error("❌ " + message)
        
        if back:
            st.session_state.show_register = False
            st.rerun()

def show_auth_page():
    """Main authentication controller"""
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    
    # Show appropriate page
    if st.session_state.show_register:
        show_registration_page()
    else:
        show_login_page()

def logout():
    """Logout user and clear session"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.logged_in = False
    st.rerun()

def is_logged_in() -> bool:
    """Check if user is logged in"""
    return st.session_state.get('logged_in', False)

def get_current_user_id() -> int:
    """Get current user ID"""
    return st.session_state.get('user_id', None)

def require_login():
    """Decorator to require login for a page"""
    if not is_logged_in():
        show_auth_page()
        st.stop()
