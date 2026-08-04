import 'package:csv/csv.dart';
import 'package:flutter/services.dart' show rootBundle;

import '../transit/natural_sort.dart';
import 'njt_bus_stop.dart';

/// Loads and caches the bundled NJT bus stop list
/// (assets/data/njt_bus_stops.csv, built from NJT's static GTFS bus feed,
/// filtered to a NYC-metro core bounding box - see
/// backend/scripts/build_njt_bus_stops.py).
class NjtBusStopRepository {
  static const _assetPath = 'assets/data/njt_bus_stops.csv';

  List<NjtBusStop>? _cache;

  Future<List<NjtBusStop>> loadStations() async {
    final cached = _cache;
    if (cached != null) return cached;

    final raw = await rootBundle.loadString(_assetPath);
    final rows = const CsvToListConverter(eol: '\n').convert(raw);

    final header = rows.first.cast<String>();
    final stopIdCol = header.indexOf('stop_id');
    final nameCol = header.indexOf('stop_name');
    final routesCol = header.indexOf('routes');

    final stops = <NjtBusStop>[];
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

      stops.add(
        NjtBusStop(stopId: stopId, name: row[nameCol].toString(), routeNames: routeNames),
      );
    }

    stops.sort((a, b) => compareStationNames(a.name, b.name));
    _cache = stops;
    return stops;
  }
}
