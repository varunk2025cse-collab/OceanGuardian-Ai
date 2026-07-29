# 03 Flutter Audit

## Scope reviewed
The mobile audit was based on [mobile/lib/main.dart](mobile/lib/main.dart), [mobile/lib/screens/home_dashboard_screen.dart](mobile/lib/screens/home_dashboard_screen.dart), [mobile/lib/services/api_client.dart](mobile/lib/services/api_client.dart), [mobile/lib/services/sync_service.dart](mobile/lib/services/sync_service.dart), [mobile/lib/services/auth_service.dart](mobile/lib/services/auth_service.dart), and [mobile/lib/config/api_config.dart](mobile/lib/config/api_config.dart).

## Strengths
- The app is clearly built with offline-first principles in mind.
- Local persistence and sync management are implemented in [mobile/lib/services/sync_service.dart](mobile/lib/services/sync_service.dart).
- Secure storage is used for tokens in [mobile/lib/services/auth_service.dart](mobile/lib/services/auth_service.dart).
- Localization support is present via [mobile/lib/l10n](mobile/lib/l10n).

## Issues found
- [mobile/lib/config/api_config.dart](mobile/lib/config/api_config.dart) hard-codes a backend URL, which makes deployment brittle and environment-specific.
- The app uses a single-screen dashboard flow that is functional but still relatively thin compared with the ambition of the product.
- Some screens are likely to require deeper product and UX work for real fishermen, especially under sunlight, gloves, and low-connectivity conditions.
- The app does not appear to expose a formal offline map tile strategy or turn-by-turn navigation flow yet.

## UI/UX observations
- The home experience prioritizes the SOS and safety state, which is appropriate.
- The design is better than a typical student project, but the experience still needs deeper field testing with actual fishermen.

## Flutter verdict
- Flutter readiness: approximately 74%.
- Status: strong technical foundation, but not yet fully production-grade for operational field use.
