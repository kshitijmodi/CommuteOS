import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/njt/njt_bus_stop_repository.dart';

void main() {
  testWidgets('loads real NJT bus stops from the bundled CSV', (tester) async {
    final repository = NjtBusStopRepository();

    late List stops;
    await tester.runAsync(() async {
      stops = await repository.loadStations();
    });

    expect(stops, isNotEmpty);
    // Real stop confirmed against the live GTFS-RT feed during development.
    final esplanade = stops.firstWhere((s) => s.stopId == '1941');
    expect(esplanade.routeNames, contains('163'));
  });

  testWidgets('caches stops after the first load', (tester) async {
    final repository = NjtBusStopRepository();

    late List first;
    late List second;
    await tester.runAsync(() async {
      first = await repository.loadStations();
      second = await repository.loadStations();
    });

    expect(identical(first, second), isTrue);
  });
}
