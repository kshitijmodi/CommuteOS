import 'package:shared_preferences/shared_preferences.dart';

/// Persists the user's favorited station IDs on-device (Phase 1 has no
/// backend/account, so favorites are local-only and don't sync across
/// devices).
///
/// Stores MTA stations' `gtfsStopId` values. Not agency-namespaced yet since
/// only MTA exists today; if NJ Transit/PATH stations are added later and
/// their IDs could collide with MTA's, prefix keys per agency at that point.
class FavoritesRepository {
  static const _prefsKey = 'favorite_station_ids';

  Future<Set<String>> loadFavoriteIds() async {
    final prefs = await SharedPreferences.getInstance();
    return (prefs.getStringList(_prefsKey) ?? const []).toSet();
  }

  Future<void> setFavorite(String stationId, bool isFavorite) async {
    final prefs = await SharedPreferences.getInstance();
    final current = (prefs.getStringList(_prefsKey) ?? const []).toSet();
    if (isFavorite) {
      current.add(stationId);
    } else {
      current.remove(stationId);
    }
    await prefs.setStringList(_prefsKey, current.toList());
  }
}
