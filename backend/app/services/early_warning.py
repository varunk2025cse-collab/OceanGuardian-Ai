"""
Early Warning (docs/SAFETY_STATE_ENGINE.md, V2 core build Phase 13).

Scope, stated honestly: this detects when a SINGLE current safety
evaluation already reflects a meaningful COMBINATION of independent risk
factors (weather + distance-from-harbor + degraded communication/
freshness + an open incident) — the "weather worsening AND boat offshore
AND comms degrading AND stale location" pattern from the governing brief,
evaluated at the moment of the check.

What this build does NOT do: track evaluation history over time to detect
trends ("wind speed increasing over the last hour", "location updates
becoming less frequent"). That requires persisting a time series of
evaluations, which is real, scoped, follow-on work — not something to fake
by inventing a trend from a single snapshot. Treat `is_early_warning` as
"multiple real risk factors are true right now", not "things are getting
worse."

Deduplication of repeated notifications for an unchanged warning is the
caller's responsibility (see app.services.notification_service's
related_event_id dedup) — this function is a pure, stateless classifier.
"""
from dataclasses import dataclass

from app.services.safety_engine import SafetyEvaluation


_CATEGORY_KEYWORDS = {
    "weather": ("weather warning", "weather advisory"),
    "distance": ("far from the nearest",),
    "communication": ("stale", "last known", "no location data"),
    "incident": ("incident is open",),
    "battery": ("battery is low",),
}


@dataclass
class EarlyWarning:
    is_early_warning: bool
    categories: list[str]
    what_changed: str
    why_it_matters: str
    recommended_action: str
    severity: str


def evaluate(evaluation: SafetyEvaluation) -> EarlyWarning:
    fired_categories = set()
    for reason in evaluation.reasons:
        lowered = reason.lower()
        for category, keywords in _CATEGORY_KEYWORDS.items():
            if any(k in lowered for k in keywords):
                fired_categories.add(category)

    # An active SOS or CRITICAL state is already the maximum-urgency path
    # (handled directly by SOS/incident flows) — early warning exists to
    # catch the "not critical YET, but multiple things are wrong at once"
    # window, so it only fires below that ceiling.
    is_warning = len(fired_categories) >= 2 and evaluation.safety_state not in ("CRITICAL",)

    if not is_warning:
        return EarlyWarning(
            is_early_warning=False,
            categories=sorted(fired_categories),
            what_changed="",
            why_it_matters="",
            recommended_action="",
            severity="NONE",
        )

    what_changed = "; ".join(evaluation.reasons)
    why_it_matters = (
        f"{len(fired_categories)} independent risk factors are present at the same time "
        f"({', '.join(sorted(fired_categories))}), which raises the safety state to {evaluation.safety_state}."
    )
    recommended_action = (
        "Consider returning toward a safe harbor and re-establishing communication if conditions permit."
        if evaluation.safety_state in ("HIGH_RISK",)
        else "Monitor conditions closely; no immediate action required yet."
    )
    return EarlyWarning(
        is_early_warning=True,
        categories=sorted(fired_categories),
        what_changed=what_changed,
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        severity=evaluation.safety_state,
    )
