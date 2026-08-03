import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/account/auth_repository.dart';
import 'package:commuteos/account/push_registration_service.dart';

class _FakeTokenProvider implements PushTokenProvider {
  _FakeTokenProvider({this.permissionGranted = true, this.token = 'fake-fcm-token'});

  final bool permissionGranted;
  final String? token;

  @override
  Future<bool> requestPermission() async => permissionGranted;

  @override
  Future<String?> getToken() async => token;
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('returns false when not logged in', () async {
    var called = false;
    final service = PushRegistrationService(
      authRepository: AuthRepository(),
      tokenProvider: _FakeTokenProvider(),
      client: MockClient((request) async {
        called = true;
        return http.Response('{}', 200);
      }),
    );

    final result = await service.register();

    expect(result, isFalse);
    expect(called, isFalse);
  });

  test('registers the real FCM token when logged in and permitted', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    http.Request? capturedRequest;
    final service = PushRegistrationService(
      authRepository: authRepository,
      tokenProvider: _FakeTokenProvider(token: 'device-token-xyz'),
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
    expect(capturedRequest!.body, contains('"fcm_token":"device-token-xyz"'));
  });

  test('returns false when the user declines the notification permission', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    var called = false;
    final service = PushRegistrationService(
      authRepository: authRepository,
      tokenProvider: _FakeTokenProvider(permissionGranted: false),
      client: MockClient((request) async {
        called = true;
        return http.Response('{}', 200);
      }),
    );

    final result = await service.register();

    expect(result, isFalse);
    expect(called, isFalse);
  });

  test('returns false when no token could be obtained', () async {
    final authRepository = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "tok123"}', 200),
      ),
    );
    await authRepository.login('me@example.com', 'hunter2');

    final service = PushRegistrationService(
      authRepository: authRepository,
      tokenProvider: _FakeTokenProvider(token: null),
      client: MockClient((request) async => http.Response('{}', 200)),
    );

    final result = await service.register();

    expect(result, isFalse);
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
      tokenProvider: _FakeTokenProvider(),
      client: MockClient((request) async => http.Response('', 500)),
    );

    final result = await service.register();

    expect(result, isFalse);
  });
}
