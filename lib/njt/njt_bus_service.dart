import 'dart:convert';

import 'package:http/http.dart' as http;

import '../account/api_config.dart';
import '../transit/transit_models.dart';
import 'njt_bus_stop.dart';

/// Fetches NJT bus real-time arrivals through our own backend
/// (`GET /transit/njt-bus/{stop_id}`), same reasoning as NjtRailService:
/// NJT's real-time bus API needs a real username/password, so the
/// credentials stay server-side rather than shipping inside the app.
class NjtBusService implements TransitService {
  NjtBusService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  /// The Render backend this proxies through can take a while to wake up
  /// from an idle cold-start (free tier) - without an explicit timeout, a
  /// stalled request never resolves, which surfaces in the UI as an
  /// indefinite loading spinner rather than a retryable error.
  static const _requestTimeout = Duration(seconds: 20);

  @override
  Future<TransitArrivalsResult> getArrivals(TransitStation station) async {
    // A combined-terminal stop (e.g. Journal Square, merged from many bay
    // stop_ids sharing one name - see NjtBusStopRepository) needs every
    // bay's arrivals fetched together, not just the primary one - see
    // allStopIds. Ordinary single-bay stops just send the one id.
    final stopIds = station is NjtBusStop ? station.allStopIds : [station.id];
    final primaryStopId = stopIds.first;
    final extraStopIds = stopIds.skip(1).join(',');
    final uri = Uri.parse('$apiBaseUrl/transit/njt-bus/$primaryStopId').replace(
      queryParameters: extraStopIds.isEmpty ? null : {'extra_stop_ids': extraStopIds},
    );

    final http.Response response;
    try {
      response = await _client.get(uri).timeout(_requestTimeout);
    } catch (e) {
      throw NjtBusFeedException('Failed to reach NJT bus proxy: $e');
    }

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
