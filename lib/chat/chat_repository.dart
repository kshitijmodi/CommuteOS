import 'dart:convert';

import 'package:http/http.dart' as http;

import '../account/api_config.dart';
import '../account/auth_repository.dart';
import 'chat_session_store.dart';
import 'location_service.dart';

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
/// caller still gets the real stateless tier, never an error.
///
/// Real conversation memory (added 2026-08-08, see
/// backend/app/chat_ai.py's module docstring): every question used to be
/// answered with zero memory of the conversation so far - found live,
/// after it read to a real user as the app "not maintaining context."
/// Every call now sends the same persistent session id (see
/// ChatSessionStore) so a follow-up question ("what about the other
/// direction") can be resolved against what was actually asked and
/// answered before it, server-side.
///
/// Real location on every question (broadened 2026-08-09): previously
/// only asked for GPS when the question itself contained "nearest"-style
/// wording - a real user expectation found live: a station-less question
/// with no prior conversation context should still be answerable from
/// wherever the user actually is, not just ones that happen to say
/// "nearest." Real coordinates are now attached to every call once
/// location permission is available (the backend only ever uses them as
/// a fallback tier - never overriding a station the question or
/// conversation history already named, see answer_question's docstring).
/// The first-ever chat question triggers Android's real permission
/// prompt if not already granted/denied; every call after that is fast
/// (no re-prompt) regardless of the user's choice.
class ChatRepository {
  ChatRepository({
    AuthRepository? authRepository,
    http.Client? client,
    LocationService? locationService,
    ChatSessionStore? sessionStore,
  }) : _authRepository = authRepository ?? AuthRepository(),
       _client = client ?? http.Client(),
       _locationService = locationService ?? LocationService(),
       _sessionStore = sessionStore ?? ChatSessionStore();

  final AuthRepository _authRepository;
  final http.Client _client;
  final LocationService _locationService;
  final ChatSessionStore _sessionStore;

  Future<ChatAnswer> ask(String question) async {
    final token = await _authRepository.getToken();
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };

    final location = await _locationService.getCurrentLocation();
    final lat = location.latitude;
    final lng = location.longitude;

    final sessionId = await _sessionStore.getSessionId();

    final response = await _client.post(
      Uri.parse('$apiBaseUrl/chat'),
      headers: headers,
      body: jsonEncode({
        'question': question,
        if (lat != null && lng != null) 'lat': lat,
        if (lat != null && lng != null) 'lng': lng,
        'session_id': sessionId,
      }),
    );

    if (response.statusCode != 200) {
      throw ChatException(_extractErrorDetail(response));
    }

    return ChatAnswer.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  /// Starts a genuinely new conversation - see
  /// ChatSessionStore.startNewSession. Exposed here so ChatScreen's "New
  /// chat" action doesn't need to know the session store exists at all.
  Future<void> startNewConversation() => _sessionStore.startNewSession();

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
