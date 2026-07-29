import 'package:flutter_test/flutter_test.dart';
import 'package:commuteos/mta/mta_station.dart';
import 'package:commuteos/mta/station_group.dart';

MtaStation _station({
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
      _station(stopId: 'A1', complexId: '1', name: '1 Av'),
      _station(stopId: 'A2', complexId: '2', name: '2 Av'),
    ]);

    expect(groups.length, 2);
    expect(groups.every((g) => g.hasSingleStation), isTrue);
  });

  test('multiple stations sharing a name are grouped together', () {
    // Mirrors the real "Canal St" case: some share a complex, one doesn't —
    // grouping is still by name, since the UI needs a picker either way.
    final groups = StationGroup.groupByName([
      _station(stopId: 'R23', complexId: '623', name: 'Canal St', routes: ['R', 'W']),
      _station(stopId: 'Q01', complexId: '623', name: 'Canal St', routes: ['N', 'Q']),
      _station(stopId: '135', complexId: '325', name: 'Canal St', routes: ['1']),
    ]);

    expect(groups.length, 1);
    expect(groups.single.stations.length, 3);
    expect(groups.single.hasSingleStation, isFalse);
    expect(groups.single.allRoutes, ['1', 'N', 'Q', 'R', 'W']);
  });

  test('groups sort by natural station-name order', () {
    final groups = StationGroup.groupByName([
      _station(stopId: 'A', complexId: '1', name: '14 St'),
      _station(stopId: 'B', complexId: '2', name: '2 Av'),
      _station(stopId: 'C', complexId: '3', name: 'Astor Pl'),
    ]);

    expect(groups.map((g) => g.name).toList(), ['2 Av', '14 St', 'Astor Pl']);
  });
}
