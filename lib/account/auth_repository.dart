import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'api_config.dart';

/// Handles signup/login against the backend and persists the resulting
/// access token on-device. Browsing/favoriting never requires this - only
/// trip logging (see TripLogger) checks whether a token exists.
class AuthRepository {
  AuthRepository({http.Client? client}) : _client = client ?? http.Client();

  static const _tokenKey = 'auth_access_token';

  final http.Client _client;

  Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
  }

  Future<bool> isLoggedIn() async => (await getToken()) != null;

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  /// Throws [AuthException] with a user-facing message on failure.
  Future<void> signup(String email, String password) async {
    final response = await _client.post(
      Uri.parse('$apiBaseUrl/auth/signup'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );

    if (response.statusCode != 201) {
      throw AuthException(_extractErrorDetail(response, 'Signup failed'));
    }

    // Signing up doesn't log you in server-side - do that ourselves so the
    // user isn't asked to immediately re-enter what they just typed.
    await login(email, password);
  }

  Future<void> login(String email, String password) async {
    final response = await _client.post(
      Uri.parse('$apiBaseUrl/auth/login'),
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: {'username': email, 'password': password},
    );

    if (response.statusCode != 200) {
      throw AuthException(_extractErrorDetail(response, 'Login failed'));
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final token = body['access_token'] as String;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  String _extractErrorDetail(http.Response response, String fallback) {
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final detail = body['detail'];
      if (detail is String) return detail;
    } catch (_) {
      // Response wasn't JSON (e.g. the server is unreachable and some
      // proxy/error page came back instead) - fall through to the default.
    }
    return fallback;
  }
}

class AuthException implements Exception {
  AuthException(this.message);
  final String message;

  @override
  String toString() => message;
}
