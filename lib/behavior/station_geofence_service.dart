import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:native_geofence/native_geofence.dart';

import '../account/api_config.dart';
import '../account/auth_repository.dart';
import '../account/home_office_repository.dart';
import '../favorites/favorites_repository.dart';
import '../lirr/lirr_station_repository.dart';
import '../mta/mta_station_repository.dart';
import '../njt/njt_bus_stop_repository.dart';
import '../njt/njt_rail_station_repository.dart';
import '../path/path_station.dart';
import '../transit/transit_models.dart';
import 'trip_log_debounce.dart';

/// Real background geofencing: detects arrival at a favorited/home/office
/// station even with the app fully closed, so a real Trip gets logged for
/// Behavior AI without requiring the user to open that station's arrivals
/// screen first (the only trigger that existed before this - see
/// TripLogger's docs). Built 2026-08-12 after a real user question ("I keep
/// walking toward Journal Square but never get anything from Schedule
/// AI/Commute AI - is Behavior AI even gathering anything?") traced back to
/// exactly this gap.
///
/// Uses the native_geofence package - verified via its actual source (not
/// just its README/pub.dev description, same rigor as the earlier Activity
/// Recognition plugin research) to register real OS-level geofences
/// through Android's GeofencingClient/Geofence API, delivered to a
/// standalone BroadcastReceiver + WorkManager rather than a plugin that
/// fakes geofencing with a battery-draining continuous-polling foreground
/// service (see pubspec.yaml's dependency comment for the ruled-out
/// alternatives).
///
/// Deliberately geofences only a small, explicit set of stations (the
/// user's favorites plus inferred home/office) rather than "every station
/// in the app" - Android caps a single app at 100 real OS-level geofences
/// total, and a small deliberate set is also just the right scope: no
/// user needs a background trip-log signal for a station they've never
/// shown interest in.
class StationGeofenceService {
  StationGeofenceService({
    FavoritesRepository? favoritesRepository,
    HomeOfficeRepository? homeOfficeRepository,
  }) : _favoritesRepository = favoritesRepository ?? FavoritesRepository(),
       _homeOfficeRepository = homeOfficeRepository ?? HomeOfficeRepository();

  final FavoritesRepository _favoritesRepository;
  final HomeOfficeRepository _homeOfficeRepository;

  /// Geofence radius - wide enough to reliably trigger on approach given
  /// typical GPS accuracy in an urban canyon (where most of this app's
  /// stations are - dense Manhattan/Jersey City blocks can see 20-50m of
  /// real GPS drift), tight enough that two stations a few blocks apart
  /// don't both fire for the same walk. Not tuned per-station; a single
  /// fixed radius keeps the geofence set simple to reason about.
  static const _radiusMeters = 150.0;

  /// Initializes the plugin (must happen before any other call - see
  /// NativeGeofenceManager.initialize's docs) and re-registers this
  /// device's geofence set. Safe to call every app launch - createGeofence
  /// overwrites an existing geofence with the same id rather than erroring
  /// (see NativeGeofenceManager.createGeofence's docs), so this naturally
  /// self-heals if geofences were ever cleared (e.g. after certain OEM
  /// battery-optimization resets) without needing to diff against what's
  /// currently registered first.
  Future<void> initializeAndSync() async {
    await NativeGeofenceManager.instance.initialize();
    await syncGeofences();
  }

  /// Unregisters every geofence - called when the user turns the feature
  /// off from PreferencesScreen. Safe to call even if none are currently
  /// registered (see NativeGeofenceManager.removeAllGeofences's docs).
  Future<void> removeAllGeofences() => NativeGeofenceManager.instance.removeAllGeofences();

  /// Rebuilds the full geofence set from the user's current favorites +
  /// home/office inference and registers all of them. Call this again
  /// whenever favorites or home/office change (see FavoritesRepository
  /// .changes) so the geofenced set stays current - a station removed
  /// from favorites should stop being geofenced, not linger forever.
  Future<void> syncGeofences() async {
    final stations = await stationsToGeofence();

    await removeAllGeofences();
    for (final station in stations) {
      final lat = station.lat;
      final lng = station.lng;
      if (lat == null || lng == null) continue; // no real coordinates - never geofence a guessed position

      await NativeGeofenceManager.instance.createGeofence(
        Geofence(
          id: '${station.agency.name}:${station.id}',
          location: Location(latitude: lat, longitude: lng),
          radiusMeters: _radiusMeters,
          triggers: {GeofenceEvent.enter},
          iosSettings: const IosGeofenceSettings(),
          androidSettings: const AndroidGeofenceSettings(
            initialTriggers: {},
            // Real power-saving tradeoff, not a default left unconsidered:
            // a station arrival doesn't need second-level responsiveness
            // the way, say, a safety geofence would - letting the OS batch
            // this against other work saves real battery for a background
            // feature the user never directly interacts with.
            notificationResponsiveness: Duration(minutes: 2),
          ),
        ),
        geofenceTriggered,
      );
    }
  }

  /// Every real station to geofence: favorites (across every agency) plus
  /// home/office if inferred - deduplicated, since a favorited station
  /// that's also the inferred home station should only register once.
  /// Public (not private) specifically so tests can exercise this real
  /// resolution logic directly, without needing a mockable seam for the
  /// native_geofence plugin itself (which has none - it's a Pigeon-
  /// generated platform channel, not something a unit test can fake; see
  /// test/station_geofence_service_test.dart).
  @visibleForTesting
  Future<List<TransitStation>> stationsToGeofence() async {
    final favoriteKeys = await _favoritesRepository.loadFavoriteKeys();
    final homeOffice = await _homeOfficeRepository.getMyHomeOffice();

    // "<Agency.name>:<code>" pairs actually wanted, from both sources -
    // same key convention as FavoritesRepository._keyFor/TripLogDebounce,
    // deduplicated via a Set before ever resolving to a real station.
    final wantedKeys = <String>{...favoriteKeys};
    if (homeOffice != null) {
      final homeAgency = _agencyForWireModeOrNull(homeOffice.homeMode);
      if (homeAgency != null && homeOffice.homeStation != null) {
        wantedKeys.add('${homeAgency.name}:${homeOffice.homeStation}');
      }
      final officeAgency = _agencyForWireModeOrNull(homeOffice.officeMode);
      if (officeAgency != null && homeOffice.officeStation != null) {
        wantedKeys.add('${officeAgency.name}:${homeOffice.officeStation}');
      }
    }
    if (wantedKeys.isEmpty) return const [];

    final allStations = await _loadAllStationsAcrossAgencies();
    return [
      for (final station in allStations)
        if (wantedKeys.contains('${station.agency.name}:${station.id}')) station,
    ];
  }

  /// home_mode/office_mode are the backend's snake_case wire names (e.g.
  /// "njt_rail"), NOT Agency.name - agencyFromWireName is the existing,
  /// already-tested reverse mapping (see transit_models.dart).
  Agency? _agencyForWireModeOrNull(String? wireMode) =>
      wireMode == null ? null : agencyFromWireName(wireMode);

  Future<List<TransitStation>> _loadAllStationsAcrossAgencies() async {
    final results = await Future.wait([
      MtaStationRepository().loadStations(),
      NjtRailStationRepository().loadStations(),
      NjtBusStopRepository().loadStations(),
      LirrStationRepository().loadStations(),
    ]);
    return [
      ...results[0],
      ...PathStation.all,
      ...results[1],
      ...results[2],
      ...results[3],
    ];
  }
}

/// Runs in a separate background isolate (see native_geofence's
/// callback-registration model - PluginUtilities.getCallbackHandle
/// requires a top-level or static function, never a closure/instance
/// method) - has NO shared memory/state with the running app's widget
/// tree. Everything this needs (the stored auth token, the debounce
/// state) goes through SharedPreferences, which works correctly across
/// isolates since it's backed by native Android SharedPreferences, not
/// in-memory Dart state.
///
/// @pragma('vm:entry-point') is required so Dart's tree-shaking/AOT
/// compiler never strips this function - the plugin invokes it by a
/// serialized callback handle looked up at native-code runtime, not
/// through any Dart-visible call site, so nothing would otherwise mark
/// it as reachable.
@pragma('vm:entry-point')
Future<void> geofenceTriggered(GeofenceCallbackParams params) async {
  if (params.event != GeofenceEvent.enter) return;

  final now = DateTime.now();
  final debounce = TripLogDebounce();
  final authRepository = AuthRepository();
  final token = await authRepository.getToken();
  if (token == null) return; // not logged in - nothing to log

  final client = http.Client();
  try {
    for (final geofence in params.geofences) {
      // geofence.id is "<Agency.name>:<stationId>" - see
      // StationGeofenceService.syncGeofences, which is the only place
      // that ever creates one of these ids.
      final colonIndex = geofence.id.indexOf(':');
      if (colonIndex == -1) continue;
      final agencyName = geofence.id.substring(0, colonIndex);
      final stationId = geofence.id.substring(colonIndex + 1);
      final agency = _agencyByDartName[agencyName];
      if (agency == null) continue;

      if (await debounce.wasRecentlyLogged(geofence.id, now)) continue;

      final response = await client.post(
        Uri.parse('$apiBaseUrl/trips'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: jsonEncode({
          'start_time': now.toUtc().toIso8601String(),
          'mode': wireAgencyName(agency),
          'origin_stop': stationId,
          // No live-arrivals context exists at geofence-trigger time (no
          // fetch has happened - unlike ArrivalsScreen's trigger, which
          // captures the soonest real arrival's direction). Left null
          // rather than guessed, same "never fabricate a fact you don't
          // have" posture as every other real gap in this app - the
          // direction-choice Behavior AI signal just has one fewer real
          // sample from this particular trip, which is honest.
        }),
      );
      if (response.statusCode == 201) {
        await debounce.markLogged(geofence.id, now);
      }
    }
  } finally {
    client.close();
  }
}

const _agencyByDartName = {
  'mta': Agency.mta,
  'path': Agency.path,
  'njtRail': Agency.njtRail,
  'njtBus': Agency.njtBus,
  'lirr': Agency.lirr,
};
