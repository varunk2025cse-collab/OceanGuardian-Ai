"""
SQLAlchemy engine/session setup.

The MVP targets PostgreSQL in production (see DATABASE_URL in .env), but the
engine is created generically so the same code can point at SQLite for local
development or automated tests without touching application code.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import sessionmaker, declarative_base


def _sqlite_column_sql(column):
    """Return a SQLite-safe column definition without the table-qualified prefix."""
    compiled = column.compile(dialect=sqlite.dialect())
    return str(compiled).replace(f"{column.table.name}.", "")

from app.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    # SQLite needs this flag to allow use across the threadpool FastAPI uses.
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_compatible_schema(target_engine=None):
    """Add missing columns to existing SQLite tables so older DB files stay compatible."""
    if target_engine is None:
        target_engine = engine

    if not str(settings.database_url).startswith("sqlite"):
        return

    inspector = inspect(target_engine)
    for table in Base.metadata.tables.values():
        if not inspector.has_table(table.name):
            continue

        existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue

            column_sql = _sqlite_column_sql(column)
            with target_engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {column_sql}'))


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
