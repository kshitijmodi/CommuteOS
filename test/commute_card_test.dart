import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/commute/commute_card.dart';
import 'package:commuteos/commute/commute_repository.dart';
import 'package:commuteos/design/theme.dart';
import 'package:commuteos/transit/transit_models.dart';

Widget _wrap(Widget child) {
  return MaterialApp(theme: buildAppTheme(), home: Scaffold(body: child));
}

CommuteRecommendation _recommendation({
  String label = 'N',
  String message = 'Take the N - it should arrive around 8:05 AM.',
  String? usualRouteOrDirection,
  bool differsFromUsual = false,
  List<CommuteAlternative> alternatives = const [],
}) {
  return CommuteRecommendation(
    mode: 'mta',
    label: label,
    predictedArrival: DateTime.utc(2026, 1, 1, 8, 5),
    confidence: 0.9,
    isLive: true,
    message: message,
    usualRouteOrDirection: usualRouteOrDirection,
    differsFromUsual: differsFromUsual,
    alternatives: alternatives,
  );
}

void main() {
  testWidgets('shows the real phrased message and label', (tester) async {
    await tester.pumpWidget(
      _wrap(CommuteCard(agency: Agency.mta, recommendation: _recommendation())),
    );

    expect(
      find.text('Take the N - it should arrive around 8:05 AM.'),
      findsOneWidget,
    );
    expect(find.text('Best option right now'), findsOneWidget);
  });

  testWidgets('shows "take this instead" framing when it differs from usual', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        CommuteCard(
          agency: Agency.mta,
          recommendation: _recommendation(
            usualRouteOrDirection: 'W',
            differsFromUsual: true,
            alternatives: [
              CommuteAlternative(
                mode: 'mta',
                label: 'W',
                predictedArrival: DateTime.utc(2026, 1, 1, 8, 10),
                confidence: 0.9,
                isLive: true,
              ),
            ],
          ),
        ),
      ),
    );

    expect(find.text('Take this instead'), findsOneWidget);
    expect(find.text('Compared against'), findsOneWidget);
  });

  testWidgets('does not show the alternatives section when there are none', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(CommuteCard(agency: Agency.mta, recommendation: _recommendation())),
    );

    expect(find.text('Compared against'), findsNothing);
  });
}
