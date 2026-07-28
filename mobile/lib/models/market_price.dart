class MarketPriceInfo {
  final int id;
  final String species;
  final String marketName;
  final String harborRegion;
  final double pricePerKg;
  final String currency;
  final String priceDate;

  MarketPriceInfo({
    required this.id,
    required this.species,
    required this.marketName,
    required this.harborRegion,
    required this.pricePerKg,
    required this.currency,
    required this.priceDate,
  });

  factory MarketPriceInfo.fromJson(Map<String, dynamic> json) => MarketPriceInfo(
        id: json['id'] as int,
        species: json['species'] as String,
        marketName: json['market_name'] as String,
        harborRegion: json['harbor_region'] as String,
        pricePerKg: (json['price_per_kg'] as num).toDouble(),
        currency: json['currency'] as String,
        priceDate: json['price_date'] as String,
      );

  Map<String, dynamic> toCacheJson() => {
        'id': id,
        'species': species,
        'market_name': marketName,
        'harbor_region': harborRegion,
        'price_per_kg': pricePerKg,
        'currency': currency,
        'price_date': priceDate,
      };
}
