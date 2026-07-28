"""
AI Explainability Layer — LLM provider abstraction (docs/AI_ARCHITECTURE.md,
V2 core build Phase 12).

Hard rule from the governing brief: AI is never the source of truth for
safety-critical numbers. app.services.safety_engine.SafetyEngine computes
the deterministic score/state/reasons; everything here does is turn that
already-computed structured data into a natural-language explanation. If
this layer is completely unavailable, the safety engine's structured
output (score, state, reasons list) is still fully usable on its own —
callers must never assume prose is required to act safely.

Two providers:
  TemplateProvider   — deterministic, zero external dependency, always
                        available. This is the default and the only
                        provider actually exercised by tests in this
                        environment (no LLM credentials are configured
                        here).
  AnthropicProvider   — real Claude call via the Messages API, used only
                        when ANTHROPIC_API_KEY is set. Implemented against
                        the documented HTTP contract using httpx (already a
                        project dependency) rather than adding an unpinned
                        SDK dependency for a single call site. NOT verified
                        end-to-end in this environment (no credentials
                        available) — see docs/AI_ARCHITECTURE.md for the
                        explicit IMPLEMENTED-BUT-UNVERIFIED status.
"""
from abc import ABC, abstractmethod

from app.config import settings


class ExplanationRequest:
    """Structured input — exactly what the safety engine computed, nothing
    more. The provider must not be given raw DB access."""

    def __init__(
        self,
        *,
        fisherman_name: str,
        safety_state: str,
        safety_score: int,
        communication_state: str,
        freshness: str,
        trip_status: str | None,
        reasons: list[str],
    ):
        self.fisherman_name = fisherman_name
        self.safety_state = safety_state
        self.safety_score = safety_score
        self.communication_state = communication_state
        self.freshness = freshness
        self.trip_status = trip_status
        self.reasons = reasons


class AIProvider(ABC):
    @abstractmethod
    def explain(self, req: ExplanationRequest) -> tuple[str, str]:
        """Returns (explanation_text, provider_name)."""
        ...


_RECOMMENDATIONS = {
    "CRITICAL": "This requires immediate attention — verify communication and consider initiating emergency procedures if assistance is required.",
    "HIGH_RISK": "Consider returning toward a safe harbor if conditions permit, and re-establish communication as soon as possible.",
    "CAUTION": "Monitor conditions closely and keep communication active.",
    "MONITOR": "No action required yet — continue routine monitoring.",
    "SAFE": "No current safety condition requiring escalation was detected from available data.",
    "UNKNOWN": "Insufficient data to assess safety state.",
}


class TemplateProvider(AIProvider):
    """Deterministic explanation text — no LLM call, always available.
    Formatted to match the governing brief's own worked example:
    'Risk Score: 78 HIGH ... Reasons: ... Recommendation: ...'"""

    def explain(self, req: ExplanationRequest) -> tuple[str, str]:
        lines = [
            f"Safety State: {req.safety_state} ({req.safety_score}/100)",
            f"Communication: {req.communication_state} · Location: {req.freshness.replace('_', ' ')}",
        ]
        if req.reasons:
            lines.append("Why:")
            lines.extend(f"  - {r}" for r in req.reasons)
        recommendation = _RECOMMENDATIONS.get(req.safety_state, _RECOMMENDATIONS["UNKNOWN"])
        lines.append(f"Recommendation: {recommendation}")
        lines.append(
            "This is AI-assisted decision support based on available data, not a guarantee of safety "
            "and not a substitute for emergency services."
        )
        return "\n".join(lines), "template"


class AnthropicProvider(AIProvider):
    """Real LLM call to Claude — only constructed when settings.anthropic_api_key
    is set (see get_ai_provider). Falls back to TemplateProvider on any
    failure so a flaky/unreachable LLM never blocks an explanation."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def explain(self, req: ExplanationRequest) -> tuple[str, str]:
        import httpx

        prompt = (
            f"You are a marine safety assistant. A fisherman's safety state was computed "
            f"deterministically as {req.safety_state} (score {req.safety_score}/100). "
            f"Communication state: {req.communication_state}. Location freshness: {req.freshness}. "
            f"Trip status: {req.trip_status}. Contributing factors: {'; '.join(req.reasons)}. "
            f"Write a short (3-5 sentence) plain-language explanation of what this means and a "
            f"cautious recommendation. Never claim certainty about the fisherman's safety, and "
            f"never suggest AI replaces emergency services or professional rescue authority."
        )
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    self.API_URL,
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": settings.anthropic_model,
                        "max_tokens": 300,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = "".join(block.get("text", "") for block in data.get("content", []))
                if text.strip():
                    return text.strip(), "anthropic"
        except Exception:
            pass  # fall through to template — AI unavailability must never break the caller
        return TemplateProvider().explain(req)


def get_ai_provider() -> AIProvider:
    if settings.ai_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicProvider()
    return TemplateProvider()
