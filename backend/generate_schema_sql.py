"""
Generates schema.sql: the canonical PostgreSQL DDL, compiled directly from
the SQLAlchemy models so it can never drift out of sync with the actual
code. Re-run this after changing any model.

Usage: python generate_schema_sql.py > schema.sql
"""
from sqlalchemy import Enum as SAEnum
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql

from app.database import Base
# Import every model module so they register on Base.metadata
from app.models import user, family_link, location, sos, weather_alert, market_price, govt_scheme  # noqa: F401

print("-- OceanGuardian AI MVP -- PostgreSQL schema")
print("-- Auto-generated from SQLAlchemy models. Do not edit by hand;")
print("-- edit the models in app/models/ and re-run generate_schema_sql.py instead.")
print()
print("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
print()

# Enum columns compile inline as a bare type name (e.g. "userrole") in
# CREATE TABLE, but PostgreSQL requires the type to exist first via a
# separate CREATE TYPE ... AS ENUM statement. CreateTable alone won't emit
# that -- only Base.metadata.create_all() does it automatically via event
# hooks -- so for a hand-run schema.sql we have to emit it ourselves.
emitted_enums = set()
for table in Base.metadata.sorted_tables:
    for column in table.columns:
        if isinstance(column.type, SAEnum) and column.type.name not in emitted_enums:
            values = ", ".join(f"'{v}'" for v in column.type.enums)
            print(f"CREATE TYPE {column.type.name} AS ENUM ({values});")
            emitted_enums.add(column.type.name)
if emitted_enums:
    print()

for table in Base.metadata.sorted_tables:
    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect())).strip()
    print(ddl + ";")
    print()
    for index in table.indexes:
        idx_ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect())).strip()
        print(idx_ddl + ";")
    if table.indexes:
        print()
