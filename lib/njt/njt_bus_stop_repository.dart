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

      stops.add(
        NjtBusStop(
          stopId: stopId,
          name: row[nameCol].toString(),
          routeNames: row[routesCol]
              .toString()
              .split('|')
              .where((r) => r.isNotEmpty)
              .toList(),
        ),
      );
    }

    stops.sort((a, b) => compareStationNames(a.name, b.name));
    _cache = stops;
    return stops;
  }
}
