# OceanGuardian AI — Mobile App (Flutter MVP)

Offline-first fisherman app: GPS trail, one-touch SOS, weather alerts,
family tracking, market prices, government schemes, English + Tamil UI.

This repo was hand-authored (not run through `flutter create`), so two
one-time setup steps are required before it will build — see Step 1 below.
**This code has not been compiled with the actual Flutter toolchain**
(no Flutter SDK was available in the environment it was written in), so
treat it as a careful, idiomatic first draft: run `flutter analyze` as
your very first step and expect to fix a handful of small issues.

## Step 1 — One-time project setup

```bash
cd mobile

# Adds the missing android/ ios/ web/ platform folders.
# Safe to run on an existing project: it fills in gaps, it will NOT
# overwrite lib/ or pubspec.yaml.
flutter create .

flutter pub get
```

`flutter pub get` also auto-generates `lib/l10n/app_localizations.dart`
from the `.arb` files (because `generate: true` is set in pubspec.yaml)
— that generated file is what every screen imports for translated strings.

## Step 2 — Add location permissions (required for GPS + SOS)

`flutter create .` generates a default manifest with no location
permissions. The `geolocator` package needs these added by hand:

**`android/app/src/main/AndroidManifest.xml`** — inside `<manifest>`, above `<application>`:
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
<uses-permission android:name="android.permission.INTERNET"/>
```

**`ios/Runner/Info.plist`** — inside the top-level `<dict>`:
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>OceanGuardian needs your location to record your GPS trail and send accurate SOS alerts.</string>
<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>OceanGuardian needs your location to record your GPS trail and send accurate SOS alerts.</string>
```

## Step 3 — Point the app at your backend

By default the app calls `http://10.0.2.2:8000` (the Android emulator's
alias for your computer's `localhost`, where the FastAPI backend runs).

- **Android emulator**: no change needed, this just works.
- **Physical phone on the same Wi-Fi**: run with your laptop's LAN IP:
  ```bash
  flutter run --dart-define=OG_API_BASE_URL=http://192.168.1.42:8000
  ```
- **Production**: point at your deployed HTTPS API URL the same way.

## Step 4 — Run

```bash
flutter devices            # confirm an emulator/simulator/device is attached
flutter run
```

## Step 5 — Verify

```bash
flutter analyze   # static analysis - run this FIRST, fix anything it flags
flutter test      # runs test/widget_test.dart
```

## How the offline-first design works

1. **GPS** — `LocationService` writes every fix straight to the on-device
   SQLite outbox (`pending_locations`) via `LocalDbService`. The network
   is never on the critical path of "did my location get saved".
2. **SOS** — `SosService` does the same for `pending_sos`, then makes a
   best-effort live POST. Success or failure of that POST doesn't change
   what the user sees: the alert is already safely queued either way.
3. **Sync** — `SyncService` listens for connectivity changes (via
   `connectivity_plus`) and also retries on a fixed interval, in that
   priority order: pending SOS → pending GPS batch → refresh of cached
   weather/market/schemes/family data. `client_uuid` on every record makes
   re-sending an already-synced item a safe no-op (the backend dedupes on
   the same field).
4. **Reference data caching** — `ReferenceDataService` is cache-first:
   it tries the network, and on failure falls back to the last cached
   response, so Weather/Market/Schemes/Family screens still show
   *something* with zero signal, with an "offline" badge in the UI.

## Known MVP limitations (by design — see project root README "Roadmap")

- Map tiles (OpenStreetMap) require a live connection; only the GPS trail
  *data* itself is offline. Full offline tile caching is a Stage 2 item.
- No turn-by-turn "return to shore" routing yet — the Location screen
  shows the trail and current position, not a navigation route.
- Token storage uses `shared_preferences` (plaintext on disk) for MVP
  simplicity. Swap to `flutter_secure_storage` before a production launch.
- No automated background fetch when the app is fully killed (iOS/Android
  background execution limits) — sync runs while the app is open/backgrounded
  normally. A native background service is a Stage 2 hardening item.
