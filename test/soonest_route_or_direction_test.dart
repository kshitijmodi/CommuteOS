import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/transit/arrivals_screen.dart';
import 'package:commuteos/transit/transit_models.dart';

TransitArrival _arrival(String routeLabel, int minutesAway) {
  return TransitArrival(
    routeLabel: routeLabel,
    arrivalTime: DateTime.now().add(Duration(minutes: minutesAway)),
  );
}

void main() {
  group('soonestRouteOrDirectionForTripLog', () {
    test('NJT rail always returns null', () {
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {
          'departures': [_arrival('NE', 5)],
        },
        isLive: true,
      );

      expect(soonestRouteOrDirectionForTripLog(Agency.njtRail, result), isNull);
    });

    test('NJT bus always returns null', () {
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {
          'arrivals': [_arrival('163', 5)],
        },
        isLive: true,
      );

      expect(soonestRouteOrDirectionForTripLog(Agency.njtBus, result), isNull);
    });

    test('MTA returns the route of the overall soonest arrival across directions', () {
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {
          'R20N': [_arrival('N', 9), _arrival('Q', 12)],
          'R20S': [_arrival('R', 3)],
        },
        isLive: true,
      );

      expect(soonestRouteOrDirectionForTripLog(Agency.mta, result), 'R');
    });

    test('PATH returns the direction key of the overall soonest arrival', () {
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {
          'ToNY': [_arrival('PATH', 8)],
          'ToNJ': [_arrival('PATH', 2)],
        },
        isLive: true,
      );

      expect(soonestRouteOrDirectionForTripLog(Agency.path, result), 'ToNJ');
    });

    test('MTA returns null when there are no arrivals at all', () {
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {'R20N': [], 'R20S': []},
        isLive: true,
      );

      expect(soonestRouteOrDirectionForTripLog(Agency.mta, result), isNull);
    });
  });
}
