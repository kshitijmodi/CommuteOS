import 'dart:convert';

import 'package:http/http.dart' as http;

import '../transit/transit_models.dart';
import 'path_arrival.dart';
import 'path_station.dart';

/// Fetches and parses PATH's real-time arrivals feed.
///
/// This is NOT an official, documented Port Authority API — it's the same
/// unauthenticated JSON endpoint that powers the arrivals widget on PATH's
/// own website (panynj.gov). No SLA, no versioning guarantee, no support
/// channel. See OPEN_QUESTIONS.md for the "beta tier" rationale.
///
/// Because of that, this service treats staleness as a real signal, not
/// just a transport failure: if the feed's own `lastUpdated` timestamps
/// are old, that's the backend serving cached/stuck data rather than a
/// genuine "no upcoming trains" — the UI should show a "live data
/// unavailable" flag rather than trust it as current.
class PathService implements TransitService {
  PathService({http.Client? client}) : _client = client ?? http.Client();

  static final _feedUri = Uri.parse(
    'https://www.panynj.gov/bin/portauthority/ridepath.json',
  );

  /// If every arrival returned for a station is older than this, treat the
  /// response as stale rather than live. PATH's feed updates roughly every
  /// 15s under normal operation, so several minutes of staleness is a
  /// clear signal something's wrong upstream, not just normal jitter.
  static const _staleAfter = Duration(minutes: 5);

  final http.Client _client;

  @override
  Future<TransitArrivalsResult> getArrivals(TransitStation station) async {
    final pathStation = station as PathStation;

    final http.Response response;
    try {
      response = await _client.get(_feedUri);
    } catch (e) {
      throw PathFeedException('Failed to reach PATH feed: $e');
    }

    if (response.statusCode != 200) {
      throw PathFeedException(
        'PATH feed returned HTTP ${response.statusCode}',
      );
    }

    final Map<String, dynamic> body;
    try {
      body = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (e) {
      throw PathFeedException('Failed to parse PATH feed: $e');
    }

    final results = (body['results'] as List?) ?? const [];
    final stationEntry = results.cast<Map<String, dynamic>>().firstWhere(
      (r) => r['consideredStation'] == pathStation.code,
      orElse: () => const {},
    );

    final byDirection = <String, List<PathArrival>>{'ToNY': [], 'ToNJ': []};
    var newestUpdate = DateTime.fromMillisecondsSinceEpoch(0);

    final destinations = (stationEntry['destinations'] as List?) ?? const [];
    for (final destination in destinations.cast<Map<String, dynamic>>()) {
      final directionKey = destination['label'] as String?;
      if (directionKey == null || !byDirection.containsKey(directionKey)) {
        continue;
      }

      final messages = (destination['messages'] as List?) ?? const [];
      for (final message in messages.cast<Map<String, dynamic>>()) {
        final arrival = _parseArrival(message);
        if (arrival == null) continue;
        byDirection[directionKey]!.add(arrival);
        if (arrival.lastUpdated.isAfter(newestUpdate)) {
          newestUpdate = arrival.lastUpdated;
        }
      }
    }

    for (final list in byDirection.values) {
      list.sort((a, b) => a.arrivalTime.compareTo(b.arrivalTime));
    }

    final hasAnyArrivals = byDirection.values.any((l) => l.isNotEmpty);
    final isLive =
        !hasAnyArrivals || // no trains right now isn't itself "stale"
        DateTime.now().difference(newestUpdate) < _staleAfter;

    return TransitArrivalsResult(
      arrivalsByDirectionKey: {
        for (final entry in byDirection.entries)
          entry.key: [
            for (final arrival in entry.value)
              TransitArrival(
                routeLabel: 'PATH',
                arrivalTime: arrival.arrivalTime,
                headSign: arrival.headSign,
                routeColors: arrival.routeColors,
              ),
          ],
      },
      isLive: isLive,
    );
  }

  PathArrival? _parseArrival(Map<String, dynamic> message) {
    final target = message['target'] as String?;
    final headSign = message['headSign'] as String?;
    final secondsToArrival = int.tryParse(
      (message['secondsToArrival'] as String?) ?? '',
    );
    final lastUpdated = DateTime.tryParse(
      (message['lastUpdated'] as String?) ?? '',
    );

    if (target == null ||
        headSign == null ||
        secondsToArrival == null ||
        lastUpdated == null) {
      return null;
    }

    return PathArrival(
      destinationCode: target,
      headSign: headSign,
      arrivalTime: DateTime.now().add(Duration(seconds: secondsToArrival)),
      lastUpdated: lastUpdated,
      routeColors: parsePathRouteColors(message['lineColor'] as String?),
    );
  }

  @override
  void dispose() => _client.close();
}

class PathFeedException implements Exception {
  PathFeedException(this.message);
  final String message;

  @override
  String toString() => 'PathFeedException: $message';
}
