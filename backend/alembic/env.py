"""
Alembic migration environment for OceanGuardian AI.

Usage:
  alembic upgrade head          # apply all pending migrations
  alembic downgrade -1          # roll back one step
  alembic revision --autogenerate -m "description"   # generate new migration

For an EXISTING deployment (created with create_all before Alembic was introduced):
  alembic stamp 001_baseline    # mark current DB as already at baseline
  alembic upgrade head          # apply Phase 2 column additions
"""
import os
import sys
from logging.config import fileConfig
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make the app package importable from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override DB URL from environment (takes precedence over alembic.ini)
db_url = os.getenv(
    "DATABASE_URL",
    config.get_main_option("sqlalchemy.url",
                           "postgresql+psycopg2://oceanguardian:oceanguardian@localhost:5432/oceanguardian"),
)
config.set_main_option("sqlalchemy.url", db_url)

# Import ALL model modules so their tables are registered on Base.metadata
from app.database import Base                                                 # noqa: E402
from app.models import user, family_link, location, sos                      # noqa: E402, F401
from app.models import weather_alert, market_price, govt_scheme               # noqa: E402, F401
from app.models import boat, trip, harbor                                     # noqa: E402, F401
from app.models import phase5                                                 # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
