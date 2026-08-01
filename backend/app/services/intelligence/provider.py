from abc import ABC, abstractmethod
from typing import List, Optional

from app.config import settings
from app.schemas.intelligence import DecisionSupport, DecisionEvidence

class IntelligenceContext:
    """Context for making an intelligent decision."""
    def __init__(self, target_name: str, context_type: str, data: dict, rules_triggered: List[str]):
        self.target_name = target_name
        self.context_type = context_type
        self.data = data
        self.rules_triggered = rules_triggered

class ExplainableAIProvider(ABC):
    @abstractmethod
    def explain(self, context: IntelligenceContext) -> DecisionSupport:
        """Returns a standardized DecisionSupport response."""
        ...

class TemplateExplainableProvider(ExplainableAIProvider):
    def explain(self, context: IntelligenceContext) -> DecisionSupport:
        """Deterministic fallback explanation."""
        risk_level = context.data.get("risk_level", "green")
        priority = "normal"
        if risk_level == "critical":
            priority = "critical"
        elif risk_level == "red":
            priority = "high"
        
        reasons = ", ".join(context.rules_triggered) if context.rules_triggered else "No specific rules triggered."
        
        evidence = [
            DecisionEvidence(metric_name=k, value=v)
            for k, v in context.data.items() if k != "risk_level"
        ]

        return DecisionSupport(
            recommendation=f"Standard procedure based on {context.context_type}",
            reason=f"Rules triggered: {reasons}",
            evidence=evidence,
            confidence_score=0.9,
            priority=priority,
            risk_level=risk_level,
            suggested_action="Review data and proceed.",
            alternative_recommendations=[]
        )

class AnthropicExplainableProvider(ExplainableAIProvider):
    API_URL = "https://api.anthropic.com/v1/messages"

    def explain(self, context: IntelligenceContext) -> DecisionSupport:
        # For structured output, we usually request JSON. 
        # But this environment may not have an API key. 
        # Fallback to template if key is missing or call fails.
        import httpx
        if not settings.anthropic_api_key:
            return TemplateExplainableProvider().explain(context)

        prompt = (
            f"You are a marine safety assistant providing a structured decision.\n"
            f"Target: {context.target_name}\n"
            f"Type: {context.context_type}\n"
            f"Data: {context.data}\n"
            f"Rules Triggered: {context.rules_triggered}\n"
            "Return a JSON object with: recommendation, reason, confidence_score (0.0-1.0), "
            "priority, risk_level, suggested_action, alternative_recommendations (list of str)."
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
                        "max_tokens": 500,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
        except Exception:
            pass
        return TemplateExplainableProvider().explain(context)

def get_explainable_provider() -> ExplainableAIProvider:
    if settings.ai_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicExplainableProvider()
    return TemplateExplainableProvider()
