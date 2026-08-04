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

  testWidgets('skips stop_ids with no scheduled routes at all', (tester) async {
    // Regression test: several bay-level stop_ids at large terminals like
    // Journal Square Transportation Center have zero scheduled trips in
    // NJT's static GTFS (see build_njt_bus_stops.py) - these used to load
    // with an empty routeNames list and show as a confusing blank row with
    // no route badge. Confirmed real routeless stop_ids from the bundled
    // CSV as of this fix; if NJT's schedule data changes and one of these
    // gains a route, this assertion should be updated, not deleted.
    final repository = NjtBusStopRepository();

    late List stops;
    await tester.runAsync(() async {
      stops = await repository.loadStations();
    });

    const routelessStopIds = {'8278', '16020', '16021', '16801', '16945'};
    final loadedIds = stops.map((s) => s.stopId).toSet();
    expect(loadedIds.intersection(routelessStopIds), isEmpty);
    expect(stops.any((s) => s.routeNames.isEmpty), isFalse);
  });
}
