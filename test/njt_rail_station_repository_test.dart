import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/njt/njt_rail_station_repository.dart';

void main() {
  testWidgets('loads real NJT rail stations from the bundled CSV', (tester) async {
    final repository = NjtRailStationRepository();

    late List stations;
    await tester.runAsync(() async {
      stations = await repository.loadStations();
    });

    expect(stations, isNotEmpty);

    final newarkPenn = stations.firstWhere((s) => s.code == 'NP');
    expect(newarkPenn.name, 'Newark Penn Station');
    expect(newarkPenn.lines, isNotEmpty);
  });

  testWidgets('caches stations after the first load', (tester) async {
    final repository = NjtRailStationRepository();

    late List first;
    late List second;
    await tester.runAsync(() async {
      first = await repository.loadStations();
      second = await repository.loadStations();
    });

    expect(identical(first, second), isTrue);
  });
}
