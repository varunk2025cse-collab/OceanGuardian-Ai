class GovtSchemeInfo {
  final int id;
  final String title;
  final String category;
  final String region;
  final String description;
  final String eligibility;
  final String howToApply;
  final String? contactInfo;

  GovtSchemeInfo({
    required this.id,
    required this.title,
    required this.category,
    required this.region,
    required this.description,
    required this.eligibility,
    required this.howToApply,
    this.contactInfo,
  });

  factory GovtSchemeInfo.fromJson(Map<String, dynamic> json) => GovtSchemeInfo(
        id: json['id'] as int,
        title: json['title'] as String,
        category: json['category'] as String,
        region: json['region'] as String,
        description: json['description'] as String,
        eligibility: json['eligibility'] as String,
        howToApply: json['how_to_apply'] as String,
        contactInfo: json['contact_info'] as String?,
      );

  Map<String, dynamic> toCacheJson() => {
        'id': id,
        'title': title,
        'category': category,
        'region': region,
        'description': description,
        'eligibility': eligibility,
        'how_to_apply': howToApply,
        'contact_info': contactInfo,
      };
}
