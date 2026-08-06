import 'dart:convert';

import 'package:http/http.dart' as http;

import '../transit/transit_models.dart';
import 'api_config.dart';
import 'auth_repository.dart';

class Recommendation {
  const Recommendation({
    required this.mode,
    required this.label,
    required this.predictedArrival,
    required this.confidence,
    required this.isLive,
    required this.message,
    required this.tripId,
    this.alternatives = const [],
  });

  final String mode;
  final String label;
  final DateTime predictedArrival;
  final double confidence;
  final bool isLive;

  /// The AI-phrased sentence - if [alternatives] is non-empty, this
  /// explains the tradeoff against them (e.g. "sooner than your PATH"),
  /// not just this route's own number in isolation - see the backend's
  /// llm_phrasing.phrase_comparison.
  final String message;
  final String tripId;

  /// Every other real candidate that was considered and lost, soonest to
  /// least-soonest (per the backend's ranking) - shown alongside [message]
  /// so the AI's tradeoff explanation isn't a black box; a rider can see
  /// the actual numbers it reasoned over. Empty when there was only one
  /// candidate to begin with (nothing to compare against).
  final List<RecommendationAlternative> alternatives;

  factory Recommendation.fromJson(Map<String, dynamic> json) {
    return Recommendation(
      mode: json['mode'] as String,
      label: json['label'] as String,
      predictedArrival: DateTime.parse(json['predicted_arrival'] as String),
      confidence: (json['confidence'] as num).toDouble(),
      isLive: json['is_live'] as bool,
      message: json['message'] as String,
      tripId: json['trip_id'] as String,
      alternatives: ((json['alternatives'] as List?) ?? const [])
          .cast<Map<String, dynamic>>()
          .map(RecommendationAlternative.fromJson)
          .toList(),
    );
  }
}

class RecommendationAlternative {
  const RecommendationAlternative({
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

  factory RecommendationAlternative.fromJson(Map<String, dynamic> json) {
    return RecommendationAlternative(
      mode: json['mode'] as String,
      label: json['label'] as String,
      predictedArrival: DateTime.parse(json['predicted_arrival'] as String),
      confidence: (json['confidence'] as num).toDouble(),
      isLive: json['is_live'] as bool,
    );
  }
}

/// One option to compare, built from a favorited station the user already
/// has - see backend/app/routers/recommendations.py's CandidateRequest for
/// the matching server-side shape.
class RecommendationCandidate {
  const RecommendationCandidate({
    required this.station,
    required this.routeOrDirection,
  });

  final TransitStation station;

  /// MTA: a route ID from station.routes (e.g. "N").
  /// PATH: a direction key from station.directions (e.g. "ToNY").
  /// NJT rail: unused, always "" - one API call returns every line.
  final String routeOrDirection;

  Map<String, dynamic> toJson() => {
    'agency': wireAgencyName(station.agency),
    'label': station.name,
    'stop_or_station': station.id,
    'route_or_direction': routeOrDirection,
  };
}

class RecommendationException implements Exception {
  RecommendationException(this.message);
  final String message;

  @override
  String toString() => message;
}

/// Calls the Phase 3 decision engine (backend) with a set of candidate
/// routes and returns its top pick, already phrased. Requires login, same
/// as trip logging - there's no logged-out recommendation flow since the
/// engine reads the user's learned preferences.
class RecommendationRepository {
  RecommendationRepository({AuthRepository? authRepository, http.Client? client})
    : _authRepository = authRepository ?? AuthRepository(),
      _client = client ?? http.Client();

  final AuthRepository _authRepository;
  final http.Client _client;

  Future<Recommendation> getRecommendation(
    List<RecommendationCandidate> candidates,
  ) async {
    final token = await _authRepository.getToken();
    if (token == null) {
      throw RecommendationException('Log in to get recommendations.');
    }

    final response = await _client.post(
      Uri.parse('$apiBaseUrl/recommendations'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'candidates': candidates.map((c) => c.toJson()).toList(),
      }),
    );

    if (response.statusCode != 200) {
      throw RecommendationException(
        _extractErrorDetail(response, 'Could not get a recommendation'),
      );
    }

    return Recommendation.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  /// Tries to get a recommendation from the user's confirmed home/office
  /// stations, with no manual station-picking - see backend's
  /// GET /recommendations/from-home-office. Returns null (not an error)
  /// when the backend 404s, which just means home/office isn't confirmed
  /// yet or isn't resolvable to a real candidate (see
  /// recommendation_builder.specs_from_home_office on the backend) - the
  /// caller falls back to manual favorite-picking in that case, same as if
  /// this feature didn't exist.
  Future<Recommendation?> getRecommendationFromHomeOffice() async {
    final token = await _authRepository.getToken();
    if (token == null) {
      throw RecommendationException('Log in to get recommendations.');
    }

    final response = await _client.get(
      Uri.parse('$apiBaseUrl/recommendations/from-home-office'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 404) {
      return null;
    }

    if (response.statusCode != 200) {
      throw RecommendationException(
        _extractErrorDetail(response, 'Could not get a recommendation'),
      );
    }

    return Recommendation.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  String _extractErrorDetail(http.Response response, String fallback) {
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final detail = body['detail'];
      if (detail is String) return detail;
    } catch (_) {
      // Not JSON - fall through to the default message.
    }
    return fallback;
  }
}
