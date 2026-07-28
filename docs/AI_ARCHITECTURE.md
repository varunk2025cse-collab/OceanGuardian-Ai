# AI Architecture

V2 core build Phase 12 (explainability), 17 (Rescue AI panel), 18 (tools).

## Hard rule

AI is decision support, never the source of truth for safety-critical
numbers, never a substitute for emergency services, and never allowed
direct database access. The deterministic Safety Engine
(`docs/SAFETY_STATE_ENGINE.md`) computes the score/state/reasons; AI only
turns that already-computed structured data into natural language, and
only answers operational questions through authorized tool calls
(`docs/AI_TOOLS.md`).

## Provider abstraction (`backend/app/services/ai/provider.py`)

```
AIProvider (interface)
  -> TemplateProvider   deterministic, zero external dependency, always
                         available. DEFAULT and the only provider actually
                         exercised in this environment (no LLM
                         credentials configured).
  -> AnthropicProvider  real Claude Messages API call via httpx (no new
                         SDK dependency). Only constructed when
                         ANTHROPIC_API_KEY is set. Falls back to
                         TemplateProvider automatically on any failure.
```

`get_ai_provider()` selects based on `settings.ai_provider` +
`settings.anthropic_api_key`.

### Honesty note on AnthropicProvider

**IMPLEMENTED, NOT VERIFIED.** No `ANTHROPIC_API_KEY` exists in this build
environment, so the real HTTP call path has never actually been exercised
end-to-end — only code-reviewed against the documented API contract. If
you configure a real key, verify it works before relying on it in
production. Nothing in this system requires it to work: every AI-touched
endpoint degrades cleanly to `TemplateProvider` text.

## Rescue AI Panel (Phase 17) — a fixed query set, not free-text chat

`backend/app/services/ai/dispatcher.py` exposes a constrained intent list
(`active_sos`, `high_risk_vessels`, `offline_vessels`,
`unacknowledged_incidents`, `vessel_status`, `incident_summary`) — these
map 1:1 onto the governing brief's own worked examples ("Show active SOS
incidents", "Which vessels have the highest risk?", etc.). This is
deliberate, not a shortcut: without real LLM credentials, a genuine
free-text natural-language interface can't be honestly claimed as
"understanding" arbitrary questions. Every intent is answered through a
real tool call against live data (see `docs/AI_TOOLS.md`) and narrated via
the provider above.

API: `GET /api/v2/ai/intents`, `POST /api/v2/ai/query`.
Dashboard UI: `rescue-dashboard/src/pages/IncidentsPage.jsx` (AI panel).

If a real LLM is ever wired in, this same endpoint could be extended to
accept free text and use the LLM to select an intent — documented here as
the natural next step, not built now (would be unverifiable without
credentials).

## Status: IMPLEMENTED (template path), PARTIALLY VERIFIED (Anthropic path)
