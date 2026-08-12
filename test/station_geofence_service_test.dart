import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/account/auth_repository.dart';
import 'package:commuteos/account/home_office_repository.dart';
import 'package:commuteos/behavior/station_geofence_service.dart';
import 'package:commuteos/favorites/favorites_repository.dart';
import 'package:commuteos/transit/transit_models.dart';

Future<AuthRepository> _loggedInAuthRepository() async {
  final authRepository = AuthRepository(
    client: MockClient((request) async => http.Response('{"access_token": "tok123"}', 200)),
  );
  await authRepository.login('me@example.com', 'hunter2');
  return authRepository;
}

void main() {
  // stationsToGeofence loads bundled station CSVs via rootBundle
  // (MtaStationRepository etc.), which needs a real binding - plain
  // test() doesn't set one up the way testWidgets() automatically does.
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({'favorite_station_keys': <String>[]});
  });

  test('resolves a favorited PATH station to a real station with coordinates', () async {
    SharedPreferences.setMockInitialValues({
      'favorite_station_keys': ['path:JSQ'],
    });
    final homeOfficeRepository = HomeOfficeRepository(
      authRepository: await _loggedInAuthRepository(),
      client: MockClient(
        (request) async => http.Response(
          '{"home_station": null, "office_station": null, "confirmed": false, '
          '"home_mode": null, "office_mode": null}',
          200,
        ),
      ),
    );
    final service = StationGeofenceService(
      favoritesRepository: FavoritesRepository(),
      homeOfficeRepository: homeOfficeRepository,
    );

    final stations = await service.stationsToGeofence();

    expect(stations, hasLength(1));
    expect(stations.first.agency, Agency.path);
    expect(stations.first.id, 'JSQ');
    expect(stations.first.lat, isNotNull);
    expect(stations.first.lng, isNotNull);
  });

  test('resolves the inferred home station even when not favorited', () async {
    final homeOfficeRepository = HomeOfficeRepository(
      authRepository: await _loggedInAuthRepository(),
      client: MockClient(
        (request) async => http.Response(
          '{"home_station": "JSQ", "office_station": null, "confirmed": true, '
          '"home_mode": "path", "office_mode": null}',
          200,
        ),
      ),
    );
    final service = StationGeofenceService(
      favoritesRepository: FavoritesRepository(),
      homeOfficeRepository: homeOfficeRepository,
    );

    final stations = await service.stationsToGeofence();

    expect(stations, hasLength(1));
    expect(stations.first.agency, Agency.path);
    expect(stations.first.id, 'JSQ');
  });

  test('a favorited station that is also the inferred home station is not duplicated', () async {
    SharedPreferences.setMockInitialValues({
      'favorite_station_keys': ['path:JSQ'],
    });
    final homeOfficeRepository = HomeOfficeRepository(
      authRepository: await _loggedInAuthRepository(),
      client: MockClient(
        (request) async => http.Response(
          '{"home_station": "JSQ", "office_station": null, "confirmed": true, '
          '"home_mode": "path", "office_mode": null}',
          200,
        ),
      ),
    );
    final service = StationGeofenceService(
      favoritesRepository: FavoritesRepository(),
      homeOfficeRepository: homeOfficeRepository,
    );

    final stations = await service.stationsToGeofence();

    expect(stations, hasLength(1));
  });

  test('resolves both a favorited MTA station and a different inferred office station', () async {
    SharedPreferences.setMockInitialValues({
      'favorite_station_keys': ['mta:R20'],
    });
    final homeOfficeRepository = HomeOfficeRepository(
      authRepository: await _loggedInAuthRepository(),
      client: MockClient(
        (request) async => http.Response(
          '{"home_station": null, "office_station": "WTC", "confirmed": true, '
          '"home_mode": null, "office_mode": "path"}',
          200,
        ),
      ),
    );
    final service = StationGeofenceService(
      favoritesRepository: FavoritesRepository(),
      homeOfficeRepository: homeOfficeRepository,
    );

    final stations = await service.stationsToGeofence();

    expect(stations.map((s) => '${s.agency.name}:${s.id}').toSet(), {'mta:R20', 'path:WTC'});
  });

  test('an unresolvable home station code (agency mismatch) is skipped, not crashed on', () async {
    // Real defensive case: home_mode names a real agency but home_station
    // doesn't match any real station in that agency's data - should never
    // happen given the backend only ever writes a real inferred code, but
    // this must not throw if it somehow did.
    final homeOfficeRepository = HomeOfficeRepository(
      authRepository: await _loggedInAuthRepository(),
      client: MockClient(
        (request) async => http.Response(
          '{"home_station": "NOT_A_REAL_CODE", "office_station": null, "confirmed": true, '
          '"home_mode": "path", "office_mode": null}',
          200,
        ),
      ),
    );
    final service = StationGeofenceService(
      favoritesRepository: FavoritesRepository(),
      homeOfficeRepository: homeOfficeRepository,
    );

    final stations = await service.stationsToGeofence();

    expect(stations, isEmpty);
  });

  test('no favorites and no home/office inference resolves to an empty list', () async {
    final homeOfficeRepository = HomeOfficeRepository(
      authRepository: await _loggedInAuthRepository(),
      client: MockClient(
        (request) async => http.Response(
          '{"home_station": null, "office_station": null, "confirmed": false, '
          '"home_mode": null, "office_mode": null}',
          200,
        ),
      ),
    );
    final service = StationGeofenceService(
      favoritesRepository: FavoritesRepository(),
      homeOfficeRepository: homeOfficeRepository,
    );

    final stations = await service.stationsToGeofence();

    expect(stations, isEmpty);
  });
}
