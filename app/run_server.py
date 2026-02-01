"""Start the FastAPI server."""
import os
import uvicorn

if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY environment variable is not set!")
    
    # Configure host and port for production
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    # Disable reload in production
    reload = os.getenv("ENVIRONMENT") != "production"
    
    print(f"Starting server on {host}:{port}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Database URL configured: {'Yes' if os.getenv('DATABASE_URL') else 'No (using SQLite)'}")
    
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
