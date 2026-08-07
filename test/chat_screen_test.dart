import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:commuteos/chat/chat_repository.dart';
import 'package:commuteos/chat/chat_screen.dart';
import 'package:commuteos/design/theme.dart';

Widget _wrap(Widget child) {
  return MaterialApp(theme: buildAppTheme(), home: child);
}

void main() {
  testWidgets('shows an empty-state prompt before any message is sent', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(ChatScreen(chatRepository: ChatRepository(client: MockClient(
        (request) async => http.Response('{"answer":"unused"}', 200),
      )))),
    );

    expect(find.textContaining('Ask about any station'), findsOneWidget);
  });

  testWidgets('sending a question shows the user message and the real answer', (
    tester,
  ) async {
    final repository = ChatRepository(
      client: MockClient(
        (request) async => http.Response(
          '{"answer":"The next PATH train is in 7 min.",'
          '"station_name":"Grove Street","agency":"path"}',
          200,
        ),
      ),
    );

    await tester.pumpWidget(_wrap(ChatScreen(chatRepository: repository)));

    await tester.enterText(find.byType(TextField), 'what\'s next from Grove Street');
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
    await tester.pumpAndSettle();

    expect(find.text('what\'s next from Grove Street'), findsOneWidget);
    expect(find.text('The next PATH train is in 7 min.'), findsOneWidget);
  });

  testWidgets('a backend error shows a real error bubble, not a crash', (
    tester,
  ) async {
    final repository = ChatRepository(
      client: MockClient(
        (request) async => http.Response('{"detail":"boom"}', 500),
      ),
    );

    await tester.pumpWidget(_wrap(ChatScreen(chatRepository: repository)));

    await tester.enterText(find.byType(TextField), 'anything');
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
    await tester.pumpAndSettle();

    expect(find.text('boom'), findsOneWidget);
  });

  testWidgets('the input is cleared after sending', (tester) async {
    final repository = ChatRepository(
      client: MockClient(
        (request) async => http.Response('{"answer":"ok"}', 200),
      ),
    );

    await tester.pumpWidget(_wrap(ChatScreen(chatRepository: repository)));

    await tester.enterText(find.byType(TextField), 'hello');
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
    await tester.pumpAndSettle();

    final textField = tester.widget<TextField>(find.byType(TextField));
    expect(textField.controller!.text, isEmpty);
  });

  testWidgets('does not send an empty/whitespace-only question', (tester) async {
    var wasCalled = false;
    final repository = ChatRepository(
      client: MockClient((request) async {
        wasCalled = true;
        return http.Response('{"answer":"ok"}', 200);
      }),
    );

    await tester.pumpWidget(_wrap(ChatScreen(chatRepository: repository)));

    await tester.enterText(find.byType(TextField), '   ');
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
    await tester.pumpAndSettle();

    expect(wasCalled, isFalse);
  });
}
