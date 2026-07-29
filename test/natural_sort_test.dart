import 'package:flutter_test/flutter_test.dart';
import 'package:commuteos/transit/natural_sort.dart';

void main() {
  test('numbered stations sort numerically, not as strings', () {
    final names = ['110 St', '1 Av', '96 St', '23 St', '2 Av', '14 St'];
    names.sort(compareStationNames);

    expect(names, ['1 Av', '2 Av', '14 St', '23 St', '96 St', '110 St']);
  });

  test('numbered stations sort before lettered stations', () {
    final names = ['Astor Pl', '1 Av', 'Canal St'];
    names.sort(compareStationNames);

    expect(names, ['1 Av', 'Astor Pl', 'Canal St']);
  });

  test('lettered stations still sort alphabetically among themselves', () {
    final names = ['Canal St', 'Astor Pl', 'Broadway'];
    names.sort(compareStationNames);

    expect(names, ['Astor Pl', 'Broadway', 'Canal St']);
  });
}
