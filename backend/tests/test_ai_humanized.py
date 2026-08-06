"""
Tests for the humanized, explainable AI layer.

Covers:
  - HumanizedExplanationRequest construction
  - TemplateProvider.explain_humanized (English + Tamil)
  - Emotional tone adaptation
  - Confidence scoring in the dispatcher
  - Explainability envelope in dispatcher responses
  - Backward compatibility of run_query_v0
"""
import pytest

from app.services.ai.provider import (
    TemplateProvider,
    HumanizedExplanationRequest,
    ExplanationRequest,
)
from app.services.ai.dispatcher import (
    run_query,
    run_query_v0,
    AIQueryIntent,
    _confidence_for,
    _explain_structured,
)


class TestHumanizedExplanationRequest:
    def test_constructs_with_defaults(self):
        req = HumanizedExplanationRequest(
            fisherman_name="Murugan",
            safety_state="HIGH_RISK",
            safety_score=65,
            communication_state="OFFLINE",
            freshness="STALE",
            trip_status="active",
            reasons=["Location is stale."],
        )
        assert req.language == "en"
        assert req.emotional_state == "calm"
        assert req.vessel_context is None
        assert req.previous_context is None
        assert req.weather_exposure is None

    def test_constructs_with_all_fields(self):
        req = HumanizedExplanationRequest(
            fisherman_name="Kumar",
            safety_state="CRITICAL",
            safety_score=95,
            communication_state="OFFLINE",
            freshness="STALE",
            trip_status="active",
            reasons=["SOS active."],
            language="ta",
            emotional_state="panic",
            vessel_context="small fiber boat",
            previous_context="advised to return early",
            weather_exposure="high waves",
        )
        assert req.language == "ta"
        assert req.emotional_state == "panic"
        assert req.vessel_context == "small fiber boat"


class TestTemplateProviderHumanized:
    def setup_method(self):
        self.provider = TemplateProvider()

    def _req(self, **kwargs):
        defaults = dict(
            fisherman_name="Murugan",
            safety_state="HIGH_RISK",
            safety_score=65,
            communication_state="OFFLINE",
            freshness="STALE",
            trip_status="active",
            reasons=["Location has not updated in a long time."],
        )
        defaults.update(kwargs)
        return HumanizedExplanationRequest(**defaults)

    def test_english_humanized_contains_state_and_recommendation(self):
        text, provider = self.provider.explain_humanized(self._req())
        assert provider == "template"
        assert "HIGH RISK" in text
        assert "Recommendation" in text
        assert "Murugan" in text

    def test_english_humanized_contains_evidence(self):
        text, _ = self.provider.explain_humanized(self._req())
        assert "What I'm seeing" in text
        assert "Location has not updated" in text

    def test_english_humanized_contains_confidence_disclaimer(self):
        text, _ = self.provider.explain_humanized(self._req())
        assert "Confidence" in text
        assert "not a guarantee" in text

    def test_english_humanized_contains_emotional_tone_for_panic(self):
        text, _ = self.provider.explain_humanized(self._req(emotional_state="panic"))
        assert "stay calm" in text.lower() or "calm" in text.lower()

    def test_english_humanized_contains_weather_context(self):
        text, _ = self.provider.explain_humanized(self._req(weather_exposure="high waves"))
        assert "high waves" in text

    def test_english_humanized_contains_memory_context(self):
        text, _ = self.provider.explain_humanized(self._req(previous_context="advised to return early"))
        assert "advised to return early" in text

    def test_tamil_humanized_contains_tamil_text(self):
        text, provider = self.provider.explain_humanized(self._req(language="ta"))
        assert provider == "template"
        # Tamil script should be present
        assert any('\u0b80' <= c <= '\u0bff' for c in text)

    def test_tamil_humanized_contains_tamil_recommendation(self):
        text, _ = self.provider.explain_humanized(self._req(language="ta"))
        assert "பரிந்துரை" in text  # "Recommendation" in Tamil

    def test_tamil_humanized_contains_confidence(self):
        text, _ = self.provider.explain_humanized(self._req(language="ta"))
        assert "நம்பிக்கை" in text  # "Confidence" in Tamil

    def test_tamil_humanized_contains_safety_disclaimer(self):
        text, _ = self.provider.explain_humanized(self._req(language="ta"))
        assert "AI" in text  # Tanglish style keeps English terms

    def test_critical_state_uses_life_safety_language(self):
        text, _ = self.provider.explain_humanized(self._req(safety_state="CRITICAL", safety_score=95))
        assert "CRITICAL" in text
        assert "life-safety" in text.lower() or "life safety" in text.lower()

    def test_unknown_state_explains_not_safe(self):
        text, _ = self.provider.explain_humanized(self._req(safety_state="UNKNOWN", safety_score=0))
        assert "not the same as 'safe'" in text

    def test_standard_explain_still_works(self):
        req = ExplanationRequest(
            fisherman_name="Murugan",
            safety_state="SAFE",
            safety_score=10,
            communication_state="ONLINE",
            freshness="LIVE",
            trip_status="active",
            reasons=["All good."],
        )
        text, provider = self.provider.explain(req)
        assert provider == "template"
        assert "SAFE" in text


class TestDispatcherConfidence:
    def test_confidence_for_empty_data(self):
        assert _confidence_for(None) == 0.3
        assert _confidence_for({}) == 0.3

    def test_confidence_for_zero_count(self):
        assert _confidence_for({"count": 0}) == 0.95

    def test_confidence_for_positive_count(self):
        conf = _confidence_for({"count": 5})
        assert 0.6 <= conf <= 0.85

    def test_confidence_for_non_count_data(self):
        conf = _confidence_for({"found": True, "latitude": 10.5, "longitude": 80.2})
        assert 0.5 <= conf <= 0.85


class TestDispatcherExplainability:
    def test_explain_structured_contains_all_fields(self):
        data = {"count": 2, "alerts": [{"id": 1}, {"id": 2}]}
        from app.models.user import User, UserRole
        user = User(id=1, role=UserRole.operator, phone_number="+911", full_name="Op")
        result = _explain_structured(AIQueryIntent.ACTIVE_SOS, data, user)
        explanation = result["explanation"]
        assert "what_happened" in explanation
        assert "why_it_matters" in explanation
        assert "evidence_used" in explanation
        assert "confidence" in explanation
        assert "confidence_label" in explanation
        assert "possible_uncertainty" in explanation
        assert "immediate_action" in explanation

    def test_explain_structured_evidence_list(self):
        data = {"count": 1, "vessels": [{"fisherman_id": 1}]}
        from app.models.user import User, UserRole
        user = User(id=1, role=UserRole.operator, phone_number="+911", full_name="Op")
        result = _explain_structured(AIQueryIntent.HIGH_RISK_VESSELS, data, user)
        evidence = result["explanation"]["evidence_used"]
        assert any(e["metric"] == "result_count" for e in evidence)
        assert any(e["metric"] == "resource_count" for e in evidence)


class TestDispatcherBackwardCompat:
    @pytest.fixture(autouse=True)
    def _operator(self, db):
        """Create a real operator user for dispatcher tests."""
        from app.models.user import User, UserRole
        op = User(
            phone_number="+919999000111",
            password_hash="test-hash",
            full_name="Test Operator",
            role=UserRole.operator,
        )
        db.add(op)
        db.commit()
        db.refresh(op)
        self.operator = op
        yield op

    def test_run_query_v0_returns_legacy_shape(self, db):
        """run_query_v0 must return only {answer, data} for backward compat."""
        result = run_query_v0(db, self.operator, AIQueryIntent.ACTIVE_SOS)
        assert "answer" in result
        assert "data" in result
        assert "confidence" not in result
        assert "explanation" not in result

    def test_run_query_returns_enhanced_shape(self, db):
        """run_query must return answer, data, confidence, explanation."""
        result = run_query(db, self.operator, AIQueryIntent.ACTIVE_SOS)
        assert "answer" in result
        assert "data" in result
        assert "confidence" in result
        assert "explanation" in result

    def test_run_query_unrecognized_intent(self, db):
        result = run_query(db, self.operator, "not_a_real_intent")
        assert result["confidence"] == 0.0
        assert result["explanation"] is None
