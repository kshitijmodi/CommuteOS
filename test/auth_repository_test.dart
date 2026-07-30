import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/account/auth_repository.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('login stores the returned access token', () async {
    final repo = AuthRepository(
      client: MockClient((request) async {
        expect(request.url.path, '/auth/login');
        return http.Response('{"access_token": "fake-token", "token_type": "bearer"}', 200);
      }),
    );

    await repo.login('me@example.com', 'hunter2');

    expect(await repo.getToken(), 'fake-token');
    expect(await repo.isLoggedIn(), isTrue);
  });

  test('login throws AuthException with server detail on failure', () async {
    final repo = AuthRepository(
      client: MockClient((request) async {
        return http.Response('{"detail": "Incorrect email or password"}', 401);
      }),
    );

    expect(
      () => repo.login('me@example.com', 'wrong'),
      throwsA(
        isA<AuthException>().having(
          (e) => e.message,
          'message',
          'Incorrect email or password',
        ),
      ),
    );
  });

  test('signup logs the user in afterward', () async {
    var loginCalled = false;
    final repo = AuthRepository(
      client: MockClient((request) async {
        if (request.url.path == '/auth/signup') {
          return http.Response('{"id": "abc", "email": "new@example.com"}', 201);
        }
        loginCalled = true;
        return http.Response('{"access_token": "new-token"}', 200);
      }),
    );

    await repo.signup('new@example.com', 'hunter2');

    expect(loginCalled, isTrue);
    expect(await repo.getToken(), 'new-token');
  });

  test('logout clears the stored token', () async {
    final repo = AuthRepository(
      client: MockClient(
        (request) async => http.Response('{"access_token": "t"}', 200),
      ),
    );
    await repo.login('me@example.com', 'hunter2');
    expect(await repo.isLoggedIn(), isTrue);

    await repo.logout();

    expect(await repo.isLoggedIn(), isFalse);
  });

  test('isLoggedIn is false with no stored token', () async {
    final repo = AuthRepository();
    expect(await repo.isLoggedIn(), isFalse);
  });
}
