import 'package:csv/csv.dart';
import 'package:flutter/services.dart' show rootBundle;

import '../transit/natural_sort.dart';
import 'lirr_station.dart';

/// Loads and caches the bundled LIRR station list
/// (assets/data/lirr_stations.csv, built from the MTA's static LIRR GTFS
/// feed - see backend/scripts/build_lirr_stations.py).
class LirrStationRepository {
  static const _assetPath = 'assets/data/lirr_stations.csv';

  List<LirrStation>? _cache;

  Future<List<LirrStation>> loadStations() async {
    final cached = _cache;
    if (cached != null) return cached;

    final raw = await rootBundle.loadString(_assetPath);
    final rows = const CsvToListConverter(eol: '\n').convert(raw);

    final header = rows.first.cast<String>();
    final stopIdCol = header.indexOf('stop_id');
    final codeCol = header.indexOf('stop_code');
    final nameCol = header.indexOf('stop_name');
    final branchesCol = header.indexOf('branches');
    final latCol = header.indexOf('lat');
    final lonCol = header.indexOf('lon');

    final stations = <LirrStation>[];
    for (final row in rows.skip(1)) {
      final code = row[codeCol].toString();
      if (code.isEmpty) continue;

      final branches = row[branchesCol]
          .toString()
          .split('|')
          .where((b) => b.isNotEmpty)
          .toList();
      // A station with no scheduled branches at all (e.g. Belmont Park,
      // which only runs during racing season/major events - confirmed via
      // the current static GTFS having near-zero regular scheduled trips
      // there) has nothing real to show - same reasoning as NJT bus's
      // routeless-stop filtering (NjtBusStopRepository).
      if (branches.isEmpty) continue;

      stations.add(
        LirrStation(
          stopId: row[stopIdCol].toString(),
          code: code,
          name: row[nameCol].toString(),
          branches: branches,
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
