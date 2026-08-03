import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/account/auth_repository.dart';
import 'package:commuteos/account/push_registration_service.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('returns false when not logged in', () async {
    var called = false;
    final service = PushRegistrationService(
      authRepository: AuthRepository(),
      client: MockClient((request) async {
        called = true;
        return http.Response('{}', 200);
      }),
    );

    final result = await service.register();

    expect(result, isFalse);
    expect(called, isFalse);
  });

  test('registers a stub token when logged in', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    http.Request? capturedRequest;
    final service = PushRegistrationService(
      authRepository: authRepository,
      client: MockClient((request) async {
        capturedRequest = request;
        return http.Response('{}', 200);
      }),
    );

    final result = await service.register();

    expect(result, isTrue);
    expect(capturedRequest!.url.path, '/users/me/fcm-token');
    expect(capturedRequest!.method, 'PUT');
    expect(capturedRequest!.headers['Authorization'], 'Bearer tok123');
    expect(capturedRequest!.body, contains('"fcm_token":"stub-token-'));
  });

  test('returns false when the backend rejects the request', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    final service = PushRegistrationService(
      authRepository: authRepository,
      client: MockClient((request) async => http.Response('', 500)),
    );

    final result = await service.register();

    expect(result, isFalse);
  });
}
