import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/lirr/lirr_station_repository.dart';

void main() {
  testWidgets('loads real LIRR stations from the bundled CSV', (tester) async {
    final repository = LirrStationRepository();

    late List stations;
    await tester.runAsync(() async {
      stations = await repository.loadStations();
    });

    expect(stations, isNotEmpty);

    // Jamaica is a real hub served by most of LIRR's 13 branches -
    // confirmed against the actual static GTFS during development.
    final jamaica = stations.firstWhere((s) => s.code == 'JAM');
    expect(jamaica.name, 'Jamaica');
    expect(jamaica.stopId, '102');
    expect(jamaica.branches.length, greaterThan(5));
    expect(jamaica.branches, contains('Babylon Branch'));
  });

  testWidgets(
    'excludes stations with no scheduled branches (e.g. Belmont Park)',
    (tester) async {
      // Regression-style test: Belmont Park only runs during racing
      // season/major events, so the current static GTFS has near-zero
      // regular scheduled trips there - same reasoning as NJT bus's
      // routeless-stop filtering (NjtBusStopRepository).
      final repository = LirrStationRepository();

      late List stations;
      await tester.runAsync(() async {
        stations = await repository.loadStations();
      });

      expect(stations.any((s) => s.code == 'BRT'), isFalse);
      expect(stations.any((s) => s.branches.isEmpty), isFalse);
    },
  );

  testWidgets('caches stations after the first load', (tester) async {
    final repository = LirrStationRepository();

    late List first;
    late List second;
    await tester.runAsync(() async {
      first = await repository.loadStations();
      second = await repository.loadStations();
    });

    expect(identical(first, second), isTrue);
  });
}
