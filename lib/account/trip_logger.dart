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
  ///
  /// Returns the new Trip's id on success, or null on failure/logged-out -
  /// DepartureDetector uses this to know which trip a later left_at report
  /// (see reportLeftAt) belongs to.
  Future<String?> logStationView({
    required String mode,
    required String originStop,
    String? routeOrDirection,
  }) async {
    final token = await _authRepository.getToken();
    if (token == null) return null; // not logged in - nothing to log

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
        return null;
      }
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      return body['id'] as String?;
    } catch (e) {
      developer.log('Trip log failed: $e', name: 'TripLogger');
      return null;
    }
  }

  /// Reports when the user actually started moving toward [tripId]'s
  /// station - see backend Trip.left_at's docstring. Feeds Behavior AI's
  /// timing-buffer signal. Fire-and-forget, same failure posture as
  /// [logStationView]: a missed report shouldn't surface to the user.
  Future<void> reportLeftAt(String tripId, DateTime leftAt) async {
    final token = await _authRepository.getToken();
    if (token == null) return;

    try {
      final response = await _client.patch(
        Uri.parse('$apiBaseUrl/trips/$tripId/outcome'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: jsonEncode({'left_at': leftAt.toUtc().toIso8601String()}),
      );
      if (response.statusCode != 200) {
        developer.log(
          'left_at report failed: HTTP ${response.statusCode}',
          name: 'TripLogger',
        );
      }
    } catch (e) {
      developer.log('left_at report failed: $e', name: 'TripLogger');
    }
  }
}
