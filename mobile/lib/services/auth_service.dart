import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/user.dart';
import 'api_client.dart';

/// Owns the session: tokens + the logged-in user, persisted so the app
/// stays logged in across restarts (a fisherman should not have to log
/// back in with a signal-less phone mid-trip).
///
/// Security note (docs/SECURITY.md, V2 core build Phase 21): access/refresh
/// tokens are the actual bearer credentials — a stolen refresh token is a
/// stolen session — so they live in flutter_secure_storage (Android
/// Keystore / iOS Keychain-backed), not plain shared_preferences. The
/// non-sensitive cached user profile JSON stays in shared_preferences;
/// there's nothing to protect there beyond what the token itself already
/// gates.
class AuthService {
  AuthService._internal();
  static final AuthService instance = AuthService._internal();

  static const _secureStorage = FlutterSecureStorage();
  static const _kAccessToken = 'og_access_token';
  static const _kRefreshToken = 'og_refresh_token';
  static const _kUserJson = 'og_user_json';

  AppUser? currentUser;
  String? _accessToken;
  String? _refreshToken;

  Future<void> loadSession() async {
    _accessToken = await _secureStorage.read(key: _kAccessToken);
    _refreshToken = await _secureStorage.read(key: _kRefreshToken);
    final prefs = await SharedPreferences.getInstance();
    final userJson = prefs.getString(_kUserJson);
    if (userJson != null) {
      currentUser = AppUser.fromJson(jsonDecode(userJson) as Map<String, dynamic>);
    }
  }

  bool get isLoggedIn => _accessToken != null && currentUser != null;
  String? get accessToken => _accessToken;
  String? get refreshToken => _refreshToken;

  Future<void> _persist(Map<String, dynamic> tokenPair) async {
    _accessToken = tokenPair['access_token'] as String;
    _refreshToken = tokenPair['refresh_token'] as String;
    currentUser = AppUser.fromJson(tokenPair['user'] as Map<String, dynamic>);

    await _secureStorage.write(key: _kAccessToken, value: _accessToken!);
    await _secureStorage.write(key: _kRefreshToken, value: _refreshToken!);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kUserJson, jsonEncode(tokenPair['user']));
  }

  Future<void> register({
    required String phoneNumber,
    required String password,
    required String fullName,
    required String role,
    required String preferredLanguage,
    String? boatName,
    String? homeHarbor,
    String? emergencyContactName,
    String? emergencyContactPhone,
  }) async {
    final body = {
      'phone_number': phoneNumber,
      'password': password,
      'full_name': fullName,
      'role': role,
      'preferred_language': preferredLanguage,
      if (boatName != null) 'boat_name': boatName,
      if (homeHarbor != null) 'home_harbor': homeHarbor,
      if (emergencyContactName != null) 'emergency_contact_name': emergencyContactName,
      if (emergencyContactPhone != null) 'emergency_contact_phone': emergencyContactPhone,
    };
    final result = await ApiClient.instance.postPublic('/auth/register', body);
    await _persist(result);
  }

  Future<void> login({required String phoneNumber, required String password}) async {
    final result = await ApiClient.instance.postPublic('/auth/login', {
      'phone_number': phoneNumber,
      'password': password,
    });
    await _persist(result);
  }

  Future<bool> tryRefreshToken() async {
    if (_refreshToken == null) return false;
    try {
      final result = await ApiClient.instance.postPublic('/auth/refresh', {
        'refresh_token': _refreshToken,
      });
      await _persist(result);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<void> logout() async {
    await _secureStorage.delete(key: _kAccessToken);
    await _secureStorage.delete(key: _kRefreshToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kUserJson);
    _accessToken = null;
    _refreshToken = null;
    currentUser = null;
  }
}
