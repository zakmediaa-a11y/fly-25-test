# 🚀 LookingUp.Online - Setup Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Database Setup (Supabase)](#database-setup)
3. [Local Setup](#local-setup)
4. [Streamlit Cloud Deployment](#streamlit-cloud-deployment)
5. [API Deployment](#api-deployment)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## ✅ Prerequisites

- Python 3.9 or higher
- Git installed
- Supabase account (free tier works)
- Dodo Payments account (test mode)
- GitHub account

---

## 🗄️ Database Setup (Supabase)

### Step 1 Create Supabase Project

1. Go to httpssupabase.com
2. Click New Project
3. Fill in
   - Name `lookingup-online`
   - Database Password (save this!)
   - Region (pick closest to you)
4. Wait 2-3 minutes for setup

### Step 2 Run Database Schema

1. In Supabase Dashboard, click SQL Editor (left sidebar)
2. Click New Query
3. Copy-paste the entire content from Artifact #1 (Database Schema)
4. Click RUN button (bottom right)
5. You should see Success. No rows returned
6. ✅ Done! Your database is ready!

### Step 3 Get Supabase Credentials

1. Go to Settings  API (left sidebar)
2. Copy these values
   - Project URL (looks like `httpsxxxxx.supabase.co`)
   - anonpublic key (under Project API keys)
   - service_role key (click Reveal first, then copy)

---

## 💻 Local Setup

### Step 1 Clone Your Repository

```bash
# Open Git Bash
cd Desktop  # or wherever you want
git clone httpsgithub.comyour-usernameyour-repo.git
cd your-repo
```

### Step 2 Create Virtual Environment (Optional but Recommended)

```bash
python -m venv venv

# Activate it
# Windows
venvScriptsactivate
# MacLinux
source venvbinactivate
```

### Step 3 Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 Create .env File

1. Copy `.env.example` to `.env`
```bash
cp .env.example .env
```

2. Open `.env` in Notepad and fill in
```
DODO_API_KEY=NRaMm2UsZdCXqJ-0.9mPZ8WNIIsfF_cd8uQNt_ZZ2ZqkjjmmaxdjZ-kZuOfthZj3G
DODO_WEBHOOK_SECRET=whsec_jIRk2nSzIAMMku4OSGfo5yEYDCs8asMR
DODO_PRODUCT_WEEKLY=pdt_u0AH23qlTyWM957XiDzYe
DODO_PRODUCT_MONTHLY=pdt_xRvkpWJIN8eWJ6GdI3Xhi
DODO_PRODUCT_PRO=pdt_6UKsmdOnuNIjcNdkQP7lj

SUPABASE_URL=httpsulnqpmvwvlnmmsaklplu.supabase.co
SUPABASE_ANON_KEY=[paste your anon key]
SUPABASE_SERVICE_KEY=[paste your service key]

JWT_SECRET=make-this-random-like-pizza123coffee456
APP_URL=httplocalhost8501
```

### Step 5 Test Locally

```bash
streamlit run app.py
```

Browser should open at `httplocalhost8501`

---

## ☁️ Streamlit Cloud Deployment

### Step 1 Push to GitHub

```bash
# Make sure your repo is private!
# Add all new files
git add .
git commit -m Added auth, payments, and API
git push
```

⚠️ IMPORTANT Your repo MUST be private (contains API keys in secrets)

### Step 2 Deploy to Streamlit Cloud

1. Go to httpsshare.streamlit.io
2. Click New app
3. Select your GitHub repository
4. Main file `app.py`
5. Click Advanced settings...

### Step 3 Add Secrets

In the Secrets section, paste this (fill in YOUR values)

```toml
# Dodo Payments
DODO_API_KEY = NRaMm2UsZdCXqJ-0.9mPZ8WNIIsfF_cd8uQNt_ZZ2ZqkjjmmaxdjZ-kZuOfthZj3G
DODO_WEBHOOK_SECRET = whsec_jIRk2nSzIAMMku4OSGfo5yEYDCs8asMR
DODO_PRODUCT_WEEKLY = pdt_u0AH23qlTyWM957XiDzYe
DODO_PRODUCT_MONTHLY = pdt_xRvkpWJIN8eWJ6GdI3Xhi
DODO_PRODUCT_PRO = pdt_6UKsmdOnuNIjcNdkQP7lj

# Supabase
SUPABASE_URL = httpsulnqpmvwvlnmmsaklplu.supabase.co
SUPABASE_ANON_KEY = your_anon_key_here
SUPABASE_SERVICE_KEY = your_service_key_here

# Security
JWT_SECRET = your-random-secret-key
APP_URL = httpsyour-app-name.streamlit.app
```

6. Click Deploy!
7. Wait 2-3 minutes
8. ✅ Your app is live!

### Step 4 Update APP_URL

1. Once deployed, copy your Streamlit app URL (e.g., `httpsyour-app.streamlit.app`)
2. Go back to App settings  Secrets
3. Update `APP_URL` to your actual URL
4. Save and reboot app

---

## 🔌 API Deployment (Optional)

The API is included in `api.py` but needs separate deployment for production use.

### Option 1 Deploy API on Render.com (Free)

1. Go to httpsrender.com
2. Click New +  Web Service
3. Connect your GitHub repo
4. Settings
   - Name `lookingup-api`
   - Runtime Python 3
   - Build Command `pip install -r requirements.txt`
   - Start Command `uvicorn apiapp --host 0.0.0.0 --port $PORT`
5. Add all environment variables from your `.env`
6. Deploy!

### Option 2 Keep API in Same Streamlit App

For MVP, you can call API functions directly from Streamlit (no separate deployment needed).

---

## 🧪 Testing

### Test User Signup

1. Go to your app
2. Click Sign Up tab
3. Create account
   - Name Test User
   - Email test@youremail.com
   - Password Test123456
4. Should see Account created successfully!

### Test Login

1. Login with your new account
2. Should see dashboard with Free Tier plan

### Test Payment Flow

1. Click Manage Subscription or go to pricing
2. Click Start Free Trial on Weekly plan
3. Should redirect to Dodo Payments checkout
4. Use test card `4242 4242 4242 4242`
5. Complete payment
6. Should return to app with trial active

### Test Verification

1. After login, go to Verify Emails - Manual
2. Enter `test@gmail.com`
3. Click Verify
4. Should see results

### Test API Key Generation

1. Upgrade to Pro plan (or manually set in database)
2. Go to settingsAPI section
3. Generate API key
4. Test with

```bash
curl -X POST httpsyour-api-url.comverify 
  -H X-API-Key your_api_key 
  -H Content-Type applicationjson 
  -d '{email test@example.com}'
```

---

## 🐛 Troubleshooting

### Module not found errors

```bash
pip install -r requirements.txt --upgrade
```

### Database connection failed

- Check Supabase URL and keys in `.env`
- Make sure database schema was run successfully
- Check if Supabase project is paused (free tier pauses after inactivity)

### Port 25 blocked in SMTP verification

- Normal on some platforms (Streamlit Cloud, etc.)
- Verification will still work but with lower accuracy
- For production, deploy on VPS with port 25 access

### Payment not activating subscription

- Check Dodo webhook is configured
- Check product IDs match in `.env`
- Check Supabase subscriptions table manually

### Can't login after signup

- Check password meets requirements (8+ chars, letters + numbers)
- Check Supabase users table - is user created
- Check browser console for errors

---

## 📚 File Structure

```
your-project
├── app.py                 # Main Streamlit app (UPDATED)
├── auth.py                # Authentication system (NEW)
├── payments.py            # Payment integration (NEW)
├── api.py                 # FastAPI backend (NEW)
├── requirements.txt       # Dependencies (UPDATED)
├── .env                   # Local secrets (DO NOT COMMIT)
├── .env.example           # Template for .env
├── .gitignore             # Git ignore rules
├── README.md              # This file
└── verification_history.csv  # Created automatically
```

---

## 🔐 Security Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] GitHub repo is PRIVATE
- [ ] Supabase service key is only in secrets (never in code)
- [ ] JWT_SECRET is random and strong
- [ ] Passwords are hashed with bcrypt
- [ ] API keys are hashed in database
- [ ] Rate limiting is enabled

---

## 🚀 Next Steps

1. ✅ Setup complete Test everything!
2. 🎨 Customize UI colors and branding
3. 📧 Set up custom domain
4. 💰 Switch Dodo to production mode
5. 📣 Launch and get customers!

---

## 💬 Need Help

- Check Supabase docs httpssupabase.comdocs
- Check Streamlit docs httpsdocs.streamlit.io
- Check Dodo Payments docs httpsdocs.dodopayments.com

---

## 📝 Quick Commands Reference

```bash
# Local development
streamlit run app.py

# Install new package
pip install package-name
pip freeze  requirements.txt

# Git commands
git status
git add .
git commit -m message
git push

# Check Python version
python --version

# Create virtual environment
python -m venv venv
venvScriptsactivate  # Windows
source venvbinactivate  # MacLinux
```

---

You're all set! Let's launch this thing! 🚀💜