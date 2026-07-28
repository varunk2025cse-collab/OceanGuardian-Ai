import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_schema_compat.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from app.database import ensure_compatible_schema


def test_ensure_compatible_schema_adds_missing_trip_id_column(tmp_path):
    db_path = tmp_path / "compat.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sos_alerts (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL)"))

    ensure_compatible_schema(engine)

    inspector = inspect(engine)
    columns = [column["name"] for column in inspector.get_columns("sos_alerts")]

    assert "trip_id" in columns
