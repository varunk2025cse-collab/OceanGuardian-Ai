import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import 'auth_service.dart';

/// Thin wrapper around `http` that:
///  - prefixes every call with the API base URL
///  - attaches the bearer token automatically
///  - retries once after a silent token refresh on a 401
///  - throws ApiException with a readable message on failure
///
/// Every screen/service calls through here rather than using `http`
/// directly, so token handling and error shape stay consistent everywhere.
class ApiException implements Exception {
  final int? statusCode;
  final String message;
  ApiException(this.message, {this.statusCode});
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient._internal();
  static final ApiClient instance = ApiClient._internal();

  Uri _uri(String path) => Uri.parse('${ApiConfig.apiV1}$path');
  Uri _uriV2(String path) => Uri.parse('${ApiConfig.baseUrl}/api/v2$path');

  Map<String, String> _headers({bool auth = true}) {
    final headers = {'Content-Type': 'application/json'};
    if (auth && AuthService.instance.accessToken != null) {
      headers['Authorization'] = 'Bearer ${AuthService.instance.accessToken}';
    }
    return headers;
  }

  dynamic _decode(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    }
    String message = 'Request failed (${response.statusCode})';
    try {
      final body = jsonDecode(response.body);
      if (body is Map && body['detail'] != null) {
        message = body['detail'].toString();
      }
    } catch (_) {
      // non-JSON error body; keep the generic message
    }
    throw ApiException(message, statusCode: response.statusCode);
  }

  /// POST without auth header (register/login/refresh).
  Future<Map<String, dynamic>> postPublic(String path, Map<String, dynamic> body) async {
    final response = await http
        .post(_uri(path), headers: _headers(auth: false), body: jsonEncode(body))
        .timeout(const Duration(seconds: 15));
    return _decode(response) as Map<String, dynamic>;
  }

  Future<dynamic> get(String path) => _withRetry(() async {
        final response = await http.get(_uri(path), headers: _headers()).timeout(const Duration(seconds: 15));
        return _decode(response);
      });

  /// Same as [get] but against the /api/v2 surface (safety state, tracking
  /// fleet, incidents, AI) rather than /api/v1.
  Future<dynamic> getV2(String path) => _withRetry(() async {
        final response = await http.get(_uriV2(path), headers: _headers()).timeout(const Duration(seconds: 15));
        return _decode(response);
      });

  Future<dynamic> post(String path, Map<String, dynamic> body) => _withRetry(() async {
        final response = await http
            .post(_uri(path), headers: _headers(), body: jsonEncode(body))
            .timeout(const Duration(seconds: 15));
        return _decode(response);
      });

  Future<dynamic> patch(String path, Map<String, dynamic> body) => _withRetry(() async {
        final response = await http
            .patch(_uri(path), headers: _headers(), body: jsonEncode(body))
            .timeout(const Duration(seconds: 15));
        return _decode(response);
      });

  /// On a 401, attempts exactly one silent refresh-and-retry. If the
  /// refresh token is also dead, surfaces the original 401 so the UI can
  /// route to the login screen.
  Future<T> _withRetry<T>(Future<T> Function() attempt) async {
    try {
      return await attempt();
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        final refreshed = await AuthService.instance.tryRefreshToken();
        if (refreshed) return attempt();
      }
      rethrow;
    }
  }
}
