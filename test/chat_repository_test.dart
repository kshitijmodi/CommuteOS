import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/account/auth_repository.dart';
import 'package:commuteos/chat/chat_repository.dart';
import 'package:commuteos/chat/location_service.dart';

Future<AuthRepository> _loggedInAuthRepository() async {
  final authRepository = AuthRepository(
    client: MockClient(
      (request) async => http.Response('{"access_token": "tok123"}', 200),
    ),
  );
  await authRepository.login('me@example.com', 'hunter2');
  return authRepository;
}

/// A fake that never touches the real geolocator plugin (which has no
/// platform implementation in a plain `flutter test` run) - returns
/// whatever fixed result the test configures, so these tests exercise
/// ChatRepository's own "should I even ask for location" logic and
/// request-body wiring, not the real GPS stack (which is covered live).
class _FakeLocationService implements LocationService {
  _FakeLocationService(this.result);

  final LocationResult result;
  int callCount = 0;

  @override
  Future<LocationResult> getCurrentLocation() async {
    callCount++;
    return result;
  }
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

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

    test('does not send an Authorization header when not logged in', () async {
      http.Request? capturedRequest;
      final repository = ChatRepository(
        authRepository: AuthRepository(),
        client: MockClient((request) async {
          capturedRequest = request;
          return http.Response('{"answer":"hi"}', 200);
        }),
      );

      await repository.ask('hi');

      expect(capturedRequest!.headers.containsKey('Authorization'), isFalse);
    });

    test('sends the real token when logged in, unlocking the personalized tier', () async {
      final authRepository = await _loggedInAuthRepository();
      http.Request? capturedRequest;
      final repository = ChatRepository(
        authRepository: authRepository,
        client: MockClient((request) async {
          capturedRequest = request;
          return http.Response('{"answer":"Take the N instead of your usual W."}', 200);
        }),
      );

      await repository.ask('what do I usually take from here');

      expect(capturedRequest!.headers['Authorization'], 'Bearer tok123');
    });

    test('fetches and sends real coordinates for a "nearest" question', () async {
      final fakeLocation = _FakeLocationService(
        const LocationResult.available(40.7318097, -74.0628655),
      );
      http.Request? capturedRequest;
      final repository = ChatRepository(
        locationService: fakeLocation,
        client: MockClient((request) async {
          capturedRequest = request;
          return http.Response(
            '{"answer":"Journal Square is 0.0 mi away.","station_name":"Journal Square","agency":"path"}',
            200,
          );
        }),
      );

      await repository.ask('what is the nearest path station to me?');

      expect(fakeLocation.callCount, 1);
      expect(capturedRequest!.body, contains('"lat":40.7318097'));
      expect(capturedRequest!.body, contains('"lng":-74.0628655'));
    });

    test('does not request location for a question with no location keyword', () async {
      final fakeLocation = _FakeLocationService(
        const LocationResult.available(40.7318097, -74.0628655),
      );
      final repository = ChatRepository(
        locationService: fakeLocation,
        client: MockClient(
          (request) async => http.Response(
            '{"answer":"The next PATH train is in 7 min.","station_name":"Grove Street","agency":"path"}',
            200,
          ),
        ),
      );

      await repository.ask('what\'s next from Grove Street');

      expect(fakeLocation.callCount, 0);
    });

    test('sends no lat/lng when location is unavailable', () async {
      final fakeLocation = _FakeLocationService(
        const LocationResult.unavailable('location permission denied'),
      );
      http.Request? capturedRequest;
      final repository = ChatRepository(
        locationService: fakeLocation,
        client: MockClient((request) async {
          capturedRequest = request;
          return http.Response(
            '{"answer":"I don\'t have your location.","station_name":null,"agency":null}',
            200,
          );
        }),
      );

      await repository.ask('what is the closest station to me?');

      expect(fakeLocation.callCount, 1);
      expect(capturedRequest!.body, isNot(contains('lat')));
      expect(capturedRequest!.body, isNot(contains('lng')));
    });

    test('sends the same real session id with every question - real conversation memory', () async {
      final requests = <http.Request>[];
      final repository = ChatRepository(
        client: MockClient((request) async {
          requests.add(request);
          return http.Response('{"answer":"ok"}', 200);
        }),
      );

      await repository.ask('what\'s next from Grove Street');
      await repository.ask('what time is the next one');

      expect(requests, hasLength(2));
      final firstBody = jsonDecode(requests[0].body) as Map<String, dynamic>;
      final secondBody = jsonDecode(requests[1].body) as Map<String, dynamic>;
      expect(firstBody['session_id'], isNotNull);
      // The SAME real id both times - this is what lets the backend
      // resolve the second question as a follow-up to the first, not two
      // unrelated single-turn questions.
      expect(secondBody['session_id'], firstBody['session_id']);
    });

    test('startNewConversation makes the NEXT question use a different session id', () async {
      final requests = <http.Request>[];
      final repository = ChatRepository(
        client: MockClient((request) async {
          requests.add(request);
          return http.Response('{"answer":"ok"}', 200);
        }),
      );

      await repository.ask('what\'s next from Grove Street');
      await repository.startNewConversation();
      await repository.ask('what\'s next from Hoboken');

      final firstBody = jsonDecode(requests[0].body) as Map<String, dynamic>;
      final secondBody = jsonDecode(requests[1].body) as Map<String, dynamic>;
      expect(secondBody['session_id'], isNot(firstBody['session_id']));
    });
  });
}
