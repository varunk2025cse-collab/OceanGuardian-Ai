/// Mirrors backend BoatDocument (app/models/boat.py) + DocumentOut schema.
class BoatDocument {
  final int id;
  final int boatId;
  final String documentType;
  final String? documentNumber;
  final String? issuingAuthority;
  final DateTime? issueDate;
  final DateTime? expiryDate;
  final String? fileUrl;
  final String? fileHash;
  final bool isVerified;
  final DateTime? verifiedAt;
  final String? notes;
  final DateTime createdAt;

  BoatDocument({
    required this.id,
    required this.boatId,
    required this.documentType,
    this.documentNumber,
    this.issuingAuthority,
    this.issueDate,
    this.expiryDate,
    this.fileUrl,
    this.fileHash,
    this.isVerified = false,
    this.verifiedAt,
    this.notes,
    required this.createdAt,
  });

  bool get isExpired {
    if (expiryDate == null) return false;
    return expiryDate!.isBefore(DateTime.now());
  }

  int? get daysUntilExpiry {
    if (expiryDate == null) return null;
    return DateTime.now().difference(expiryDate!).inDays.abs();
  }

  factory BoatDocument.fromJson(Map<String, dynamic> json) => BoatDocument(
        id: json['id'] as int,
        boatId: json['boat_id'] as int,
        documentType: json['document_type'] as String,
        documentNumber: json['document_number'] as String?,
        issuingAuthority: json['issuing_authority'] as String?,
        issueDate: json['issue_date'] == null ? null : DateTime.parse(json['issue_date'] as String),
        expiryDate: json['expiry_date'] == null ? null : DateTime.parse(json['expiry_date'] as String),
        fileUrl: json['file_url'] as String?,
        fileHash: json['file_hash'] as String?,
        isVerified: json['is_verified'] as bool? ?? false,
        verifiedAt: json['verified_at'] == null ? null : DateTime.parse(json['verified_at'] as String),
        notes: json['notes'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  Map<String, dynamic> toApiJson() => {
        'document_type': documentType,
        if (documentNumber != null) 'document_number': documentNumber,
        if (issuingAuthority != null) 'issuing_authority': issuingAuthority,
        if (issueDate != null) 'issue_date': issueDate!.toIso8601String().substring(0, 10),
        if (expiryDate != null) 'expiry_date': expiryDate!.toIso8601String().substring(0, 10),
        if (fileUrl != null) 'file_url': fileUrl,
        if (fileHash != null) 'file_hash': fileHash,
        if (notes != null) 'notes': notes,
      };

  Map<String, dynamic> toDbMap() => {
        'id': id,
        'boat_id': boatId,
        'document_type': documentType,
        'document_number': documentNumber,
        'issuing_authority': issuingAuthority,
        'issue_date': issueDate?.toIso8601String().substring(0, 10),
        'expiry_date': expiryDate?.toIso8601String().substring(0, 10),
        'file_url': fileUrl,
        'file_hash': fileHash,
        'is_verified': isVerified ? 1 : 0,
        'verified_at': verifiedAt?.toIso8601String(),
        'notes': notes,
        'created_at': createdAt.toIso8601String(),
      };

  factory BoatDocument.fromDbMap(Map<String, dynamic> map) => BoatDocument(
        id: map['id'] as int,
        boatId: map['boat_id'] as int,
        documentType: map['document_type'] as String,
        documentNumber: map['document_number'] as String?,
        issuingAuthority: map['issuing_authority'] as String?,
        issueDate: map['issue_date'] == null ? null : DateTime.parse('${map['issue_date']}T00:00:00'),
        expiryDate: map['expiry_date'] == null ? null : DateTime.parse('${map['expiry_date']}T00:00:00'),
        fileUrl: map['file_url'] as String?,
        fileHash: map['file_hash'] as String?,
        isVerified: (map['is_verified'] as int? ?? 0) == 1,
        verifiedAt: map['verified_at'] == null ? null : DateTime.parse(map['verified_at'] as String),
        notes: map['notes'] as String?,
        createdAt: DateTime.parse(map['created_at'] as String),
      );
}

/// Valid document type constants matching backend VALID_DOCUMENT_TYPES.
class DocumentTypes {
  static const registrationCertificate = 'registration_certificate';
  static const fishingLicense = 'fishing_license';
  static const insurancePolicy = 'insurance_policy';
  static const inspectionCertificate = 'inspection_certificate';
  static const seaworthinessCertificate = 'seaworthiness_certificate';
  static const crewList = 'crew_list';
  static const other = 'other';

  static const all = {
    registrationCertificate, fishingLicense, insurancePolicy,
    inspectionCertificate, seaworthinessCertificate, crewList, other,
  };

  static const mandatoryForTrip = {
    registrationCertificate, fishingLicense, insurancePolicy,
  };
}
