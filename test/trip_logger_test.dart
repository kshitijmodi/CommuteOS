import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/account/auth_repository.dart';
import 'package:commuteos/account/trip_logger.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('does not call the network when logged out', () async {
    var called = false;
    final logger = TripLogger(
      authRepository: AuthRepository(),
      client: MockClient((request) async {
        called = true;
        return http.Response('', 201);
      }),
    );

    await logger.logStationView(mode: 'mta', originStop: 'R20N');

    expect(called, isFalse);
  });

  test('posts a trip with the stored token when logged in', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    http.Request? capturedRequest;
    final logger = TripLogger(
      authRepository: authRepository,
      client: MockClient((request) async {
        capturedRequest = request as http.Request;
        return http.Response('{}', 201);
      }),
    );

    await logger.logStationView(mode: 'path', originStop: 'JSQ');

    expect(capturedRequest, isNotNull);
    expect(capturedRequest!.url.path, '/trips');
    expect(capturedRequest!.headers['Authorization'], 'Bearer tok123');
    expect(capturedRequest!.body, contains('"mode":"path"'));
    expect(capturedRequest!.body, contains('"origin_stop":"JSQ"'));
  });

  test('swallows network errors without throwing', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    final logger = TripLogger(
      authRepository: authRepository,
      client: MockClient((request) async => throw Exception('offline')),
    );

    await expectLater(
      logger.logStationView(mode: 'mta', originStop: 'R20N'),
      completes,
    );
  });
}
