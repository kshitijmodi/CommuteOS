import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/main.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('App launches and shows the empty favorites state', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const CommuteOSApp());
    // Asset loading (the bundled station CSVs - MTA, NJT rail, NJT bus)
    // goes through real async I/O, which the fake clock behind
    // tester.pump() doesn't advance — poll with runAsync until the loaded
    // state actually appears, rather than a fixed delay that gets flakier
    // as more/larger CSVs are bundled over time.
    for (var i = 0; i < 20; i++) {
      await tester.runAsync(() => Future.delayed(const Duration(milliseconds: 250)));
      await tester.pump();
      if (find.text('No favorite stations yet').evaluate().isNotEmpty) break;
    }

    expect(find.text('CommuteOS'), findsOneWidget);
    expect(find.text('No favorite stations yet'), findsOneWidget);
  });
}
