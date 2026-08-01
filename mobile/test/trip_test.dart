import 'package:flutter_test/flutter_test.dart';
import 'package:oceanguardian_mvp/models/trip.dart';
import 'package:oceanguardian_mvp/services/trip_service.dart';

void main() {
  test('Trip.fromJson parses backend TripOut shape', () {
    final trip = Trip.fromJson({
      'id': 42,
      'user_id': 7,
      'boat_id': null,
      'status': 'active',
      'start_time': '2026-01-01T05:30:00+00:00',
      'end_time': null,
      'estimated_return_at': null,
      'start_latitude': 11.0,
      'start_longitude': 79.8,
      'destination': 'Fishing grounds',
      'notes': null,
      'created_at': '2026-01-01T05:30:00+00:00',
    });
    expect(trip.id, 42);
    expect(trip.status, 'active');
    expect(trip.destination, 'Fishing grounds');
    expect(trip.isInProgress, isTrue);
  });

  test('isInProgress is true for active/returning/emergency and false for terminal states', () {
    for (final status in ['active', 'returning', 'emergency']) {
      final trip = Trip.fromJson({'id': 1, 'status': status, 'start_time': '2026-01-01T00:00:00+00:00'});
      expect(trip.isInProgress, isTrue, reason: '$status should be in-progress');
    }
    for (final status in ['completed', 'cancelled', 'planned']) {
      final trip = Trip.fromJson({'id': 1, 'status': status, 'start_time': '2026-01-01T00:00:00+00:00'});
      expect(trip.isInProgress, isFalse, reason: '$status should not be in-progress');
    }
  });

  test('buildStartTripPayload includes boat_id when a boat is selected', () {
    final payload = TripService.buildStartTripPayload(
      destination: 'Fishing grounds',
      estimatedReturnAt: DateTime.utc(2026, 1, 1, 6, 30),
      notes: 'Early departure',
      boatId: 7,
    );

    expect(payload['boat_id'], 7);
    expect(payload['destination'], 'Fishing grounds');
    expect(payload['notes'], 'Early departure');
  });
}
