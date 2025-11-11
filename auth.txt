"""
Authentication system for LookingUp.Online
Handles user registration, login, and session management
"""

import streamlit as st
import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import re

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-key")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    if not any(c.isalpha() for c in password):
        return False, "Password must contain at least one letter"
    return True, "Password is strong"

def create_user(email: str, password: str, full_name: str = None) -> tuple[bool, str, dict]:
    """Create a new user account"""
    try:
        # Validate email
        if not validate_email(email):
            return False, "Invalid email format", None
        
        # Validate password
        is_valid, msg = validate_password(password)
        if not is_valid:
            return False, msg, None
        
        # Check if user exists
        existing = supabase.table('users').select('*').eq('email', email).execute()
        if existing.data:
            return False, "Email already registered", None
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user
        user_data = {
            'email': email,
            'password_hash': password_hash,
            'full_name': full_name,
            'email_verified': False
        }
        
        result = supabase.table('users').insert(user_data).execute()
        
        if result.data:
            user = result.data[0]
            return True, "Account created successfully!", user
        else:
            return False, "Failed to create account", None
            
    except Exception as e:
        return False, f"Error: {str(e)}", None

def login_user(email: str, password: str) -> tuple[bool, str, dict]:
    """Authenticate user and return user data"""
    try:
        # Get user by email
        result = supabase.table('users').select('*').eq('email', email).execute()
        
        if not result.data:
            return False, "Invalid email or password", None
        
        user = result.data[0]
        
        # Check if account is active
        if not user.get('is_active', True):
            return False, "Account is deactivated", None
        
        # Verify password
        if not verify_password(password, user['password_hash']):
            return False, "Invalid email or password", None
        
        # Update last login
        supabase.table('users').update({
            'last_login': datetime.utcnow().isoformat()
        }).eq('id', user['id']).execute()
        
        # Get subscription info
        sub_result = supabase.table('subscriptions').select('*').eq('user_id', user['id']).execute()
        if sub_result.data:
            user['subscription'] = sub_result.data[0]
        else:
            user['subscription'] = None
        
        return True, "Login successful!", user
        
    except Exception as e:
        return False, f"Error: {str(e)}", None

def get_user_subscription(user_id: str) -> dict:
    """Get user's current subscription"""
    try:
        result = supabase.table('subscriptions').select('*').eq('user_id', user_id).execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        st.error(f"Error fetching subscription: {e}")
        return None

def check_usage_limit(user_id: str, operation_type: str = 'verify') -> tuple[bool, int, int]:
    """
    Check if user has reached their daily limit
    Returns: (can_use, current_usage, limit)
    """
    try:
        # Get subscription
        sub = get_user_subscription(user_id)
        if not sub:
            return False, 0, 0
        
        plan_type = sub['plan_type']
        
        # Define limits
        limits = {
            'free': 100,
            'weekly': float('inf'),  # Unlimited
            'monthly': float('inf'),  # Unlimited
            'pro': float('inf')  # Unlimited
        }
        
        limit = limits.get(plan_type, 0)
        
        # If unlimited, always allow
        if limit == float('inf'):
            return True, 0, limit
        
        # Get today's usage
        today = datetime.utcnow().date()
        usage_result = supabase.table('daily_usage').select('*').eq('user_id', user_id).eq('date', today.isoformat()).execute()
        
        if usage_result.data:
            current_usage = usage_result.data[0]['total_count']
        else:
            current_usage = 0
        
        can_use = current_usage < limit
        return can_use, current_usage, limit
        
    except Exception as e:
        st.error(f"Error checking usage: {e}")
        return False, 0, 0

def log_usage(user_id: str, operation_type: str, email_count: int = 1, api_key_id: str = None):
    """Log usage to database"""
    try:
        # Log detailed usage
        supabase.table('usage_logs').insert({
            'user_id': user_id,
            'api_key_id': api_key_id,
            'operation_type': operation_type,
            'email_count': email_count,
            'success': True
        }).execute()
        
        # Update daily usage
        if operation_type == 'verify':
            supabase.rpc('increment_daily_usage', {
                'p_user_id': user_id,
                'p_verify_count': email_count
            }).execute()
        elif operation_type == 'find':
            supabase.rpc('increment_daily_usage', {
                'p_user_id': user_id,
                'p_find_count': email_count
            }).execute()
        
    except Exception as e:
        st.error(f"Error logging usage: {e}")

def get_speed_delay(plan_type: str) -> float:
    """Get delay between checks based on plan"""
    delays = {
        'free': 2.0,      # Slow (2 seconds)
        'weekly': 2.0,    # Same as free
        'monthly': 2.0,   # Same as free
        'pro': 0.0        # Instant (no delay)
    }
    return delays.get(plan_type, 2.0)

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'subscription' not in st.session_state:
        st.session_state.subscription = None

def logout():
    """Logout user"""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.subscription = None
    st.rerun()

def show_login_page():
    """Display login/signup page"""
    st.title("🔐 Welcome to LookingUp.Online")
    st.markdown("### Professional Email Verification & Finder")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.markdown("#### Login to your account")
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("Please fill in all fields")
                else:
                    success, message, user = login_user(email, password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.subscription = user.get('subscription')
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    
    with tab2:
        st.markdown("#### Create a new account")
        st.info("🎉 Start with 100 FREE verifications per day!")
        
        with st.form("signup_form"):
            full_name = st.text_input("Full Name", key="signup_name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            password_confirm = st.text_input("Confirm Password", type="password", key="signup_password_confirm")
            
            st.caption("Password must be at least 8 characters with letters and numbers")
            
            submit = st.form_submit_button("Create Account", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("Please fill in all required fields")
                elif password != password_confirm:
                    st.error("Passwords do not match")
                else:
                    success, message, user = create_user(email, password, full_name)
                    if success:
                        st.success(message)
                        st.info("Please login with your new account")
                    else:
                        st.error(message)

def show_user_header():
    """Display user info in header"""
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        user = st.session_state.user
        sub = st.session_state.subscription or get_user_subscription(user['id'])
        
        if sub:
            plan_name = sub['plan_type'].upper()
            status = sub['status']
            
            if status == 'trial':
                trial_end = sub.get('trial_ends_at')
                if trial_end:
                    days_left = (datetime.fromisoformat(trial_end.replace('Z', '+00:00')) - datetime.utcnow()).days
                    st.info(f"👋 {user.get('full_name', user['email'])} | 🎁 Trial: {days_left} days left")
                else:
                    st.info(f"👋 {user.get('full_name', user['email'])} | 📦 {plan_name}")
            else:
                st.info(f"👋 {user.get('full_name', user['email'])} | 📦 {plan_name}")
    
    with col2:
        if sub and sub['plan_type'] == 'free':
            can_use, current, limit = check_usage_limit(user['id'])
            st.metric("Today's Usage", f"{current}/{limit}")
    
    with col3:
        if st.button("Logout", use_container_width=True):
            logout()

def require_auth(func):
    """Decorator to require authentication"""
    def wrapper(*args, **kwargs):
        init_session_state()
        if not st.session_state.authenticated:
            show_login_page()
            return
        return func(*args, **kwargs)
    return wrapper