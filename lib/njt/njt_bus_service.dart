import 'dart:convert';

import 'package:http/http.dart' as http;

import '../account/api_config.dart';
import '../transit/transit_models.dart';

/// Fetches NJT bus real-time arrivals through our own backend
/// (`GET /transit/njt-bus/{stop_id}`), same reasoning as NjtRailService:
/// NJT's real-time bus API needs a real username/password, so the
/// credentials stay server-side rather than shipping inside the app.
class NjtBusService implements TransitService {
  NjtBusService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<TransitArrivalsResult> getArrivals(TransitStation station) async {
    final response = await _client.get(
      Uri.parse('$apiBaseUrl/transit/njt-bus/${station.id}'),
    );

    if (response.statusCode != 200) {
      throw NjtBusFeedException(
        'NJT bus proxy returned HTTP ${response.statusCode}',
      );
    }

    final Map<String, dynamic> body;
    try {
      body = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (e) {
      throw NjtBusFeedException('Failed to parse NJT bus response: $e');
    }

    final rawArrivals = (body['arrivals'] as List?) ?? const [];
    final arrivals = <TransitArrival>[];
    for (final entry in rawArrivals.cast<Map<String, dynamic>>()) {
      final routeLabel = entry['route_label'] as String?;
      final arrivalTimeStr = entry['arrival_time'] as String?;
      if (routeLabel == null || arrivalTimeStr == null) continue;

      final arrivalTime = DateTime.tryParse(arrivalTimeStr);
      if (arrivalTime == null) continue;

      arrivals.add(TransitArrival(routeLabel: routeLabel, arrivalTime: arrivalTime));
    }

    // All arrivals go under the single synthetic "arrivals" direction key
    // - see NjtBusStop's docstring on why there's no real direction split
    // to query by.
    return TransitArrivalsResult(
      arrivalsByDirectionKey: {'arrivals': arrivals},
      isLive: (body['is_live'] as bool?) ?? true,
    );
  }

  @override
  void dispose() => _client.close();
}

class NjtBusFeedException implements Exception {
  NjtBusFeedException(this.message);
  final String message;

  @override
  String toString() => 'NjtBusFeedException: $message';
}
