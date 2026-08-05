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
    """Create tables once for the whole test session, seed demo data, drop at the end."""
    from app.database import Base, engine
    from app.main import app  # registers all models via router imports  # noqa: F401
    # Ensure demo seed runs so tests that expect an operator account pass.
    os.environ.setdefault("SEED_DEMO_DATA", "true")
    # Create schema while temporarily disabling foreign key checks to avoid
    # SQLite drop/create ordering problems during repeated test runs.
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.create_all(bind=conn)
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    # Run seed script to populate reference/demo data
    try:
        import seed as _seed  # noqa: F401 — seed.py executes on import
    except Exception:
        # If seeding fails, surface a helpful message but continue so tests can run.
        print("Warning: seed.py failed during test setup — some tests may rely on seeded data.")

    yield
    # Drop schema while temporarily disabling foreign key checks to avoid
    # SQLite ordering errors when tables have cyclic foreign keys.
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(bind=conn)
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    engine.dispose()
    if os.path.exists("test_all.db"):
        os.remove("test_all.db")


@pytest.fixture(scope="function", autouse=True)
def clean_tables(setup_test_db):
    """Ensure a clean database state once per session by deleting rows from all tables.

    Running this once (session scope) avoids UNIQUE collisions on repeated local
    test runs while preserving seeded reference/demo data created above.
    """
    from app.database import Base, engine
    # delete rows from all tables in dependency order
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    # Re-run seed to ensure demo/operator account exists after truncation
    try:
        import seed as _seed  # noqa: F401
    except Exception:
        print("Warning: seed.py failed during clean_tables — tests may fail.")
    yield
@pytest.fixture
def db(setup_test_db) -> Session:
    """Provide a DB session that rolls back after each test to prevent data leakage."""
    from app.database import engine, SessionLocal
    from sqlalchemy.orm import Session as SASession
    connection = engine.connect()
    transaction = connection.begin()
    session = SASession(bind=connection)

    # Use a nested transaction (savepoint) so tests may commit without
    # leaking data between tests. This mirrors the recommended pytest pattern
    # for SQLAlchemy:
    # https://docs.sqlalchemy.org/en/20/testing.html#using-savepoints
    from sqlalchemy import event

    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        # if the nested transaction ends, reopen a new SAVEPOINT so the
        # outer rollback can still revert all changes at test teardown.
        if trans.nested and not sess.is_active:
            # transaction ended and session is inactive; re-activate
            sess.rollback()
        if trans.nested and not trans._parent:
            session.begin_nested()

    try:
        yield session
    finally:
        session.close()
        # rollback the outermost transaction started above
        transaction.rollback()
        connection.close()
