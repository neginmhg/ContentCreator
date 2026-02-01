"""Database session and engine."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import DB_PATH
from app.models import Base

DB_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _migrate_processing_step() -> None:
    """Add processing_step column to videos if it doesn't exist (for existing DBs)."""
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE videos ADD COLUMN processing_step VARCHAR(64)"))
            conn.commit()
        except Exception:
            conn.rollback()
            # Column already exists or other error; ignore
            pass


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_processing_step()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
