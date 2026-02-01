"""Migration script to add last_completed_step column to videos table."""
from app.db import SessionLocal, init_db
from app.models import Video
from sqlalchemy import text

def add_last_completed_step_column():
    """Add last_completed_step column to videos table if it doesn't exist."""
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(text("PRAGMA table_info(videos)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'last_completed_step' not in columns:
            # Add the column
            db.execute(text("ALTER TABLE videos ADD COLUMN last_completed_step VARCHAR(64)"))
            db.commit()
            print("Added last_completed_step column to videos table")
        else:
            print("last_completed_step column already exists")
            
    except Exception as e:
        print(f"Error adding column: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_last_completed_step_column()
