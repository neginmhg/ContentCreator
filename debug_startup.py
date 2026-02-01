#!/usr/bin/env python3
"""Debug startup script to identify deployment issues."""

import os
import sys
from pathlib import Path

print("=== Content Generator Debug Startup ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {Path.cwd()}")

# Check environment variables
print("\n=== Environment Variables ===")
print(f"OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")
print(f"DATABASE_URL: {'SET' if os.getenv('DATABASE_URL') else 'NOT SET (using SQLite)'}")
print(f"ENVIRONMENT: {os.getenv('ENVIRONMENT', 'development')}")
print(f"HOST: {os.getenv('HOST', '0.0.0.0')}")
print(f"PORT: {os.getenv('PORT', '8000')}")

# Try importing app modules
print("\n=== Import Tests ===")
try:
    from app.config import DB_URL, IS_PRODUCTION
    print("✅ app.config imported successfully")
    print(f"   DB_URL: {DB_URL[:20]}..." if len(DB_URL) > 20 else f"   DB_URL: {DB_URL}")
    print(f"   IS_PRODUCTION: {IS_PRODUCTION}")
except Exception as e:
    print(f"❌ app.config import failed: {e}")

try:
    from app.db import init_db
    print("✅ app.db imported successfully")
except Exception as e:
    print(f"❌ app.db import failed: {e}")

try:
    from app.main import app
    print("✅ app.main imported successfully")
except Exception as e:
    print(f"❌ app.main import failed: {e}")

# Try database initialization
print("\n=== Database Test ===")
try:
    from app.db import init_db
    init_db()
    print("✅ Database initialization successful")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")

print("\n=== Ready to Start Server ===")
print("If all tests pass, the app should start successfully.")
