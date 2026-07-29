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
    // Asset loading (the bundled station CSV) goes through real async I/O,
    // which the fake clock behind tester.pump() doesn't advance — let it
    // run for real, then pump once to rebuild with the resolved data.
    await tester.runAsync(() => Future.delayed(const Duration(seconds: 1)));
    await tester.pump();

    expect(find.text('CommuteOS'), findsOneWidget);
    expect(find.text('No favorite stations yet.'), findsOneWidget);
  });
}
