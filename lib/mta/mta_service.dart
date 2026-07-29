import 'package:gtfs_realtime_bindings/gtfs_realtime_bindings.dart';
import 'package:http/http.dart' as http;

import 'mta_arrival.dart';
import 'mta_feed.dart';

/// Fetches and parses a single MTA GTFS-RT feed.
///
/// Isolated per agency/feed by design: a parse or network failure here
/// surfaces as a thrown [MtaFeedException] rather than taking down other
/// feeds (PATH, NJ Transit) that may be wired up alongside this one later.
class MtaService {
  MtaService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  /// Fetches [feed] and returns arrivals at [stopId], sorted soonest first.
  ///
  /// [stopId] should be a GTFS stop_id, e.g. "R16N" for the northbound
  /// platform at Union Square on the N/Q/R/W feed.
  Future<List<MtaArrival>> getArrivalsForStop(
    MtaFeed feed,
    String stopId,
  ) async {
    final http.Response response;
    try {
      response = await _client.get(feed.uri);
    } catch (e) {
      throw MtaFeedException('Failed to reach MTA feed ${feed.name}: $e');
    }

    if (response.statusCode != 200) {
      throw MtaFeedException(
        'MTA feed ${feed.name} returned HTTP ${response.statusCode}',
      );
    }

    final FeedMessage message;
    try {
      message = FeedMessage.fromBuffer(response.bodyBytes);
    } catch (e) {
      throw MtaFeedException('Failed to parse MTA feed ${feed.name}: $e');
    }

    final arrivals = <MtaArrival>[];
    for (final entity in message.entity) {
      if (!entity.hasTripUpdate()) continue;
      final tripUpdate = entity.tripUpdate;
      final routeId = tripUpdate.trip.routeId;

      for (final stopTimeUpdate in tripUpdate.stopTimeUpdate) {
        if (stopTimeUpdate.stopId != stopId) continue;
        if (!stopTimeUpdate.hasArrival()) continue;

        final epochSeconds = stopTimeUpdate.arrival.time.toInt();
        if (epochSeconds <= 0) continue;

        arrivals.add(
          MtaArrival(
            routeId: routeId,
            stopId: stopId,
            arrivalTime: DateTime.fromMillisecondsSinceEpoch(
              epochSeconds * 1000,
            ),
          ),
        );
      }
    }

    arrivals.sort((a, b) => a.arrivalTime.compareTo(b.arrivalTime));
    return arrivals;
  }

  void dispose() => _client.close();
}

class MtaFeedException implements Exception {
  MtaFeedException(this.message);
  final String message;

  @override
  String toString() => 'MtaFeedException: $message';
}
