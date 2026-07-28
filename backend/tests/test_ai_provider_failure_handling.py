"""
AI provider verification (Final Release Engineering Phase D).

No ANTHROPIC_API_KEY exists in this environment, so a real end-to-end
Anthropic call cannot be honestly claimed as verified — see
docs/AI_ARCHITECTURE.md. What CAN be verified without real credentials is
the thing that actually matters for safety: AnthropicProvider must never
raise, and must always fall back to TemplateProvider, regardless of what
the HTTP layer does (auth failure, timeout, malformed response, rate
limit, outage). These tests mock httpx directly to prove that contract.

`test_anthropic_live_call_if_configured` is a REAL integration test that
only runs if ANTHROPIC_API_KEY is actually set — it is skipped (not
faked as passing) otherwise, so CI output honestly reflects whether the
real path has ever been exercised.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.ai.provider import AnthropicProvider, ExplanationRequest, TemplateProvider, get_ai_provider


def _sample_request() -> ExplanationRequest:
    return ExplanationRequest(
        fisherman_name="Test Fisherman",
        safety_state="HIGH_RISK",
        safety_score=72,
        communication_state="OFFLINE",
        freshness="STALE",
        trip_status="active",
        reasons=["Active weather advisory nearby.", "Location has not updated in a long time (STALE)."],
    )


def test_template_provider_is_default_without_credentials():
    provider = get_ai_provider()
    assert isinstance(provider, TemplateProvider)


def test_template_provider_never_calls_network():
    text, name = TemplateProvider().explain(_sample_request())
    assert name == "template"
    assert "HIGH_RISK" in text
    assert "72/100" in text
    assert "not a guarantee of safety" in text


@patch("httpx.Client")
def test_anthropic_provider_falls_back_on_auth_failure(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value.__enter__.return_value = mock_client

    text, provider_name = AnthropicProvider().explain(_sample_request())
    assert provider_name == "template"  # fell back, did not raise
    assert "HIGH_RISK" in text


@patch("httpx.Client")
def test_anthropic_provider_falls_back_on_timeout(mock_client_cls):
    import httpx

    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("timed out")
    mock_client_cls.return_value.__enter__.return_value = mock_client

    text, provider_name = AnthropicProvider().explain(_sample_request())
    assert provider_name == "template"


@patch("httpx.Client")
def test_anthropic_provider_falls_back_on_malformed_response(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"unexpected": "shape"}  # no "content" key
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value.__enter__.return_value = mock_client

    text, provider_name = AnthropicProvider().explain(_sample_request())
    assert provider_name == "template"


@patch("httpx.Client")
def test_anthropic_provider_falls_back_on_rate_limit(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("429 Too Many Requests")
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value.__enter__.return_value = mock_client

    text, provider_name = AnthropicProvider().explain(_sample_request())
    assert provider_name == "template"


@patch("httpx.Client")
def test_anthropic_provider_succeeds_with_well_formed_response(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"content": [{"type": "text", "text": "Conditions are elevated risk."}]}
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value.__enter__.return_value = mock_client

    text, provider_name = AnthropicProvider().explain(_sample_request())
    assert provider_name == "anthropic"
    assert text == "Conditions are elevated risk."


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — real Anthropic integration is UNVERIFIED in this environment (docs/AI_ARCHITECTURE.md)",
)
def test_anthropic_live_call_if_configured():
    """Only runs when real credentials are exported. If this ever shows as
    SKIPPED in a CI run, that means the Anthropic path is still unverified
    — do not report it as verified based on this file's other (mocked)
    tests passing."""
    text, provider_name = AnthropicProvider().explain(_sample_request())
    assert provider_name == "anthropic"
    assert len(text) > 0
