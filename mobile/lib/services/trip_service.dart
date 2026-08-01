import 'package:flutter/foundation.dart';
import '../models/trip.dart';
import 'api_client.dart';
import 'location_service.dart';

/// Trip lifecycle against the backend's /trips/* API
/// (app/routers/trips.py + app/services/trip_service.py). The state machine
/// itself is enforced server-side; this class is a thin client plus the
/// piece of local wiring that matters for GPS tagging: whenever the active
/// trip changes, LocationService.instance.currentTripId is updated so new
/// pings get tagged with it.
class TripService {
  TripService._internal();
  static final TripService instance = TripService._internal();

  final ValueNotifier<Trip?> activeTrip = ValueNotifier(null);

  static Map<String, dynamic> buildStartTripPayload({
    String? destination,
    DateTime? estimatedReturnAt,
    String? notes,
    int? boatId,
  }) {
    return {
      if (destination != null && destination.isNotEmpty) 'destination': destination,
      if (estimatedReturnAt != null) 'estimated_return_at': estimatedReturnAt.toUtc().toIso8601String(),
      if (notes != null && notes.isNotEmpty) 'notes': notes,
      if (boatId != null) 'boat_id': boatId,
    };
  }

  Future<void> refreshActiveTrip() async {
    try {
      final json = await ApiClient.instance.get('/trips/active');
      final trip = json == null ? null : Trip.fromJson(json as Map<String, dynamic>);
      activeTrip.value = trip;
      LocationService.instance.currentTripId = trip?.id;
    } catch (_) {
      // Offline or server unreachable — leave whatever we last knew locally;
      // GPS/SOS capture never depends on this succeeding.
    }
  }

  Future<Trip> startTrip({String? destination, DateTime? estimatedReturnAt, String? notes, int? boatId}) async {
    final json = await ApiClient.instance.post('/trips/start', buildStartTripPayload(
      destination: destination,
      estimatedReturnAt: estimatedReturnAt,
      notes: notes,
      boatId: boatId,
    ));
    final trip = Trip.fromJson(json as Map<String, dynamic>);
    activeTrip.value = trip;
    LocationService.instance.currentTripId = trip.id;
    return trip;
  }

  Future<Trip> endTrip({String? notes}) async {
    final json = await ApiClient.instance.post('/trips/end', {
      if (notes != null && notes.isNotEmpty) 'notes': notes,
    });
    final trip = Trip.fromJson(json as Map<String, dynamic>);
    activeTrip.value = null;
    LocationService.instance.currentTripId = null;
    return trip;
  }

  Future<Trip> markReturning() async {
    final current = activeTrip.value;
    if (current == null) throw StateError('No active trip to transition');
    final json = await ApiClient.instance.patch('/trips/${current.id}/status', {'status': 'returning'});
    final trip = Trip.fromJson(json as Map<String, dynamic>);
    activeTrip.value = trip;
    return trip;
  }
}
