import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'auth_repository.dart';

class LearnedPreferences {
  const LearnedPreferences({
    required this.walkingToleranceM,
    required this.transferAversionScore,
    required this.reliabilityPref,
    required this.tripCount,
    required this.walkingToleranceLearned,
  });

  final double walkingToleranceM;
  final double transferAversionScore;
  final double reliabilityPref;

  /// How many trips this user has logged in total - the backend's real
  /// signal for whether the values above reflect actual usage or are still
  /// just untouched schema defaults (see preference_engine.py).
  final int tripCount;

  /// Whether [walkingToleranceM] has actually been recomputed from real
  /// trip history (see backend's MIN_TRIPS_FOR_WALKING_TOLERANCE) - false
  /// means it's still the untouched default and shouldn't be presented as
  /// something CommuteOS has learned. transferAversionScore has no
  /// equivalent flag: it's always the neutral default today regardless of
  /// tripCount (the real signal for it doesn't exist in the data model
  /// yet - see the backend module's docstring), so it should always be
  /// treated as not-yet-learned rather than gated on tripCount.
  final bool walkingToleranceLearned;

  factory LearnedPreferences.fromJson(Map<String, dynamic> json) {
    return LearnedPreferences(
      walkingToleranceM: (json['walking_tolerance_m'] as num).toDouble(),
      transferAversionScore: (json['transfer_aversion_score'] as num)
          .toDouble(),
      reliabilityPref: (json['reliability_pref'] as num).toDouble(),
      tripCount: (json['trip_count'] as num).toInt(),
      walkingToleranceLearned: json['walking_tolerance_learned'] as bool,
    );
  }
}

/// Fetches the current user's learned preferences (Phase 2) - requires
/// login, same as TripLogger; there's nothing to show a logged-out user.
class PreferencesRepository {
  PreferencesRepository({AuthRepository? authRepository, http.Client? client})
    : _authRepository = authRepository ?? AuthRepository(),
      _client = client ?? http.Client();

  final AuthRepository _authRepository;
  final http.Client _client;

  Future<LearnedPreferences?> getMyPreferences() async {
    final token = await _authRepository.getToken();
    if (token == null) return null;

    final response = await _client.get(
      Uri.parse('$apiBaseUrl/preferences/me'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) return null;

    return LearnedPreferences.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  /// Triggers what the nightly batch job otherwise does on a schedule -
  /// see backend/app/routers/preferences.py's `/me/recompute`.
  Future<LearnedPreferences?> recomputeMyPreferences() async {
    final token = await _authRepository.getToken();
    if (token == null) return null;

    final response = await _client.post(
      Uri.parse('$apiBaseUrl/preferences/me/recompute'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) return null;

    return LearnedPreferences.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }
}
