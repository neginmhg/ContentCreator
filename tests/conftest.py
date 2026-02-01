"""Pytest fixtures."""
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


@pytest.fixture
def db_engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    yield create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def db_session(db_engine):
    Base.metadata.create_all(bind=db_engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
