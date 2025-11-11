"""
API Backend for LookingUp.Online
FastAPI endpoints for programmatic access
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import hashlib
import secrets
import os
from supabase import create_client, Client
from datetime import datetime

# Email verifier (import from your main code)
import sys
sys.path.append('.')
from app import EmailVerifier

# Initialize
app = FastAPI(title="LookingUp API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Email verifier instance
verifier = EmailVerifier()

# Models
class VerifyEmailRequest(BaseModel):
    email: EmailStr
    check_smtp: bool = True
    check_catch_all: bool = True

class VerifyBulkRequest(BaseModel):
    emails: List[EmailStr]
    check_smtp: bool = True
    check_catch_all: bool = True

class FindEmailRequest(BaseModel):
    first_name: str
    last_name: str
    domain: str

class APIKeyResponse(BaseModel):
    key: str
    prefix: str
    name: str

class VerificationResponse(BaseModel):
    email: str
    status: str
    deliverable: bool
    confidence_score: int
    syntax_valid: bool
    domain_exists: bool
    mx_records_exist: bool
    smtp_verified: Optional[bool]
    is_catch_all: Optional[bool]
    is_disposable: bool
    is_role_based: bool
    is_free_provider: bool
    details: List[str]

# Authentication
async def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key from header"""
    try:
        # Hash the provided key
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        
        # Look up in database
        result = supabase.table('api_keys').select('*, users(*)').eq('key_hash', key_hash).eq('is_active', True).execute()
        
        if not result.data:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        api_key_data = result.data[0]
        user = api_key_data['users']
        
        # Check if user subscription is active
        sub_result = supabase.table('subscriptions').select('*').eq('user_id', user['id']).execute()
        
        if not sub_result.data:
            raise HTTPException(status_code=403, detail="No active subscription")
        
        subscription = sub_result.data[0]
        
        # Only Pro plan gets API access
        if subscription['plan_type'] != 'pro':
            raise HTTPException(status_code=403, detail="API access requires Pro plan")
        
        if subscription['status'] not in ['active', 'trial']:
            raise HTTPException(status_code=403, detail="Subscription not active")
        
        # Update last used
        supabase.table('api_keys').update({
            'last_used_at': datetime.utcnow().isoformat()
        }).eq('id', api_key_data['id']).execute()
        
        return {
            'user_id': user['id'],
            'api_key_id': api_key_data['id'],
            'subscription': subscription
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints
@app.get("/")
async def root():
    return {
        "message": "LookingUp API v1.0.0",
        "docs": "/docs",
        "status": "operational"
    }

@app.post("/verify", response_model=VerificationResponse)
async def verify_email(
    request: VerifyEmailRequest,
    auth: dict = Depends(verify_api_key)
):
    """Verify a single email address"""
    try:
        # Perform verification
        result = verifier.verify(
            request.email,
            check_smtp=request.check_smtp,
            check_catch_all=request.check_catch_all
        )
        
        # Log usage
        supabase.table('usage_logs').insert({
            'user_id': auth['user_id'],
            'api_key_id': auth['api_key_id'],
            'operation_type': 'verify',
            'email_count': 1,
            'success': True
        }).execute()
        
        # Increment daily usage
        supabase.rpc('increment_daily_usage', {
            'p_user_id': auth['user_id'],
            'p_verify_count': 1
        }).execute()
        
        return VerificationResponse(
            email=result.email,
            status=result.status,
            deliverable=result.deliverable,
            confidence_score=result.confidence_score,
            syntax_valid=result.syntax_valid,
            domain_exists=result.domain_exists,
            mx_records_exist=result.mx_records_exist,
            smtp_verified=result.smtp_verified,
            is_catch_all=result.is_catch_all,
            is_disposable=result.is_disposable,
            is_role_based=result.is_role_based,
            is_free_provider=result.is_free_provider,
            details=result.details
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify/bulk", response_model=List[VerificationResponse])
async def verify_bulk(
    request: VerifyBulkRequest,
    auth: dict = Depends(verify_api_key)
):
    """Verify multiple email addresses"""
    try:
        if len(request.emails) > 1000:
            raise HTTPException(status_code=400, detail="Maximum 1000 emails per request")
        
        results = []
        for email in request.emails:
            result = verifier.verify(
                email,
                check_smtp=request.check_smtp,
                check_catch_all=request.check_catch_all
            )
            
            results.append(VerificationResponse(
                email=result.email,
                status=result.status,
                deliverable=result.deliverable,
                confidence_score=result.confidence_score,
                syntax_valid=result.syntax_valid,
                domain_exists=result.domain_exists,
                mx_records_exist=result.mx_records_exist,
                smtp_verified=result.smtp_verified,
                is_catch_all=result.is_catch_all,
                is_disposable=result.is_disposable,
                is_role_based=result.is_role_based,
                is_free_provider=result.is_free_provider,
                details=result.details
            ))
        
        # Log usage
        supabase.table('usage_logs').insert({
            'user_id': auth['user_id'],
            'api_key_id': auth['api_key_id'],
            'operation_type': 'bulk_verify',
            'email_count': len(request.emails),
            'success': True
        }).execute()
        
        # Increment daily usage
        supabase.rpc('increment_daily_usage', {
            'p_user_id': auth['user_id'],
            'p_verify_count': len(request.emails)
        }).execute()
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/find", response_model=VerificationResponse)
async def find_email(
    request: FindEmailRequest,
    auth: dict = Depends(verify_api_key)
):
    """Find and verify email from name and domain"""
    try:
        # Generate patterns
        patterns = verifier.generate_email_patterns(
            request.first_name,
            request.last_name,
            request.domain
        )
        
        found_email = None
        best_result = None
        
        # Test each pattern
        for pattern_info in patterns:
            email = pattern_info['email']
            result = verifier.verify(email, check_smtp=True, check_catch_all=True)
            
            # If found valid, return immediately
            if result.smtp_verified is True:
                found_email = email
                best_result = result
                break
            
            # Keep track of best result
            if best_result is None or result.confidence_score > best_result.confidence_score:
                found_email = email
                best_result = result
        
        if not best_result:
            raise HTTPException(status_code=404, detail="Could not find email")
        
        # Log usage
        supabase.table('usage_logs').insert({
            'user_id': auth['user_id'],
            'api_key_id': auth['api_key_id'],
            'operation_type': 'find',
            'email_count': 1,
            'success': True
        }).execute()
        
        # Increment daily usage
        supabase.rpc('increment_daily_usage', {
            'p_user_id': auth['user_id'],
            'p_find_count': 1
        }).execute()
        
        return VerificationResponse(
            email=best_result.email,
            status=best_result.status,
            deliverable=best_result.deliverable,
            confidence_score=best_result.confidence_score,
            syntax_valid=best_result.syntax_valid,
            domain_exists=best_result.domain_exists,
            mx_records_exist=best_result.mx_records_exist,
            smtp_verified=best_result.smtp_verified,
            is_catch_all=best_result.is_catch_all,
            is_disposable=best_result.is_disposable,
            is_role_based=best_result.is_role_based,
            is_free_provider=best_result.is_free_provider,
            details=best_result.details
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/usage")
async def get_usage(auth: dict = Depends(verify_api_key)):
    """Get usage statistics"""
    try:
        # Get today's usage
        today = datetime.utcnow().date()
        usage_result = supabase.table('daily_usage').select('*').eq('user_id', auth['user_id']).eq('date', today.isoformat()).execute()
        
        if usage_result.data:
            usage = usage_result.data[0]
        else:
            usage = {
                'verify_count': 0,
                'find_count': 0,
                'total_count': 0
            }
        
        # Get subscription info
        sub = auth['subscription']
        
        return {
            'plan': sub['plan_type'],
            'status': sub['status'],
            'today': {
                'verifications': usage.get('verify_count', 0),
                'finds': usage.get('find_count', 0),
                'total': usage.get('total_count', 0)
            },
            'limits': {
                'daily_limit': 'unlimited' if sub['plan_type'] != 'free' else 100,
                'rate_limit': '60 requests/minute'
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)