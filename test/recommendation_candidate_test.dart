import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/account/recommendation_repository.dart';
import 'package:commuteos/mta/mta_station.dart';
import 'package:commuteos/njt/njt_bus_stop.dart';
import 'package:commuteos/njt/njt_rail_station.dart';
import 'package:commuteos/path/path_station.dart';

void main() {
  group('RecommendationCandidate.toJson agency field', () {
    // Dart's Agency.name is camelCase ("njtRail", "njtBus"), but the
    // backend expects snake_case ("njt_rail", "njt_bus") matching its
    // Python module names - regression test for a real bug where these
    // were sent mismatched and would have failed backend validation.
    test('MTA station serializes agency as "mta"', () {
      const station = MtaStation(
        gtfsStopId: 'R20',
        complexId: '1',
        name: 'Union Sq',
        borough: 'M',
        routes: ['N'],
        northLabel: 'Uptown',
        southLabel: 'Downtown',
        lat: 40.7359,
        lng: -73.9906,
      );
      final candidate = RecommendationCandidate(station: station, routeOrDirection: 'N');
      expect(candidate.toJson()['agency'], 'mta');
    });

    test('PATH station serializes agency as "path"', () {
      const station = PathStation(code: 'JSQ', name: 'Journal Square', state: 'NJ', lat: 40.7318097, lng: -74.0628655);
      final candidate = RecommendationCandidate(station: station, routeOrDirection: 'ToNY');
      expect(candidate.toJson()['agency'], 'path');
    });

    test('NJT rail station serializes agency as "njt_rail", not "njtRail"', () {
      const station = NjtRailStation(
        code: 'NP',
        name: 'Newark Penn Station',
        lines: ['NEC'],
        lat: 40.7342,
        lng: -74.1645,
      );
      final candidate = RecommendationCandidate(station: station, routeOrDirection: '');
      expect(candidate.toJson()['agency'], 'njt_rail');
    });

    test('NJT bus stop serializes agency as "njt_bus", not "njtBus"', () {
      const station = NjtBusStop(
        stopId: '1941',
        name: 'The Esplanade',
        routeNames: ['163'],
        lat: 40.7357,
        lng: -74.0301,
      );
      final candidate = RecommendationCandidate(station: station, routeOrDirection: '');
      expect(candidate.toJson()['agency'], 'njt_bus');
    });
  });
}
