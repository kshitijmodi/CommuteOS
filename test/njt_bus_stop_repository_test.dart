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
    // Real stop confirmed against the current bundled CSV (NJT wholesale
    // renumbered stop_ids since this test was first written - see
    // OPEN_QUESTIONS.md's 2026-08-13 entry - the old "1941"/Esplanade
    // example no longer exists under that id, so this was updated to a
    // real, currently-correct stop rather than left pointing at stale data).
    final stop = stops.firstWhere((s) => s.stopId == '11092');
    expect(stop.routeNames, contains('76'));
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

    final stop = stops.firstWhere((s) => s.stopId == '11092');
    expect(stop.mergedStopIds, isEmpty);
    expect(stop.allStopIds, ['11092']);
  });

  testWidgets(
    'does not merge two same-named stops that are actually far apart',
    (tester) async {
      // Regression test for a real bug reported from the phone: two
      // stop_ids sharing an exact name can be genuinely different physical
      // stops on opposite sides of an intersection/street rather than bays
      // of one terminal - the old merge-by-name-alone logic folded them
      // into one NjtBusStop, mixing both directions' arrivals into one
      // list. Confirmed via a dataset-wide scan that this is not a
      // one-off: hundreds of same-named stop_id groups are actually >60m
      // apart. Fixed by only merging same-named stop_ids within a real
      // terminal's radius.
      //
      // Real example updated 2026-08-13: NJT wholesale renumbered their
      // bus stop_ids since this test was first written (see
      // OPEN_QUESTIONS.md's 2026-08-13 entry) - the original "1ST AVE AT
      // ALDENE RD" (stop_ids 14573/14582) no longer exists under those
      // ids, so this now uses a real, currently-correct far-apart pair
      // instead of stale ones.
      final repository = NjtBusStopRepository();

      late List stops;
      await tester.runAsync(() async {
        stops = await repository.loadStations();
      });

      final entries = stops
          .where((s) => s.name == 'PATERSON PLANK RD AT MURRAY HILL PKWY')
          .toList();

      expect(entries, hasLength(2));
      for (final stop in entries) {
        expect(stop.mergedStopIds, isEmpty);
      }
      expect(
        entries.map((s) => s.stopId).toSet(),
        {'11108', '11334'},
      );
    },
  );

  testWidgets(
    'unmerged same-named stops get a real "toward" hint so they read as distinguishable',
    (tester) async {
      // Follow-up to the far-apart-stops fix above: once a real far-apart
      // same-named pair stops being wrongly merged, the station picker
      // showed two rows with identical route chips and identical area
      // text ("NJ") - visibly duplicated with no way to tell which one a
      // rider actually wants. Real example updated 2026-08-13 alongside
      // the far-apart test above, for the same reason (NJT's stop_id
      // renumbering) - confirmed against the current bundled CSV.
      final repository = NjtBusStopRepository();

      late List stops;
      await tester.runAsync(() async {
        stops = await repository.loadStations();
      });

      final byId = {
        for (final s in stops.where((s) => s.name == 'PATERSON PLANK RD AT MURRAY HILL PKWY'))
          s.stopId: s,
      };

      expect(byId['11108']!.toward, 'Ridgewood');
      expect(byId['11334']!.toward, 'New York');
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
