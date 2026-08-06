import 'package:csv/csv.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:gtfs_realtime_bindings/gtfs_realtime_bindings.dart';
import 'package:http/http.dart' as http;

import '../transit/transit_models.dart';
import 'lirr_station.dart';

/// Fetches and parses LIRR's real-time GTFS-RT feed directly - confirmed
/// live, public, and unauthenticated (same infrastructure as MTA subway's
/// feed, no API key needed), so this calls the feed directly the same way
/// MtaService does, unlike NJT rail/bus which need a backend proxy for
/// credentials LIRR simply doesn't require.
///
/// The real-time feed gives a trip_id + route_id + per-stop arrival time
/// per update, but no destination/headsign text - confirmed by inspecting
/// a real response. A trip_id there matches a trip_id in LIRR's static
/// GTFS trips.txt exactly, so the real branch name and destination come
/// from a bundled trip_id -> (branch, headsign) lookup
/// (assets/data/lirr_trip_routes.csv, built by
/// backend/scripts/build_lirr_stations.py) - the same "trip_id doesn't
/// self-describe its route" shape as NJT bus, just small enough (~2,100
/// trips vs. NJT bus's ~46k) to bundle and join client-side instead of
/// needing a backend round-trip.
class LirrService implements TransitService {
  LirrService({http.Client? client}) : _client = client ?? http.Client();

  static final _feedUri = Uri.parse(
    'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/lirr%2Fgtfs-lirr',
  );

  /// Without an explicit timeout, a stalled request never resolves, which
  /// surfaces in the UI as an indefinite loading spinner rather than a
  /// retryable error - same reasoning as every other transit service.
  static const _requestTimeout = Duration(seconds: 15);

  final http.Client _client;

  static Map<String, ({String branch, String headsign})>? _tripRoutesCache;

  static Future<Map<String, ({String branch, String headsign})>> _loadTripRoutes() async {
    final cached = _tripRoutesCache;
    if (cached != null) return cached;

    final raw = await rootBundle.loadString('assets/data/lirr_trip_routes.csv');
    final rows = const CsvToListConverter(eol: '\n').convert(raw);
    final header = rows.first.cast<String>();
    final tripIdCol = header.indexOf('trip_id');
    final branchCol = header.indexOf('branch');
    final headsignCol = header.indexOf('headsign');

    final result = <String, ({String branch, String headsign})>{};
    for (final row in rows.skip(1)) {
      final tripId = row[tripIdCol].toString();
      if (tripId.isEmpty) continue;
      result[tripId] = (
        branch: row[branchCol].toString(),
        headsign: row[headsignCol].toString(),
      );
    }
    _tripRoutesCache = result;
    return result;
  }

  @override
  Future<TransitArrivalsResult> getArrivals(TransitStation station) async {
    // The real-time feed matches against LIRR's numeric stop_id, NOT the
    // 3-letter stop_code (station.id) every other part of the app uses -
    // see LirrStation.stopId's docstring for why these are different.
    final stopId = station is LirrStation ? station.stopId : station.id;
    final tripRoutes = await _loadTripRoutes();

    final http.Response response;
    try {
      response = await _client.get(_feedUri).timeout(_requestTimeout);
    } catch (e) {
      throw LirrFeedException('Failed to reach LIRR feed: $e');
    }

    if (response.statusCode != 200) {
      throw LirrFeedException('LIRR feed returned HTTP ${response.statusCode}');
    }

    final FeedMessage feed;
    try {
      feed = FeedMessage.fromBuffer(response.bodyBytes);
    } catch (e) {
      throw LirrFeedException('Failed to parse LIRR feed: $e');
    }

    final arrivals = <TransitArrival>[];
    for (final entity in feed.entity) {
      if (!entity.hasTripUpdate()) continue;
      final tripUpdate = entity.tripUpdate;
      // CANCELED trips report stops with no timing data at all (see the
      // build script's doc on a real inspected example) - skip rather
      // than surface a cancellation as a phantom arrival with no time.
      if (tripUpdate.trip.scheduleRelationship ==
          TripDescriptor_ScheduleRelationship.CANCELED) {
        continue;
      }
      final tripRoute = tripRoutes[tripUpdate.trip.tripId];

      for (final stopTimeUpdate in tripUpdate.stopTimeUpdate) {
        if (stopTimeUpdate.stopId != stopId) continue;
        if (!stopTimeUpdate.hasArrival()) continue;

        final epochSeconds = stopTimeUpdate.arrival.time.toInt();
        if (epochSeconds <= 0) continue;

        arrivals.add(
          TransitArrival(
            routeLabel: tripRoute?.branch ?? 'LIRR',
            arrivalTime: DateTime.fromMillisecondsSinceEpoch(epochSeconds * 1000, isUtc: true),
            headSign: tripRoute?.headsign,
          ),
        );
      }
    }

    arrivals.sort((a, b) => a.arrivalTime.compareTo(b.arrivalTime));
    // No separate staleness signal in this feed beyond fetch success/failure
    // - same reasoning as mta.py/njt_rail.py/njt_bus.py.
    return TransitArrivalsResult(
      arrivalsByDirectionKey: {'arrivals': arrivals},
      isLive: true,
    );
  }

  @override
  void dispose() => _client.close();
}

class LirrFeedException implements Exception {
  LirrFeedException(this.message);
  final String message;

  @override
  String toString() => 'LirrFeedException: $message';
}
