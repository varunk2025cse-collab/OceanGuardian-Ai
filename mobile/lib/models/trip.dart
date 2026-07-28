/// Mirrors backend TripOut (app/schemas/trip.py) and the state machine in
/// app/services/trip_service.py. Status is one of: planned, active,
/// returning, completed, cancelled, emergency.
class Trip {
  final int id;
  final String status;
  final DateTime startTime;
  final DateTime? endTime;
  final DateTime? estimatedReturnAt;
  final String? destination;
  final String? notes;

  Trip({
    required this.id,
    required this.status,
    required this.startTime,
    this.endTime,
    this.estimatedReturnAt,
    this.destination,
    this.notes,
  });

  bool get isInProgress => status == 'active' || status == 'returning' || status == 'emergency';

  factory Trip.fromJson(Map<String, dynamic> json) => Trip(
        id: json['id'] as int,
        status: json['status'] as String,
        startTime: DateTime.parse(json['start_time'] as String),
        endTime: json['end_time'] == null ? null : DateTime.parse(json['end_time'] as String),
        estimatedReturnAt:
            json['estimated_return_at'] == null ? null : DateTime.parse(json['estimated_return_at'] as String),
        destination: json['destination'] as String?,
        notes: json['notes'] as String?,
      );
}
