import pytest

from app.notifications.preference_service import preference_store, PreferenceError


def test_set_and_get_preferences_basic():
    user_id = "user-1"
    channels = {"sms": True, "email": False, "push": True}
    prefs = preference_store.set_preferences(user_id, channels, quiet_start=None, quiet_end=None, emergency_override=True)
    assert prefs.user_id == user_id
    assert prefs.channels["sms"] is True
    assert prefs.emergency_override is True

    got = preference_store.get_preferences(user_id)
    assert got is not None
    assert got.user_id == user_id


def test_invalid_channel_raises():
    with pytest.raises(PreferenceError):
        preference_store.set_preferences("u2", {"fax": True})


def test_invalid_time_format_raises():
    with pytest.raises(PreferenceError):
        preference_store.set_preferences("u3", {"sms": True}, quiet_start="24:00")


def test_list_preferences_contains_set_item():
    user_id = "list-user"
    preference_store.set_preferences(user_id, {"sms": False, "email": True, "push": False})
    all_prefs = preference_store.list_preferences()
    assert user_id in all_prefs
