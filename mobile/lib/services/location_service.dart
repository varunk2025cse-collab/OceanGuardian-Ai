import 'dart:async';
import 'package:battery_plus/battery_plus.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:geolocator/geolocator.dart';
import 'package:uuid/uuid.dart';
import '../config/api_config.dart';
import '../models/location_point.dart';
import 'local_db_service.dart';

/// Captures GPS fixes and writes them to the offline outbox FIRST, always.
///
/// This is the core of "offline GPS location storage": the phone never
/// waits for a network call to succeed before considering a fix "saved".
/// SyncService is solely responsible for draining the outbox later -
/// LocationService's job ends the moment the point is on disk.
class LocationService {
  LocationService._internal();
  static final LocationService instance = LocationService._internal();

  final _uuid = const Uuid();
  final _battery = Battery();
  Timer? _periodicTimer;
  StreamSubscription<Position>? _positionStream;

  /// Set by TripService when a trip is active, so new pings get tagged
  /// with it server-side (see LocationPoint.tripId). Left null between
  /// trips — tracking still runs (for "last known location" even when no
  /// trip is active), it just isn't associated with a specific voyage.
  int? currentTripId;

  /// Call once after login / on app start for an active trip.
  Future<bool> requestPermissionAndStart() async {
    final enabled = await Geolocator.isLocationServiceEnabled();
    if (!enabled) return false;

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      return false;
    }

    _startPeriodicCapture();
    return true;
  }

  void _startPeriodicCapture() {
    _periodicTimer?.cancel();
    // Take a fix immediately, then on the configured interval. A simple
    // timer (rather than a continuous high-frequency stream) is the right
    // trade-off for boat trips that can run many hours: it gives a
    // meaningful trail without draining the battery a fisherman may need
    // for the SOS button itself, hours into the trip.
    captureOnce();
    _periodicTimer = Timer.periodic(ApiConfig.locationCaptureInterval, (_) => captureOnce());
  }

  Future<LocationPoint?> captureOnce() async {
    try {
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 20),
      );
      final batteryPercent = await _readBatteryPercent();
      final networkType = await _readNetworkType();
      final point = LocationPoint(
        clientUuid: _uuid.v4(),
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyMeters: position.accuracy,
        speedMps: position.speed,
        headingDegrees: position.heading,
        altitudeMeters: position.altitude,
        batteryPercent: batteryPercent,
        networkType: networkType,
        tripId: currentTripId,
        recordedAt: DateTime.now(),
      );
      await LocalDbService.instance.queueLocation(point.toDbMap());
      return point;
    } catch (_) {
      // GPS fix failed (no satellite lock, permission revoked mid-trip,
      // etc.) - silently skip this tick; the next timer tick tries again.
      return null;
    }
  }

  Future<double?> _readBatteryPercent() async {
    try {
      final level = await _battery.batteryLevel;
      return level.toDouble();
    } catch (_) {
      return null; // Not available on this platform/emulator — never block the fix on it.
    }
  }

  Future<String?> _readNetworkType() async {
    try {
      final results = await Connectivity().checkConnectivity();
      if (results.contains(ConnectivityResult.wifi)) return 'WIFI';
      if (results.contains(ConnectivityResult.mobile)) return 'MOBILE';
      if (results.every((r) => r == ConnectivityResult.none)) return 'OFFLINE';
      return results.first.name.toUpperCase();
    } catch (_) {
      return null;
    }
  }

  /// Returns the most recent fix from this device's own local trail,
  /// regardless of sync state — used to center the in-app map. Deliberately
  /// reads the full trail (recentLocations), not the sync outbox filter
  /// (unsyncedLocations), so a point that's already synced or mid-retry
  /// still counts as "where am I now".
  Future<LocationPoint?> lastKnownLocal() async {
    final rows = await LocalDbService.instance.recentLocations(limit: 1);
    if (rows.isEmpty) return null;
    return LocationPoint.fromDbMap(rows.first);
  }

  void stop() {
    _periodicTimer?.cancel();
    _positionStream?.cancel();
  }
}
