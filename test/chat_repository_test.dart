import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:commuteos/chat/chat_repository.dart';

void main() {
  group('ask', () {
    test('sends the question and parses a real arrivals answer', () async {
      http.Request? capturedRequest;
      final repository = ChatRepository(
        client: MockClient((request) async {
          capturedRequest = request;
          return http.Response(
            '{"answer":"The next PATH train is in 7 min.",'
            '"station_name":"Grove Street","agency":"path"}',
            200,
          );
        }),
      );

      final result = await repository.ask('what\'s next from Grove Street');

      expect(capturedRequest!.method, 'POST');
      expect(capturedRequest!.url.path, '/chat');
      expect(capturedRequest!.body, contains('what\'s next from Grove Street'));
      expect(result.text, 'The next PATH train is in 7 min.');
      expect(result.stationName, 'Grove Street');
      expect(result.agency, 'path');
    });

    test('parses a clarifying answer with no station resolved', () async {
      final repository = ChatRepository(
        client: MockClient(
          (request) async => http.Response(
            '{"answer":"I couldn\'t find a station matching that.",'
            '"station_name":null,"agency":null}',
            200,
          ),
        ),
      );

      final result = await repository.ask('nonsense query');

      expect(result.stationName, isNull);
      expect(result.agency, isNull);
    });

    test('throws ChatException with the real error detail on failure', () async {
      final repository = ChatRepository(
        client: MockClient(
          (request) async => http.Response('{"detail":"boom"}', 500),
        ),
      );

      expect(
        () => repository.ask('anything'),
        throwsA(
          isA<ChatException>().having((e) => e.message, 'message', 'boom'),
        ),
      );
    });

    test('falls back to a generic message when the error body is not JSON', () async {
      final repository = ChatRepository(
        client: MockClient((request) async => http.Response('not json', 502)),
      );

      expect(() => repository.ask('anything'), throwsA(isA<ChatException>()));
    });

    test('requires no auth header', () async {
      http.Request? capturedRequest;
      final repository = ChatRepository(
        client: MockClient((request) async {
          capturedRequest = request;
          return http.Response('{"answer":"hi"}', 200);
        }),
      );

      await repository.ask('hi');

      expect(capturedRequest!.headers.containsKey('Authorization'), isFalse);
    });
  });
}
