import 'dart:convert';

import 'package:http/http.dart' as http;

import '../account/api_config.dart';

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

/// Calls Chat AI's stateless tier (POST /chat) - no login required, matching
/// the backend's "browsing/asking never needs an account" pattern. Fully
/// stateless: each question is sent with no conversation history attached,
/// matching the backend's own statelessness (see chat_ai.py's docstring) -
/// the personalized tier that would need history isn't built yet.
class ChatRepository {
  ChatRepository({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<ChatAnswer> ask(String question) async {
    final response = await _client.post(
      Uri.parse('$apiBaseUrl/chat'),
      headers: {'Content-Type': 'application/json'},
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
