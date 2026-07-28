import '../models/weather_alert.dart';
import '../models/market_price.dart';
import '../models/govt_scheme.dart';
import '../models/family_status.dart';
import 'api_client.dart';
import 'local_db_service.dart';

/// Cache-first reads for the read-mostly screens (Weather, Market,
/// Schemes, Family). Every method:
///   1. Tries a live network call and refreshes the cache on success.
///   2. Falls back to whatever is cached if the network call fails.
/// The screen gets data either way, plus a `fromCache` + `asOf` flag so it
/// can show "Last updated 3 hours ago (offline)" instead of pretending
/// stale data is live.
class ReferenceResult<T> {
  final List<T> items;
  final bool fromCache;
  final DateTime? asOf;
  ReferenceResult(this.items, {required this.fromCache, this.asOf});
}

class ReferenceDataService {
  ReferenceDataService._internal();
  static final ReferenceDataService instance = ReferenceDataService._internal();

  Future<ReferenceResult<WeatherAlertInfo>> weatherAlerts({double? lat, double? lon}) async {
    try {
      final path = (lat != null && lon != null) ? '/weather/active?lat=$lat&lon=$lon' : '/weather/active';
      final data = await ApiClient.instance.get(path) as List;
      await LocalDbService.instance.putCache('weather_active', data);
      return ReferenceResult(data.map((e) => WeatherAlertInfo.fromJson(e)).toList(), fromCache: false);
    } catch (_) {
      final cached = await LocalDbService.instance.getCache('weather_active');
      if (cached == null) return ReferenceResult([], fromCache: true);
      final (data, asOf) = cached;
      return ReferenceResult(
        (data as List).map((e) => WeatherAlertInfo.fromJson(e)).toList(),
        fromCache: true,
        asOf: asOf,
      );
    }
  }

  Future<ReferenceResult<MarketPriceInfo>> marketPrices({String? region}) async {
    try {
      final path = region != null ? '/market/prices?region=$region' : '/market/prices';
      final data = await ApiClient.instance.get(path) as List;
      await LocalDbService.instance.putCache('market_prices', data);
      return ReferenceResult(data.map((e) => MarketPriceInfo.fromJson(e)).toList(), fromCache: false);
    } catch (_) {
      final cached = await LocalDbService.instance.getCache('market_prices');
      if (cached == null) return ReferenceResult([], fromCache: true);
      final (data, asOf) = cached;
      return ReferenceResult(
        (data as List).map((e) => MarketPriceInfo.fromJson(e)).toList(),
        fromCache: true,
        asOf: asOf,
      );
    }
  }

  Future<ReferenceResult<GovtSchemeInfo>> govtSchemes() async {
    try {
      final data = await ApiClient.instance.get('/schemes/') as List;
      await LocalDbService.instance.putCache('govt_schemes', data);
      return ReferenceResult(data.map((e) => GovtSchemeInfo.fromJson(e)).toList(), fromCache: false);
    } catch (_) {
      final cached = await LocalDbService.instance.getCache('govt_schemes');
      if (cached == null) return ReferenceResult([], fromCache: true);
      final (data, asOf) = cached;
      return ReferenceResult(
        (data as List).map((e) => GovtSchemeInfo.fromJson(e)).toList(),
        fromCache: true,
        asOf: asOf,
      );
    }
  }

  Future<ReferenceResult<FishermanStatus>> familyStatus() async {
    try {
      final data = await ApiClient.instance.get('/family/status') as List;
      await LocalDbService.instance.putCache('family_status', data);
      return ReferenceResult(data.map((e) => FishermanStatus.fromJson(e)).toList(), fromCache: false);
    } catch (_) {
      final cached = await LocalDbService.instance.getCache('family_status');
      if (cached == null) return ReferenceResult([], fromCache: true);
      final (data, asOf) = cached;
      return ReferenceResult(
        (data as List).map((e) => FishermanStatus.fromJson(e)).toList(),
        fromCache: true,
        asOf: asOf,
      );
    }
  }

  Future<void> linkFisherman({required String phoneNumber, String? relation}) {
    return ApiClient.instance.post('/family/link', {
      'fisherman_phone_number': phoneNumber,
      'relation': relation,
    });
  }
}
