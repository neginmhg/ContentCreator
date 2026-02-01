"""Database session and engine."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import DB_URL, IS_PRODUCTION
from app.models import Base

# Configure engine based on database type
if IS_PRODUCTION:
    # Production database (PostgreSQL, etc.)
    engine = create_engine(DB_URL)
else:
    # Development database (SQLite)
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _migrate_processing_step() -> None:
    """Add processing_step column to videos if it doesn't exist (for existing DBs)."""
    with engine.connect() as conn:
        try:
            if IS_PRODUCTION:
                # PostgreSQL syntax
                conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS processing_step VARCHAR(64)"))
            else:
                # SQLite syntax
                conn.execute(text("ALTER TABLE videos ADD COLUMN processing_step VARCHAR(64)"))
            conn.commit()
        except Exception:
            conn.rollback()
            # Column already exists or other error; ignore
            pass


def _migrate_last_completed_step() -> None:
    """Add last_completed_step column if it doesn't exist."""
    with engine.connect() as conn:
        try:
            if IS_PRODUCTION:
                # PostgreSQL syntax
                conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS last_completed_step VARCHAR(64)"))
                conn.execute(text("ALTER TABLE blogs ADD COLUMN IF NOT EXISTS last_completed_step VARCHAR(64)"))
            else:
                # SQLite syntax
                conn.execute(text("ALTER TABLE videos ADD COLUMN last_completed_step VARCHAR(64)"))
                conn.execute(text("ALTER TABLE blogs ADD COLUMN last_completed_step VARCHAR(64)"))
            conn.commit()
        except Exception:
            conn.rollback()
            # Column already exists or other error; ignore
            pass


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_processing_step()
    _migrate_last_completed_step()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
