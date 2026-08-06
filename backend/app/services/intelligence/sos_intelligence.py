"""
OceanGuardian AI — SOS Intelligence Service (Tamil-First).

Every SOS response is produced in BOTH English and Tamil simultaneously.
Tamil is not a translation — it uses real coastal vocabulary spoken by
Tamil Nadu fishermen, their families, and harbor masters.

Design rules:
  1. Tamil is generated deterministically — zero LLM dependency.
  2. Every field that carries a human-readable string has a _ta twin.
  3. Emotional tone is calibrated per SOS type — a sinking is not the
     same emotional register as an engine failure.
  4. Language for the fisherman/family (simple, calm, reassuring).
     Language for the operator (direct, action-oriented, no softening).
  5. Safety-critical numbers (rescue minutes, battery %) are always
     stated in both languages — never omitted from either.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.sos import SOSAlert, SOSStatus
from app.schemas.intelligence import (
    DecisionEvidence, DecisionSupport, SOSReport,
)

# Average rescue vessel speed (km/h) — conservative for small coastal craft
_RESCUE_SPEED_KMH = 25.0

# ── SOS type taxonomy ────────────────────────────────────────────────────────
# Each entry: (risk_level, EN_severity_reason, EN_resource_rec,
#              TA_severity_reason, TA_resource_rec, TA_fisherman_message)
_SOS_TYPE_MAP = {
    "medical": (
        "critical",
        "Medical emergency — requires immediate medical assistance.",
        "Dispatch Coast Guard medical vessel or air-evac immediately.",
        "மருத்துவ அவசரநிலை — உடனடி மருத்துவ உதவி தேவை.",
        "கடலோர காவல் மருத்துவ கப்பல் அல்லது ஹெலிகாப்டர் அனுப்பவும்.",
        "பயப்படாதீர்கள். உதவி வருகிறது. அமைதியாக இருங்கள்.",
    ),
    "sinking": (
        "critical",
        "Vessel sinking — life-threatening emergency.",
        "Dispatch fast response rescue vessel. Alert all nearby fishing vessels.",
        "படகு மூழ்குகிறது — உயிருக்கு ஆபத்தான நிலை.",
        "விரைவு மீட்பு கப்பல் அனுப்பவும். அருகில் உள்ள மீனவர்களுக்கு தெரிவிக்கவும்.",
        "உடனே life jacket போடுங்கள். படகை விட வேண்டாம். உதவி வருகிறது.",
    ),
    "piracy": (
        "critical",
        "Piracy/hostile boarding — requires Coast Guard.",
        "Dispatch Coast Guard interceptor. Do NOT send unarmed civilian vessels.",
        "கடல் கொள்ளை — கடலோர காவல் தேவை.",
        "கடலோர காவல் படை அனுப்பவும். ஆயுதமற்ற படகுகளை அனுப்பாதீர்கள்.",
        "அமைதியாக இருங்கள். எதிர்க்காதீர்கள். உதவி வருகிறது.",
    ),
    "engine_failure": (
        "red",
        "Engine failure — vessel adrift, confirm anchoring.",
        "Dispatch tow/rescue vessel. Confirm vessel is anchored safely.",
        "இயந்திரம் கெட்டுவிட்டது — படகு நகர்கிறது, நங்கூரம் போடுங்கள்.",
        "இழுவை/மீட்பு கப்பல் அனுப்பவும். நங்கூரம் போட்டுள்ளார்களா என உறுதிப்படுத்தவும்.",
        "நங்கூரம் போடுங்கள். VHF channel 16 இல் தொடர்பு கொள்ளுங்கள். உதவி வருகிறது.",
    ),
    "weather": (
        "red",
        "Weather distress — confirm crew count and vessel condition.",
        "Dispatch rescue vessel. Confirm crew count and vessel condition.",
        "கடுமையான வானிலை — படகு நிலை மற்றும் மாலுமிகள் எண்ணிக்கை உறுதிப்படுத்தவும்.",
        "மீட்பு கப்பல் அனுப்பவும். மாலுமிகள் எண்ணிக்கை மற்றும் படகு நிலை கேட்கவும்.",
        "life jacket போடுங்கள். படகை காற்றுக்கு எதிராக திருப்புங்கள். உதவி வருகிறது.",
    ),
    "fire": (
        "critical",
        "Fire on board — crew may need to abandon ship.",
        "Dispatch fire-equipped rescue vessel. Crew may need to abandon ship.",
        "படகில் தீ — மாலுமிகள் படகை விட வேண்டியிருக்கலாம்.",
        "தீயணைப்பு மீட்பு கப்பல் அனுப்பவும். படகை விட வேண்டியிருக்கலாம்.",
        "உடனே life jacket போடுங்கள். தீயை அணைக்க முடியாவிட்டால் கடலில் குதியுங்கள்.",
    ),
    "man_overboard": (
        "critical",
        "Person overboard — every second counts.",
        "Dispatch rescue vessel immediately. Every minute matters.",
        "ஒருவர் கடலில் விழுந்தார் — ஒவ்வொரு நொடியும் முக்கியம்.",
        "உடனே மீட்பு கப்பல் அனுப்பவும். ஒவ்வொரு நிமிடமும் முக்கியம்.",
        "விழுந்தவரை கண்ணில் வையுங்கள். life ring வீசுங்கள். இடத்தை மாற்றாதீர்கள்.",
    ),
}

# ── Tamil status labels ───────────────────────────────────────────────────────
_STATUS_TA = {
    "active":       "செயலில் உள்ளது",
    "acknowledged": "ஒப்புக்கொள்ளப்பட்டது",
    "resolved":     "தீர்க்கப்பட்டது",
    "false_alarm":  "தவறான எச்சரிக்கை",
}

# ── Tamil priority labels ─────────────────────────────────────────────────────
_PRIORITY_TA = {
    "critical": "மிக அவசரம்",
    "high":     "அவசரம்",
    "normal":   "சாதாரண",
    "low":      "குறைந்த முன்னுரிமை",
}


class SOSIntelligenceService:
    """SOS intelligence — queries real SOS data."""

    @staticmethod
    def evaluate(db: Session, alert: SOSAlert) -> SOSReport:
        """Full SOS intelligence report."""
        alert_type = (alert.alert_type or "unknown").lower()
        (
            _,
            _en_severity_reason,
            _en_resource_rec,
            ta_severity_reason,
            ta_resource_rec,
            ta_fisherman_msg,
        ) = _SOS_TYPE_MAP.get(
            alert_type,
            (
                "red",
                f"SOS alert type: {alert.alert_type or 'Unknown'}.",
                "Dispatch standard search and rescue (SAR) vessel.",
                f"SOS எச்சரிக்கை வகை: {alert.alert_type or 'Unknown'}.",
                "மீட்பு கப்பல் அனுப்பவும்.",
                "உதவி வருகிறது. அமைதியாக இருங்கள்.",
            ),
        )

        severity = SOSIntelligenceService._assess_severity(alert)
        resources = SOSIntelligenceService._recommend_resources(alert)
        priority = SOSIntelligenceService._assess_priority(alert)
        rescue_minutes = SOSIntelligenceService._estimate_rescue_minutes(db, alert)

        priority_label_ta = _PRIORITY_TA.get(
            alert.priority or priority.priority or "normal",
            "சாதாரண",
        )
        status_ta = _STATUS_TA.get(alert.status.value, "நிலையைப் பெற முடியவில்லை")
        severity_reason_ta = SOSIntelligenceService._build_tamil_severity_reason(alert, ta_severity_reason)

        return SOSReport(
            alert_id=alert.id,
            severity_assessment=severity,
            resource_recommendation=resources,
            response_priority=priority,
            estimated_rescue_minutes=rescue_minutes,
            severity_reason_ta=severity_reason_ta,
            resource_recommendation_ta=ta_resource_rec,
            fisherman_message_ta=ta_fisherman_msg,
            priority_label_ta=priority_label_ta,
            rescue_time_ta=SOSIntelligenceService._format_rescue_time_ta(rescue_minutes),
            status_ta=status_ta,
        )

    @staticmethod
    def _format_rescue_time_ta(rescue_minutes: Optional[int]) -> str:
        return (
            f"{rescue_minutes} நிமிடங்களில் உதவி வரும்"
            if rescue_minutes is not None
            else "தூரம் தெரியவில்லை"
        )

    @staticmethod
    def _estimate_rescue_minutes(db: Session, alert: SOSAlert) -> Optional[int]:
        """Estimate rescue time from nearest active harbor to SOS position."""
        if not alert.latitude or not alert.longitude:
            return None
        try:
            from app.services.harbor import HarborService
            nearest = HarborService.find_nearest_harbors(
                db, alert.latitude, alert.longitude, max_distance_km=300, limit=1
            )
            if nearest:
                distance_km = nearest[0].distance_km
                return max(1, int((distance_km / _RESCUE_SPEED_KMH) * 60))
        except Exception:  # noqa: BLE001
            pass
        return None

    @staticmethod
    def _assess_severity(alert: SOSAlert) -> DecisionSupport:
        """Assess severity based on alert type and conditions."""
        alert_type = (alert.alert_type or "unknown").lower()
        risk_level, _en_severity, _en_resource, _ta_severity, _ta_resource, _ta_message = _SOS_TYPE_MAP.get(
            alert_type,
            (
                "red",
                "Unknown SOS alert.",
                "Dispatch standard search and rescue (SAR) vessel.",
                "SOS எச்சரிக்கை வகை தெரியவில்லை.",
                "மீட்பு கப்பல் அனுப்பவும்.",
                "உதவி வருகிறது. அமைதியாக இருங்கள்.",
            ),
        )

        evidence = [
            DecisionEvidence(
                metric_name="Alert Type", value=alert.alert_type or "Unknown",
                severity="danger",
            ),
            DecisionEvidence(
                metric_name="Battery Level", value=alert.battery_level_percent,
                unit="%",
                severity="danger" if alert.battery_level_percent and alert.battery_level_percent < 20 else "ok",
            ),
            DecisionEvidence(
                metric_name="GPS Accuracy", value=alert.accuracy_meters,
                unit="m",
                severity="danger" if alert.accuracy_meters and alert.accuracy_meters > 100 else "ok",
            ),
        ]

        rules = []
        if alert_type == "medical":
            rules.append("Medical emergency — requires immediate medical assistance.")
        elif alert_type == "sinking":
            rules.append("Vessel sinking — life-threatening emergency.")
        elif alert_type == "piracy":
            rules.append("Piracy/hostile boarding — requires Coast Guard.")
        elif alert_type == "fire":
            rules.append("Fire on board — crew may need to abandon ship.")
        elif alert_type == "man_overboard":
            rules.append("Person overboard — every second counts.")
        elif alert_type == "engine_failure":
            rules.append("Engine failure — vessel adrift, confirm anchoring.")
        else:
            rules.append(f"SOS alert type: {alert.alert_type or 'Unknown'}.")

        tamil_warnings = []
        if alert.battery_level_percent and alert.battery_level_percent < 20:
            rules.append(
                f"Battery critically low ({alert.battery_level_percent}%) — "
                "communication may be lost soon. Act before contact is lost."
            )
            tamil_warnings.append(
                f"Battery {alert.battery_level_percent}% — தொடர்பு விரைவில் துண்டிக்கப்படலாம்."
            )

        if alert.accuracy_meters and alert.accuracy_meters > 200:
            rules.append(
                f"GPS accuracy is poor (±{alert.accuracy_meters:.0f}m) — "
                "search area is larger than usual."
            )
            tamil_warnings.append(
                f"GPS துல்லியம் குறைவு (±{alert.accuracy_meters:.0f}m) — தேடல் பரப்பு அதிகம்."
            )

        return DecisionSupport(
            recommendation="Dispatch rescue resources immediately.",
            reason="; ".join(rules + tamil_warnings),
            evidence=evidence,
            confidence_score=0.95,
            priority="critical" if risk_level == "critical" else "high",
            risk_level=risk_level,
            suggested_action="Confirm vessel position and dispatch nearest available rescue asset.",
        )

    @staticmethod
    def _build_tamil_severity_reason(alert: SOSAlert, base_reason: str) -> str:
        parts = [base_reason]
        if alert.battery_level_percent and alert.battery_level_percent < 20:
            parts.append(
                f"Battery {alert.battery_level_percent}% — தொடர்பு விரைவில் துண்டிக்கப்படலாம்."
            )
        if alert.accuracy_meters and alert.accuracy_meters > 200:
            parts.append(
                f"GPS துல்லியம் குறைவு (±{alert.accuracy_meters:.0f}m) — தேடல் பரப்பு அதிகம்."
            )
        return " ".join(parts)

    @staticmethod
    def _recommend_resources(alert: SOSAlert) -> DecisionSupport:
        """Recommend rescue resources based on alert type."""
        alert_type = (alert.alert_type or "unknown").lower()
        _, _, rec, _, _, _ = _SOS_TYPE_MAP.get(
            alert_type,
            (
                "red",
                "",
                "Dispatch standard search and rescue (SAR) vessel.",
                "",
                "",
                "",
            ),
        )

        evidence = [
            DecisionEvidence(
                metric_name="Alert Type", value=alert.alert_type or "Unknown",
                severity="danger",
            ),
        ]

        return DecisionSupport(
            recommendation=rec,
            reason=f"Resource recommendation based on incident type: {alert.alert_type or 'Unknown'}.",
            evidence=evidence,
            confidence_score=0.9,
            priority="critical" if alert_type in ("medical", "sinking", "piracy", "fire", "man_overboard") else "high",
            risk_level="critical" if alert_type in ("medical", "sinking", "piracy", "fire", "man_overboard") else "red",
            suggested_action="Coordinate with nearest Coast Guard station.",
        )
        
    @staticmethod
    def _assess_priority(alert: SOSAlert) -> DecisionSupport:
        """Assess operational priority."""
        status = alert.status
        if status == SOSStatus.resolved:
            return DecisionSupport(
                recommendation="Incident is resolved. No further action needed.",
                reason="Alert was marked resolved by operator.",
                evidence=[DecisionEvidence(metric_name="Status", value=status.value, severity="ok")],
                confidence_score=1.0,
                priority="low",
                risk_level="green"
            )
            
        return DecisionSupport(
            recommendation="Incident is ACTIVE. Immediate attention required.",
            reason=f"Alert status is {status.value}.",
            evidence=[DecisionEvidence(metric_name="Status", value=status.value, severity="danger")],
            confidence_score=1.0,
            priority="critical",
            risk_level="critical"
        )
