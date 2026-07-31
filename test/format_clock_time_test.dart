import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/design/components.dart';

void main() {
  group('formatClockTime', () {
    test('formats a plain afternoon time', () {
      expect(formatClockTime(DateTime(2026, 1, 1, 17, 24)), '5:24 PM');
    });

    test('formats a plain morning time', () {
      expect(formatClockTime(DateTime(2026, 1, 1, 8, 5)), '8:05 AM');
    });

    test('midnight is 12 AM, not 0 AM', () {
      expect(formatClockTime(DateTime(2026, 1, 1, 0, 0)), '12:00 AM');
    });

    test('noon is 12 PM, not 0 PM', () {
      expect(formatClockTime(DateTime(2026, 1, 1, 12, 0)), '12:00 PM');
    });

    test('pads single-digit minutes', () {
      expect(formatClockTime(DateTime(2026, 1, 1, 9, 3)), '9:03 AM');
    });
  });
}
