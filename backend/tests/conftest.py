"""
Test configuration — ensures all test modules use the same SQLite database
and that the engine/session are set up exactly once per pytest session.
"""
import os
import sys
import pytest
from sqlalchemy.orm import Session

# Set DATABASE_URL BEFORE any app imports touch pydantic-settings
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_all.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ENVIRONMENT", "test")  # disables rate limiting — see app/core/rate_limit.py

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create tables once for the whole test session, drop at the end."""
    from app.database import Base, engine
    from app.main import app  # registers all models via router imports  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("test_all.db"):
        os.remove("test_all.db")


@pytest.fixture
def db(setup_test_db) -> Session:
    """Provide a DB session that rolls back after each test to prevent data leakage."""
    from app.database import engine, SessionLocal
    from sqlalchemy.orm import Session as SASession
    connection = engine.connect()
    transaction = connection.begin()
    session = SASession(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
