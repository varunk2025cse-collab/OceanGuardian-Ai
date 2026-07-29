/// Mirrors backend BoatCrewMember (app/models/boat.py) + CrewMemberOut schema.
class BoatCrewMember {
  final int id;
  final int boatId;
  final int? userId;
  final String fullName;
  final String? phoneNumber;
  final String role;
  final bool isPrimaryContact;
  final bool isActive;
  final DateTime assignedAt;
  final DateTime? removedAt;
  final String? removalReason;

  BoatCrewMember({
    required this.id,
    required this.boatId,
    this.userId,
    required this.fullName,
    this.phoneNumber,
    required this.role,
    this.isPrimaryContact = false,
    this.isActive = true,
    required this.assignedAt,
    this.removedAt,
    this.removalReason,
  });

  bool get isCaptain => role == 'captain';

  factory BoatCrewMember.fromJson(Map<String, dynamic> json) => BoatCrewMember(
        id: json['id'] as int,
        boatId: json['boat_id'] as int,
        userId: json['user_id'] as int?,
        fullName: json['full_name'] as String,
        phoneNumber: json['phone_number'] as String?,
        role: json['role'] as String,
        isPrimaryContact: json['is_primary_contact'] as bool? ?? false,
        isActive: json['is_active'] as bool? ?? true,
        assignedAt: DateTime.parse(json['assigned_at'] as String),
        removedAt: json['removed_at'] == null ? null : DateTime.parse(json['removed_at'] as String),
        removalReason: json['removal_reason'] as String?,
      );

  Map<String, dynamic> toApiJson() => {
        if (userId != null) 'user_id': userId,
        'full_name': fullName,
        if (phoneNumber != null) 'phone_number': phoneNumber,
        'role': role,
        'is_primary_contact': isPrimaryContact,
      };

  Map<String, dynamic> toDbMap() => {
        'id': id,
        'boat_id': boatId,
        'user_id': userId,
        'full_name': fullName,
        'phone_number': phoneNumber,
        'role': role,
        'is_primary_contact': isPrimaryContact ? 1 : 0,
        'is_active': isActive ? 1 : 0,
        'assigned_at': assignedAt.toIso8601String(),
        'removed_at': removedAt?.toIso8601String(),
        'removal_reason': removalReason,
      };

  factory BoatCrewMember.fromDbMap(Map<String, dynamic> map) => BoatCrewMember(
        id: map['id'] as int,
        boatId: map['boat_id'] as int,
        userId: map['user_id'] as int?,
        fullName: map['full_name'] as String,
        phoneNumber: map['phone_number'] as String?,
        role: map['role'] as String,
        isPrimaryContact: (map['is_primary_contact'] as int? ?? 0) == 1,
        isActive: (map['is_active'] as int? ?? 1) == 1,
        assignedAt: DateTime.parse(map['assigned_at'] as String),
        removedAt: map['removed_at'] == null ? null : DateTime.parse(map['removed_at'] as String),
        removalReason: map['removal_reason'] as String?,
      );
}

/// Valid crew role constants matching backend VALID_CREW_ROLES.
class CrewRoles {
  static const captain = 'captain';
  static const navigator = 'navigator';
  static const engineer = 'engineer';
  static const deckhand = 'deckhand';
  static const lookout = 'lookout';
  static const medic = 'medic';
  static const owner = 'owner';
  static const other = 'other';

  static const all = {
    captain, navigator, engineer, deckhand,
    lookout, medic, owner, other,
  };
}
