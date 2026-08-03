import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'auth_repository.dart';

/// Registers this device for proactive server-push commute notifications
/// (the scheduled backend job in backend/app/jobs/send_commute_notifications.py
/// that runs the real decision engine + LLM phrasing, unlike the old
/// fixed-time local reminder it replaces).
///
/// STUB: [_obtainPushToken] returns a fake local token rather than a real
/// Firebase Cloud Messaging one - actually receiving a push requires a
/// real Firebase project (account-creation step only the user can do,
/// same as the earlier Neon/Render setup), so this pipeline is built and
/// wired end-to-end first with a stub token, swapped for real FCM
/// registration once project credentials exist. Everything downstream
/// (the backend's fcm_token column, the notification job) already treats
/// this as an opaque string, so nothing else needs to change when it is.
class PushRegistrationService {
  PushRegistrationService({AuthRepository? authRepository, http.Client? client})
    : _authRepository = authRepository ?? AuthRepository(),
      _client = client ?? http.Client();

  final AuthRepository _authRepository;
  final http.Client _client;

  /// Returns true if registration succeeded (token obtained and sent to
  /// the backend). False if the user isn't logged in - push notifications
  /// require an account, same as trip logging/recommendations, since the
  /// backend needs somewhere to store the token against.
  Future<bool> register() async {
    final token = await _authRepository.getToken();
    if (token == null) return false;

    final pushToken = await _obtainPushToken();

    final response = await _client.put(
      Uri.parse('$apiBaseUrl/users/me/fcm-token'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({'fcm_token': pushToken}),
    );

    return response.statusCode == 200;
  }

  /// STUB - see class docstring. Replace with real FCM token retrieval
  /// (FirebaseMessaging.instance.getToken()) once a Firebase project
  /// exists.
  Future<String> _obtainPushToken() async {
    return 'stub-token-${DateTime.now().microsecondsSinceEpoch}';
  }
}
