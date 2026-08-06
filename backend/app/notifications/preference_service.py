"""Notification preference service.

Provides a validated preferences layer with both an in-memory fallback store
and a SQLAlchemy-backed store for persisted preferences.

Features:
- Supported channels: sms, push, email
- Per-user preferences with enabled flag per channel
- Quiet hours: start/end in HH:MM 24-hour format
- Emergency override: boolean allowing critical alerts through
- Basic validation and logging
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any
import logging
import re

logger = logging.getLogger(__name__)

VALID_CHANNELS = {"sms", "email", "push"}
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass
class NotificationPreferences:
    user_id: str
    channels: Dict[str, bool]
    quiet_hours_start: Optional[str] = None  # HH:MM
    quiet_hours_end: Optional[str] = None
    emergency_override: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PreferenceError(Exception):
    pass


from sqlalchemy.orm import Session
from app.models.notification_models import NotificationPreference as DBNotificationPreference


class DBPreferenceStore:
    """DB-backed preference store using the NotificationPreference model."""

    def __init__(self):
        self._initialized = True

    def validate_time(self, t: Optional[str]) -> None:
        if t is None:
            return
        if not isinstance(t, str) or not _TIME_RE.match(t):
            raise PreferenceError(f"invalid_time_format: {t}")

    def validate_channels(self, channels: Dict[str, bool]) -> None:
        if not isinstance(channels, dict):
            raise PreferenceError("channels_must_be_object")
        for k in channels:
            if k not in VALID_CHANNELS:
                raise PreferenceError(f"invalid_channel: {k}")
            if not isinstance(channels[k], bool):
                raise PreferenceError("channel_flag_must_be_boolean")

    def set_preferences(self, db: Session, user_id: int, channels: Dict[str, bool], quiet_start: Optional[str] = None, quiet_end: Optional[str] = None, emergency_override: bool = False):
        self.validate_channels(channels)
        self.validate_time(quiet_start)
        self.validate_time(quiet_end)
        # Upsert
        pref = db.query(DBNotificationPreference).filter(DBNotificationPreference.user_id == user_id).first()
        channels_json = {c: bool(channels.get(c, False)) for c in VALID_CHANNELS}
        if pref is None:
            pref = DBNotificationPreference(
                user_id=user_id,
                preferred_language=None,
                preferred_channels=channels_json,
                quiet_hours={"start": quiet_start, "end": quiet_end} if (quiet_start or quiet_end) else None,
                emergency_override=bool(emergency_override),
            )
            db.add(pref)
        else:
            pref.preferred_channels = channels_json
            pref.quiet_hours = {"start": quiet_start, "end": quiet_end} if (quiet_start or quiet_end) else None
            pref.emergency_override = bool(emergency_override)
        db.flush()
        return pref

    def get_preferences(self, db: Session, user_id: int):
        return db.query(DBNotificationPreference).filter(DBNotificationPreference.user_id == user_id).first()

    def list_preferences(self, db: Session):
        return db.query(DBNotificationPreference).all()


class PreferenceStore:
    def __init__(self):
        # user_id -> NotificationPreferences
        self._store: Dict[str, NotificationPreferences] = {}

    def validate_time(self, t: Optional[str]) -> None:
        if t is None:
            return
        if not isinstance(t, str) or not _TIME_RE.match(t):
            raise PreferenceError(f"invalid_time_format: {t}")

    def validate_channels(self, channels: Dict[str, bool]) -> None:
        if not isinstance(channels, dict):
            raise PreferenceError("channels_must_be_object")
        for k in channels:
            if k not in VALID_CHANNELS:
                raise PreferenceError(f"invalid_channel: {k}")
            if not isinstance(channels[k], bool):
                raise PreferenceError("channel_flag_must_be_boolean")

    def set_preferences(self, user_id: str, channels: Dict[str, bool], quiet_start: Optional[str] = None, quiet_end: Optional[str] = None, emergency_override: bool = False) -> NotificationPreferences:
        self.validate_channels(channels)
        self.validate_time(quiet_start)
        self.validate_time(quiet_end)
        prefs = NotificationPreferences(
            user_id=user_id,
            channels={c: bool(channels.get(c, False)) for c in VALID_CHANNELS},
            quiet_hours_start=quiet_start,
            quiet_hours_end=quiet_end,
            emergency_override=bool(emergency_override),
        )
        self._store[user_id] = prefs
        logger.info("Set notification preferences for user %s", user_id)
        return prefs

    def get_preferences(self, user_id: str) -> Optional[NotificationPreferences]:
        return self._store.get(user_id)

    def list_preferences(self) -> Dict[str, NotificationPreferences]:
        return dict(self._store)


# A module-level store instance for easy use
preference_store = PreferenceStore()

db_preference_store = DBPreferenceStore()
