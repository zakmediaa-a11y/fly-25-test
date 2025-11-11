"""
LookingUp.Online - Complete Streamlit App
Email Verification & Finder with Auth, Payments, and API
"""

import re
import dns.resolver
import socket
import time
import random
import streamlit as st
import pandas as pd
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from datetime import datetime
import hashlib
import secrets

# Import our modules
from auth import (
    init_session_state, show_login_page, show_user_header, 
    get_user_subscription, check_usage_limit, log_usage, 
    get_speed_delay, logout
)
from payments import show_pricing_page, show_subscription_status, PLANS

# Page config
st.set_page_config(
    page_title="LookingUp.Online - Email Verification", 
    page_icon="📧", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with your colors
st.markdown("""
<style>
    /* Your brand colors */
    :root {
        --primary: #540863;
        --secondary: #92487A;
        --accent: #E49BA6;
        --light: #FFD3D5;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #540863 0%, #92487A 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    
    /* Button styling */
    .stButton>button {
        background: linear-gradient(135deg, #540863 0%, #92487A 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #92487A 0%, #E49BA6 100%);
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(84, 8, 99, 0.3);
    }
    
    /* Card styling */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        border-left: 4px solid #540863;
    }
    
    /* Success/Error colors matching brand */
    .success-box {
        background: #FFD3D5;
        border-left: 4px solid #92487A;
        padding: 1rem;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

@dataclass
class EmailVerificationResult:
    email: str
    status: str
    syntax_valid: bool
    domain_exists: bool
    mx_records_exist: bool
    smtp_verified: Optional[bool]
    is_catch_all: Optional[bool]
    is_disposable: bool
    is_role_based: bool
    is_free_provider: bool
    mx_records: List[str]
    details: List[str]
    confidence_score: int
    deliverable: bool

class EmailVerifier:
    def __init__(self):
        self.disposable_domains = {
            'tempmail.com', 'guerrillamail.com', 'mailinator.com', '10minutemail.com',
            'throwaway.email', 'yopmail.com', 'temp-mail.org', 'getnada.com',
            'trashmail.com', 'fakeinbox.com', 'maildrop.cc', 'sharklasers.com',
        }
        
        self.role_prefixes = {
            'admin', 'info', 'support', 'sales', 'contact', 'help', 'service',
            'office', 'noreply', 'no-reply', 'webmaster', 'postmaster',
        }
        
        self.free_providers = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com',
            'icloud.com', 'mail.com', 'protonmail.com', 'zoho.com',
        }
    
    def validate_syntax(self, email: str) -> Tuple[bool, str]:
        if not email or '@' not in email:
            return False, "Missing @ symbol"
        if email.count('@') > 1:
            return False, "Multiple @ symbols"
        
        try:
            local, domain = email.split('@')
        except:
            return False, "Invalid format"
        
        if not local or len(local) > 64:
            return False, "Invalid local part length"
        if local.startswith('.') or local.endswith('.'):
            return False, "Local part cannot start/end with dot"
        if '..' in local:
            return False, "Consecutive dots"
        if not domain or len(domain) > 255:
            return False, "Invalid domain length"
        
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Invalid email format"
        
        return True, "Valid syntax"
    
    def check_domain_exists(self, domain: str) -> bool:
        try:
            socket.gethostbyname(domain)
            return True
        except:
            return False
    
    def get_mx_records(self, domain: str) -> List[str]:
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            sorted_mx = sorted(mx_records, key=lambda x: x.preference)
            return [str(r.exchange).rstrip('.') for r in sorted_mx]
        except:
            return []
    
    def smtp_verify(self, email: str, mx_host: str, timeout: int = 15) -> Tuple[Optional[bool], str]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((mx_host, 25))
            
            banner = sock.recv(1024).decode('utf-8', errors='ignore')
            if not banner.startswith('220'):
                sock.close()
                return None, f"Invalid banner"
            
            sock.send(b'EHLO verify.local\r\n')
            time.sleep(0.5)
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            
            if not response.startswith('250'):
                sock.send(b'HELO verify.local\r\n')
                time.sleep(0.5)
                response = sock.recv(1024).decode('utf-8', errors='ignore')
                if not response.startswith('250'):
                    sock.close()
                    return None, f"HELO failed"
            
            sender = random.choice(['verify@gmail.com', 'check@yahoo.com'])
            sock.send(f'MAIL FROM:<{sender}>\r\n'.encode())
            time.sleep(0.5)
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            
            if not response.startswith('250'):
                sock.close()
                return None, f"MAIL FROM rejected"
            
            sock.send(f'RCPT TO:<{email}>\r\n'.encode())
            time.sleep(0.5)
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            
            sock.send(b'QUIT\r\n')
            sock.close()
            
            response_code = response[:3]
            
            if response_code in ['250', '251']:
                return True, "Mailbox verified"
            elif response_code in ['550', '551', '552', '553']:
                return False, "Mailbox does not exist"
            else:
                return None, f"Inconclusive ({response_code})"
                
        except Exception as e:
            return None, f"Error: {str(e)[:40]}"
    
    def check_catch_all(self, domain: str, mx_host: str) -> Optional[bool]:
        random_local = f"nonexistent{random.randint(100000, 999999)}test{random.randint(1000, 9999)}"
        random_email = f"{random_local}@{domain}"
        try:
            result, _ = self.smtp_verify(random_email, mx_host, timeout=10)
            return result is True
        except:
            return None
    
    def is_disposable(self, domain: str) -> bool:
        return domain.lower() in self.disposable_domains
    
    def is_role_based(self, email: str) -> bool:
        local_part = email.split('@')[0].lower()
        return local_part in self.role_prefixes
    
    def is_free_provider(self, domain: str) -> bool:
        return domain.lower() in self.free_providers
    
    def calculate_confidence(self, result: 'EmailVerificationResult') -> int:
        score = 0
        if result.syntax_valid:
            score += 10
        if result.domain_exists:
            score += 10
        if result.mx_records_exist:
            score += 20
        if result.smtp_verified is True:
            score += 50
        elif result.smtp_verified is False:
            return 0
        if result.is_catch_all:
            score -= 15
        if result.is_disposable:
            score = min(score, 30)
        if result.is_role_based:
            score -= 5
        return max(0, min(100, score))
    
    def verify(self, email: str, check_smtp: bool = True, check_catch_all: bool = True) -> EmailVerificationResult:
        email = email.strip().lower()
        details = []
        
        syntax_valid, syntax_msg = self.validate_syntax(email)
        if not syntax_valid:
            return EmailVerificationResult(
                email=email, status='INVALID', syntax_valid=False,
                domain_exists=False, mx_records_exist=False, smtp_verified=None,
                is_catch_all=None, is_disposable=False, is_role_based=False,
                is_free_provider=False, mx_records=[], details=[syntax_msg],
                confidence_score=0, deliverable=False
            )
        
        domain = email.split('@')[1]
        is_disposable = self.is_disposable(domain)
        is_role_based = self.is_role_based(email)
        is_free_provider = self.is_free_provider(domain)
        
        if is_disposable:
            details.append("Disposable email")
        if is_role_based:
            details.append("Role-based address")
        
        domain_exists = self.check_domain_exists(domain)
        if not domain_exists:
            details.append("Domain does not exist")
            return EmailVerificationResult(
                email=email, status='INVALID', syntax_valid=True,
                domain_exists=False, mx_records_exist=False, smtp_verified=None,
                is_catch_all=None, is_disposable=is_disposable,
                is_role_based=is_role_based, is_free_provider=is_free_provider,
                mx_records=[], details=details, confidence_score=10, deliverable=False
            )
        
        mx_records = self.get_mx_records(domain)
        mx_records_exist = len(mx_records) > 0
        
        if not mx_records_exist:
            details.append("No MX records")
            return EmailVerificationResult(
                email=email, status='INVALID', syntax_valid=True,
                domain_exists=True, mx_records_exist=False, smtp_verified=None,
                is_catch_all=None, is_disposable=is_disposable,
                is_role_based=is_role_based, is_free_provider=is_free_provider,
                mx_records=[], details=details, confidence_score=20, deliverable=False
            )
        
        smtp_verified = None
        if check_smtp:
            smtp_verified, smtp_detail = self.smtp_verify(email, mx_records[0])
            details.append(smtp_detail)
        
        is_catch_all = None
        if check_catch_all and mx_records and smtp_verified is not False:
            is_catch_all = self.check_catch_all(domain, mx_records[0])
            if is_catch_all:
                details.append("Catch-all domain")
        
        if smtp_verified is False:
            status = 'INVALID'
            deliverable = False
        elif smtp_verified is True and not is_disposable:
            status = 'VALID'
            deliverable = True
        elif is_disposable or is_catch_all:
            status = 'RISKY'
            deliverable = smtp_verified is True
        else:
            status = 'UNKNOWN'
            deliverable = False
        
        result = EmailVerificationResult(
            email=email, status=status, syntax_valid=syntax_valid,
            domain_exists=domain_exists, mx_records_exist=mx_records_exist,
            smtp_verified=smtp_verified, is_catch_all=is_catch_all,
            is_disposable=is_disposable, is_role_based=is_role_based,
            is_free_provider=is_free_provider, mx_records=mx_records,
            details=details, confidence_score=0, deliverable=deliverable
        )
        
        result.confidence_score = self.calculate_confidence(result)
        return result
    
    def generate_email_patterns(self, first_name: str, last_name: str, domain: str) -> List[Dict[str, str]]:
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        
        patterns = [
            (f"{first}{last}@{domain}", "firstlast"),
            (f"{last}{first}@{domain}", "lastfirst"),
            (f"{first}_{last}@{domain}", "first_last"),
            (f"{last}_{first}@{domain}", "last_first"),
            (f"{first}.{last}@{domain}", "first.last"),
            (f"{last}.{first}@{domain}", "last.first"),
            (f"{first}-{last}@{domain}", "first-last"),
            (f"{last}-{first}@{domain}", "last-first"),
            (f"{first[0]}{last}@{domain}", "flast"),
            (f"{first}{last[0]}@{domain}", "firstl"),
            (f"{last[0]}{first}@{domain}", "lfirst"),
            (f"{last}{first[0]}@{domain}", "lastf"),
            (f"{first}@{domain}", "first"),
            (f"{last}@{domain}", "last"),
            (f"{first[0]}.{last}@{domain}", "f.last"),
            (f"{first}.{last[0]}@{domain}", "first.l"),
            (f"{last}.{first[0]}@{domain}", "last.f"),
            (f"{last[0]}.{first}@{domain}", "l.first"),
            (f"{first}_{last[0]}@{domain}", "first_l"),
            (f"{last}_{first[0]}@{domain}", "last_f"),
            (f"{first[0]}_{last}@{domain}", "f_last"),
            (f"{last[0]}_{first}@{domain}", "l_first"),
            (f"{last[0]}-{first}@{domain}", "l-first"),
            (f"{first[0]}-{last}@{domain}", "f-last"),
            (f"{first}-{last[0]}@{domain}", "first-l"),
            (f"{last}-{first[0]}@{domain}", "last-f"),
        ]
        
        return [{"email": email, "pattern": pattern} for email, pattern in patterns]

@st.cache_resource
def get_verifier():
    return EmailVerifier()

def generate_api_key(user_id: str, name: str) -> tuple[str, str]:
    """Generate a new API key"""
    from supabase import create_client
    
    # Generate random key
    key = f"lup_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_prefix = key[:12] + "..."
    
    # Save to database
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY")
    )
    
    result = supabase.table('api_keys').insert({
        'user_id': user_id,
        'key_hash': key_hash,
        'key_prefix': key_prefix,
        'name': name,
        'is_active': True
    }).execute()
    
    if result.data:
        return key, key_prefix
    return None, None

def main():
    # Initialize session
    init_session_state()
    
    # Check authentication
    if not st.session_state.authenticated:
        show_login_page()
        return
    
    # Show user header
    show_user_header()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🎯 LookingUp.Online")
        show_subscription_status()
        
        st.markdown("---")
        st.markdown("### 🔗 Quick Links")
        
        # Navigation
        if 'show_pricing' not in st.session_state:
            st.session_state.show_pricing = False
        
        if st.button("💳 Pricing & Plans", use_container_width=True):
            st.session_state.show_pricing = True
            st.rerun()
        
        if st.button("🔑 API Keys", use_container_width=True):
            st.session_state.show_pricing = False
            st.session_state['active_page'] = 'api_keys'
            st.rerun()
        
        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.show_pricing = False
            st.session_state['active_page'] = 'dashboard'
            st.rerun()
    
    # Show pricing page if requested
    if st.session_state.get('show_pricing', False):
        show_pricing_page()
        return
    
    # Show API keys page
    if st.session_state.get('active_page') == 'api_keys':
        show_api_keys_page()
        return
    
    # Main app
    verifier = get_verifier()
    user = st.session_state.user
    sub = get_user_subscription(user['id'])
    
    # Get speed delay for user's plan
    delay = get_speed_delay(sub['plan_type'] if sub else 'free')
    
    # Header
    st.markdown(f"""
    <div class="main-header">
        <h1>📧 Email Verification & Finder</h1>
        <p>Professional email validation powered by SMTP verification</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check usage limits for free tier
    if sub and sub['plan_type'] == 'free':
        can_use, current, limit = check_usage_limit(user['id'])
        if not can_use:
            st.error(f"🚫 Daily limit reached ({current}/{limit} used today)")
            st.info("Upgrade to unlimited plan to continue!")
            if st.button("View Plans", type="primary"):
                st.session_state.show_pricing = True
                st.rerun()
            return
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "✅ Verify Emails",
        "🔍 Find Emails",
        "📁 Bulk Upload",
        "📊 Analytics"
    ])
    
    with tab1:
        show_verify_tab(verifier, user, delay)
    
    with tab2:
        show_find_tab(verifier, user, delay)
    
    with tab3:
        show_bulk_tab(verifier, user, delay)
    
    with tab4:
        show_analytics_tab(user)

def show_verify_tab(verifier, user, delay):
    """Verify emails tab"""
    st.markdown("### ✅ Verify Email Addresses")
    st.caption("Enter emails to verify (one per line or comma-separated)")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        email_input = st.text_area(
            "Email Addresses",
            placeholder="user1@gmail.com\nuser2@yahoo.com\nuser3@example.com",
            height=200,
            key="verify_input"
        )
    
    with col2:
        st.metric("Speed", f"{delay}s delay" if delay > 0 else "⚡ Instant")
        verify_btn = st.button("🚀 Verify", type="primary", use_container_width=True)
    
    if verify_btn:
        if not email_input or not email_input.strip():
            st.error("Please enter at least one email")
            return
        
        emails = [e.strip() for e in email_input.replace(',', '\n').split('\n') if e.strip()]
        
        if not emails:
            st.error("No valid emails found")
            return
        
        results = []
        total = len(emails)
        
        progress = st.progress(0)
        status = st.empty()
        
        for i, email in enumerate(emails):
            status.text(f"Verifying {i+1}/{total}: {email}")
            progress.progress((i+1)/total)
            
            result = verifier.verify(email)
            
            # Log usage
            log_usage(user['id'], 'verify', 1)
            
            results.append({
                'Email': result.email,
                'Status': result.status,
                'Deliverable': '✅' if result.deliverable else '❌',
                'Confidence': f"{result.confidence_score}%",
                'Details': '; '.join(result.details)
            })
            
            if i < total - 1 and delay > 0:
                time.sleep(delay)
        
        df = pd.DataFrame(results)
        
        valid = sum(1 for r in results if r['Status'] == 'VALID')
        st.success(f"✅ Complete! {valid}/{total} valid emails")
        
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, "results.csv", "text/csv")

def show_find_tab(verifier, user, delay):
    """Find emails tab"""
    st.markdown("### 🔍 Find Email Addresses")
    st.caption("Enter names and domains to find emails")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        find_input = st.text_area(
            "Names and Domains (format: FirstName LastName domain.com)",
            placeholder="John Doe acme.com\nJane Smith techcorp.io",
            height=200,
            key="find_input"
        )
    
    with col2:
        st.info("Tests 26 patterns per person")
        find_btn = st.button("🔍 Find", type="primary", use_container_width=True)
    
    if find_btn:
        if not find_input:
            st.error("Please enter at least one entry")
            return
        
        lines = [l.strip() for l in find_input.split('\n') if l.strip()]
        results = []
        
        progress = st.progress(0)
        status = st.empty()
        
        for idx, line in enumerate(lines):
            status.text(f"Finding {idx+1}/{len(lines)}")
            progress.progress((idx+1)/len(lines))
            
            parts = re.split(r'[,\s]+', line)
            if len(parts) < 3:
                results.append({
                    'Name': line,
                    'Found_Email': 'ERROR',
                    'Status': 'Invalid format'
                })
                continue
            
            first, last, domain = parts[0], parts[1], parts[2]
            patterns = verifier.generate_email_patterns(first, last, domain)
            
            best_email = None
            best_result = None
            
            for p in patterns:
                result = verifier.verify(p['email'])
                if result.smtp_verified:
                    best_email = p['email']
                    best_result = result
                    break
                if not best_result or result.confidence_score > best_result.confidence_score:
                    best_email = p['email']
                    best_result = result
                time.sleep(delay)
            
            # Log usage
            log_usage(user['id'], 'find', 1)
            
            if best_result:
                results.append({
                    'Name': f"{first} {last}",
                    'Domain': domain,
                    'Found_Email': best_email,
                    'Status': best_result.status,
                    'Confidence': f"{best_result.confidence_score}%"
                })
        
        df = pd.DataFrame(results)
        found = sum(1 for r in results if r.get('Status') == 'VALID')
        
        st.success(f"🎯 Found {found}/{len(lines)} emails!")
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, "found_emails.csv", "text/csv")

def show_bulk_tab(verifier, user, delay):
    """Bulk CSV upload tab"""
    st.markdown("### 📁 Bulk CSV Upload")
    
    uploaded_file = st.file_uploader("Upload CSV", type=['csv'])
    
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.write("Preview:", df.head())
        
        col = st.selectbox("Select email column", df.columns)
        
        if st.button("Process", type="primary"):
            emails = df[col].dropna().tolist()
            
            # Process with progress
            results = []
            progress = st.progress(0)
            
            for i, email in enumerate(emails):
                progress.progress((i+1)/len(emails))
                result = verifier.verify(str(email))
                log_usage(user['id'], 'verify', 1)
                
                results.append({
                    'Status': result.status,
                    'Deliverable': result.deliverable,
                    'Confidence': result.confidence_score
                })
                
                if delay > 0 and i < len(emails) - 1:
                    time.sleep(delay)
            
            results_df = pd.DataFrame(results)
            final = pd.concat([df, results_df], axis=1)
            
            st.success("✅ Processing complete!")
            st.dataframe(final)
            
            csv = final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Results", csv, "bulk_results.csv", "text/csv")

def show_analytics_tab(user):
    """Analytics dashboard"""
    st.markdown("### 📊 Usage Analytics")
    
    from supabase import create_client
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY")
    )
    
    # Get usage stats
    result = supabase.table('daily_usage').select('*').eq('user_id', user['id']).order('date', desc=True).limit(30).execute()
    
    if result.data:
        df = pd.DataFrame(result.data)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Verifications", df['verify_count'].sum())
        with col2:
            st.metric("Total Finds", df['find_count'].sum())
        with col3:
            st.metric("Total Operations", df['total_count'].sum())
        
        st.line_chart(df.set_index('date')['total_count'])
    else:
        st.info("No usage data yet. Start verifying emails!")

def show_api_keys_page():
    """API Keys management page"""
    st.markdown("### 🔑 API Keys")
    
    user = st.session_state.user
    sub = get_user_subscription(user['id'])
    
    if not sub or sub['plan_type'] != 'pro':
        st.warning("⚠️ API access requires Pro plan")
        if st.button("Upgrade to Pro"):
            st.session_state.show_pricing = True
            st.rerun()
        return
    
    st.success("✅ API Access Enabled")
    
    # Show API documentation
    with st.expander("📚 API Documentation"):
        st.markdown("""
        ### Authentication
        Include your API key in the `X-API-Key` header:
        ```bash
        curl -X POST "https://your-api.com/verify" \\
          -H "X-API-Key: your_api_key" \\
          -H "Content-Type: application/json" \\
          -d '{"email": "test@example.com"}'
        ```
        
        ### Endpoints
        - `POST /verify` - Verify single email
        - `POST /verify/bulk` - Verify multiple emails
        - `POST /find` - Find email from name + domain
        - `GET /usage` - Get usage statistics
        
        Full docs: https://docs.lookingup.online/api
        """)
    
    # Generate new key
    st.markdown("### Generate New Key")
    key_name = st.text_input("Key Name", placeholder="My App")
    
    if st.button("Generate API Key", type="primary"):
        if not key_name:
            st.error("Please enter a key name")
        else:
            key, prefix = generate_api_key(user['id'], key_name)
            if key:
                st.success("✅ API Key Generated!")
                st.code(key, language="text")
                st.warning("⚠️ Copy this key now! You won't see it again.")
            else:
                st.error("Failed to generate key")
    
    # List existing keys
    st.markdown("### Your API Keys")
    
    from supabase import create_client
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY")
    )
    
    result = supabase.table('api_keys').select('*').eq('user_id', user['id']).eq('is_active', True).execute()
    
    if result.data:
        for key_data in result.data:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.text(f"🔑 {key_data['name']}")
                st.caption(f"Key: {key_data['key_prefix']}")
            with col2:
                st.caption(f"Created: {key_data['created_at'][:10]}")
            with col3:
                if st.button("Revoke", key=f"revoke_{key_data['id']}"):
                    supabase.table('api_keys').update({'is_active': False}).eq('id', key_data['id']).execute()
                    st.success("Key revoked!")
                    st.rerun()
    else:
        st.info("No API keys yet. Generate one above!")

if __name__ == "__main__":
    main()