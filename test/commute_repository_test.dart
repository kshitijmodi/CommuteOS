import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/account/auth_repository.dart';
import 'package:commuteos/commute/commute_repository.dart';

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

  group('getRecommendation', () {
    test('returns null when not logged in', () async {
      final repository = CommuteRepository(
        authRepository: AuthRepository(),
        client: MockClient((request) async => http.Response('{}', 200)),
      );

      final result = await repository.getRecommendation('mta', 'R01');

      expect(result, isNull);
    });

    test('returns null (not an error) when the backend 404s', () async {
      final authRepository = await _loggedInAuthRepository();
      final repository = CommuteRepository(
        authRepository: authRepository,
        client: MockClient((request) async => http.Response('{}', 404)),
      );

      final result = await repository.getRecommendation('mta', 'R01');

      expect(result, isNull);
    });

    test('calls the real endpoint and parses a real result', () async {
      final authRepository = await _loggedInAuthRepository();
      http.Request? capturedRequest;
      final repository = CommuteRepository(
        authRepository: authRepository,
        client: MockClient((request) async {
          capturedRequest = request;
          return http.Response(
            '{"mode":"mta","label":"N","predicted_arrival":"2026-01-01T08:05:00Z",'
            '"confidence":0.9,"is_live":true,"message":"Take the N - it should arrive around 8:05 AM.",'
            '"usual_route_or_direction":null,"differs_from_usual":false,"alternatives":[]}',
            200,
          );
        }),
      );

      final result = await repository.getRecommendation('mta', 'R01');

      expect(capturedRequest!.method, 'GET');
      expect(capturedRequest!.url.path, '/commute/mta/R01');
      expect(capturedRequest!.headers['Authorization'], 'Bearer tok123');
      expect(result, isNotNull);
      expect(result!.label, 'N');
      expect(result.differsFromUsual, isFalse);
      expect(result.usualRouteOrDirection, isNull);
      expect(result.alternatives, isEmpty);
    });

    test('parses real alternatives and a differs-from-usual result', () async {
      final authRepository = await _loggedInAuthRepository();
      final repository = CommuteRepository(
        authRepository: authRepository,
        client: MockClient(
          (request) async => http.Response(
            '{"mode":"mta","label":"N","predicted_arrival":"2026-01-01T08:05:00Z",'
            '"confidence":0.9,"is_live":true,"message":"Take the N instead of your usual W.",'
            '"usual_route_or_direction":"W","differs_from_usual":true,'
            '"alternatives":[{"mode":"mta","label":"W","predicted_arrival":"2026-01-01T08:10:00Z",'
            '"confidence":0.9,"is_live":true}]}',
            200,
          ),
        ),
      );

      final result = await repository.getRecommendation('mta', 'R01');

      expect(result!.differsFromUsual, isTrue);
      expect(result.usualRouteOrDirection, 'W');
      expect(result.alternatives, hasLength(1));
      expect(result.alternatives.single.label, 'W');
    });

    test('throws CommuteException for a real (non-404) backend error', () async {
      final authRepository = await _loggedInAuthRepository();
      final repository = CommuteRepository(
        authRepository: authRepository,
        client: MockClient((request) async => http.Response('{"detail":"boom"}', 500)),
      );

      expect(
        () => repository.getRecommendation('mta', 'R01'),
        throwsA(isA<CommuteException>()),
      );
    });
  });
}
