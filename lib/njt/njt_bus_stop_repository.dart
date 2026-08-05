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

    // Grouped by name first, not appended directly to a flat list - large
    // terminals (Journal Square, Irvington Bus Terminal, Secaucus Junction
    // Bus Plaza, and others - confirmed via the bundled CSV) are modeled by
    // NJT's static GTFS as many separate bay-level stop_ids sharing one
    // exact stop_name, with no single stop_id representing "every bus at
    // this terminal." Verified these are genuine same-location bay
    // clusters, not an unrelated-stops-sharing-a-name collision, by
    // checking coordinate spread stays within ~30m for every repeated name
    // in the dataset. Each name's bays get merged into one combined
    // NjtBusStop below so a user picks the terminal once and sees every
    // bay's arrivals together, instead of having to guess which of ~26
    // near-identical rows has the bus they want.
    final byName = <String, List<(String stopId, List<String> routes)>>{};
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

      byName.putIfAbsent(row[nameCol].toString(), () => []).add((stopId, routeNames));
    }

    final stops = <NjtBusStop>[
      for (final entry in byName.entries)
        NjtBusStop(
          stopId: entry.value.first.$1,
          name: entry.key,
          routeNames: {for (final bay in entry.value) ...bay.$2}.toList()..sort(),
          mergedStopIds: entry.value.length > 1
              ? [for (final bay in entry.value) bay.$1]
              : null,
        ),
    ];

    stops.sort((a, b) => compareStationNames(a.name, b.name));
    _cache = stops;
    return stops;
  }
}
