import 'package:gtfs_realtime_bindings/gtfs_realtime_bindings.dart';
import 'package:http/http.dart' as http;

import '../transit/transit_models.dart';
import 'mta_arrival.dart';
import 'mta_feed.dart';
import 'mta_station.dart';

/// Fetches and parses a single MTA GTFS-RT feed.
///
/// Isolated per agency/feed by design: a parse or network failure here
/// surfaces as a thrown [MtaFeedException] rather than taking down other
/// feeds (PATH, NJ Transit) that may be wired up alongside this one later.
class MtaService implements TransitService {
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

  /// Fetches arrivals at [station] for both directions, across every feed
  /// the station's routes require (some stations, e.g. transfer complexes,
  /// span more than one feed). A feed that fails to fetch/parse doesn't
  /// block the others — its arrivals are just omitted.
  ///
  /// Returns a map from stop_id (north/south) to that direction's arrivals.
  Future<Map<String, List<MtaArrival>>> getArrivalsForStation(
    MtaStation station,
  ) async {
    final wantedStopIds = {station.northStopId, station.southStopId};
    final byDirection = <String, List<MtaArrival>>{
      station.northStopId: [],
      station.southStopId: [],
    };

    await Future.wait(
      station.feeds.map((feed) async {
        List<MtaArrival> allArrivalsAtStation;
        try {
          allArrivalsAtStation = await _getArrivalsForAnyStop(
            feed,
            wantedStopIds,
          );
        } catch (_) {
          // Isolated per feed: one feed failing shouldn't blank out arrivals
          // this station gets from its other feed(s), if any.
          return;
        }

        for (final arrival in allArrivalsAtStation) {
          byDirection[arrival.stopId]?.add(arrival);
        }
      }),
    );

    for (final list in byDirection.values) {
      list.sort((a, b) => a.arrivalTime.compareTo(b.arrivalTime));
    }
    return byDirection;
  }

  @override
  Future<TransitArrivalsResult> getArrivals(TransitStation station) async {
    final byDirection = await getArrivalsForStation(station as MtaStation);
    return TransitArrivalsResult(
      arrivalsByDirectionKey: {
        for (final entry in byDirection.entries)
          entry.key: [
            for (final arrival in entry.value)
              TransitArrival(
                routeLabel: arrival.routeId,
                arrivalTime: arrival.arrivalTime,
              ),
          ],
      },
      // MTA's feed has no separate "is this stale" signal beyond fetch
      // success/failure — if the fetch succeeded at all, treat it as live.
      isLive: true,
    );
  }

  Future<List<MtaArrival>> _getArrivalsForAnyStop(
    MtaFeed feed,
    Set<String> stopIds,
  ) async {
    final response = await _client.get(feed.uri);
    if (response.statusCode != 200) {
      throw MtaFeedException(
        'MTA feed ${feed.name} returned HTTP ${response.statusCode}',
      );
    }

    final message = FeedMessage.fromBuffer(response.bodyBytes);
    final arrivals = <MtaArrival>[];
    for (final entity in message.entity) {
      if (!entity.hasTripUpdate()) continue;
      final tripUpdate = entity.tripUpdate;
      final routeId = tripUpdate.trip.routeId;

      for (final stopTimeUpdate in tripUpdate.stopTimeUpdate) {
        if (!stopIds.contains(stopTimeUpdate.stopId)) continue;
        if (!stopTimeUpdate.hasArrival()) continue;

        final epochSeconds = stopTimeUpdate.arrival.time.toInt();
        if (epochSeconds <= 0) continue;

        arrivals.add(
          MtaArrival(
            routeId: routeId,
            stopId: stopTimeUpdate.stopId,
            arrivalTime: DateTime.fromMillisecondsSinceEpoch(
              epochSeconds * 1000,
            ),
          ),
        );
      }
    }
    return arrivals;
  }

  @override
  void dispose() => _client.close();
}

class MtaFeedException implements Exception {
  MtaFeedException(this.message);
  final String message;

  @override
  String toString() => 'MtaFeedException: $message';
}
