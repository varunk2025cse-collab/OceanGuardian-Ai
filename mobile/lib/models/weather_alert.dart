class WeatherAlertInfo {
  final int id;
  final String title;
  final String description;
  final String hazardType;
  final String severity; // advisory | warning | danger
  final double centerLatitude;
  final double centerLongitude;
  final double radiusKm;
  final DateTime validFrom;
  final DateTime validUntil;
  final String? source;

  WeatherAlertInfo({
    required this.id,
    required this.title,
    required this.description,
    required this.hazardType,
    required this.severity,
    required this.centerLatitude,
    required this.centerLongitude,
    required this.radiusKm,
    required this.validFrom,
    required this.validUntil,
    this.source,
  });

  factory WeatherAlertInfo.fromJson(Map<String, dynamic> json) => WeatherAlertInfo(
        id: json['id'] as int,
        title: json['title'] as String,
        description: json['description'] as String,
        hazardType: json['hazard_type'] as String,
        severity: json['severity'] as String,
        centerLatitude: (json['center_latitude'] as num).toDouble(),
        centerLongitude: (json['center_longitude'] as num).toDouble(),
        radiusKm: (json['radius_km'] as num).toDouble(),
        validFrom: DateTime.parse(json['valid_from'] as String),
        validUntil: DateTime.parse(json['valid_until'] as String),
        source: json['source'] as String?,
      );

  Map<String, dynamic> toCacheJson() => {
        'id': id,
        'title': title,
        'description': description,
        'hazard_type': hazardType,
        'severity': severity,
        'center_latitude': centerLatitude,
        'center_longitude': centerLongitude,
        'radius_km': radiusKm,
        'valid_from': validFrom.toIso8601String(),
        'valid_until': validUntil.toIso8601String(),
        'source': source,
      };
}
