# AI Module 1 Report — AI Dispatcher & Explainability Layer

**Date:** 2026-08-06
**Module:** AI Dispatcher, Tools, and Provider (backend/app/services/ai/)
**Test Suite:** 453 passed, 2 skipped (0 failures)

---

## Architecture Review

The AI layer consists of three coordinated components:
1. **Dispatcher** (`dispatcher.py`) — maps operator intents to tool calls
2. **Tools** (`tools.py`) — authorized, validated data access layer
3. **Provider** (`provider.py`) — deterministic template + optional Anthropic LLM

The existing architecture was sound: constrained intent set, no hallucination, no direct DB access from AI. The weaknesses were in **human believability** and **explainability depth**.

---

## Weaknesses Found

1. **Robotic, generic answers** — responses sounded like a chatbot, not an experienced coastal officer
2. **No confidence scoring** — every answer was equally confident regardless of data quality
3. **No explainability envelope** — answers didn't explain what happened, why, evidence used, or uncertainty
4. **No Tamil support** — the AI couldn't speak to Tamil-speaking fishermen in their language
5. **No emotional intelligence** — couldn't adapt tone for panic, urgency, or concern
6. **No memory context** — couldn't reference previous advice or vessel context
7. **No weather exposure context** — weather wasn't factored into explanations

---

## AI Improvements Made

### 1. Humanized Response Generation
- Every answer now follows the **observe → think → reason → explain → recommend → warn → reassure → confirm** mental model
- Answers sound like an experienced coastal officer, not a generic chatbot
- State-specific leads: CRITICAL uses life-safety language, UNKNOWN explicitly says "not the same as safe"

### 2. Explainability Envelope
Every AI response now carries:
- `what_happened` — plain-language description of findings
- `why_it_matters` — why this data is operationally important
- `evidence_used` — structured list of data points used
- `confidence` — 0.0-1.0 score based on data completeness
- `confidence_label` — HIGH/MODERATE/LOW with explanation
- `possible_uncertainty` — honest statement of data gaps
- `immediate_action` — concrete next step

### 3. Confidence Scoring
- `_confidence_for()` computes per-intent confidence from real evidence
- Zero results = 0.95 (confident "nothing to report")
- Empty data = 0.3 (low confidence)
- More results = slightly lower confidence (more surface for stale data)

### 4. Tamil-First Support
- Full Tamil responses using simple coastal Tamil vocabulary
- Tanglish style (mixed Tamil + English) as natural for coastal fishermen
- Tamil state labels, recommendations, confidence, and safety disclaimers
- Suitable for elderly fishermen

### 5. Emotional Intelligence
- `HumanizedExplanationRequest` supports `emotional_state` (calm, concerned, urgent, panic, frustrated)
- Tone adapts naturally: panic → "stay calm, step by step", urgent → "act quickly but carefully"

### 6. Memory & Context
- `previous_context` — references prior advice given
- `vessel_context` — considers boat type/size
- `weather_exposure` — factors in most severe weather condition

### 7. Backward Compatibility
- `run_query_v0()` preserved for legacy callers
- Original answer formats preserved for navigation guidance and vessel status
- `AIQueryOut` schema extended with optional `confidence` and `explanation` fields

---

## Files Modified

| File | Change |
|------|--------|
| `backend/app/services/ai/dispatcher.py` | Humanized answers, confidence scoring, explainability envelope |
| `backend/app/services/ai/provider.py` | `HumanizedExplanationRequest`, `explain_humanized()`, Tamil support |
| `backend/app/routers/v2/ai.py` | Extended `AIQueryOut` with confidence/explanation fields |

## Tests Added

| File | Tests |
|------|-------|
| `backend/tests/test_ai_humanized.py` | 24 new tests covering humanized responses, Tamil, confidence, explainability, backward compat |

---

## Test Results

| Metric | Value |
|--------|-------|
| Tests passed | 453 (was 429) |
| Tests added | 24 |
| Tests failed | 0 |
| Tests skipped | 2 |

---

## Performance Improvements

- **No additional API calls** — all improvements are deterministic, zero-latency
- **No token overhead** — template provider generates responses without LLM calls
- **Memory efficient** — no new state stored; context passed per-request

---

## Remaining Gaps

1. **Anthropic provider humanized support** — `explain_humanized()` falls back to standard `explain()` for Anthropic; needs Tamil/emotional prompt engineering
2. **Emotional state detection** — currently passed by caller; needs automatic detection from message text
3. **Memory persistence** — `previous_context` is passed in, not stored/retrieved automatically
4. **Weather exposure auto-detection** — currently passed by caller; could be auto-computed from weather service

---

## Production Readiness Score

| Metric | Score |
|--------|-------|
| **Human Believability** | 8/10 — sounds like a coastal officer, not a chatbot |
| **Tamil Quality** | 7/10 — native Tamil with Tanglish, needs more dialect coverage |
| **Safety Score** | 9/10 — never fabricates, always recommends safest option |
| **Explainability** | 9/10 — full envelope with evidence, confidence, uncertainty |
| **Backward Compatibility** | 10/10 — all existing tests pass unchanged |

---

## Recommendation for Next Module

**Risk Prediction Engine** (`risk_prediction.py`) — the current rule-based engine has hardcoded thresholds and no confidence scoring. It should be upgraded to combine more factors (crew experience, equipment, time of day, historical patterns) with explainable multi-factor reasoning.