import 'dart:convert';
import 'dart:developer' as developer;

import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'auth_repository.dart';

/// Logs a trip data point to the backend whenever a logged-in user opens a
/// station's arrivals screen - the passive usage signal the PRD's Phase 2
/// preference model is built on. A no-op for logged-out users; browsing
/// never requires an account.
class TripLogger {
  TripLogger({AuthRepository? authRepository, http.Client? client})
    : _authRepository = authRepository ?? AuthRepository(),
      _client = client ?? http.Client();

  final AuthRepository _authRepository;
  final http.Client _client;

  /// [mode] should be the backend's wire name for the station's agency
  /// (see wireAgencyName in transit_models.dart, e.g. "njt_rail" - NOT
  /// Agency.name directly, which is camelCase and doesn't match).
  /// [routeOrDirection] is the specific route/direction actually shown
  /// when arrivals loaded (see ArrivalsScreen), if the agency has one -
  /// null for NJT rail/bus, which don't need one. Failures are logged, not
  /// surfaced to the user - a missed trip log entry shouldn't interrupt
  /// someone checking arrival times.
  Future<void> logStationView({
    required String mode,
    required String originStop,
    String? routeOrDirection,
  }) async {
    final token = await _authRepository.getToken();
    if (token == null) return; // not logged in - nothing to log

    try {
      final response = await _client.post(
        Uri.parse('$apiBaseUrl/trips'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: jsonEncode({
          'start_time': DateTime.now().toUtc().toIso8601String(),
          'mode': mode,
          'origin_stop': originStop,
          'route_or_direction': routeOrDirection,
        }),
      );
      if (response.statusCode != 201) {
        developer.log(
          'Trip log failed: HTTP ${response.statusCode}',
          name: 'TripLogger',
        );
      }
    } catch (e) {
      developer.log('Trip log failed: $e', name: 'TripLogger');
    }
  }
}
