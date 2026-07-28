class LocationPoint {
  final String clientUuid;
  final double latitude;
  final double longitude;
  final double? accuracyMeters;
  final double? speedMps;
  final double? headingDegrees;
  final double? altitudeMeters;
  final double? batteryPercent;
  final String? networkType;
  final int? tripId;
  final DateTime recordedAt;
  final bool synced;
  final String syncStatus;

  LocationPoint({
    required this.clientUuid,
    required this.latitude,
    required this.longitude,
    required this.recordedAt,
    this.accuracyMeters,
    this.speedMps,
    this.headingDegrees,
    this.altitudeMeters,
    this.batteryPercent,
    this.networkType,
    this.tripId,
    this.synced = false,
    this.syncStatus = 'pending',
  });

  Map<String, dynamic> toApiJson() => {
        'client_uuid': clientUuid,
        'latitude': latitude,
        'longitude': longitude,
        'accuracy_meters': accuracyMeters,
        'speed_mps': speedMps,
        'heading_degrees': headingDegrees,
        'altitude_meters': altitudeMeters,
        'battery_percent': batteryPercent,
        'network_type': networkType,
        'source': 'MOBILE_GPS',
        'recorded_at': recordedAt.toUtc().toIso8601String(),
      };

  Map<String, dynamic> toDbMap() => {
        'client_uuid': clientUuid,
        'latitude': latitude,
        'longitude': longitude,
        'accuracy_meters': accuracyMeters,
        'speed_mps': speedMps,
        'heading_degrees': headingDegrees,
        'altitude_meters': altitudeMeters,
        'battery_percent': batteryPercent,
        'network_type': networkType,
        'trip_id': tripId,
        'recorded_at': recordedAt.toUtc().toIso8601String(),
        'synced': synced ? 1 : 0,
        'sync_status': syncStatus,
      };

  factory LocationPoint.fromDbMap(Map<String, dynamic> map) => LocationPoint(
        clientUuid: map['client_uuid'] as String,
        latitude: map['latitude'] as double,
        longitude: map['longitude'] as double,
        accuracyMeters: map['accuracy_meters'] as double?,
        speedMps: map['speed_mps'] as double?,
        headingDegrees: map['heading_degrees'] as double?,
        altitudeMeters: map['altitude_meters'] as double?,
        batteryPercent: map['battery_percent'] as double?,
        networkType: map['network_type'] as String?,
        tripId: map['trip_id'] as int?,
        recordedAt: DateTime.parse(map['recorded_at'] as String),
        synced: (map['synced'] as int? ?? 0) == 1,
        syncStatus: (map['sync_status'] as String?) ?? 'pending',
      );
}
