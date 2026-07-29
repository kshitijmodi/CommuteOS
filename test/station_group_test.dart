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
    expect(groups.single.allRoutes, ['1', 'N', 'Q', 'R', 'W']);
  });

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
      const PathStation(code: 'NWK', name: 'Newark', state: 'NJ'),
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
      expect(groups.single.allRoutes, containsAll(['1', '2', '3', 'PATH']));
    },
  );
}
