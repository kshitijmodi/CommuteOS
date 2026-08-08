import 'dart:convert';

import 'package:http/http.dart' as http;

import '../account/api_config.dart';
import '../account/auth_repository.dart';

/// One answer from Chat AI's stateless tier (see backend/app/chat_ai.py) -
/// [stationName]/[agency] are non-null only when the backend actually
/// resolved a real station and fetched real live arrivals for it; null for
/// a clarifying/refusal response (no match, ambiguous, out of scope) so
/// the UI can tell the two cases apart if it ever needs to.
class ChatAnswer {
  const ChatAnswer({required this.text, this.stationName, this.agency});

  final String text;
  final String? stationName;
  final String? agency;

  factory ChatAnswer.fromJson(Map<String, dynamic> json) {
    return ChatAnswer(
      text: json['answer'] as String,
      stationName: json['station_name'] as String?,
      agency: json['agency'] as String?,
    );
  }
}

class ChatException implements Exception {
  ChatException(this.message);
  final String message;

  @override
  String toString() => message;
}

/// Calls Chat AI (POST /chat) - one endpoint, both tiers. Login is
/// optional, not required, matching the backend's "browsing/asking never
/// needs an account" pattern: if the user happens to be logged in, this
/// attaches their token so a personal-sounding question ("what do I
/// usually take from here") can use the personalized tier; a logged-out
/// caller still gets the real stateless tier, never an error. Fully
/// stateless in the conversational sense either way: each question is
/// sent with no message history attached, matching the backend's own
/// statelessness (see chat_ai.py's docstring).
class ChatRepository {
  ChatRepository({AuthRepository? authRepository, http.Client? client})
    : _authRepository = authRepository ?? AuthRepository(),
      _client = client ?? http.Client();

  final AuthRepository _authRepository;
  final http.Client _client;

  Future<ChatAnswer> ask(String question) async {
    final token = await _authRepository.getToken();
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };

    final response = await _client.post(
      Uri.parse('$apiBaseUrl/chat'),
      headers: headers,
      body: jsonEncode({'question': question}),
    );

    if (response.statusCode != 200) {
      throw ChatException(_extractErrorDetail(response));
    }

    return ChatAnswer.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  String _extractErrorDetail(http.Response response) {
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final detail = body['detail'];
      if (detail is String) return detail;
    } catch (_) {
      // Not JSON - fall through to the default message.
    }
    return 'Could not reach the chat assistant. Try again later.';
  }
}
