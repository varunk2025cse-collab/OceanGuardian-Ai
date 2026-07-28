"""
Rescue AI Panel dispatcher (docs/AI_ARCHITECTURE.md Phase 17) — turns a
constrained set of operator questions into tool calls + a narrated answer.

This is deliberately NOT a free-text LLM chat: there are no LLM
credentials configured in this environment, and the governing brief is
explicit that the AI must never hallucinate operational facts. A fixed
intent set that maps 1:1 onto docs/AI_TOOLS.md functions is honest about
what's actually happening — every one of the example questions from the
spec is answerable through a real tool call, narrated via
app.services.ai.provider (template by default, real Claude if configured).
If ANTHROPIC_API_KEY is ever set, the exact same intents keep working
unchanged — only the narration quality of the AI_QUERY response changes.
"""
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.ai import tools as ai_tools


class AIQueryIntent:
    ACTIVE_SOS = "active_sos"
    HIGH_RISK_VESSELS = "high_risk_vessels"
    OFFLINE_VESSELS = "offline_vessels"
    UNACKNOWLEDGED_INCIDENTS = "unacknowledged_incidents"
    VESSEL_STATUS = "vessel_status"          # requires fisherman_id
    INCIDENT_SUMMARY = "incident_summary"    # requires incident_id
    NAVIGATION_GUIDANCE = "navigation_guidance"  # requires fisherman_id

    ALL = {
        ACTIVE_SOS, HIGH_RISK_VESSELS, OFFLINE_VESSELS, UNACKNOWLEDGED_INCIDENTS,
        VESSEL_STATUS, INCIDENT_SUMMARY, NAVIGATION_GUIDANCE,
    }

    # Mirrors the exact example questions from the governing brief, so the
    # Rescue AI panel UI can present them as one-tap buttons.
    LABELS = {
        ACTIVE_SOS: "Show active SOS incidents",
        HIGH_RISK_VESSELS: "Which vessels have the highest risk?",
        OFFLINE_VESSELS: "Show vessels with stale GPS",
        UNACKNOWLEDGED_INCIDENTS: "Which incidents have not been acknowledged?",
    }


def run_query(db: Session, user: User, intent: str, fisherman_id: int | None = None, incident_id: int | None = None) -> dict:
    if intent not in AIQueryIntent.ALL:
        return {"answer": "Unrecognized query.", "data": None}

    if intent == AIQueryIntent.ACTIVE_SOS:
        data = ai_tools.get_active_sos(db, user)
        answer = f"{data['count']} active SOS alert(s)." if data["count"] else "No active SOS alerts."
        return {"answer": answer, "data": data}

    if intent == AIQueryIntent.HIGH_RISK_VESSELS:
        data = ai_tools.get_high_risk_vessels(db, user)
        if not data["count"]:
            return {"answer": "No vessels currently at HIGH_RISK or CRITICAL.", "data": data}
        names = ", ".join(f"{v['fisherman_name']} ({v['safety_state']})" for v in data["vessels"])
        return {"answer": f"{data['count']} high-risk vessel(s): {names}", "data": data}

    if intent == AIQueryIntent.OFFLINE_VESSELS:
        data = ai_tools.get_offline_vessels(db, user)
        answer = f"{data['count']} vessel(s) with stale or unknown GPS." if data["count"] else "All active vessels have recent location data."
        return {"answer": answer, "data": data}

    if intent == AIQueryIntent.UNACKNOWLEDGED_INCIDENTS:
        data = ai_tools.get_active_incidents(db, user)
        unacked = [i for i in data["incidents"] if i["status"] == "received"]
        answer = f"{len(unacked)} incident(s) awaiting acknowledgement." if unacked else "No unacknowledged incidents."
        return {"answer": answer, "data": {"count": len(unacked), "incidents": unacked}}

    if intent == AIQueryIntent.VESSEL_STATUS:
        if fisherman_id is None:
            return {"answer": "A fisherman_id is required for this query.", "data": None}
        safety = ai_tools.get_safety_state(db, user, fisherman_id)
        location = ai_tools.get_latest_location(db, user, fisherman_id)
        from app.services.ai.provider import get_ai_provider, ExplanationRequest

        req = ExplanationRequest(
            fisherman_name=str(fisherman_id),
            safety_state=safety["safety_state"],
            safety_score=safety["safety_score"],
            communication_state=safety["communication_state"],
            freshness=safety["freshness"],
            trip_status=safety["trip_status"],
            reasons=safety["reasons"],
        )
        text, provider_name = get_ai_provider().explain(req)
        return {"answer": text, "data": {"safety": safety, "location": location}, "provider": provider_name}

    if intent == AIQueryIntent.NAVIGATION_GUIDANCE:
        if fisherman_id is None:
            return {"answer": "A fisherman_id is required for this query.", "data": None}
        data = ai_tools.get_navigation_guidance(db, user, fisherman_id)
        if not data.get("harbor_found"):
            return {"answer": data.get("detail", "No navigation guidance available."), "data": data}
        answer = (
            f"Nearest safe harbor: {data['harbor_name']}, {data['distance_km']}km "
            f"bearing {data['compass_direction']} ({data['bearing_degrees']}°), "
            f"about {data['estimated_minutes_to_reach']} min at typical boat speed."
        )
        return {"answer": answer, "data": data}

    if intent == AIQueryIntent.INCIDENT_SUMMARY:
        if incident_id is None:
            return {"answer": "An incident_id is required for this query.", "data": None}
        data = ai_tools.generate_incident_summary(db, user, incident_id)
        return {"answer": data["summary"], "data": data["report"], "provider": data["summary_provider"]}

    return {"answer": "Unrecognized query.", "data": None}
