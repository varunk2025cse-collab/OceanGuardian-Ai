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


class HumanizedExplanationRequest:
    """Structured input for humanized, emotionally-aware explanations.

    Extends ExplanationRequest with optional context fields that a
    production AI provider can use to adapt tone and language:
      - language: "en" | "ta" for Tamil-first responses
      - emotional_state: detected urgency/stress (calm, concerned, urgent, panic)
      - vessel_context: boat type/size for vessel-appropriate advice
      - previous_context: a short memory snippet of prior advice given
      - weather_exposure: most severe active weather factor
    """
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
        language: str = "en",
        emotional_state: str = "calm",
        vessel_context: str | None = None,
        previous_context: str | None = None,
        weather_exposure: str | None = None,
    ):
        self.fisherman_name = fisherman_name
        self.safety_state = safety_state
        self.safety_score = safety_score
        self.communication_state = communication_state
        self.freshness = freshness
        self.trip_status = trip_status
        self.reasons = reasons
        self.language = language
        self.emotional_state = emotional_state
        self.vessel_context = vessel_context
        self.previous_context = previous_context
        self.weather_exposure = weather_exposure


class AIProvider(ABC):
    @abstractmethod
    def explain(self, req: ExplanationRequest) -> tuple[str, str]:
        """Returns (explanation_text, provider_name)."""
        ...

    def explain_humanized(self, req: HumanizedExplanationRequest) -> tuple[str, str]:
        """Returns a humanized, emotionally-aware explanation.

        Default implementation falls back to the standard explain() so
        every provider gets humanized support for free."""
        standard = ExplanationRequest(
            fisherman_name=req.fisherman_name,
            safety_state=req.safety_state,
            safety_score=req.safety_score,
            communication_state=req.communication_state,
            freshness=req.freshness,
            trip_status=req.trip_status,
            reasons=req.reasons,
        )
        return self.explain(standard)


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

    def explain_humanized(self, req: HumanizedExplanationRequest) -> tuple[str, str]:
        """Humanized, emotionally-aware explanation with Tamil-first support.

        The tone follows an experienced coastal elder's mental model:
        observe → think → reason → explain → recommend → warn → reassure →
        confirm. It never sounds like a generic chatbot and never creates
        panic — it states facts calmly and gives a clear next step.
        """
        # ── Tamil-first response when requested ──────────────────────────
        if req.language == "ta":
            return self._explain_tamil(req), "template"

        # ── English humanized response ───────────────────────────────────
        state = req.safety_state
        score = req.safety_score

        # Emotional tone adaptation
        tone = {
            "panic": "I understand this is stressful. Let's stay calm and work through this step by step.",
            "urgent": "This needs your attention now. Let's act quickly but carefully.",
            "concerned": "I want you to be aware of this — it's important but manageable.",
            "frustrated": "I understand this is frustrating. Let's focus on what we can do right now.",
            "calm": "",
        }.get(req.emotional_state, "")

        # State-specific lead
        if state == "CRITICAL":
            lead = (
                f"{req.fisherman_name} is in a CRITICAL situation right now. "
                "This is not a drill — treat it as a life-safety event."
            )
        elif state == "HIGH_RISK":
            lead = (
                f"{req.fisherman_name} is at HIGH RISK. Conditions are deteriorating "
                "and this needs active monitoring."
            )
        elif state == "CAUTION":
            lead = (
                f"{req.fisherman_name} is in a CAUTION state. "
                "Conditions warrant a closer watch, but there's no immediate emergency."
            )
        elif state == "MONITOR":
            lead = (
                f"{req.fisherman_name} is in a MONITOR state. "
                "Keep an eye on things, but no immediate escalation is needed."
            )
        elif state == "UNKNOWN":
            lead = (
                f"We don't have enough data to assess {req.fisherman_name}'s safety right now. "
                "This is not the same as 'safe' — it means we need more information."
            )
        else:
            lead = (
                f"{req.fisherman_name} is in a SAFE state. "
                "No immediate concerns from the available data."
            )

        # Evidence-based reasoning
        reason_lines = []
        if req.reasons:
            reason_lines.append("What I'm seeing:")
            reason_lines.extend(f"  • {r}" for r in req.reasons[:5])

        # Recommendation
        rec = _RECOMMENDATIONS.get(state, _RECOMMENDATIONS["UNKNOWN"])

        # Weather exposure context
        weather_note = ""
        if req.weather_exposure:
            weather_note = f"\nWeather is a factor: {req.weather_exposure}."

        # Memory context
        memory_note = ""
        if req.previous_context:
            memory_note = f"\nRemembering our earlier conversation: {req.previous_context}"

        # Vessel context
        vessel_note = ""
        if req.vessel_context:
            vessel_note = f"\nConsidering the vessel: {req.vessel_context}."

        # Confidence framing
        confidence_note = (
            f"\nConfidence: {req.safety_score}/100 based on available data. "
            "This is decision support, not a guarantee — always verify with direct communication."
        )

        parts = [tone, lead]
        if reason_lines:
            parts.extend(reason_lines)
        parts.append(f"Recommendation: {rec}")
        if weather_note:
            parts.append(weather_note.strip())
        if vessel_note:
            parts.append(vessel_note.strip())
        if memory_note:
            parts.append(memory_note.strip())
        parts.append(confidence_note.strip())
        parts.append(
            "This is AI-assisted decision support based on available data, not a guarantee of safety "
            "and not a substitute for emergency services."
        )
        return "\n\n".join(p for p in parts if p), "template"

    def _explain_tamil(self, req: HumanizedExplanationRequest) -> str:
        """Tamil-first explanation using simple coastal Tamil vocabulary.

        Uses mixed Tamil + English (Tanglish) as is natural for coastal
        fishermen, with simple words suitable for elderly users. Never
        translates English mechanically — it speaks like a local elder.
        """
        state = req.safety_state
        score = req.safety_score

        # Tamil state labels
        state_ta = {
            "CRITICAL": "மிகவும் ஆபத்தான நிலை",
            "HIGH_RISK": "அதிக ஆபத்து",
            "CAUTION": "கவனம் தேவை",
            "MONITOR": "கண்காணிக்க வேண்டும்",
            "SAFE": "பாதுகாப்பான நிலை",
            "UNKNOWN": "தெளிவான தகவல் இல்லை",
        }.get(state, "தெரியாத நிலை")

        # Tamil emotional tone
        tone_ta = {
            "panic": "பயப்பட வேண்டாம். அமைதியாக இருங்கள். படிப்படியாக செய்வோம்.",
            "urgent": "இப்போதே கவனம் தேவை. வேகமாக ஆனால் கவனமாக செய்வோம்.",
            "concerned": "இது முக்கியம். ஆனால் நிர்வகிக்க முடியும்.",
            "frustrated": "புரிகிறது. ஆனால் இப்போது செய்ய வேண்டியதை செய்வோம்.",
            "calm": "",
        }.get(req.emotional_state, "")

        # Tamil lead
        if state == "CRITICAL":
            lead = (
                f"{req.fisherman_name} அவர்களின் நிலை மிகவும் ஆபத்தானது. "
                "இது உயிர் காக்கும் நேரம். உடனே உதவி அனுப்ப வேண்டும்."
            )
        elif state == "HIGH_RISK":
            lead = (
                f"{req.fisherman_name} அவர்களுக்கு அதிக ஆபத்து உள்ளது. "
                "நிலைமை மோசமாகி வருகிறது. கவனமாக கண்காணிக்க வேண்டும்."
            )
        elif state == "CAUTION":
            lead = (
                f"{req.fisherman_name} அவர்களுக்கு கவனம் தேவை. "
                "உடனடி ஆபத்து இல்லை, ஆனால் கண்காணிக்க வேண்டும்."
            )
        elif state == "MONITOR":
            lead = (
                f"{req.fisherman_name} அவர்களை கண்காணிக்க வேண்டும். "
                "இப்போது பெரிய பிரச்சனை இல்லை."
            )
        elif state == "UNKNOWN":
            lead = (
                f"{req.fisherman_name} அவர்களின் நிலை பற்றி போதுமான தகவல் இல்லை. "
                "இது 'பாதுகாப்பானது' என்று அர்த்தம் இல்லை — மேலும் தகவல் தேவை."
            )
        else:
            lead = (
                f"{req.fisherman_name} அவர்கள் பாதுகாப்பான நிலையில் உள்ளனர். "
                "இப்போது கவலைப்பட வேண்டியதில்லை."
            )

        # Tamil reasons
        reason_lines = []
        if req.reasons:
            reason_lines.append("நான் பார்ப்பது:")
            reason_lines.extend(f"  • {r}" for r in req.reasons[:5])

        # Tamil recommendation
        rec_ta = {
            "CRITICAL": "உடனே தொடர்பு கொண்டு உதவி அனுப்ப வேண்டும்.",
            "HIGH_RISK": "பாதுகாப்பான துறைமுகத்திற்கு திரும்புவது நல்லது. தொடர்பை மீண்டும் ஏற்படுத்த வேண்டும்.",
            "CAUTION": "நிலைமையை கவனமாக பார்த்து கொள்ளுங்கள். தொடர்பை வைத்திருங்கள்.",
            "MONITOR": "இப்போது எந்த நடவடிக்கையும் தேவையில்லை. வழக்கமான கண்காணிப்பு போதும்.",
            "SAFE": "இப்போது எந்த பிரச்சனையும் இல்லை.",
            "UNKNOWN": "மேலும் தகவல் தேவை. தொடர்பு கொள்ள முயற்சிக்கவும்.",
        }.get(state, "மேலும் தகவல் தேவை.")

        # Confidence
        confidence_ta = (
            f"\nநம்பிக்கை அளவு: {score}/100. இது தகவல்களின் அடிப்படையில் மட்டுமே. "
            "நேரடி தொடர்பு மூலம் எப்போதும் உறுதிப்படுத்தவும்."
        )

        parts = [tone_ta, lead]
        if reason_lines:
            parts.extend(reason_lines)
        parts.append(f"பரிந்துரை: {rec_ta}")
        parts.append(confidence_ta.strip())
        parts.append(
            "இது AI உதவி முடிவு ஆதரவு மட்டுமே. உண்மையான பாதுகாப்பு உறுதி அல்ல. "
            "அவசர சேவைகளை மாற்றாது."
        )
        return "\n\n".join(p for p in parts if p)


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
