import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/account/home_office_repository.dart';

void main() {
  group('HomeOffice.fromJson', () {
    test('parses home/office stations, confirmed flag, and mode fields', () {
      final homeOffice = HomeOffice.fromJson({
        'home_station': 'JSQ',
        'office_station': 'WTC',
        'confirmed': true,
        'home_mode': 'path',
        'office_mode': 'mta',
      });

      expect(homeOffice.homeStation, 'JSQ');
      expect(homeOffice.officeStation, 'WTC');
      expect(homeOffice.confirmed, isTrue);
      expect(homeOffice.homeMode, 'path');
      expect(homeOffice.officeMode, 'mta');
    });

    test('mode fields are null when nothing has been inferred yet', () {
      // Real case this must handle: a brand-new user's first
      // GET /home-office/me, before any Trip has ever been logged.
      final homeOffice = HomeOffice.fromJson({
        'home_station': null,
        'office_station': null,
        'confirmed': false,
        'home_mode': null,
        'office_mode': null,
      });

      expect(homeOffice.homeMode, isNull);
      expect(homeOffice.officeMode, isNull);
      expect(homeOffice.hasInference, isFalse);
    });
  });
}
