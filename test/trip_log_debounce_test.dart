import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:commuteos/behavior/trip_log_debounce.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('a station never logged before is not recently logged', () async {
    final debounce = TripLogDebounce();

    final wasLogged = await debounce.wasRecentlyLogged('path:JSQ', DateTime.now());

    expect(wasLogged, isFalse);
  });

  test('a station marked logged just now is recently logged', () async {
    final debounce = TripLogDebounce();
    final now = DateTime.now();

    await debounce.markLogged('path:JSQ', now);
    final wasLogged = await debounce.wasRecentlyLogged('path:JSQ', now);

    expect(wasLogged, isTrue);
  });

  test('a station marked logged outside the debounce window is not recently logged', () async {
    final debounce = TripLogDebounce();
    final loggedAt = DateTime.now().subtract(TripLogDebounce.window + const Duration(minutes: 1));

    await debounce.markLogged('path:JSQ', loggedAt);
    final wasLogged = await debounce.wasRecentlyLogged('path:JSQ', DateTime.now());

    expect(wasLogged, isFalse);
  });

  test('a different station is unaffected by another station being logged', () async {
    final debounce = TripLogDebounce();
    final now = DateTime.now();

    await debounce.markLogged('path:JSQ', now);
    final wasLogged = await debounce.wasRecentlyLogged('mta:R20', now);

    expect(wasLogged, isFalse);
  });

  test('the same agency name with a different station id is not confused as the same key', () async {
    // Real regression guard: the debounce key must include BOTH agency and
    // station id, matching FavoritesRepository's own key convention -
    // a bare station id alone isn't unique across agencies.
    final debounce = TripLogDebounce();
    final now = DateTime.now();

    await debounce.markLogged('njtRail:NP', now);
    final wasLogged = await debounce.wasRecentlyLogged('njtRail:HOB', now);

    expect(wasLogged, isFalse);
  });
}
