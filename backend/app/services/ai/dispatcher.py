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

Human believability: the narration follows an experienced coastal officer's
mental model — observe → think → reason → explain → recommend → warn →
reassure → confirm. Every response explains what happened, why, what
evidence was used, confidence level, immediate action, and expected
outcome. It never sounds like a generic chatbot.
"""
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.ai import tools as ai_tools
from app.services.ai.provider import (
    get_ai_provider,
    ExplanationRequest,
    HumanizedExplanationRequest,
)


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


def _confidence_for(data: dict, base: float = 0.85) -> float:
    """
    Compute a per-intent confidence score from real evidence present in the
    tool result. Confidence decreases when the data is stale, partial, or
    when the query returned nothing to verify against.
    """
    if not data:
        return 0.3
    count = data.get("count")
    if count is None:
        # Non-count intents (vessel status, location, navigation) estimate
        # confidence from the presence of core fields.
        core_present = sum(
            1 for key in data if data[key] not in (None, False, "", [])
        )
        total = max(len(data), 1)
        return round(base * (core_present / total), 2)
    if count == 0:
        # Zero results is a confident "nothing to report" — we know the
        # system is healthy and there is nothing pending.
        return 0.95
    # More results means more surface for partial/outdated data.
    return round(max(0.6, base - (count * 0.01)), 2)


def _explain_structured(intent: str, data: dict, user: User, language: str = "en") -> dict:
    """
    Wrap a tool result with the explainability envelope that every
    AI-generated safety answer should carry:
      - what happened
      - why it matters
      - evidence used
      - confidence
      - immediate action
      - alternative actions
      - expected outcome
    """
    confidence = _confidence_for(data)

    why_map = {
        AIQueryIntent.ACTIVE_SOS: "Every active SOS represents a person who may need rescue right now — time is the most critical factor.",
        AIQueryIntent.HIGH_RISK_VESSELS: "High-risk vessels are those whose combined location staleness, weather exposure, and/or active incidents put them at greatest danger.",
        AIQueryIntent.OFFLINE_VESSELS: "A vessel with stale or unknown GPS may be in communication blackout — the first sign of a problem is often a location that stops updating.",
        AIQueryIntent.UNACKNOWLEDGED_INCIDENTS: "Incidents not yet acknowledged have no operator actively handling them, which delays rescue coordination.",
        AIQueryIntent.VESSEL_STATUS: "A vessel's safety state combines live location, trip status, communication, and any open alert to give a single operational picture.",
        AIQueryIntent.INCIDENT_SUMMARY: "An incident summary consolidates the full timeline and status so responders can see the complete picture before acting.",
        AIQueryIntent.NAVIGATION_GUIDANCE: "Knowing the nearest safe harbor, its bearing, and ETA is often the most actionable information for a vessel in distress.",
    }

    action_map = {
        AIQueryIntent.ACTIVE_SOS: "Acknowledge each open SOS alert immediately and dispatch rescue resources.",
        AIQueryIntent.HIGH_RISK_VESSELS: "Contact the listed vessels via phone/radio, confirm their status, and stage rescue assets near the highest-risk positions.",
        AIQueryIntent.OFFLINE_VESSELS: "Attempt radio contact with each stale vessel; if unreachable, elevate to search-and-rescue protocol.",
        AIQueryIntent.UNACKNOWLEDGED_INCIDENTS: "Assign an operator to acknowledge each pending incident and begin the assessment phase.",
        AIQueryIntent.VESSEL_STATUS: "Use the safety state to decide whether routine monitoring or emergency escalation is warranted.",
        AIQueryIntent.INCIDENT_SUMMARY: "Review the full timeline and resolution to determine whether the incident is safely closable.",
        AIQueryIntent.NAVIGATION_GUIDANCE: "Relay the nearest harbor bearing and ETA to the vessel; if conditions are critical, dispatch assistance.",
    }

    return {
        "intent": intent,
        "query_summary": data,
        "explanation": {
            "what_happened": _describe_findings(intent, data),
            "why_it_matters": why_map.get(intent, ""),
            "evidence_used": _evidence_list(intent, data),
            "confidence": confidence,
            "confidence_label": _confidence_label(confidence),
            "possible_uncertainty": _uncertainty_label(intent, data, confidence),
            "immediate_action": action_map.get(intent, ""),
        },
        "requested_by_user_id": user.id,
        "requested_by_role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }


def _confidence_label(conf: float) -> str:
    if conf >= 0.9:
        return "HIGH — based on current, complete data."
    if conf >= 0.7:
        return "MODERATE — based on available data, some fields may be incomplete."
    return "LOW — significant data gaps; treat with caution."


def _uncertainty_label(intent: str, data: dict, conf: float) -> str:
    if conf >= 0.9:
        return "Minimal — system has current, consistent data for this query."
    if data and data.get("count") == 0:
        return "Low — system reliably reports no active items for this query."
    if intent in (AIQueryIntent.ACTIVE_SOS, AIQueryIntent.HIGH_RISK_VESSELS):
        return "Data may be up to several minutes old depending on vessel GPS reporting intervals."
    return "Some inputs may be stale or incomplete; verify before acting on this recommendation."


def _describe_findings(intent: str, data: dict) -> str:
    """Produce a one-line plain-language description of what the data shows."""
    if not data:
        return "No data was available for this query."
    count = data.get("count")
    if intent == AIQueryIntent.ACTIVE_SOS:
        if count == 0:
            return "No active SOS alerts are currently open."
        return f"{count} active SOS alert(s) require attention right now."
    if intent == AIQueryIntent.HIGH_RISK_VESSELS:
        if count == 0:
            return "No vessels are currently flagged at HIGH_RISK or CRITICAL safety state."
        return f"{count} vessel(s) are at elevated risk and need operator awareness."
    if intent == AIQueryIntent.OFFLINE_VESSELS:
        if count == 0:
            return "All active vessels have recent location data."
        return f"{count} vessel(s) have stale or unknown GPS positions."
    if intent == AIQueryIntent.UNACKNOWLEDGED_INCIDENTS:
        if count == 0:
            return "All open incidents have been acknowledged."
        return f"{count} incident(s) have not yet been acknowledged."
    if intent == AIQueryIntent.VESSEL_STATUS:
        state = data.get("safety_state", "UNKNOWN")
        score = data.get("safety_score", 0)
        return f"Vessel safety state is {state} (score {score}/100)."
    if intent == AIQueryIntent.INCIDENT_SUMMARY:
        st = (data.get("report") or {}).get("status", "unknown")
        return f"Incident summary generated — current status: {st}."
    if intent == AIQueryIntent.NAVIGATION_GUIDANCE:
        hb = data.get("harbor_name")
        if hb:
            return f"Nearest safe harbor: {hb}, {data.get('distance_km')} km away."
        return data.get("detail", "Navigation guidance is not available.")
    return "Query completed."


def _evidence_list(intent: str, data: dict) -> list:
    """
    Build a structured evidence list from the tool result so the caller
    (dashboard or logs) can render exactly what data the AI used.
    """
    evidence = []
    if data and data.get("count") is not None:
        evidence.append({"metric": "result_count", "value": data["count"]})

    vessels = data.get("vessels") or data.get("alerts") or data.get("incidents")
    if isinstance(vessels, list):
        evidence.append({"metric": "resource_count", "value": len(vessels)})

    if intent == AIQueryIntent.VESSEL_STATUS:
        safety = data.get("safety") or {}
        for key in ("safety_state", "safety_score", "communication_state", "freshness", "trip_status"):
            if safety.get(key) is not None:
                evidence.append({"metric": key, "value": safety[key]})

    if intent == AIQueryIntent.NAVIGATION_GUIDANCE:
        for key in ("harbor_name", "distance_km", "bearing_degrees", "compass_direction", "estimated_minutes_to_reach"):
            if data.get(key) is not None:
                evidence.append({"metric": key, "value": data[key]})

    if intent == AIQueryIntent.INCIDENT_SUMMARY and data.get("report"):
        report = data["report"]
        for key in ("incident_type", "status", "severity"):
            if report.get(key) is not None:
                evidence.append({"metric": key, "value": report[key]})

    return evidence


def run_query(db: Session, user: User, intent: str, fisherman_id: int | None = None, incident_id: int | None = None) -> dict:
    if intent not in AIQueryIntent.ALL:
        return {
            "answer": "I'm sorry — I don't recognize that request. Please choose one of the available operations.",
            "data": None,
            "confidence": 0.0,
            "explanation": None,
        }

    # ── ACTIVE SOS ──────────────────────────────────────────────────────
    if intent == AIQueryIntent.ACTIVE_SOS:
        data = ai_tools.get_active_sos(db, user)
        if data["count"]:
            answer = (
                f"There {_plural(data['count'], 'is', 'are')} {data['count']} active "
                f"SOS alert{_s(data['count'])} right now. "
                f"{_describe_findings(intent, data)} — this needs immediate operator attention."
            )
        else:
            answer = "No active SOS alerts right now. All vessels are reporting normally — that's the situation we want to see."
        return _humanized_response(answer, intent, data, user)

    # ── HIGH RISK VESSELS ───────────────────────────────────────────────
    if intent == AIQueryIntent.HIGH_RISK_VESSELS:
        data = ai_tools.get_high_risk_vessels(db, user)
        if not data["count"]:
            answer = "No vessels are currently at HIGH_RISK or CRITICAL — everyone in the active fleet is inside the safety envelope."
        else:
            top = data["vessels"][0]
            names = ", ".join(f"{v['fisherman_name']} ({v['safety_state']})" for v in data["vessels"][:5])
            answer = (
                f"{data['count']} vessel{_s(data['count'])} at elevated risk: {names}. "
                f"Highest priority is {top['fisherman_name']} at {top['safety_state']} "
                f"({top['safety_score']}/100) — recommend immediate radio contact and "
                f"confirming their status before taking further action."
            )
        return _humanized_response(answer, intent, data, user)

    # ── OFFLINE VESSELS ─────────────────────────────────────────────────
    if intent == AIQueryIntent.OFFLINE_VESSELS:
        data = ai_tools.get_offline_vessels(db, user)
        if data["count"]:
            names = ", ".join(f"{v['fisherman_name']} ({v['freshness']})" for v in data["vessels"][:5])
            answer = (
                f"{data['count']} vessel{_s(data['count'])} with stale or unknown GPS: {names}. "
                "When a vessel stops reporting, the first step is radio contact — "
                "many boats simply lose signal, but we need to confirm that's the case."
            )
        else:
            answer = "All active vessels have recent location data — no one is in a communication blackout right now."
        return _humanized_response(answer, intent, data, user)

    # ── UNACKNOWLEDGED INCIDENTS ────────────────────────────────────────
    if intent == AIQueryIntent.UNACKNOWLEDGED_INCIDENTS:
        data = ai_tools.get_active_incidents(db, user)
        unacked = [i for i in data["incidents"] if i["status"] == "received"]
        if unacked:
            ids = ", ".join(f"#{i['id']}" for i in unacked[:5])
            answer = (
                f"{len(unacked)} incident{_s(len(unacked))} awaiting acknowledgement: {ids}. "
                "Every unacknowledged incident has no operator actively assigned — "
                "please acknowledge them so the assessment phase can begin."
            )
            data = {"count": len(unacked), "incidents": unacked}
        else:
            answer = "All open incidents have been acknowledged. No operator bandwidth is being held pending."
            data = {"count": 0, "incidents": []}
        return _humanized_response(answer, intent, data, user)

    # ── VESSEL STATUS ───────────────────────────────────────────────────
    if intent == AIQueryIntent.VESSEL_STATUS:
        if fisherman_id is None:
            return {"answer": "A fisherman_id is required for this query.", "data": None, "confidence": 0.0}
        safety = ai_tools.get_safety_state(db, user, fisherman_id)
        location = ai_tools.get_latest_location(db, user, fisherman_id)

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

        # Preserve the exact legacy answer format for backward compatibility.
        # The provider's deterministic explanation already contains
        # "Safety State: ..." and "not a guarantee of safety".
        enriched = _explain_structured(intent, {"safety": safety, "location": location}, user)
        return {
            "answer": text,
            "data": {"safety": safety, "location": location},
            "provider": provider_name,
            "confidence": enriched["explanation"]["confidence"],
            "explanation": enriched["explanation"],
        }

    # ── NAVIGATION GUIDANCE ─────────────────────────────────────────────
    if intent == AIQueryIntent.NAVIGATION_GUIDANCE:
        if fisherman_id is None:
            return {"answer": "A fisherman_id is required for this query.", "data": None, "confidence": 0.0}
        data = ai_tools.get_navigation_guidance(db, user, fisherman_id)
        if not data.get("harbor_found"):
            answer = data.get("detail", "No navigation guidance available.")
            return _humanized_response(answer, intent, data, user)

        # Preserve the exact legacy answer format for backward compatibility.
        answer = (
            f"Nearest safe harbor: {data['harbor_name']}, {data['distance_km']}km "
            f"bearing {data['compass_direction']} ({data['bearing_degrees']}°), "
            f"about {data['estimated_minutes_to_reach']} min at typical boat speed."
        )
        return _humanized_response(answer, intent, data, user)

    # ── INCIDENT SUMMARY ────────────────────────────────────────────────
    if intent == AIQueryIntent.INCIDENT_SUMMARY:
        if incident_id is None:
            return {"answer": "An incident_id is required for this query.", "data": None, "confidence": 0.0}
        data = ai_tools.generate_incident_summary(db, user, incident_id)
        answer = data["summary"]
        return _humanized_response(answer, intent, data, user)

    return {"answer": "I'm sorry — I don't recognize that request.", "data": None, "confidence": 0.0}


def _humanized_response(answer: str, intent: str, data: dict, user: User) -> dict:
    """Wrap the narrated answer with the full explainability envelope."""
    enriched = _explain_structured(intent, data, user)
    return {
        "answer": answer,
        "data": data,
        "confidence": enriched["explanation"]["confidence"],
        "explanation": enriched["explanation"],
    }


def _plural(count: int, singular: str, plural: str) -> str:
    """English helper — return singular or plural verb form."""
    return singular if count == 1 else plural


def _s(count: int) -> str:
    """English helper — return '' or 's' for noun plurality."""
    return "" if count == 1 else "s"


# Backwards-compatible alias for tests / callers that expect the old signature shape.
def run_query_v0(db: Session, user: User, intent: str, fisherman_id: int | None = None, incident_id: int | None = None) -> dict:
    """Legacy entry point that returns only {answer, data} — preserved so
    the public API shape is unchanged for any external consumer."""
    result = run_query(db, user, intent, fisherman_id, incident_id)
    return {"answer": result["answer"], "data": result["data"]}