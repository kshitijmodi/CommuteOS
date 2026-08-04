import 'dart:convert';

import 'package:http/http.dart' as http;

import '../account/api_config.dart';
import '../transit/transit_models.dart';

/// Fetches NJT rail real-time arrivals through our own backend
/// (`GET /transit/njt-rail/{station_code}`), not directly against NJT's
/// API the way MtaService/PathService call their feeds directly.
///
/// This is a deliberate difference: NJT rail requires a real username/
/// password to mint an auth token (see backend/app/transit/njt_rail.py),
/// unlike MTA/PATH which are public and unauthenticated. Shipping those
/// credentials inside the Flutter app would mean anyone who decompiles the
/// APK can extract and reuse them - so the backend holds the credentials
/// and this service just calls our own hosted proxy endpoint instead.
class NjtRailService implements TransitService {
  NjtRailService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  /// See NjtBusService's docstring on the same constant - the Render
  /// backend this proxies through can cold-start-stall on an idle request,
  /// and without a timeout that surfaces as an indefinite loading spinner.
  static const _requestTimeout = Duration(seconds: 20);

  @override
  Future<TransitArrivalsResult> getArrivals(TransitStation station) async {
    final http.Response response;
    try {
      response = await _client
          .get(Uri.parse('$apiBaseUrl/transit/njt-rail/${station.id}'))
          .timeout(_requestTimeout);
    } catch (e) {
      throw NjtRailFeedException('Failed to reach NJT rail proxy: $e');
    }

    if (response.statusCode != 200) {
      throw NjtRailFeedException(
        'NJT rail proxy returned HTTP ${response.statusCode}',
      );
    }

    final Map<String, dynamic> body;
    try {
      body = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (e) {
      throw NjtRailFeedException('Failed to parse NJT rail response: $e');
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

    // All arrivals go under the single synthetic "departures" direction key
    // - see NjtRailStation's docstring on why there's no real direction
    // split to query by.
    return TransitArrivalsResult(
      arrivalsByDirectionKey: {'departures': arrivals},
      isLive: (body['is_live'] as bool?) ?? true,
    );
  }

  @override
  void dispose() => _client.close();
}

class NjtRailFeedException implements Exception {
  NjtRailFeedException(this.message);
  final String message;

  @override
  String toString() => 'NjtRailFeedException: $message';
}
