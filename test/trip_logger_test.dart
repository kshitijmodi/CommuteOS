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
        capturedRequest = request;
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

  test('includes route_or_direction when provided', () async {
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
        capturedRequest = request;
        return http.Response('{}', 201);
      }),
    );

    await logger.logStationView(
      mode: 'mta',
      originStop: 'R20N',
      routeOrDirection: 'N',
    );

    expect(capturedRequest!.body, contains('"route_or_direction":"N"'));
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

  test('returns the real trip id on success', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    final logger = TripLogger(
      authRepository: authRepository,
      client: MockClient(
        (request) async => http.Response('{"id": "trip-abc-123"}', 201),
      ),
    );

    final tripId = await logger.logStationView(mode: 'mta', originStop: 'R20N');

    expect(tripId, 'trip-abc-123');
  });

  test('returns null when logged out', () async {
    final logger = TripLogger(
      authRepository: AuthRepository(),
      client: MockClient((request) async => http.Response('{}', 201)),
    );

    final tripId = await logger.logStationView(mode: 'mta', originStop: 'R20N');

    expect(tripId, isNull);
  });

  test('returns null on a failed request', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    final logger = TripLogger(
      authRepository: authRepository,
      client: MockClient((request) async => http.Response('', 500)),
    );

    final tripId = await logger.logStationView(mode: 'mta', originStop: 'R20N');

    expect(tripId, isNull);
  });

  group('reportLeftAt', () {
    test('PATCHes left_at with the stored token when logged in', () async {
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
          capturedRequest = request;
          return http.Response('{}', 200);
        }),
      );

      final leftAt = DateTime.utc(2026, 1, 1, 8, 0);
      await logger.reportLeftAt('trip-abc-123', leftAt);

      expect(capturedRequest, isNotNull);
      expect(capturedRequest!.method, 'PATCH');
      expect(capturedRequest!.url.path, '/trips/trip-abc-123/outcome');
      expect(capturedRequest!.headers['Authorization'], 'Bearer tok123');
      expect(capturedRequest!.body, contains('"left_at"'));
      expect(capturedRequest!.body, contains('2026-01-01T08:00:00.000Z'));
    });

    test('does not call the network when logged out', () async {
      var called = false;
      final logger = TripLogger(
        authRepository: AuthRepository(),
        client: MockClient((request) async {
          called = true;
          return http.Response('{}', 200);
        }),
      );

      await logger.reportLeftAt('trip-abc-123', DateTime.now());

      expect(called, isFalse);
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
        logger.reportLeftAt('trip-abc-123', DateTime.now()),
        completes,
      );
    });
  });
}
