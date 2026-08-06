import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/account/auth_repository.dart';
import 'package:commuteos/account/recommendation_repository.dart';

Future<AuthRepository> _loggedInAuthRepository() async {
  final authRepository = AuthRepository(
    client: MockClient(
      (request) async => http.Response('{"access_token": "tok123"}', 200),
    ),
  );
  await authRepository.login('me@example.com', 'hunter2');
  return authRepository;
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('getRecommendationFromHomeOffice', () {
    test('returns null (not an error) when the backend 404s', () async {
      final authRepository = await _loggedInAuthRepository();
      final repository = RecommendationRepository(
        authRepository: authRepository,
        client: MockClient((request) async => http.Response('{}', 404)),
      );

      final result = await repository.getRecommendationFromHomeOffice();

      expect(result, isNull);
    });

    test('calls the from-home-office endpoint and parses a real result', () async {
      final authRepository = await _loggedInAuthRepository();
      http.Request? capturedRequest;
      final repository = RecommendationRepository(
        authRepository: authRepository,
        client: MockClient((request) async {
          capturedRequest = request;
          return http.Response(
            '{"mode":"mta","label":"R20N","predicted_arrival":"2026-01-01T08:10:00Z",'
            '"confidence":0.9,"is_live":true,"message":"Take the N.","trip_id":"abc"}',
            200,
          );
        }),
      );

      final result = await repository.getRecommendationFromHomeOffice();

      expect(capturedRequest!.method, 'GET');
      expect(capturedRequest!.url.path, '/recommendations/from-home-office');
      expect(result, isNotNull);
      expect(result!.mode, 'mta');
      expect(result.label, 'R20N');
      // No "alternatives" key in this payload at all - should default to
      // empty rather than throw, since older/simpler responses (or a
      // single-candidate comparison) never include one.
      expect(result.alternatives, isEmpty);
    });

    test('parses real alternatives when the backend compared 2+ candidates', () async {
      final authRepository = await _loggedInAuthRepository();
      final repository = RecommendationRepository(
        authRepository: authRepository,
        client: MockClient(
          (request) async => http.Response(
            '{"mode":"mta","label":"R20N","predicted_arrival":"2026-01-01T08:10:00Z",'
            '"confidence":0.9,"is_live":true,"message":"Take the N - it is sooner.",'
            '"trip_id":"abc","alternatives":[{"mode":"path","label":"PATH",'
            '"predicted_arrival":"2026-01-01T08:15:00Z","confidence":0.9,"is_live":true}]}',
            200,
          ),
        ),
      );

      final result = await repository.getRecommendationFromHomeOffice();

      expect(result!.alternatives, hasLength(1));
      expect(result.alternatives.single.mode, 'path');
      expect(result.alternatives.single.label, 'PATH');
    });

    test('throws for a real (non-404) backend error', () async {
      final authRepository = await _loggedInAuthRepository();
      final repository = RecommendationRepository(
        authRepository: authRepository,
        client: MockClient((request) async => http.Response('{"detail":"boom"}', 500)),
      );

      expect(
        () => repository.getRecommendationFromHomeOffice(),
        throwsA(isA<RecommendationException>()),
      );
    });

    test('throws when not logged in', () async {
      final repository = RecommendationRepository(
        authRepository: AuthRepository(),
        client: MockClient((request) async => http.Response('{}', 200)),
      );

      expect(
        () => repository.getRecommendationFromHomeOffice(),
        throwsA(isA<RecommendationException>()),
      );
    });
  });
}
