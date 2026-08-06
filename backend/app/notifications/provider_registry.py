"""Notification provider registry and basic providers.

Provides:
- NotificationProvider (base abstract class)
- SimulationProvider (for local/dev/testing)
- TwilioProvider (minimal scaffold)
- register_provider / get_provider helpers
- provider_health function

This module is intentionally lightweight so production hardening (retries,
rate limiting, async adapters, batching, metrics) can be added iteratively.
"""
from __future__ import annotations

import os
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    """Abstract base for notification providers."""

    name: str

    @abstractmethod
    def send(self, to: str, template: str, context: dict) -> dict:
        """Send a notification. Returns provider-specific result dict."""

    @abstractmethod
    def health_check(self) -> dict:
        """Return health/status information for this provider."""


_PROVIDERS: Dict[str, NotificationProvider] = {}


def register_provider(provider: NotificationProvider) -> None:
    if provider.name in _PROVIDERS:
        logger.warning("Overwriting existing provider registration: %s", provider.name)
    _PROVIDERS[provider.name] = provider
    logger.info("Registered notification provider: %s", provider.name)


def get_provider(name: str) -> Optional[NotificationProvider]:
    return _PROVIDERS.get(name)


def list_providers() -> list[str]:
    return list(_PROVIDERS.keys())


def provider_health() -> dict:
    """Run health_check() for every registered provider and return aggregated status."""
    out = {}
    for name, prov in _PROVIDERS.items():
        try:
            out[name] = prov.health_check()
        except Exception as e:
            logger.exception("Provider %s health check failed", name)
            out[name] = {"ok": False, "error": str(e)}
    return out


# ----------------------------------------------------------------------------
# Simulation provider — useful for local dev and tests
# ----------------------------------------------------------------------------
class SimulationProvider(NotificationProvider):
    name = "simulation"

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def send(self, to: str, template: str, context: dict) -> dict:
        logger.info("[SimulationProvider] send -> to=%s template=%s context=%s", to, template, context)
        # Return a deterministic payload that tests and local dev can assert against
        return {"ok": True, "id": f"sim-{hash((to, template)) & 0xffffffff}", "provider": self.name}

    def health_check(self) -> dict:
        return {"ok": self.enabled, "type": "simulation"}


# ----------------------------------------------------------------------------
# Twilio provider scaffold
# ----------------------------------------------------------------------------
class TwilioProvider(NotificationProvider):
    name = "twilio"

    def __init__(self, account_sid: Optional[str] = None, auth_token: Optional[str] = None, from_number: Optional[str] = None):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_FROM_NUMBER")

    def send(self, to: str, template: str, context: dict) -> dict:
        """Send an SMS via Twilio REST API (blocking). This is a minimal synchronous
        implementation. Production should use async workers, retries, idempotency keys
        and robust error handling.
        """
        if not (self.account_sid and self.auth_token and self.from_number):
            raise RuntimeError("Twilio provider not configured")
        # Lazy import to avoid adding runtime dependency for environments that don't use Twilio
        try:
            import requests
        except Exception:
            raise RuntimeError("requests library is required for TwilioProvider")

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        body = {
            "From": self.from_number,
            "To": to,
            "Body": template.format(**context),
        }
        resp = requests.post(url, data=body, auth=(self.account_sid, self.auth_token), timeout=10)
        if resp.status_code >= 400:
            logger.error("Twilio send failed: %s %s", resp.status_code, resp.text)
            return {"ok": False, "status_code": resp.status_code, "error": resp.text}
        return {"ok": True, "provider_id": resp.json().get("sid")}

    def health_check(self) -> dict:
        # A lightweight check: validate credentials appear present
        ok = bool(self.account_sid and self.auth_token and self.from_number)
        return {"ok": ok, "configured": ok}


# Register default providers for immediate use in local/dev
try:
    register_provider(SimulationProvider(enabled=True))
except Exception:
    logger.exception("Failed to register simulation provider")

try:
    register_provider(TwilioProvider())
except Exception:
    # Twilio registration may be noisy if env vars not present — that's fine
    logger.debug("Twilio provider not configured; skipped registration")
