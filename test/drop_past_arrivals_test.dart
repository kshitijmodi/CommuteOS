import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/transit/transit_models.dart';

TransitArrival _arrival(int minutesAway) {
  return TransitArrival(
    routeLabel: '59',
    arrivalTime: DateTime.now().add(Duration(minutes: minutesAway)),
  );
}

void main() {
  group('dropPastArrivals', () {
    test('drops arrivals well in the past', () {
      // Regression test for a real bug reported from the phone: NJT bus's
      // feed can still contain a stop_time_update from earlier in a trip
      // that has already passed this stop (e.g. an already-departed bus) -
      // MinutesAway collapses any non-positive countdown to "NOW", so a bus
      // that left 60/45/22/18 minutes ago all displayed identically as
      // "NOW" with no way to tell it was stale.
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {
          'arrivals': [_arrival(-60), _arrival(-45), _arrival(-22), _arrival(-18), _arrival(5)],
        },
        isLive: true,
      );

      final filtered = dropPastArrivals(result);

      expect(filtered.arrivalsByDirectionKey['arrivals']!.length, 1);
      expect(
        filtered.arrivalsByDirectionKey['arrivals']!.single.timeUntilArrival.inMinutes,
        closeTo(5, 1),
      );
    });

    test('keeps an arrival within the grace window (genuinely "now")', () {
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {
          'arrivals': [_arrival(0)],
        },
        isLive: true,
      );

      final filtered = dropPastArrivals(result);

      expect(filtered.arrivalsByDirectionKey['arrivals'], hasLength(1));
    });

    test('preserves isLive and every direction key, even if now empty', () {
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {
          'north': [_arrival(-30)],
          'south': [_arrival(10)],
        },
        isLive: false,
      );

      final filtered = dropPastArrivals(result);

      expect(filtered.isLive, isFalse);
      expect(filtered.arrivalsByDirectionKey['north'], isEmpty);
      expect(filtered.arrivalsByDirectionKey['south'], hasLength(1));
    });

    test('is a no-op when every arrival is already in the future', () {
      final result = TransitArrivalsResult(
        arrivalsByDirectionKey: {
          'arrivals': [_arrival(3), _arrival(12)],
        },
        isLive: true,
      );

      final filtered = dropPastArrivals(result);

      expect(filtered.arrivalsByDirectionKey['arrivals'], hasLength(2));
    });
  });
}
