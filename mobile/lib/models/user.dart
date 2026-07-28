class AppUser {
  final int id;
  final String phoneNumber;
  final String fullName;
  final String role; // "fisherman" | "family"
  final String preferredLanguage;
  final String? boatName;
  final String? homeHarbor;

  AppUser({
    required this.id,
    required this.phoneNumber,
    required this.fullName,
    required this.role,
    required this.preferredLanguage,
    this.boatName,
    this.homeHarbor,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as int,
        phoneNumber: json['phone_number'] as String,
        fullName: json['full_name'] as String,
        role: json['role'] as String,
        preferredLanguage: json['preferred_language'] as String,
        boatName: json['boat_name'] as String?,
        homeHarbor: json['home_harbor'] as String?,
      );

  bool get isFisherman => role == 'fisherman';
}
