"""
Harbor model — re-export shim for v1 backward compatibility.

The canonical Harbor ORM class now lives in app.models.phase5.
This module re-exports it so that existing imports like
  `from app.models.harbor import Harbor`
continue to work without creating a duplicate table definition.
"""
from app.models.phase5 import Harbor  # noqa: F401 — re-export
