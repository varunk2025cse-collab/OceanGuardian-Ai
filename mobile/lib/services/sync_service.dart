import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import '../config/api_config.dart';
import '../models/location_point.dart';
import 'api_client.dart';
import 'auth_service.dart';
import 'local_db_service.dart';

/// The four states Part 2 of the core build requires the UI to be able to
/// show, never silently hidden behind a spinner: ONLINE (connectivity
/// present, nothing pending or last sync succeeded), OFFLINE (no
/// connectivity — GPS/SOS capture keeps running locally regardless),
/// SYNCING (a sync attempt is in flight), SYNC_ERROR (connectivity is
/// present but the last sync attempt to the backend failed — distinct from
/// OFFLINE because "I have signal but the server rejected/timed out" is a
/// different problem for a fisherman/operator to reason about than "no
/// signal at all").
enum SyncUiStatus { online, offline, syncing, syncError }

/// Drains the offline outbox the moment connectivity returns, and keeps
/// retrying on an interval in case the first window of signal is too brief
/// (common near the coast: a few bars for thirty seconds, then gone again).
///
/// Sync priority order matters:
///   1. Pending SOS alerts (a life-safety message that's been sitting
///      unsent is the single most urgent thing this app can ever send)
///   2. Pending GPS location batch (so family tracking and the rescue
///      dashboard reflect the boat's real recent track)
///   3. Refresh of read-mostly reference data (weather/market/schemes/
///      family status) so those screens have something current to show
///      offline again afterwards.
///
/// Failed location batches back off exponentially (LocalDbService applies
/// the backoff schedule) rather than retrying every fixed interval forever,
/// so a boat with zero signal for days doesn't spin the sync loop pointlessly
/// — the periodic timer here just gives failed rows a chance to be picked
/// up again once their individual backoff window has passed.
class SyncService {
  SyncService._internal();
  static final SyncService instance = SyncService._internal();

  /// Current sync/connectivity state for the UI. Widgets can
  /// `ValueListenableBuilder` on this directly.
  final ValueNotifier<SyncUiStatus> status = ValueNotifier(SyncUiStatus.offline);

  StreamSubscription<List<ConnectivityResult>>? _connectivitySub;
  Timer? _retryTimer;
  bool _syncing = false;
  bool _hasConnectivity = false;

  void start() {
    _connectivitySub = Connectivity().onConnectivityChanged.listen((results) {
      _hasConnectivity = results.any((r) => r != ConnectivityResult.none);
      if (_hasConnectivity) {
        syncNow();
      } else {
        status.value = SyncUiStatus.offline;
      }
    });
    Connectivity().checkConnectivity().then((results) {
      _hasConnectivity = results.any((r) => r != ConnectivityResult.none);
      status.value = _hasConnectivity ? SyncUiStatus.online : SyncUiStatus.offline;
    });
    _retryTimer = Timer.periodic(ApiConfig.syncRetryInterval, (_) => syncNow());
  }

  void stop() {
    _connectivitySub?.cancel();
    _retryTimer?.cancel();
  }

  Future<void> syncNow() async {
    if (_syncing || !AuthService.instance.isLoggedIn) return;
    if (!_hasConnectivity) {
      status.value = SyncUiStatus.offline;
      return;
    }
    _syncing = true;
    status.value = SyncUiStatus.syncing;
    var hadError = false;
    try {
      await _syncPendingSos();
      await _syncPendingLocations();
      await _refreshReferenceCaches();
    } catch (_) {
      // A failure here means "server unreachable despite having signal" —
      // the outbox is untouched (LocalDbService already recorded the
      // per-row backoff) and the next timer tick or connectivity event
      // will try again. Surface SYNC_ERROR rather than silently going back
      // to ONLINE so the fisherman/family aren't told everything is fine
      // when it isn't.
      hadError = true;
    } finally {
      _syncing = false;
      status.value = hadError ? SyncUiStatus.syncError : SyncUiStatus.online;
    }
  }

  Future<void> _syncPendingSos() async {
    final pending = await LocalDbService.instance.unsyncedSos();
    for (final row in pending) {
      try {
        final result = await ApiClient.instance.post('/sos/trigger', {
          'client_uuid': row['client_uuid'],
          'latitude': row['latitude'],
          'longitude': row['longitude'],
          'accuracy_meters': row['accuracy_meters'],
          'battery_level_percent': row['battery_level_percent'],
          'alert_type': row['alert_type'] ?? 'MANUAL_SOS',
          'network_type': row['network_type'],
          'message': row['message'],
          'triggered_at': row['triggered_at'],
        });
        await LocalDbService.instance
            .markSosSynced(row['client_uuid'] as String, status: result['status'] as String? ?? 'active');
      } catch (_) {
        // Leave this one queued; SOS items are sent one-by-one (not
        // batched) so a single bad record never blocks the rest, and so
        // each gets its own clear server-side idempotency check.
      }
    }
  }

  Future<void> _syncPendingLocations() async {
    final pending = await LocalDbService.instance.unsyncedLocations();
    if (pending.isEmpty) return;

    final clientUuids = pending.map((r) => r['client_uuid'] as String).toList();
    await LocalDbService.instance.markLocationsSyncing(clientUuids);

    final points = pending.map((row) => LocationPoint.fromDbMap(row).toApiJson()).toList();
    try {
      await ApiClient.instance.post('/locations/sync', {'points': points});
      // A non-throwing response means the server accepted (or recognized as
      // already-seen) every client_uuid we sent - either way it's safe to
      // mark them synced locally.
      await LocalDbService.instance.markLocationsSynced(clientUuids);
    } catch (e) {
      await LocalDbService.instance.markLocationsFailed(clientUuids);
      rethrow;
    }
  }

  Future<void> _refreshReferenceCaches() async {
    try {
      final weather = await ApiClient.instance.get('/weather/active');
      await LocalDbService.instance.putCache('weather_active', weather);
    } catch (_) {}

    try {
      final market = await ApiClient.instance.get('/market/prices');
      await LocalDbService.instance.putCache('market_prices', market);
    } catch (_) {}

    try {
      final schemes = await ApiClient.instance.get('/schemes/');
      await LocalDbService.instance.putCache('govt_schemes', schemes);
    } catch (_) {}

    if (AuthService.instance.currentUser?.role == 'family') {
      try {
        final status = await ApiClient.instance.get('/family/status');
        await LocalDbService.instance.putCache('family_status', status);
      } catch (_) {}
    }
  }
}
