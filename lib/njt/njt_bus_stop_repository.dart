import 'dart:math' as math;

import 'package:csv/csv.dart';
import 'package:flutter/services.dart' show rootBundle;

import '../transit/natural_sort.dart';
import 'njt_bus_stop.dart';

/// A same-named stop_id's own routes plus real coordinates, needed to tell
/// a genuine multi-bay terminal apart from unrelated stops that just
/// happen to share a name - see [_isSingleTerminal].
typedef _Bay = (String stopId, List<String> routes, double lat, double lon);

/// Loads and caches the bundled NJT bus stop list
/// (assets/data/njt_bus_stops.csv, built from NJT's static GTFS bus feed,
/// filtered to a NYC-metro core bounding box - see
/// backend/scripts/build_njt_bus_stops.py).
class NjtBusStopRepository {
  static const _assetPath = 'assets/data/njt_bus_stops.csv';

  /// Same-named stop_ids within this radius of each other are treated as
  /// one physical terminal's bays (e.g. Journal Square's ~26 bays, all
  /// within ~30m of each other) and merged into one combined NjtBusStop.
  /// Chosen with headroom above that ~30m verified case while still well
  /// under real street-level separation - a scan of the full bundled
  /// dataset found the terminal-style clusters this is meant to catch all
  /// stay under this, while unrelated same-named stops (opposite sides of
  /// an intersection, different streets entirely) start around ~60m+.
  static const _terminalRadiusMeters = 60.0;

  List<NjtBusStop>? _cache;

  Future<List<NjtBusStop>> loadStations() async {
    final cached = _cache;
    if (cached != null) return cached;

    final raw = await rootBundle.loadString(_assetPath);
    final rows = const CsvToListConverter(eol: '\n').convert(raw);

    final header = rows.first.cast<String>();
    final stopIdCol = header.indexOf('stop_id');
    final nameCol = header.indexOf('stop_name');
    final latCol = header.indexOf('lat');
    final lonCol = header.indexOf('lon');
    final routesCol = header.indexOf('routes');

    // Grouped by name first, not appended directly to a flat list - large
    // terminals (Journal Square, Irvington Bus Terminal, Secaucus Junction
    // Bus Plaza, and others - confirmed via the bundled CSV) are modeled by
    // NJT's static GTFS as many separate bay-level stop_ids sharing one
    // exact stop_name, with no single stop_id representing "every bus at
    // this terminal." Each name's bays get merged into one combined
    // NjtBusStop below *only* when they're actually close together (see
    // _isSingleTerminal) - a real-device bug report (route 59 showing 7x
    // at "1st Ave at Aldene Rd," several with stale "NOW" times) traced
    // back to two stop_ids 113m apart (almost certainly opposite-direction
    // stops, not terminal bays) being wrongly merged, mixing both
    // directions' arrivals into one list. A dataset-wide scan found 209 of
    // 1,309 same-named groups are actually >60m apart - this was never a
    // one-off. Same-named stops that fail the distance check are left
    // unmerged, so StationGroup's existing name-collision picker (already
    // used for e.g. MTA's unconnected same-name stations) surfaces them
    // separately instead.
    final byName = <String, List<_Bay>>{};
    for (final row in rows.skip(1)) {
      final stopId = row[stopIdCol].toString();
      if (stopId.isEmpty) continue;

      final routeNames = row[routesCol]
          .toString()
          .split('|')
          .where((r) => r.isNotEmpty)
          .toList();
      // A stop_id with no scheduled routes at all (~1% of the bundled
      // stops, but ~19% at large multi-bay terminals like Journal Square -
      // see build_njt_bus_stops.py) has nothing real to show: no route
      // badge, and no way to distinguish it from every other blank row at
      // the same terminal. Almost always a bay-level stop_id NJT's static
      // schedule data never assigns a trip to (inactive/reserved/stale),
      // not a genuinely in-service stop the join is failing to find - skip
      // it rather than show a confusing routeless row.
      if (routeNames.isEmpty) continue;

      final lat = double.tryParse(row[latCol].toString()) ?? 0;
      final lon = double.tryParse(row[lonCol].toString()) ?? 0;
      byName.putIfAbsent(row[nameCol].toString(), () => []).add((stopId, routeNames, lat, lon));
    }

    final stops = <NjtBusStop>[
      for (final entry in byName.entries)
        if (entry.value.length > 1 && _isSingleTerminal(entry.value))
          NjtBusStop(
            stopId: entry.value.first.$1,
            name: entry.key,
            routeNames: {for (final bay in entry.value) ...bay.$2}.toList()..sort(),
            mergedStopIds: [for (final bay in entry.value) bay.$1],
          )
        else
          for (final bay in entry.value)
            NjtBusStop(stopId: bay.$1, name: entry.key, routeNames: bay.$2..sort()),
    ];

    stops.sort((a, b) => compareStationNames(a.name, b.name));
    _cache = stops;
    return stops;
  }

  /// True when every bay in [bays] is within [_terminalRadiusMeters] of
  /// every other bay - i.e. they're genuinely one physical terminal, not
  /// unrelated same-named stops that happen to be far apart.
  static bool _isSingleTerminal(List<_Bay> bays) {
    for (var i = 0; i < bays.length; i++) {
      for (var j = i + 1; j < bays.length; j++) {
        if (_distanceMeters(bays[i].$3, bays[i].$4, bays[j].$3, bays[j].$4) >
            _terminalRadiusMeters) {
          return false;
        }
      }
    }
    return true;
  }

  /// Haversine distance in meters between two lat/lon points.
  static double _distanceMeters(double lat1, double lon1, double lat2, double lon2) {
    const earthRadiusMeters = 6371000.0;
    final dLat = _toRad(lat2 - lat1);
    final dLon = _toRad(lon2 - lon1);
    final a = math.sin(dLat / 2) * math.sin(dLat / 2) +
        math.cos(_toRad(lat1)) * math.cos(_toRad(lat2)) * math.sin(dLon / 2) * math.sin(dLon / 2);
    return earthRadiusMeters * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
  }

  static double _toRad(double degrees) => degrees * math.pi / 180;
}
