import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/main.dart';

void main() {
  testWidgets('App launches and shows the station search screen', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const CommuteOSApp());

    expect(find.text('CommuteOS'), findsOneWidget);
    expect(find.text('Search stations…'), findsOneWidget);
  });
}
