import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/main.dart';

void main() {
  testWidgets('App launches and shows the arrivals screen title', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const CommuteOSApp());

    expect(find.text('Union Square (N/Q/R/W, northbound)'), findsOneWidget);
  });
}
