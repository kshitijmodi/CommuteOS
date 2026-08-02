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
  });

  final String mode;
  final String label;
  final DateTime predictedArrival;
  final double confidence;
  final bool isLive;
  final String message;
  final String tripId;

  factory Recommendation.fromJson(Map<String, dynamic> json) {
    return Recommendation(
      mode: json['mode'] as String,
      label: json['label'] as String,
      predictedArrival: DateTime.parse(json['predicted_arrival'] as String),
      confidence: (json['confidence'] as num).toDouble(),
      isLive: json['is_live'] as bool,
      message: json['message'] as String,
      tripId: json['trip_id'] as String,
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

  /// Dart's Agency.name is camelCase (e.g. "njtRail"), but the backend's
  /// CandidateRequest.agency is a snake_case Literal ("njt_rail") matching
  /// its Python module names - an explicit mapping here, not station.agency
  /// .name directly, since the two naming conventions don't line up and a
  /// silent mismatch would fail as an unhandled 422 from the backend.
  static const _agencyWireNames = {
    Agency.mta: 'mta',
    Agency.path: 'path',
    Agency.njtRail: 'njt_rail',
    Agency.njtBus: 'njt_bus',
  };

  Map<String, dynamic> toJson() => {
    'agency': _agencyWireNames[station.agency],
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
