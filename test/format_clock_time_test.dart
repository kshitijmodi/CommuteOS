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

    test('converts a UTC-flagged time to local before formatting', () {
      // Regression test for a real bug: NJT rail/bus arrivals arrive as
      // UTC-flagged DateTimes (parsed from the backend's ISO timestamps -
      // see njt_rail_service.dart/njt_bus_service.dart), but this used to
      // read .hour/.minute directly off the UTC value, displaying the raw
      // UTC wall-clock time instead of the device's real local time - off
      // by the UTC/Eastern offset (~4-5h), while the "N min" countdown
      // next to it looked correct (a timezone-agnostic instant
      // difference), masking the bug. Asserted against a locally-computed
      // expectation (not a hardcoded clock string) since the correct
      // output depends on whatever timezone the test machine is in - the
      // bug this guards against is "ignores tzinfo entirely," which this
      // still catches on any machine.
      final utcTime = DateTime.utc(2026, 1, 1, 20, 24);
      final expectedLocal = utcTime.toLocal();
      final expectedHour12 = expectedLocal.hour % 12 == 0 ? 12 : expectedLocal.hour % 12;
      final expectedMinute = expectedLocal.minute.toString().padLeft(2, '0');
      final expectedPeriod = expectedLocal.hour < 12 ? 'AM' : 'PM';

      expect(
        formatClockTime(utcTime),
        '$expectedHour12:$expectedMinute $expectedPeriod',
      );
    });
  });
}
