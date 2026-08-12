import 'package:shared_preferences/shared_preferences.dart';

/// Prevents the same station visit from being logged as two separate real
/// Trip rows when it's reported through more than one trigger in close
/// succession - e.g. a background geofence "enter" event fires, and the
/// user then opens that exact station's arrivals screen a minute later
/// (or the reverse order). Before this existed there was only ever one
/// trigger (ArrivalsScreen), so nothing needed to coordinate across
/// triggers - see OPEN_QUESTIONS.md's 2026-08-12 entry for the real
/// background-geofencing feature this was built for.
///
/// Persisted via SharedPreferences (not an in-memory field) specifically
/// because the geofence trigger runs in a separate background isolate
/// (see native_geofence's callback model) with no shared memory with the
/// running app - an in-memory "last logged" map in one isolate would be
/// invisible to a check made from the other.
class TripLogDebounce {
  /// A repeat "arrival" at the same station within this window is treated
  /// as the same real visit, not a second one - generous enough to cover
  /// "walked in range, then opened the app to check arrivals a few
  /// minutes later" without being so long that a genuine second trip
  /// later the same day gets silently dropped.
  static const window = Duration(minutes: 15);

  static const _prefsKeyPrefix = 'trip_log_debounce_';

  /// Key is "`<Agency.name>`:`<stationId>`" (e.g. "njtRail:NP") - matches
  /// FavoritesRepository's exact key convention (its private _keyFor),
  /// since a station id alone isn't unique across agencies (see
  /// TransitStation.id's docs). Deliberately Agency.name, NOT
  /// wireAgencyName's snake_case backend wire format - this key never
  /// crosses the wire, so it should match this codebase's existing
  /// on-device key convention instead of inventing a second one.
  String _prefsKey(String agencyAndStationKey) => '$_prefsKeyPrefix$agencyAndStationKey';

  /// True if a trip for this station was already logged (by either
  /// trigger) within [window] of [now]. Callers should check this BEFORE
  /// logging, and call [markLogged] immediately after a successful log -
  /// there's a small unavoidable race if both triggers fire at nearly the
  /// exact same instant, but that's an acceptable, rare edge case for a
  /// passive learning signal (not a billing/ledger system).
  Future<bool> wasRecentlyLogged(String agencyAndStationKey, DateTime now) async {
    final prefs = await SharedPreferences.getInstance();
    final storedMillis = prefs.getInt(_prefsKey(agencyAndStationKey));
    if (storedMillis == null) return false;

    final loggedAt = DateTime.fromMillisecondsSinceEpoch(storedMillis, isUtc: true);
    return now.difference(loggedAt) < window;
  }

  Future<void> markLogged(String agencyAndStationKey, DateTime loggedAt) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_prefsKey(agencyAndStationKey), loggedAt.toUtc().millisecondsSinceEpoch);
  }
}
