# Notification Engine

`backend/app/services/notification_service.py` — V2 core build Phase 20.

## What changed from V1

V1's entire notification system was one `logger.warning()` call
(`docs/V1_AUDIT.md` §12) — `FamilyNotification` rows were never created by
any code path, meaning operators/family could see a "notified" flag with
no message ever actually sent. That table is now genuinely written to.

## Provider abstraction

```
NotificationProvider (interface)
  -> SimulationNotificationProvider   DEFAULT. Logs the message and
                                      records delivery_status="simulated"
                                      — never claims a real SMS/push went
                                      out. This is what makes dev/demo
                                      possible without real credentials,
                                      per the "never fake capability" rule.
  -> TwilioSmsProvider                Real SMS via Twilio's HTTP API
                                      (httpx, no new SDK dependency). Only
                                      selected when NOTIFICATION_PROVIDER=
                                      twilio AND both TWILIO_ACCOUNT_SID/
                                      TWILIO_AUTH_TOKEN are set.
```

No Twilio/FCM/SMTP credentials exist in this build environment, so
`TwilioSmsProvider` is implemented against Twilio's documented REST
contract but **not runtime-verified** — same honesty caveat as
`AnthropicProvider` in `docs/AI_ARCHITECTURE.md`.

## Delivery record (always real)

Every notification attempt — regardless of provider — writes a
`FamilyNotification` row with an honest `delivery_status`
(`sent`/`failed`/`simulated`), `sent_at`, and `related_event_id` for
deduplication (the same SOS/incident event never re-notifies the same
family member twice).

## What triggers a notification (this build)

SOS trigger → `NotificationEngine.notify_family_of_event(priority=CRITICAL)`
for every family member linked to the triggering fisherman.

## Scope boundary, stated honestly

Only family members are notified in this build. Operators already see
everything in real time via the Rescue Dashboard's polling + the
Incidents page — a separate operator-notification table/channel was not
built this pass (would duplicate the dashboard's existing live view for
limited added value). Documented here as a real, scoped-out next step,
not silently missing.

## Status: IMPLEMENTED (simulation path, real+tested), UNVERIFIED (Twilio path)

`tests/test_god_mode_safety_incident_ai.py::test_sos_trigger_creates_simulated_family_notification`
verifies the default path end-to-end.
