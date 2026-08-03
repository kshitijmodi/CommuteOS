import 'dart:convert';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'auth_repository.dart';

/// Thin seam around the two FirebaseMessaging calls this service needs -
/// lets tests fake permission/token behavior with plain Dart instead of
/// mocking the Firebase SDK's platform channels directly.
abstract class PushTokenProvider {
  Future<bool> requestPermission();
  Future<String?> getToken();
}

class _FirebaseMessagingTokenProvider implements PushTokenProvider {
  const _FirebaseMessagingTokenProvider();

  @override
  Future<bool> requestPermission() async {
    final settings = await FirebaseMessaging.instance.requestPermission();
    return settings.authorizationStatus != AuthorizationStatus.denied;
  }

  @override
  Future<String?> getToken() => FirebaseMessaging.instance.getToken();
}

/// Registers this device for proactive server-push commute notifications
/// (the scheduled backend job in backend/app/jobs/send_commute_notifications.py
/// that runs the real decision engine + LLM phrasing, unlike the old
/// fixed-time local reminder it replaces).
///
/// Real Firebase Cloud Messaging registration - requests the Android 13+
/// runtime notification permission, then gets this device's real FCM
/// token and sends it to the backend, which uses it to actually deliver
/// pushes (see backend/app/notify_service.py).
class PushRegistrationService {
  PushRegistrationService({
    AuthRepository? authRepository,
    http.Client? client,
    PushTokenProvider? tokenProvider,
  }) : _authRepository = authRepository ?? AuthRepository(),
       _client = client ?? http.Client(),
       _tokenProvider = tokenProvider ?? const _FirebaseMessagingTokenProvider();

  final AuthRepository _authRepository;
  final http.Client _client;
  final PushTokenProvider _tokenProvider;

  /// Returns true if registration succeeded (permission granted, token
  /// obtained, and sent to the backend). False if the user isn't logged
  /// in - push notifications require an account, same as trip logging/
  /// recommendations, since the backend needs somewhere to store the
  /// token against - or if the user declines the notification permission,
  /// or if no token could be obtained.
  Future<bool> register() async {
    final authToken = await _authRepository.getToken();
    if (authToken == null) return false;

    final granted = await _tokenProvider.requestPermission();
    if (!granted) return false;

    final pushToken = await _tokenProvider.getToken();
    if (pushToken == null) return false;

    final response = await _client.put(
      Uri.parse('$apiBaseUrl/users/me/fcm-token'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $authToken',
      },
      body: jsonEncode({'fcm_token': pushToken}),
    );

    return response.statusCode == 200;
  }
}
