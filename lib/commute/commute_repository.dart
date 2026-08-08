import 'dart:convert';

import 'package:http/http.dart' as http;

import '../account/api_config.dart';
import '../account/auth_repository.dart';

/// Commute AI's real-time recommendation for a specific station - see
/// backend/app/commute_engine.py. Fetched fresh every time the client
/// asks (no caching), since it's only meaningful right now.
class CommuteRecommendation {
  const CommuteRecommendation({
    required this.mode,
    required this.label,
    required this.predictedArrival,
    required this.confidence,
    required this.isLive,
    required this.message,
    required this.usualRouteOrDirection,
    required this.differsFromUsual,
    this.alternatives = const [],
  });

  final String mode;
  final String label;
  final DateTime predictedArrival;
  final double confidence;
  final bool isLive;

  /// The AI-phrased sentence - explicitly says "take X instead of your
  /// usual Y" when [differsFromUsual], otherwise a plain confirmation.
  final String message;

  /// The user's own inferred usual pick at this station/hour (Behavior
  /// AI's direction-choice signal), if there's enough history - null
  /// otherwise, meaning there's nothing to compare against yet.
  final String? usualRouteOrDirection;

  /// True only when there's a real usual pick AND the winner differs
  /// from it - the actual "take X instead" moment, not just "no usual
  /// known yet."
  final bool differsFromUsual;

  final List<CommuteAlternative> alternatives;

  factory CommuteRecommendation.fromJson(Map<String, dynamic> json) {
    return CommuteRecommendation(
      mode: json['mode'] as String,
      label: json['label'] as String,
      predictedArrival: DateTime.parse(json['predicted_arrival'] as String),
      confidence: (json['confidence'] as num).toDouble(),
      isLive: json['is_live'] as bool,
      message: json['message'] as String,
      usualRouteOrDirection: json['usual_route_or_direction'] as String?,
      differsFromUsual: json['differs_from_usual'] as bool,
      alternatives: ((json['alternatives'] as List?) ?? const [])
          .cast<Map<String, dynamic>>()
          .map(CommuteAlternative.fromJson)
          .toList(),
    );
  }
}

class CommuteAlternative {
  const CommuteAlternative({
    required this.mode,
    required this.label,
    required this.predictedArrival,
    required this.confidence,
    required this.isLive,
  });

  final String mode;
  final String label;
  final DateTime predictedArrival;
  final double confidence;
  final bool isLive;

  factory CommuteAlternative.fromJson(Map<String, dynamic> json) {
    return CommuteAlternative(
      mode: json['mode'] as String,
      label: json['label'] as String,
      predictedArrival: DateTime.parse(json['predicted_arrival'] as String),
      confidence: (json['confidence'] as num).toDouble(),
      isLive: json['is_live'] as bool,
    );
  }
}

class CommuteException implements Exception {
  CommuteException(this.message);
  final String message;

  @override
  String toString() => message;
}

/// Calls Commute AI (GET /commute/{agency}/{code}) - requires login, same
/// as the manual recommendation flow, since it reads the user's own
/// Behavior AI history to know their usual pick. There's no meaningful
/// logged-out version of this feature the way there is for plain
/// arrivals browsing or Chat AI's stateless tier.
class CommuteRepository {
  CommuteRepository({AuthRepository? authRepository, http.Client? client})
    : _authRepository = authRepository ?? AuthRepository(),
      _client = client ?? http.Client();

  final AuthRepository _authRepository;
  final http.Client _client;

  /// Returns null (not an error) when the user isn't logged in, or when
  /// the backend 404s (station not in its index, or no live arrivals for
  /// any of its real candidates right now) - callers fall back to
  /// showing arrivals unranked in both cases, same as if this feature
  /// didn't exist, per the PRD's explicit Commute AI fallback.
  Future<CommuteRecommendation?> getRecommendation(
    String agency,
    String code,
  ) async {
    final token = await _authRepository.getToken();
    if (token == null) return null;

    final response = await _client.get(
      Uri.parse('$apiBaseUrl/commute/$agency/$code'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 404) {
      return null;
    }

    if (response.statusCode != 200) {
      throw CommuteException(_extractErrorDetail(response));
    }

    return CommuteRecommendation.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  String _extractErrorDetail(http.Response response) {
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final detail = body['detail'];
      if (detail is String) return detail;
    } catch (_) {
      // Not JSON - fall through to the default message.
    }
    return 'Could not get a commute recommendation.';
  }
}
