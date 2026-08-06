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

    expect(stops.any((s) => s.routeNames.isEmpty), isFalse);
  });

  testWidgets(
    'merges a large terminal\'s many bay-level stop_ids into one combined stop',
    (tester) async {
      // Regression test for a real bug: Journal Square Transportation
      // Center has ~26 separate stop_ids in NJT's static GTFS sharing this
      // exact name, with no single stop_id representing "every bus here" -
      // tapping into the station list used to force a pick among ~26
      // near-identical bay rows instead of showing one combined view.
      final repository = NjtBusStopRepository();

      late List stops;
      await tester.runAsync(() async {
        stops = await repository.loadStations();
      });

      final journalSquareEntries = stops
          .where((s) => s.name == 'JOURNAL SQUARE TRANSPORTATION CENTER')
          .toList();

      expect(journalSquareEntries, hasLength(1));
      final journalSquare = journalSquareEntries.single;
      expect(journalSquare.mergedStopIds.length, greaterThan(1));
      expect(journalSquare.allStopIds, journalSquare.mergedStopIds);
      // Routes across every bay should be present, de-duplicated, e.g. the
      // "1" bus (bay 16802/17010) and "10" bus (bay 16943/16948/etc.).
      expect(journalSquare.routeNames, contains('1'));
      expect(journalSquare.routeNames, contains('10'));
      expect(journalSquare.routeNames.toSet().length, journalSquare.routeNames.length);
    },
  );

  testWidgets('does not merge an ordinary single-bay stop', (tester) async {
    final repository = NjtBusStopRepository();

    late List stops;
    await tester.runAsync(() async {
      stops = await repository.loadStations();
    });

    final esplanade = stops.firstWhere((s) => s.stopId == '1941');
    expect(esplanade.mergedStopIds, isEmpty);
    expect(esplanade.allStopIds, ['1941']);
  });

  testWidgets(
    'does not merge two same-named stops that are actually far apart',
    (tester) async {
      // Regression test for a real bug reported from the phone: "1ST AVE AT
      // ALDENE RD" has two stop_ids (14573, 14582) in NJT's static GTFS
      // sharing this exact name, but they're ~113m apart - almost certainly
      // opposite-direction stops on either side of the intersection, not
      // bays of one terminal. The old merge-by-name-alone logic folded them
      // into one NjtBusStop, so a single arrivals fetch mixed both
      // directions' route 59 buses into one list - route 59 showed up to 7
      // times, several already past their arrival time. Confirmed via a
      // dataset-wide scan that this is not a one-off: 209 of 1,309
      // same-named stop_id groups are actually >60m apart. Fixed by only
      // merging same-named stop_ids within a real terminal's radius; stops
      // that fail that check now load as separate NjtBusStops sharing a
      // name, so StationGroup's existing collision picker handles them
      // instead of a silent, incorrect merge.
      final repository = NjtBusStopRepository();

      late List stops;
      await tester.runAsync(() async {
        stops = await repository.loadStations();
      });

      final aldeneEntries = stops.where((s) => s.name == '1ST AVE AT ALDENE RD').toList();

      expect(aldeneEntries, hasLength(2));
      for (final stop in aldeneEntries) {
        expect(stop.mergedStopIds, isEmpty);
      }
      expect(
        aldeneEntries.map((s) => s.stopId).toSet(),
        {'14573', '14582'},
      );
    },
  );

  testWidgets(
    'unmerged same-named stops get a real "toward" hint so they read as distinguishable',
    (tester) async {
      // Follow-up to the far-apart-stops fix above: once the two "1ST AVE
      // AT ALDENE RD" stop_ids stopped being wrongly merged, the station
      // picker showed two rows with identical route chips and identical
      // area text ("NJ") - visibly duplicated with no way to tell which
      // one a rider actually wants. Route 59's real route_long_name is
      // "Plainfield - Newark" (GTFS's <dir0 terminus> - <dir1 terminus>
      // convention); stop 14573 serves direction 1 (toward Newark) and
      // 14582 serves direction 0 (toward Plainfield) - confirmed against
      // NJT's real static GTFS bus feed.
      final repository = NjtBusStopRepository();

      late List stops;
      await tester.runAsync(() async {
        stops = await repository.loadStations();
      });

      final aldeneById = {
        for (final s in stops.where((s) => s.name == '1ST AVE AT ALDENE RD')) s.stopId: s,
      };

      expect(aldeneById['14573']!.toward, 'Newark');
      expect(aldeneById['14582']!.toward, 'Plainfield');
    },
  );

  testWidgets('a merged terminal has no "toward" hint (it covers every direction)', (
    tester,
  ) async {
    final repository = NjtBusStopRepository();

    late List stops;
    await tester.runAsync(() async {
      stops = await repository.loadStations();
    });

    final journalSquare = stops.firstWhere(
      (s) => s.name == 'JOURNAL SQUARE TRANSPORTATION CENTER',
    );

    expect(journalSquare.toward, isNull);
  });
}
