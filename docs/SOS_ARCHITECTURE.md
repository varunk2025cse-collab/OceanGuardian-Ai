# SOS Architecture (SOS 2.0)

V2 core build Phase 14. Builds on the V1 offline-first SOS design (audited
as genuinely solid — see `docs/V1_AUDIT.md`), extending it rather than
replacing it.

## Non-negotiable

Manual SOS works with zero dependency on AI, weather, or the notification
provider. The trigger flow (`mobile/lib/services/sos_service.dart`) writes
to the local SQLite outbox before any network call — unchanged from V1.

## Emergency taxonomy (new)

`MANUAL_SOS | MAN_OVERBOARD | MEDICAL | FIRE | CAPSIZE | COLLISION |
ENGINE_FAILURE | SEVERE_WEATHER | FUEL_SHORTAGE | COMMUNICATION_FAILURE |
UNKNOWN` — validated server-side (`backend/app/schemas/sos.py`
`EMERGENCY_TYPES`) and client-side (`mobile/lib/models/sos_alert.dart`
`EmergencyType`).

UX constraint: selecting a type is **optional and never blocks the
primary send action** — the confirmation dialog defaults to `MANUAL_SOS`
and lets the fisherman tap a specific type as a quick refinement within
the same dialog, not an extra screen or required step. This preserves the
"SOS must be immediately accessible, one motion" requirement from the
governing brief.

## Device state capture

`network_type` (mobile connectivity at the moment of trigger) is now
captured alongside the existing `battery_level_percent`, both stored on
the alert (`sos_alerts.network_type`, new column).

## What happens on trigger (`POST /api/v1/sos/trigger`)

1. Alert persisted (idempotent on `client_uuid`, unchanged from V1).
2. `notify_emergency_contacts()` — structured log line (V1 behavior,
   unchanged; real dispatch happens in step 4).
3. `IncidentService.create_from_sos()` — auto-creates a `RECEIVED`
   incident (`docs/INCIDENT_ENGINE.md`), first timeline event written.
4. `NotificationEngine.notify_family_of_event()` — real
   `FamilyNotification` rows created for every linked family member
   (`docs/NOTIFICATIONS.md`), `priority=CRITICAL`.

## Status: IMPLEMENTED

Offline-first trigger: unchanged from V1 (already solid). Taxonomy +
device state + auto-incident + auto-notification: new, tested in
`tests/test_god_mode_safety_incident_ai.py`.
