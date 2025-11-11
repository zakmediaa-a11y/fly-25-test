"""
Dodo Payments integration for LookingUp.Online
Handles subscriptions and payment processing
"""

import streamlit as st
import os
import requests
from datetime import datetime, timedelta
from supabase import create_client, Client

# Configuration
DODO_API_KEY = os.getenv("DODO_API_KEY")
DODO_BASE_URL = "https://test.dodopayments.com"  # Use test for now
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
APP_URL = os.getenv("APP_URL", "https://your-app.streamlit.app")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Plan configurations
PLANS = {
    'free': {
        'name': 'Free Tier',
        'price': 0,
        'period': None,
        'verifications_per_day': 100,
        'speed': 'Standard (2s delay)',
        'features': [
            '100 verifications per day',
            'Email finding included',
            'Standard speed (2s delay)',
            'Basic support'
        ]
    },
    'weekly': {
        'name': 'Weekly Plan',
        'price': 5,
        'period': 'week',
        'product_id': os.getenv("DODO_PRODUCT_WEEKLY"),
        'trial_days': 3,
        'verifications_per_day': float('inf'),
        'speed': 'Standard (2s delay)',
        'features': [
            '✨ Unlimited verifications',
            'Unlimited email finding',
            'Standard speed (2s delay)',
            '3-day free trial',
            'Email support'
        ]
    },
    'monthly': {
        'name': 'Monthly Plan',
        'price': 15,
        'period': 'month',
        'product_id': os.getenv("DODO_PRODUCT_MONTHLY"),
        'trial_days': 7,
        'verifications_per_day': float('inf'),
        'speed': 'Standard (2s delay)',
        'features': [
            '✨ Unlimited verifications',
            'Unlimited email finding',
            'Standard speed (2s delay)',
            '7-day free trial',
            'Priority email support',
            'Best value!'
        ]
    },
    'pro': {
        'name': 'Pro Plan',
        'price': 35,
        'period': 'month',
        'product_id': os.getenv("DODO_PRODUCT_PRO"),
        'trial_days': 0,
        'verifications_per_day': float('inf'),
        'speed': '⚡ Instant (0s delay)',
        'features': [
            '✨ Unlimited verifications',
            'Unlimited email finding',
            '⚡ INSTANT speed (no delay)',
            'API access included',
            'Priority support',
            '24/7 assistance'
        ]
    }
}

def create_checkout_session(user_id: str, user_email: str, plan_type: str) -> tuple[bool, str, str]:
    """Create a Dodo Payments checkout session"""
    try:
        plan = PLANS.get(plan_type)
        if not plan or plan_type == 'free':
            return False, "Invalid plan", None
        
        headers = {
            'Authorization': f'Bearer {DODO_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        return_url = f"{APP_URL}?payment_success=true&plan={plan_type}"
        
        payload = {
            'product_cart': [{
                'product_id': plan['product_id'],
                'quantity': 1
            }],
            'customer': {
                'email': user_email,
                'name': st.session_state.user.get('full_name', user_email)
            },
            'return_url': return_url,
            'metadata': {
                'user_id': user_id,
                'plan_type': plan_type
            }
        }
        
        response = requests.post(
            f"{DODO_BASE_URL}/checkouts",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            checkout_url = data.get('checkout_url')
            session_id = data.get('id')
            return True, checkout_url, session_id
        else:
            return False, f"Payment error: {response.text}", None
            
    except Exception as e:
        return False, f"Error creating checkout: {str(e)}", None

def activate_subscription(user_id: str, plan_type: str, dodo_subscription_id: str = None, is_trial: bool = False):
    """Activate or update user subscription"""
    try:
        plan = PLANS.get(plan_type)
        
        now = datetime.utcnow()
        
        if is_trial and plan.get('trial_days', 0) > 0:
            status = 'trial'
            trial_ends_at = now + timedelta(days=plan['trial_days'])
            current_period_end = trial_ends_at
        else:
            status = 'active'
            trial_ends_at = None
            if plan['period'] == 'week':
                current_period_end = now + timedelta(days=7)
            elif plan['period'] == 'month':
                current_period_end = now + timedelta(days=30)
            else:
                current_period_end = None
        
        # Check if subscription exists
        existing = supabase.table('subscriptions').select('*').eq('user_id', user_id).execute()
        
        subscription_data = {
            'user_id': user_id,
            'plan_type': plan_type,
            'status': status,
            'dodo_subscription_id': dodo_subscription_id,
            'trial_ends_at': trial_ends_at.isoformat() if trial_ends_at else None,
            'current_period_start': now.isoformat(),
            'current_period_end': current_period_end.isoformat() if current_period_end else None,
            'cancel_at_period_end': False
        }
        
        if existing.data:
            # Update existing subscription
            result = supabase.table('subscriptions').update(subscription_data).eq('user_id', user_id).execute()
        else:
            # Create new subscription
            result = supabase.table('subscriptions').insert(subscription_data).execute()
        
        if result.data:
            # Update session state
            st.session_state.subscription = result.data[0]
            return True
        return False
        
    except Exception as e:
        st.error(f"Error activating subscription: {e}")
        return False

def cancel_subscription(user_id: str):
    """Cancel subscription at end of period"""
    try:
        result = supabase.table('subscriptions').update({
            'cancel_at_period_end': True,
            'updated_at': datetime.utcnow().isoformat()
        }).eq('user_id', user_id).execute()
        
        return bool(result.data)
    except Exception as e:
        st.error(f"Error cancelling subscription: {e}")
        return False

def show_pricing_page():
    """Display pricing plans"""
    st.title("💳 Choose Your Plan")
    st.markdown("### Unlimited email verification & finding")
    
    # Check if coming back from successful payment
    if 'payment_success' in st.query_params:
        st.success("🎉 Payment successful! Your subscription is now active!")
        plan_type = st.query_params.get('plan', 'monthly')
        user_id = st.session_state.user['id']
        activate_subscription(user_id, plan_type, is_trial=True)
        st.rerun()
    
    cols = st.columns(4)
    
    current_sub = st.session_state.subscription
    current_plan = current_sub['plan_type'] if current_sub else 'free'
    
    for idx, (plan_key, plan) in enumerate(PLANS.items()):
        with cols[idx]:
            # Card styling
            is_current = plan_key == current_plan
            is_pro = plan_key == 'pro'
            
            if is_pro:
                st.markdown("### 🌟 " + plan['name'])
            else:
                st.markdown("### " + plan['name'])
            
            # Price
            if plan['price'] == 0:
                st.markdown("## FREE")
            else:
                st.markdown(f"## ${plan['price']}")
                st.caption(f"per {plan['period']}")
            
            # Trial badge
            if plan.get('trial_days', 0) > 0:
                st.success(f"🎁 {plan['trial_days']}-day free trial")
            
            st.markdown("---")
            
            # Features
            for feature in plan['features']:
                if '✨' in feature or '⚡' in feature:
                    st.markdown(f"**{feature}**")
                else:
                    st.markdown(f"✓ {feature}")
            
            st.markdown("---")
            
            # Action button
            if is_current:
                if plan_key == 'free':
                    st.info("Current Plan")
                else:
                    st.success("✓ Active")
                    if st.button("Cancel Subscription", key=f"cancel_{plan_key}", use_container_width=True):
                        if cancel_subscription(st.session_state.user['id']):
                            st.success("Subscription will cancel at end of period")
                            st.rerun()
            else:
                if plan_key == 'free':
                    st.caption("Default plan for all users")
                else:
                    button_label = "Start Free Trial" if plan.get('trial_days', 0) > 0 else "Subscribe"
                    
                    if st.button(button_label, key=f"sub_{plan_key}", type="primary" if is_pro else "secondary", use_container_width=True):
                        success, checkout_url, session_id = create_checkout_session(
                            st.session_state.user['id'],
                            st.session_state.user['email'],
                            plan_key
                        )
                        
                        if success:
                            st.markdown(f"[Click here to complete payment]({checkout_url})")
                            st.info("You'll be redirected to secure checkout...")
                        else:
                            st.error(checkout_url)
    
    st.markdown("---")
    
    # FAQ
    with st.expander("❓ Frequently Asked Questions"):
        st.markdown("""
        **What happens after the free trial?**
        - You'll be charged automatically unless you cancel before trial ends
        
        **Can I cancel anytime?**
        - Yes! Cancel anytime and use until end of billing period
        
        **What's the difference between plans?**
        - Free: 100 verifications/day, standard speed
        - Weekly/Monthly: Unlimited verifications, standard speed
        - Pro: Unlimited + INSTANT speed (no delay between checks)
        
        **Do you offer refunds?**
        - Yes, within 7 days of purchase if you're not satisfied
        
        **Is my payment information secure?**
        - Yes! We use Dodo Payments with bank-level encryption
        """)
    
    # Comparison table
    with st.expander("📊 Detailed Comparison"):
        comparison_data = {
            'Feature': [
                'Daily Verifications',
                'Email Finding',
                'Verification Speed',
                'API Access',
                'Support',
                'Free Trial'
            ],
            'Free': [
                '100/day',
                '✓ Included',
                'Standard (2s)',
                '✗',
                'Basic',
                'N/A'
            ],
            'Weekly ($5/week)': [
                '∞ Unlimited',
                '✓ Included',
                'Standard (2s)',
                '✗',
                'Email',
                '3 days'
            ],
            'Monthly ($15/month)': [
                '∞ Unlimited',
                '✓ Included',
                'Standard (2s)',
                '✗',
                'Priority',
                '7 days'
            ],
            'Pro ($35/month)': [
                '∞ Unlimited',
                '✓ Included',
                '⚡ Instant (0s)',
                '✓ Included',
                '24/7',
                'No trial'
            ]
        }
        
        import pandas as pd
        st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)

def show_subscription_status():
    """Show current subscription status in sidebar"""
    sub = st.session_state.subscription
    
    if not sub:
        st.sidebar.warning("No active subscription")
        return
    
    plan = PLANS.get(sub['plan_type'], {})
    
    st.sidebar.markdown("### 📦 Your Plan")
    st.sidebar.info(f"**{plan.get('name', 'Unknown')}**")
    
    if sub['status'] == 'trial':
        trial_end = sub.get('trial_ends_at')
        if trial_end:
            days_left = (datetime.fromisoformat(trial_end.replace('Z', '+00:00')) - datetime.utcnow()).days
            st.sidebar.success(f"🎁 Trial: {days_left} days left")
    
    if sub['plan_type'] == 'free':
        from auth import check_usage_limit
        can_use, current, limit = check_usage_limit(st.session_state.user['id'])
        st.sidebar.metric("Today's Usage", f"{current}/{limit}")
        
        if not can_use:
            st.sidebar.error("Daily limit reached!")
            st.sidebar.button("Upgrade Now", on_click=lambda: st.session_state.update({'show_pricing': True}))
    else:
        st.sidebar.success("∞ Unlimited verifications")
    
    if st.sidebar.button("Manage Subscription", use_container_width=True):
        st.session_state['show_pricing'] = True