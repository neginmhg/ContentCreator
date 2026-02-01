"""Add source management tables to the database."""
from app.db import engine
from app.models import Base


def upgrade():
    """Create source management tables."""
    Base.metadata.create_all(bind=engine)
    print("Source management tables created successfully!")


if __name__ == "__main__":
    upgrade()
