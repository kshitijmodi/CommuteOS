import 'package:flutter_test/flutter_test.dart';
import 'package:commuteos/mta/mta_station.dart';
import 'package:commuteos/path/path_station.dart';
import 'package:commuteos/transit/station_group.dart';

MtaStation _mtaStation({
  required String stopId,
  required String complexId,
  required String name,
  List<String> routes = const ['1'],
}) {
  return MtaStation(
    gtfsStopId: stopId,
    complexId: complexId,
    name: name,
    borough: 'M',
    routes: routes,
    northLabel: 'Uptown',
    southLabel: 'Downtown',
  );
}

void main() {
  test('stations with distinct names each get their own group', () {
    final groups = StationGroup.groupByName([
      _mtaStation(stopId: 'A1', complexId: '1', name: '1 Av'),
      _mtaStation(stopId: 'A2', complexId: '2', name: '2 Av'),
    ]);

    expect(groups.length, 2);
    expect(groups.every((g) => g.hasSingleStation), isTrue);
  });

  test('multiple stations sharing a name are grouped together', () {
    // Mirrors the real "Canal St" case: some share a complex, one doesn't —
    // grouping is still by name, since the UI needs a picker either way.
    final groups = StationGroup.groupByName([
      _mtaStation(stopId: 'R23', complexId: '623', name: 'Canal St', routes: ['R', 'W']),
      _mtaStation(stopId: 'Q01', complexId: '623', name: 'Canal St', routes: ['N', 'Q']),
      _mtaStation(stopId: '135', complexId: '325', name: 'Canal St', routes: ['1']),
    ]);

    expect(groups.length, 1);
    expect(groups.single.stations.length, 3);
    expect(groups.single.hasSingleStation, isFalse);
  });

  test(
    'flags a real name collision between unconnected MTA complexes, e.g. "23 St"',
    () {
      // Regression test for a real bug: MTA's Stations.csv has four
      // separate, unconnected "23 St" stations (N/R/W, A/C/E, F/M, and the
      // 1 train) that share nothing but a plain name. StationListTile used
      // to union routes across every station sharing a name, so all four
      // rows showed M (and A/C/E, and 1, etc.) even on stations those
      // trains never serve - hasUnconnectedMtaCollision is what lets the
      // tile detect this and skip the misleading combined chip list.
      final groups = StationGroup.groupByName([
        _mtaStation(stopId: 'R19', complexId: '14', name: '23 St', routes: ['N', 'R', 'W']),
        _mtaStation(stopId: 'A30', complexId: '165', name: '23 St', routes: ['A', 'C', 'E']),
        _mtaStation(stopId: 'D18', complexId: '228', name: '23 St', routes: ['F', 'M']),
        _mtaStation(stopId: '130', complexId: '320', name: '23 St', routes: ['1']),
      ]);

      expect(groups.single.hasUnconnectedMtaCollision, isTrue);
    },
  );

  test(
    'does not flag a real connected complex (same complexId) as a collision',
    () {
      final groups = StationGroup.groupByName([
        _mtaStation(stopId: 'R23', complexId: '623', name: 'Canal St', routes: ['R', 'W']),
        _mtaStation(stopId: 'Q01', complexId: '623', name: 'Canal St', routes: ['N', 'Q']),
      ]);

      expect(groups.single.hasUnconnectedMtaCollision, isFalse);
    },
  );

  test('groups sort by natural station-name order', () {
    final groups = StationGroup.groupByName([
      _mtaStation(stopId: 'A', complexId: '1', name: '14 St'),
      _mtaStation(stopId: 'B', complexId: '2', name: '2 Av'),
      _mtaStation(stopId: 'C', complexId: '3', name: 'Astor Pl'),
    ]);

    expect(groups.map((g) => g.name).toList(), ['2 Av', '14 St', 'Astor Pl']);
  });

  test('stations from different agencies group together on name alone', () {
    // No real-world collision today (verified against MTA's Stations.csv),
    // but the grouping logic itself is agency-agnostic and should stay that
    // way — this proves it doesn't silently assume a single agency's types.
    final groups = StationGroup.groupByName([
      _mtaStation(stopId: 'X1', complexId: '1', name: 'Newark'),
      const PathStation(code: 'NWK', name: 'Newark', state: 'NJ', lat: 40.7344963, lng: -74.1638550),
    ]);

    expect(groups.length, 1);
    expect(groups.single.stations.length, 2);
  });

  test(
    'PATH stations at shared physical locations merge with MTA, not duplicate',
    () {
      // Regression test: PathStation.all previously used ordinal-suffixed
      // names ("14th St", "23rd St", "33rd St") that didn't match MTA's
      // exact station names ("14 St", "23 St", "33 St"), so tapping the
      // MTA row never surfaced PATH trains and vice versa — two separate
      // rows for what's actually one accessible physical location.
      final groups = StationGroup.groupByName([
        _mtaStation(stopId: '132', complexId: '166', name: '14 St', routes: ['1', '2', '3']),
        PathStation.all.firstWhere((s) => s.code == '14S'),
      ]);

      expect(groups.length, 1);
      expect(groups.single.stations.length, 2);
      // A PATH+MTA merge at a real shared location is intentional, not an
      // unconnected-MTA-complex collision (PATH isn't an MtaStation, so it
      // doesn't contribute a complexId) - the combined chip list is correct
      // here, unlike the "23 St" case above.
      expect(groups.single.hasUnconnectedMtaCollision, isFalse);
    },
  );
}
