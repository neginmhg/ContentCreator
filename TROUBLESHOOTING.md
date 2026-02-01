# 🚨 Deployment Troubleshooting Guide

## 502 Error Fix

Your deployment failed with a 502 error. Follow these steps to fix it:

### Step 1: Check Railway Logs

1. Go to your Railway project
2. Click on your service
3. Check the "Logs" tab
4. Look for specific error messages

### Step 2: Common Issues & Fixes

#### Issue 1: Missing OPENAI_API_KEY
**Error:** `WARNING: OPENAI_API_KEY environment variable is not set!`
**Fix:** In Railway dashboard → Settings → Variables, add:
```
OPENAI_API_KEY=sk-your-actual-openai-key
```

#### Issue 2: Database Connection Error
**Error:** `sqlalchemy.exc.OperationalError: could not connect to server`
**Fix:** Railway automatically sets DATABASE_URL. If you see this error:
1. Check if PostgreSQL service is running
2. Try redeploying: `railway up`

#### Issue 3: Import Error
**Error:** `ModuleNotFoundError: No module named 'app'`
**Fix:** Ensure all files are committed to Git:
```bash
git add .
git commit -m "Fix deployment"
git push origin main
```

#### Issue 4: Port Binding Error
**Error:** `Address already in use`
**Fix:** The updated run_server.py handles this automatically.

### Step 3: Run Debug Script

Create a temporary deployment to test:

1. **Update Procfile temporarily:**
```procfile
web: python debug_startup.py
```

2. **Deploy and check logs** for detailed error information

3. **Restore original Procfile:**
```procfile
web: sh -c "python -c 'from app.db import init_db; init_db()' && python -m app.run_server"
```

### Step 4: Quick Fix Checklist

- [ ] **OPENAI_API_KEY** is set in Railway environment variables
- [ ] **All files are committed** to GitHub
- [ ] **requirements.txt** includes all dependencies
- [ ] **Procfile** uses correct startup command
- [ ] **No syntax errors** in Python files

### Step 5: Redeploy

After fixing issues:

```bash
# Commit any fixes
git add .
git commit -m "Fix deployment issues"
git push origin main

# Force redeploy on Railway
# In Railway dashboard: Click "Deploy" → "Redeploy"
```

## Environment Variables Required

### Minimum Required:
```bash
OPENAI_API_KEY=sk-your-actual-openai-key
```

### Optional (Railway sets automatically):
```bash
DATABASE_URL=postgresql://user:password@host:port/db
PORT=8000
HOST=0.0.0.0
ENVIRONMENT=production
```

## What the Updates Do

### Enhanced run_server.py:
- ✅ Checks for missing environment variables
- ✅ Uses Railway's PORT and HOST settings
- ✅ Disables reload in production
- ✅ Provides startup logging

### Updated Procfile:
- ✅ Initializes database before starting server
- ✅ Uses shell command for better error handling

### Health Check Endpoint:
- ✅ `/health` endpoint for monitoring
- ✅ Helps Railway detect if app is running

## Still Having Issues?

### 1. Check Complete Logs
Look for the actual error message in Railway logs, not just "502 Bad Gateway".

### 2. Test Locally with Production Settings
```bash
# Set production-like environment
export DATABASE_URL="sqlite:///test.db"
export OPENAI_API_KEY="test-key"
export ENVIRONMENT="production"

# Test startup
python debug_startup.py
```

### 3. Minimal Reproduction
If still failing, create a minimal app:
```python
# test_app.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello World"}

# Procfile: web: uvicorn test_app:app --host 0.0.0.0 --port $PORT
```

### 4. Contact Support
If all else fails:
- Check Railway status page
- Contact Railway support
- Post error logs in GitHub issues

## Most Common Fix

90% of 502 errors are fixed by:

1. **Setting OPENAI_API_KEY** in Railway environment variables
2. **Committing all files** to GitHub
3. **Redeploying** the service

Try these first before diving into complex debugging!
