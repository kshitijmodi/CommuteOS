import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'auth_repository.dart';

class LearnedPreferences {
  const LearnedPreferences({
    required this.walkingToleranceM,
    required this.transferAversionScore,
    required this.reliabilityPref,
  });

  final double walkingToleranceM;
  final double transferAversionScore;
  final double reliabilityPref;

  factory LearnedPreferences.fromJson(Map<String, dynamic> json) {
    return LearnedPreferences(
      walkingToleranceM: (json['walking_tolerance_m'] as num).toDouble(),
      transferAversionScore: (json['transfer_aversion_score'] as num)
          .toDouble(),
      reliabilityPref: (json['reliability_pref'] as num).toDouble(),
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
