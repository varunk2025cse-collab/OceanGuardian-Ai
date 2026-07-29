/// Mirrors backend BoatEquipmentItem (app/models/boat.py) + EquipmentItemOut schema.
class BoatEquipmentItem {
  final int id;
  final int boatId;
  final String category;
  final String itemName;
  final int quantity;
  final String condition;
  final DateTime? lastCheckedAt;
  final DateTime? expiryDate;
  final String? notes;
  final bool isMandatory;
  final DateTime createdAt;

  BoatEquipmentItem({
    required this.id,
    required this.boatId,
    required this.category,
    required this.itemName,
    this.quantity = 1,
    this.condition = 'good',
    this.lastCheckedAt,
    this.expiryDate,
    this.notes,
    this.isMandatory = false,
    required this.createdAt,
  });

  bool get isUsable => condition == 'good' || condition == 'fair';
  bool get needsReplacement => condition == 'poor' || condition == 'missing';
  bool get isExpired {
    if (expiryDate == null) return false;
    return expiryDate!.isBefore(DateTime.now());
  }

  factory BoatEquipmentItem.fromJson(Map<String, dynamic> json) => BoatEquipmentItem(
        id: json['id'] as int,
        boatId: json['boat_id'] as int,
        category: json['category'] as String,
        itemName: json['item_name'] as String,
        quantity: json['quantity'] as int? ?? 1,
        condition: json['condition'] as String? ?? 'good',
        lastCheckedAt: json['last_checked_at'] == null ? null : DateTime.parse(json['last_checked_at'] as String),
        expiryDate: json['expiry_date'] == null ? null : DateTime.parse(json['expiry_date'] as String),
        notes: json['notes'] as String?,
        isMandatory: json['is_mandatory'] as bool? ?? false,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  Map<String, dynamic> toApiJson() => {
        'category': category,
        'item_name': itemName,
        'quantity': quantity,
        'condition': condition,
        if (lastCheckedAt != null) 'last_checked_at': lastCheckedAt!.toIso8601String().substring(0, 10),
        if (expiryDate != null) 'expiry_date': expiryDate!.toIso8601String().substring(0, 10),
        if (notes != null) 'notes': notes,
        'is_mandatory': isMandatory,
      };

  Map<String, dynamic> toDbMap() => {
        'id': id,
        'boat_id': boatId,
        'category': category,
        'item_name': itemName,
        'quantity': quantity,
        'condition': condition,
        'last_checked_at': lastCheckedAt?.toIso8601String().substring(0, 10),
        'expiry_date': expiryDate?.toIso8601String().substring(0, 10),
        'notes': notes,
        'is_mandatory': isMandatory ? 1 : 0,
        'created_at': createdAt.toIso8601String(),
      };

  factory BoatEquipmentItem.fromDbMap(Map<String, dynamic> map) => BoatEquipmentItem(
        id: map['id'] as int,
        boatId: map['boat_id'] as int,
        category: map['category'] as String,
        itemName: map['item_name'] as String,
        quantity: map['quantity'] as int? ?? 1,
        condition: map['condition'] as String? ?? 'good',
        lastCheckedAt: map['last_checked_at'] == null ? null : DateTime.parse('${map['last_checked_at']}T00:00:00'),
        expiryDate: map['expiry_date'] == null ? null : DateTime.parse('${map['expiry_date']}T00:00:00'),
        notes: map['notes'] as String?,
        isMandatory: (map['is_mandatory'] as int? ?? 0) == 1,
        createdAt: DateTime.parse(map['created_at'] as String),
      );
}

/// Equipment category constants matching backend VALID_EQUIPMENT_CATEGORIES.
class EquipmentCategories {
  static const lifeSaving = 'life_saving';
  static const fireSafety = 'fire_safety';
  static const navigation = 'navigation';
  static const communication = 'communication';
  static const firstAid = 'first_aid';
  static const fishingGear = 'fishing_gear';
  static const engineSpare = 'engine_spare';
  static const other = 'other';

  static const all = {
    lifeSaving, fireSafety, navigation, communication,
    firstAid, fishingGear, engineSpare, other,
  };

  /// Equipment categories the Readiness Service checks.
  static const mandatoryForTrip = {
    lifeSaving, fireSafety, communication, firstAid, navigation,
  };
}
