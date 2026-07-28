class FishermanStatus {
  final int fishermanId;
  final String fullName;
  final String? boatName;
  final double? lastLatitude;
  final double? lastLongitude;
  final DateTime? lastSeenAt;
  final bool activeSos;
  // LIVE/RECENT/LAST_KNOWN/STALE/UNKNOWN, computed server-side — see
  // backend app/services/tracking_service.py compute_freshness. Never
  // inferred client-side so the threshold logic has one source of truth.
  final String freshness;
  // SAFE/MONITOR/CAUTION/HIGH_RISK/CRITICAL/UNKNOWN, computed server-side —
  // see backend app/services/safety_engine.py. Distinct from `freshness`:
  // a fisherman can be HIGH_RISK while still ONLINE, or UNKNOWN-safety
  // while LIVE (no trip in progress).
  final String safetyState;
  final String? incidentStatus;

  FishermanStatus({
    required this.fishermanId,
    required this.fullName,
    required this.activeSos,
    this.boatName,
    this.lastLatitude,
    this.lastLongitude,
    this.lastSeenAt,
    this.freshness = 'UNKNOWN',
    this.safetyState = 'UNKNOWN',
    this.incidentStatus,
  });

  factory FishermanStatus.fromJson(Map<String, dynamic> json) => FishermanStatus(
        fishermanId: json['fisherman_id'] as int,
        fullName: json['full_name'] as String,
        boatName: json['boat_name'] as String?,
        lastLatitude: (json['last_latitude'] as num?)?.toDouble(),
        lastLongitude: (json['last_longitude'] as num?)?.toDouble(),
        lastSeenAt: json['last_seen_at'] == null ? null : DateTime.parse(json['last_seen_at'] as String),
        activeSos: json['active_sos'] as bool,
        freshness: json['freshness'] as String? ?? 'UNKNOWN',
        safetyState: json['safety_state'] as String? ?? 'UNKNOWN',
        incidentStatus: json['incident_status'] as String?,
      );
}
