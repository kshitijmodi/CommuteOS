import 'package:csv/csv.dart';
import 'package:flutter/services.dart' show rootBundle;

import '../transit/natural_sort.dart';
import 'njt_rail_station.dart';

/// Loads and caches the bundled NJT rail station list
/// (assets/data/njt_rail_stations.csv, built from NJT's static GTFS rail
/// feed - see backend/scripts/build_njt_rail_stations.py).
class NjtRailStationRepository {
  static const _assetPath = 'assets/data/njt_rail_stations.csv';

  List<NjtRailStation>? _cache;

  Future<List<NjtRailStation>> loadStations() async {
    final cached = _cache;
    if (cached != null) return cached;

    final raw = await rootBundle.loadString(_assetPath);
    final rows = const CsvToListConverter(eol: '\n').convert(raw);

    final header = rows.first.cast<String>();
    final codeCol = header.indexOf('stop_code');
    final nameCol = header.indexOf('stop_name');
    final linesCol = header.indexOf('lines');
    final latCol = header.indexOf('lat');
    final lonCol = header.indexOf('lon');

    final stations = <NjtRailStation>[];
    for (final row in rows.skip(1)) {
      final code = row[codeCol].toString();
      if (code.isEmpty) continue;

      stations.add(
        NjtRailStation(
          code: code,
          name: row[nameCol].toString(),
          lines: row[linesCol]
              .toString()
              .split('|')
              .where((l) => l.isNotEmpty)
              .toList(),
          lat: double.tryParse(row[latCol].toString()) ?? 0,
          lng: double.tryParse(row[lonCol].toString()) ?? 0,
        ),
      );
    }

    stations.sort((a, b) => compareStationNames(a.name, b.name));
    _cache = stations;
    return stations;
  }
}
