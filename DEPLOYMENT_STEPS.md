# 🚀 Complete Deployment Guide

## ✅ Changes Made for Production Deployment

### 1. Database Configuration
- **Dual database support**: SQLite for development, PostgreSQL for production
- **Environment-based switching**: Uses `DATABASE_URL` environment variable
- **Automatic migrations**: Handles both SQLite and PostgreSQL schema changes

### 2. New Files Created
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Local development with PostgreSQL
- `Procfile` - Railway deployment configuration
- `startup.sh` - Database initialization script

### 3. Updated Files
- `app/config.py` - Production database support
- `app/db.py` - Multi-database engine configuration
- `requirements.txt` - Added PostgreSQL driver
- `.env.example` - Production environment variables

---

## 📋 Exact Deployment Steps

### Step 1: Prepare Your Local Repository

```bash
# Stop any running server
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Test local setup still works
source .venv/bin/activate && python -m app.run_server
# Verify it works, then stop it
```

### Step 2: Commit All Changes

```bash
# Add all new files
git add .

# Commit changes
git commit -m "Add production deployment support

- Database configuration for SQLite/PostgreSQL
- Docker and docker-compose setup
- Railway deployment configuration
- Updated requirements and environment variables"
```

### Step 3: Push to GitHub

```bash
# If you haven't set up remote yet
git remote add origin https://github.com/yourusername/content-generator-app.git

# Push to GitHub
git push -u origin main
```

### Step 4: Deploy to Railway (Recommended)

1. **Go to [railway.app](https://railway.app)**
2. **Sign up/login** with GitHub
3. **Click "New Project" → "Deploy from GitHub repo"**
4. **Select your repository**
5. **Add Environment Variables:**
   ```
   OPENAI_API_KEY=sk-your-actual-openai-key
   ```
6. **Click "Deploy"**

**That's it! Railway will:**
- Detect it's a Python app
- Provision PostgreSQL database
- Set `DATABASE_URL` automatically
- Install dependencies
- Start your application

### Step 5: Alternative - Deploy to Render

1. **Go to [render.com](https://render.com)**
2. **Sign up/login** with GitHub
3. **Click "New +" → "Web Service"**
4. **Connect your GitHub repository**
5. **Configure:**
   - **Name**: content-generator
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m app.run_server`
6. **Add Environment Variables:**
   ```
   OPENAI_API_KEY=sk-your-actual-openai-key
   DATABASE_URL=postgresql://your-db-url-here
   ```
7. **Click "Create Web Service"**

### Step 6: Alternative - Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# This creates:
# - PostgreSQL database
# - Application with all dependencies
# - Persistent data volumes
```

---

## 🔧 Environment Variables Required

### Minimum Required:
```bash
OPENAI_API_KEY=sk-your-actual-openai-key
```

### Optional (with defaults):
```bash
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
OPENAI_DRAFT_MODEL=gpt-4o-mini
DRAFT_MAX_CHARS=1200
AUDIO_CHUNK_MINUTES=10
TIMEZONE=America/Los_Angeles
YT_DLP_JS_RUNTIMES=node
FFMPEG_LOCATION=
```

### Database (auto-set by Railway):
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

---

## 📁 Files Structure for Production

```
content-generator-app/
├── app/                    # ✅ Main application
├── requirements.txt        # ✅ Dependencies (includes PostgreSQL)
├── Dockerfile             # ✅ Container setup
├── docker-compose.yml     # ✅ Local development
├── Procfile              # ✅ Railway deployment
├── startup.sh            # ✅ Database initialization
├── .env.example          # ✅ Environment template
├── .gitignore            # ✅ Excludes sensitive data
├── channels.txt          # ✅ Default channels
├── blogs.txt             # ✅ Default blogs
├── style.md              # ✅ Writing style
└── README.md             # ✅ Documentation
```

---

## 🧪 Testing Before Deploy

```bash
# Test with PostgreSQL locally
docker-compose up -d

# Wait 30 seconds, then test
curl http://localhost:8000

# Check logs
docker-compose logs app
```

---

## 🚨 Important Notes

### Security:
- ❌ **Never commit `.env`** to Git
- ✅ **Always use environment variables** for API keys
- ✅ **Railway automatically provides** HTTPS and database

### Database:
- ✅ **Railway provides PostgreSQL** automatically
- ✅ **Data persists** across deployments
- ✅ **Automatic migrations** on startup

### Performance:
- ✅ **PostgreSQL** is much faster than SQLite
- ✅ **Railway handles** scaling automatically
- ✅ **CDN included** for static assets

---

## 🎯 Quick Deployment Checklist

- [ ] Test locally: `python -m app.run_server`
- [ ] Commit all changes to Git
- [ ] Push to GitHub
- [ ] Set up Railway account
- [ ] Add `OPENAI_API_KEY` environment variable
- [ ] Deploy from Railway dashboard
- [ ] Test deployed application

---

## 🆘 Troubleshooting

### If deployment fails:
1. **Check Railway logs** for errors
2. **Verify `OPENAI_API_KEY`** is set correctly
3. **Check requirements.txt** has all dependencies
4. **Ensure all files** are committed to Git

### Common issues:
- **Missing ffmpeg**: Railway includes it
- **Database connection**: Railway sets this automatically
- **Port conflicts**: Railway handles port mapping

---

## 🎉 You're Ready!

After following these steps, your application will be:
- ✅ **Live on the internet** with HTTPS
- ✅ **Using PostgreSQL** database
- ✅ **Automatically deployed** on Git push
- ✅ **Monitored** with health checks
- ✅ **Scalable** with Railway's infrastructure

Your app will be available at: `https://your-app-name.railway.app`
