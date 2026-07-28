import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:geolocator/geolocator.dart';
import 'package:uuid/uuid.dart';
import '../models/sos_alert.dart';
import 'api_client.dart';
import 'local_db_service.dart';

/// One-touch SOS workflow.
///
/// Safety-critical sequence, in order:
///  1. Get the best GPS fix available RIGHT NOW (short timeout - a stale
///     fix is still useful, waiting 20s for a perfect one is not).
///  2. Write the alert to the local outbox IMMEDIATELY. This is the
///     "save" - it cannot be lost even if the app crashes a second later.
///  3. Only after it's safely on disk, attempt to send it live. If that
///     fails (no signal), SyncService will keep retrying in the
///     background every `syncRetryInterval` until it gets through.
///
/// The UI should treat step 2 as "SOS sent" the instant it completes -
/// never make a panicking person wait on a network call to know their
/// alert was captured.
class SosService {
  SosService._internal();
  static final SosService instance = SosService._internal();

  final _uuid = const Uuid();

  Future<SosAlert> trigger({
    String? message,
    int? batteryLevelPercent,
    String alertType = EmergencyType.manual,
  }) async {
    Position? position;
    try {
      position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 8),
      );
    } catch (_) {
      // Fall back to the last fix Geolocator has cached on-device rather
      // than blocking the SOS button on a fresh GPS lock.
      position = await Geolocator.getLastKnownPosition();
    }

    if (position == null) {
      throw Exception('Unable to get a GPS position. Move to open sky and try again.');
    }

    String? networkType;
    try {
      final results = await Connectivity().checkConnectivity();
      networkType = results.contains(ConnectivityResult.none) ? 'OFFLINE' : results.first.name.toUpperCase();
    } catch (_) {
      networkType = null;
    }

    final alert = SosAlert(
      clientUuid: _uuid.v4(),
      latitude: position.latitude,
      longitude: position.longitude,
      accuracyMeters: position.accuracy,
      batteryLevelPercent: batteryLevelPercent,
      alertType: alertType,
      networkType: networkType,
      message: message,
      triggeredAt: DateTime.now(),
    );

    // Step 2: persist locally first, unconditionally.
    await LocalDbService.instance.queueSos(alert.toDbMap());

    // Step 3: best-effort immediate send. Failure is NOT an error to the
    // caller - the alert is already safely queued and SyncService owns
    // retrying it.
    try {
      final result = await ApiClient.instance.post('/sos/trigger', alert.toApiJson());
      await LocalDbService.instance.markSosSynced(alert.clientUuid, status: result['status'] as String? ?? 'active');
    } catch (_) {
      // No connectivity right now - stays in the outbox for SyncService.
    }

    return alert;
  }
}
