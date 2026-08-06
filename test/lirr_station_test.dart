import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/lirr/lirr_station.dart';

void main() {
  group('lirrBranchAbbreviation', () {
    test('uses the known short code for a real branch', () {
      expect(lirrBranchAbbreviation('Babylon Branch'), 'BAB');
      expect(lirrBranchAbbreviation('Montauk Branch'), 'MTK');
      expect(lirrBranchAbbreviation('Port Washington Branch'), 'PW');
    });

    test('falls back to the first 3 letters for an unrecognized branch', () {
      expect(lirrBranchAbbreviation('Future Extension'), 'FUT');
    });
  });

  group('LirrStation', () {
    test('routes returns abbreviations, not full branch names', () {
      const station = LirrStation(
        stopId: '102',
        code: 'JAM',
        name: 'Jamaica',
        branches: ['Babylon Branch', 'Montauk Branch'],
      );

      expect(station.routes, ['BAB', 'MTK']);
    });

    test('id is the public station code, not the internal stop_id', () {
      const station = LirrStation(
        stopId: '102',
        code: 'JAM',
        name: 'Jamaica',
        branches: ['Babylon Branch'],
      );

      expect(station.id, 'JAM');
      expect(station.stopId, '102');
    });
  });
}
