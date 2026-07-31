import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/transit/arrivals_screen.dart';
import 'package:commuteos/transit/transit_models.dart';

TransitArrival _arrival(String? headSign, int minutesAway) {
  return TransitArrival(
    routeLabel: 'PATH',
    arrivalTime: DateTime.now().add(Duration(minutes: minutesAway)),
    headSign: headSign,
  );
}

void main() {
  group('groupByDestination (via arrivals_screen)', () {
    test('groups multiple destinations, sorted alphabetically', () {
      final arrivals = [
        _arrival('Newark', 4),
        _arrival('Hoboken', 1),
        _arrival('Newark', 9),
        _arrival('Hoboken', 9),
      ];

      final groups = groupArrivalsByDestination(arrivals);

      expect(groups, isNotNull);
      expect(groups!.keys.toList(), ['Hoboken', 'Newark']);
      expect(groups['Newark']!.length, 2);
      expect(groups['Hoboken']!.length, 2);
    });

    test('preserves soonest-first order within each destination group', () {
      final arrivals = [_arrival('Newark', 4), _arrival('Hoboken', 1), _arrival('Newark', 9)];

      final groups = groupArrivalsByDestination(arrivals);

      final newark = groups!['Newark']!;
      expect(newark[0].timeUntilArrival < newark[1].timeUntilArrival, isTrue);
    });

    test('returns null when only one destination exists', () {
      final arrivals = [_arrival('Newark', 4), _arrival('Newark', 9)];
      expect(groupArrivalsByDestination(arrivals), isNull);
    });

    test('returns null when no headsign data exists at all (MTA case)', () {
      final arrivals = [_arrival(null, 4), _arrival(null, 9)];
      expect(groupArrivalsByDestination(arrivals), isNull);
    });

    test('returns null when any arrival lacks a headsign, even if others have one', () {
      final arrivals = [_arrival('Newark', 4), _arrival(null, 9)];
      expect(groupArrivalsByDestination(arrivals), isNull);
    });
  });
}
