from app.schemas.intelligence import DecisionSupport, DecisionEvidence
from app.services.intelligence.provider import TemplateExplainableProvider, IntelligenceContext

def test_decision_support_schema():
    ds = DecisionSupport(
        recommendation="Action A",
        reason="Because X",
        evidence=[DecisionEvidence(metric_name="Wind", value=10)],
        confidence_score=0.8,
        priority="high",
        risk_level="red",
        suggested_action="Do Y",
        alternative_recommendations=["Or Z"]
    )
    assert ds.recommendation == "Action A"
    assert len(ds.evidence) == 1
    assert ds.evidence[0].metric_name == "Wind"


def test_template_explainable_provider():
    provider = TemplateExplainableProvider()
    context = IntelligenceContext(
        target_name="Boat A",
        context_type="Boat Health",
        data={"engine_temp": 95, "risk_level": "red"},
        rules_triggered=["Engine Overheating"]
    )
    
    result = provider.explain(context)
    
    assert isinstance(result, DecisionSupport)
    assert result.risk_level == "red"
    assert result.priority == "high"
    assert "Engine Overheating" in result.reason
    
    # risk_level is removed from evidence
    assert len(result.evidence) == 1
    assert result.evidence[0].metric_name == "engine_temp"
    assert result.evidence[0].value == 95
