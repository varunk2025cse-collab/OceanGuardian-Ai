# Boat Management AI Integration
**OceanGuardian AI — AI Architecture for Vessel Intelligence**
**Version:** 1.0

---

## 1. Design Principles

- AI is **advisory only** — never blocks safety-critical paths (SOS, emergency)
- Every AI output includes `confidence_score`, `explanation`, and `human_override` support
- Offline AI uses deterministic rule-based fallback — never claims false confidence
- All AI decisions are logged in `boat_audit_logs` with `action=ai_recommendation`
- Human override is always available and always logged

---

## 2. AI Capabilities

### 2.1 Boat Health Prediction

**Purpose:** Predict future health score degradation before it becomes critical.

**Inputs:**
- Current `health_score` from `boat_health_status`
- `engine_hours` and rate of increase (from fuel logs)
- Maintenance history (overdue count, average delay)
- Fuel consumption trend (last 10 trips)
- Age of vessel (`year_built`)
- Incident history count

**Output:**
```json
{
  "predicted_health_score_30_days": 68.5,
  "predicted_health_score_90_days": 51.2,
  "trend": "declining",
  "primary_risk_factor": "engine_hours_approaching_service_threshold",
  "explanation": "Engine hours are at 2,800 — service is recommended at 3,000. At current usage rate, you will reach this in approximately 25 days.",
  "explanation_ta": "இயந்திர மணிகள் 2,800 ஆக உள்ளன — 3,000 மணிகளில் சேவை பரிந்துரைக்கப்படுகிறது.",
  "confidence_score": 0.82,
  "model_version": "boat_health_v1.0",
  "human_override": false
}
```

**Offline fallback:** Rule-based scoring using thresholds (engine_hours > 2500 → warn, > 3000 → critical).

---

### 2.2 Maintenance Prediction

**Purpose:** Predict when the next maintenance event is needed and what type.

**Inputs:**
- Last service date and type
- Engine hours since last service
- Fuel consumption patterns
- Historical maintenance intervals for this vessel class
- Seasonal patterns (monsoon = higher wear)

**Output:**
```json
{
  "next_maintenance_type": "engine_servicing",
  "predicted_due_date": "2025-03-15",
  "days_until_due": 58,
  "urgency": "upcoming",
  "estimated_cost_rupees": 3500,
  "recommended_service_center": "Nagapattinam Marine Services",
  "explanation": "Based on your engine hours and last service date, engine servicing is due in approximately 58 days.",
  "confidence_score": 0.78,
  "model_version": "maintenance_pred_v1.0"
}
```

---

### 2.3 Trip Readiness Score

**Purpose:** Compute a 0–100 readiness score with weighted factors and plain-language explanation.

**Inputs:** All readiness check results (license, insurance, fuel, crew, equipment, inspection, boat status)

**Scoring weights:**
```
Boat status = ACTIVE          : 25 points (blocking if not met)
Fishing license valid         : 20 points (blocking if not met)
Insurance valid               : 15 points (blocking if not met)
Fuel level ≥ 20%              : 10 points
Safety equipment complete     : 10 points
Crew assigned                 : 10 points
Last inspection < 1 year      :  5 points
Engine not damaged            :  5 points (blocking if not met)
```

**Output:**
```json
{
  "readiness_score": 65,
  "is_ready": false,
  "blocking_issues": [...],
  "warnings": [...],
  "passed_checks": [...],
  "ai_recommendation": "Renew your fishing license at the Nagapattinam Fisheries office before your next trip. The office is open Monday–Saturday 9am–5pm.",
  "ai_recommendation_ta": "அடுத்த பயணத்திற்கு முன் நாகப்பட்டினம் மீன்வளத் துறை அலுவலகத்தில் உங்கள் மீன்பிடி உரிமத்தை புதுப்பிக்கவும்.",
  "confidence_score": 0.94,
  "model_version": "readiness_v1.0"
}
```

---

### 2.4 Vessel Risk Score

**Purpose:** Compute a vessel-level risk score for operators and rescue teams.

**Inputs:**
- Incident history (count, severity, recency)
- Maintenance compliance rate
- Document compliance (expired docs)
- Vessel age and class
- Owner's trip history and safety record

**Output:**
```json
{
  "risk_level": "medium",
  "risk_score": 42.5,
  "contributing_factors": [
    {"factor": "2 incidents in last 12 months", "weight": 0.35},
    {"factor": "Inspection overdue by 45 days", "weight": 0.25},
    {"factor": "Vessel age 7 years", "weight": 0.15}
  ],
  "explanation": "This vessel has a medium risk profile due to recent incidents and an overdue inspection.",
  "confidence_score": 0.71,
  "model_version": "vessel_risk_v1.0"
}
```

---

### 2.5 Equipment Recommendation

**Purpose:** Recommend safety equipment based on vessel class, fishing zone, and season.

**Inputs:**
- `vessel_class`
- `home_harbor` region
- Current season (monsoon/pre-monsoon/post-monsoon)
- Current equipment inventory
- Regulatory requirements for the region

**Output:**
```json
{
  "recommended_additions": [
    {
      "item": "VHF Radio",
      "category": "communication",
      "reason": "Required for mechanized vessels operating beyond 12 nautical miles",
      "is_regulatory_requirement": true,
      "estimated_cost_rupees": 4500
    },
    {
      "item": "Additional life jacket",
      "category": "life_saving",
      "reason": "Crew count (4) exceeds current life jacket count (3)",
      "is_regulatory_requirement": true
    }
  ],
  "confidence_score": 0.91,
  "model_version": "equipment_rec_v1.0"
}
```

---

## 3. Offline AI Behavior

When the device is offline, all AI features fall back to deterministic rule-based logic:

| Feature | Offline Behavior |
|---|---|
| Health prediction | Use last cached score + simple threshold rules |
| Maintenance prediction | Use last service date + fixed intervals (oil: 90 days, engine: 180 days) |
| Trip readiness | Full rule-based check using cached boat data — no score, just pass/fail |
| Vessel risk | Use cached risk level — show "LAST UPDATED: {date}" |
| Equipment recommendation | Use static regulatory checklist for vessel class |

All offline AI outputs include: `"offline_mode": true, "data_as_of": "2025-01-15T06:00:00Z"`

---

## 4. Human Override

Every AI recommendation has an override path:

```
User sees AI recommendation
  → User taps "Override"
  → System asks: "Why are you overriding this recommendation?"
    Options: "I disagree", "Situation has changed", "Emergency", "Other"
  → Override is logged in boat_audit_logs with reason
  → AI recommendation is marked as overridden
  → Override is used to improve future model behavior
```

Override does NOT block any action. It only records the decision.

---

## 5. Explainability Standards

Every AI output must answer:
1. **What** is the recommendation?
2. **Why** is this being recommended? (contributing factors)
3. **How confident** is the system? (0.0–1.0 score)
4. **What should the user do** next? (actionable step)
5. **What happens if ignored?** (consequence)

Plain language rules:
- Maximum 2 sentences per explanation
- No technical jargon
- Available in Tamil and English
- Voice-readable (no special characters that break TTS)
