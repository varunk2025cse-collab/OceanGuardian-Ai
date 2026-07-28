/// Emergency taxonomy mirroring the backend
/// (backend/app/schemas/sos.py EMERGENCY_TYPES) — SOS 2.0, V2 core build
/// Phase 14.
class EmergencyType {
  static const manual = 'MANUAL_SOS';
  static const manOverboard = 'MAN_OVERBOARD';
  static const medical = 'MEDICAL';
  static const fire = 'FIRE';
  static const capsize = 'CAPSIZE';
  static const collision = 'COLLISION';
  static const engineFailure = 'ENGINE_FAILURE';
  static const severeWeather = 'SEVERE_WEATHER';
  static const fuelShortage = 'FUEL_SHORTAGE';
  static const communicationFailure = 'COMMUNICATION_FAILURE';
  static const unknown = 'UNKNOWN';

  static const all = [
    manual,
    manOverboard,
    medical,
    fire,
    capsize,
    collision,
    engineFailure,
    severeWeather,
    fuelShortage,
    communicationFailure,
    unknown,
  ];
}

class SosAlert {
  final String clientUuid;
  final double latitude;
  final double longitude;
  final double? accuracyMeters;
  final int? batteryLevelPercent;
  final String alertType;
  final String? networkType;
  final String? message;
  final DateTime triggeredAt;
  final bool synced;
  final String status; // local default "active" until server confirms

  SosAlert({
    required this.clientUuid,
    required this.latitude,
    required this.longitude,
    required this.triggeredAt,
    this.accuracyMeters,
    this.batteryLevelPercent,
    this.alertType = EmergencyType.manual,
    this.networkType,
    this.message,
    this.synced = false,
    this.status = 'active',
  });

  Map<String, dynamic> toApiJson() => {
        'client_uuid': clientUuid,
        'latitude': latitude,
        'longitude': longitude,
        'accuracy_meters': accuracyMeters,
        'battery_level_percent': batteryLevelPercent,
        'alert_type': alertType,
        'network_type': networkType,
        'message': message,
        'triggered_at': triggeredAt.toUtc().toIso8601String(),
      };

  Map<String, dynamic> toDbMap() => {
        'client_uuid': clientUuid,
        'latitude': latitude,
        'longitude': longitude,
        'accuracy_meters': accuracyMeters,
        'battery_level_percent': batteryLevelPercent,
        'alert_type': alertType,
        'network_type': networkType,
        'message': message,
        'triggered_at': triggeredAt.toUtc().toIso8601String(),
        'synced': synced ? 1 : 0,
        'status': status,
      };

  factory SosAlert.fromDbMap(Map<String, dynamic> map) => SosAlert(
        clientUuid: map['client_uuid'] as String,
        latitude: map['latitude'] as double,
        longitude: map['longitude'] as double,
        accuracyMeters: map['accuracy_meters'] as double?,
        batteryLevelPercent: map['battery_level_percent'] as int?,
        alertType: map['alert_type'] as String? ?? EmergencyType.manual,
        networkType: map['network_type'] as String?,
        message: map['message'] as String?,
        triggeredAt: DateTime.parse(map['triggered_at'] as String),
        synced: (map['synced'] as int) == 1,
        status: map['status'] as String? ?? 'active',
      );

  factory SosAlert.fromApiJson(Map<String, dynamic> json) => SosAlert(
        clientUuid: json['client_uuid'] as String,
        latitude: (json['latitude'] as num).toDouble(),
        longitude: (json['longitude'] as num).toDouble(),
        accuracyMeters: (json['accuracy_meters'] as num?)?.toDouble(),
        batteryLevelPercent: json['battery_level_percent'] as int?,
        alertType: json['alert_type'] as String? ?? EmergencyType.manual,
        networkType: json['network_type'] as String?,
        message: json['message'] as String?,
        triggeredAt: DateTime.parse(json['triggered_at'] as String),
        synced: true,
        status: json['status'] as String,
      );
}
