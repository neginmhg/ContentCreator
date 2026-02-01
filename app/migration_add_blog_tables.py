"""Add blog-related tables to the database."""
from app.db import engine
from app.models import Base


def upgrade():
    """Create blog tables."""
    Base.metadata.create_all(bind=engine)
    print("Blog tables created successfully!")


if __name__ == "__main__":
    upgrade()
