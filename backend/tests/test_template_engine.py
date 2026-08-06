import pytest

from app.notifications.template_engine import engine, TemplateError, extract_placeholders


def test_register_and_preview_simple_template():
    engine.register_template("welcome", subject="Welcome {name}", body="Hello {{ name }}!")
    preview = engine.preview("welcome", {"name": "Alice"})
    assert preview["subject"] == "Welcome Alice"
    assert "Hello Alice" in preview["body"]


def test_validate_context_missing_keys():
    engine.register_template("alert", subject="ALERT: {{ level }}", body="Dear {{ name }}, event {{ event_id }}")
    res = engine.validate_context("alert", {"name": "Bob"})
    # expected placeholders include level, name, event_id
    assert "level" in res["expected"]
    assert "event_id" in res["expected"]
    assert "level" in res["missing"]
    assert "event_id" in res["missing"]


def test_extract_placeholders_handles_syntax_error():
    with pytest.raises(TemplateError):
        # malformed template
        extract_placeholders("{{ foo + }}")


def test_preview_raises_on_missing_template():
    with pytest.raises(TemplateError):
        engine.preview("nonexistent", {})
