/// Mirrors backend BoatV2Out (app/schemas/boat.py) plus the 8-state
/// lifecycle FSM from app/models/boat.py.
///
/// Contains all enterprise fields from migration 009: status, vessel
/// classification, engine metadata, verification, QR token, etc.
class Boat {
  final int id;
  final int ownerId;
  final String name;
  final String? registrationNumber;
  final String status;
  final String? vesselClass;
  final String? hullMaterial;
  final String? color;
  final double? lengthMeters;
  final double? beamMeters;
  final double? draftMeters;
  final int? yearBuilt;
  final String? engineType;
  final String? engineMake;
  final String? engineModel;
  final String? engineSerialNumber;
  final int? engineYear;
  final int? engineHorsepower;
  final double? fuelCapacityLiters;
  final int? homeHarborId;
  final String verificationStatus;
  final DateTime? verifiedAt;
  final String? qrCodeToken;
  final bool isActive;
  final int version;
  final DateTime createdAt;
  final DateTime? updatedAt;

  Boat({
    required this.id,
    required this.ownerId,
    required this.name,
    this.registrationNumber,
    this.status = 'registered',
    this.vesselClass,
    this.hullMaterial,
    this.color,
    this.lengthMeters,
    this.beamMeters,
    this.draftMeters,
    this.yearBuilt,
    this.engineType,
    this.engineMake,
    this.engineModel,
    this.engineSerialNumber,
    this.engineYear,
    this.engineHorsepower,
    this.fuelCapacityLiters,
    this.homeHarborId,
    this.verificationStatus = 'unverified',
    this.verifiedAt,
    this.qrCodeToken,
    this.isActive = true,
    this.version = 1,
    required this.createdAt,
    this.updatedAt,
  });

  /// Whether this boat can be used for trips based purely on lifecycle status.
  bool get isTripReady => status == 'active' || status == 'registered';

  factory Boat.fromJson(Map<String, dynamic> json) => Boat(
        id: json['id'] as int,
        ownerId: json['owner_id'] as int,
        name: json['name'] as String,
        registrationNumber: json['registration_number'] as String?,
        status: json['status'] as String? ?? 'registered',
        vesselClass: json['vessel_class'] as String?,
        hullMaterial: json['hull_material'] as String?,
        color: json['color'] as String?,
        lengthMeters: (json['length_meters'] as num?)?.toDouble(),
        beamMeters: (json['beam_meters'] as num?)?.toDouble(),
        draftMeters: (json['draft_meters'] as num?)?.toDouble(),
        yearBuilt: json['year_built'] as int?,
        engineType: json['engine_type'] as String?,
        engineMake: json['engine_make'] as String?,
        engineModel: json['engine_model'] as String?,
        engineSerialNumber: json['engine_serial_number'] as String?,
        engineYear: json['engine_year'] as int?,
        engineHorsepower: json['engine_horsepower'] as int?,
        fuelCapacityLiters: (json['fuel_capacity_liters'] as num?)?.toDouble(),
        homeHarborId: json['home_harbor_id'] as int?,
        verificationStatus: json['verification_status'] as String? ?? 'unverified',
        verifiedAt: json['verified_at'] == null ? null : DateTime.parse(json['verified_at'] as String),
        qrCodeToken: json['qr_code_token'] as String?,
        isActive: json['is_active'] as bool? ?? true,
        version: json['version'] as int? ?? 1,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: json['updated_at'] == null ? null : DateTime.parse(json['updated_at'] as String),
      );

  Map<String, dynamic> toApiJson() => {
        'name': name,
        'registration_number': registrationNumber,
        'vessel_class': vesselClass,
        'hull_material': hullMaterial,
        'color': color,
        'length_meters': lengthMeters,
        'beam_meters': beamMeters,
        'draft_meters': draftMeters,
        'year_built': yearBuilt,
        'engine_type': engineType,
        'engine_make': engineMake,
        'engine_model': engineModel,
        'engine_serial_number': engineSerialNumber,
        'engine_year': engineYear,
        'engine_horsepower': engineHorsepower,
        'fuel_capacity_liters': fuelCapacityLiters,
        'home_harbor_id': homeHarborId,
      };

  /// Creates the update payload with version for optimistic locking.
  Map<String, dynamic> toUpdateJson(BoatUpdate update) => {
        ...update.toJson(),
        'version': version,
      };

  Map<String, dynamic> toDbMap() => {
        'id': id,
        'owner_id': ownerId,
        'name': name,
        'registration_number': registrationNumber,
        'status': status,
        'vessel_class': vesselClass,
        'hull_material': hullMaterial,
        'color': color,
        'length_meters': lengthMeters,
        'beam_meters': beamMeters,
        'draft_meters': draftMeters,
        'year_built': yearBuilt,
        'engine_type': engineType,
        'engine_make': engineMake,
        'engine_model': engineModel,
        'engine_serial_number': engineSerialNumber,
        'engine_year': engineYear,
        'engine_horsepower': engineHorsepower,
        'fuel_capacity_liters': fuelCapacityLiters,
        'home_harbor_id': homeHarborId,
        'verification_status': verificationStatus,
        'verified_at': verifiedAt?.toIso8601String(),
        'qr_code_token': qrCodeToken,
        'is_active': isActive ? 1 : 0,
        'version': version,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt?.toIso8601String(),
      };

  factory Boat.fromDbMap(Map<String, dynamic> map) => Boat(
        id: map['id'] as int,
        ownerId: map['owner_id'] as int,
        name: map['name'] as String,
        registrationNumber: map['registration_number'] as String?,
        status: map['status'] as String? ?? 'registered',
        vesselClass: map['vessel_class'] as String?,
        hullMaterial: map['hull_material'] as String?,
        color: map['color'] as String?,
        lengthMeters: (map['length_meters'] as num?)?.toDouble(),
        beamMeters: (map['beam_meters'] as num?)?.toDouble(),
        draftMeters: (map['draft_meters'] as num?)?.toDouble(),
        yearBuilt: map['year_built'] as int?,
        engineType: map['engine_type'] as String?,
        engineMake: map['engine_make'] as String?,
        engineModel: map['engine_model'] as String?,
        engineSerialNumber: map['engine_serial_number'] as String?,
        engineYear: map['engine_year'] as int?,
        engineHorsepower: map['engine_horsepower'] as int?,
        fuelCapacityLiters: (map['fuel_capacity_liters'] as num?)?.toDouble(),
        homeHarborId: map['home_harbor_id'] as int?,
        verificationStatus: map['verification_status'] as String? ?? 'unverified',
        verifiedAt: map['verified_at'] == null ? null : DateTime.parse(map['verified_at'] as String),
        qrCodeToken: map['qr_code_token'] as String?,
        isActive: (map['is_active'] as int? ?? 1) == 1,
        version: map['version'] as int? ?? 1,
        createdAt: DateTime.parse(map['created_at'] as String),
        updatedAt: map['updated_at'] == null ? null : DateTime.parse(map['updated_at'] as String),
      );
}

/// Payload for creating or updating a boat. Mirrors BoatV2Create.
class BoatCreate {
  final String name;
  final String? registrationNumber;
  final String? vesselClass;
  final String? hullMaterial;
  final String? color;
  final double? lengthMeters;
  final double? beamMeters;
  final double? draftMeters;
  final int? yearBuilt;
  final String? engineType;
  final String? engineMake;
  final String? engineModel;
  final String? engineSerialNumber;
  final int? engineYear;
  final int? engineHorsepower;
  final double? fuelCapacityLiters;
  final int? homeHarborId;

  BoatCreate({
    required this.name,
    this.registrationNumber,
    this.vesselClass,
    this.hullMaterial,
    this.color,
    this.lengthMeters,
    this.beamMeters,
    this.draftMeters,
    this.yearBuilt,
    this.engineType,
    this.engineMake,
    this.engineModel,
    this.engineSerialNumber,
    this.engineYear,
    this.engineHorsepower,
    this.fuelCapacityLiters,
    this.homeHarborId,
  });

  Map<String, dynamic> toJson() => {
        'name': name,
        if (registrationNumber != null) 'registration_number': registrationNumber,
        if (vesselClass != null) 'vessel_class': vesselClass,
        if (hullMaterial != null) 'hull_material': hullMaterial,
        if (color != null) 'color': color,
        if (lengthMeters != null) 'length_meters': lengthMeters,
        if (beamMeters != null) 'beam_meters': beamMeters,
        if (draftMeters != null) 'draft_meters': draftMeters,
        if (yearBuilt != null) 'year_built': yearBuilt,
        if (engineType != null) 'engine_type': engineType,
        if (engineMake != null) 'engine_make': engineMake,
        if (engineModel != null) 'engine_model': engineModel,
        if (engineSerialNumber != null) 'engine_serial_number': engineSerialNumber,
        if (engineYear != null) 'engine_year': engineYear,
        if (engineHorsepower != null) 'engine_horsepower': engineHorsepower,
        if (fuelCapacityLiters != null) 'fuel_capacity_liters': fuelCapacityLiters,
        if (homeHarborId != null) 'home_harbor_id': homeHarborId,
      };
}

/// Payload for partial update. Mirrors BoatV2Update.
class BoatUpdate {
  final String? name;
  final String? registrationNumber;
  final String? vesselClass;
  final String? hullMaterial;
  final String? color;
  final double? lengthMeters;
  final double? beamMeters;
  final double? draftMeters;
  final int? yearBuilt;
  final String? engineType;
  final String? engineMake;
  final String? engineModel;
  final String? engineSerialNumber;
  final int? engineYear;
  final int? engineHorsepower;
  final double? fuelCapacityLiters;
  final int? homeHarborId;
  final bool? isActive;

  BoatUpdate({
    this.name,
    this.registrationNumber,
    this.vesselClass,
    this.hullMaterial,
    this.color,
    this.lengthMeters,
    this.beamMeters,
    this.draftMeters,
    this.yearBuilt,
    this.engineType,
    this.engineMake,
    this.engineModel,
    this.engineSerialNumber,
    this.engineYear,
    this.engineHorsepower,
    this.fuelCapacityLiters,
    this.homeHarborId,
    this.isActive,
  });

  Map<String, dynamic> toJson() => {
        if (name != null) 'name': name,
        if (registrationNumber != null) 'registration_number': registrationNumber,
        if (vesselClass != null) 'vessel_class': vesselClass,
        if (hullMaterial != null) 'hull_material': hullMaterial,
        if (color != null) 'color': color,
        if (lengthMeters != null) 'length_meters': lengthMeters,
        if (beamMeters != null) 'beam_meters': beamMeters,
        if (draftMeters != null) 'draft_meters': draftMeters,
        if (yearBuilt != null) 'year_built': yearBuilt,
        if (engineType != null) 'engine_type': engineType,
        if (engineMake != null) 'engine_make': engineMake,
        if (engineModel != null) 'engine_model': engineModel,
        if (engineSerialNumber != null) 'engine_serial_number': engineSerialNumber,
        if (engineYear != null) 'engine_year': engineYear,
        if (engineHorsepower != null) 'engine_horsepower': engineHorsepower,
        if (fuelCapacityLiters != null) 'fuel_capacity_liters': fuelCapacityLiters,
        if (homeHarborId != null) 'home_harbor_id': homeHarborId,
        if (isActive != null) 'is_active': isActive,
      };
}

/// Payload for status transition. Mirrors BoatStatusUpdate.
class BoatStatusChange {
  final String status;
  final String? reason;

  BoatStatusChange({required this.status, this.reason});

  Map<String, dynamic> toJson() => {'status': status, if (reason != null) 'reason': reason};
}

/// Boat status enum values matching backend BoatStatus.
class BoatStatusValues {
  static const registered = 'registered';
  static const active = 'active';
  static const inactive = 'inactive';
  static const maintenance = 'maintenance';
  static const emergency = 'emergency';
  static const lost = 'lost';
  static const damaged = 'damaged';
  static const decommissioned = 'decommissioned';

  static const all = {
    registered, active, inactive, maintenance,
    emergency, lost, damaged, decommissioned,
  };

  static const cannotStartTrip = {
    inactive, maintenance, emergency, lost, damaged, decommissioned,
  };
}
