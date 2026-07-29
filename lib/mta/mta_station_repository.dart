import 'package:csv/csv.dart';
import 'package:flutter/services.dart' show rootBundle;

import 'mta_station.dart';

/// Loads and caches the bundled MTA station list (assets/data/mta_stations.csv,
/// MTA's published "Stations.csv" — one row per physical station, pre-joined
/// with the routes serving it and human-readable direction labels).
class MtaStationRepository {
  static const _assetPath = 'assets/data/mta_stations.csv';

  List<MtaStation>? _cache;

  Future<List<MtaStation>> loadStations() async {
    final cached = _cache;
    if (cached != null) return cached;

    final raw = await rootBundle.loadString(_assetPath);
    final rows = const CsvToListConverter(eol: '\n').convert(raw);

    final header = rows.first.cast<String>();
    final stopIdCol = header.indexOf('GTFS Stop ID');
    final nameCol = header.indexOf('Stop Name');
    final boroughCol = header.indexOf('Borough');
    final routesCol = header.indexOf('Daytime Routes');
    final northLabelCol = header.indexOf('North Direction Label');
    final southLabelCol = header.indexOf('South Direction Label');

    final stations = <String, MtaStation>{};
    for (final row in rows.skip(1)) {
      final stopId = row[stopIdCol].toString();
      if (stopId.isEmpty) continue;

      // A handful of stop IDs appear more than once in the source file
      // (complex stations spanning multiple entries); keep the first.
      if (stations.containsKey(stopId)) continue;

      stations[stopId] = MtaStation(
        gtfsStopId: stopId,
        name: row[nameCol].toString(),
        borough: row[boroughCol].toString(),
        routes: row[routesCol]
            .toString()
            .split(' ')
            .where((r) => r.isNotEmpty)
            .toList(),
        northLabel: row[northLabelCol].toString(),
        southLabel: row[southLabelCol].toString(),
      );
    }

    final result = stations.values.toList()
      ..sort((a, b) => a.name.compareTo(b.name));
    _cache = result;
    return result;
  }
}
