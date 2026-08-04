import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../transit/transit_models.dart';

/// Persists the user's favorited stations on-device (Phase 1 has no
/// backend/account, so favorites are local-only and don't sync across
/// devices).
///
/// Keys are namespaced per agency ("mta:R20", "path:JSQ") since a station
/// id is only guaranteed unique within its own agency — MTA's alphanumeric
/// GTFS stop_ids and PATH's short station codes don't collide today, but
/// there's no guarantee that holds once NJ Transit is added too.
class FavoritesRepository {
  static const _prefsKey = 'favorite_station_keys';

  /// Fires whenever any favorite is added/removed, from any
  /// FavoritesRepository instance anywhere in the app (this is
  /// process-wide, not per-instance - see the static field below).
  ///
  /// The Favorites tab and the Search tab each keep their own persistent
  /// widget state (bottom-nav tabs live in an IndexedStack, so switching
  /// tabs never disposes/rebuilds the other one) - a favorite toggled on
  /// one tab used to leave the other tab showing stale data until
  /// something else happened to trigger a reload. Listening to this
  /// notifier is how a screen picks up a change made on a different tab
  /// immediately, without needing route-lifecycle tricks.
  static final ValueNotifier<int> changes = ValueNotifier(0);

  String _keyFor(TransitStation station) =>
      '${station.agency.name}:${station.id}';

  Future<Set<String>> loadFavoriteKeys() async {
    final prefs = await SharedPreferences.getInstance();
    return (prefs.getStringList(_prefsKey) ?? const []).toSet();
  }

  bool isFavorite(Set<String> favoriteKeys, TransitStation station) =>
      favoriteKeys.contains(_keyFor(station));

  Future<void> setFavorite(TransitStation station, bool isFavorite) async {
    final prefs = await SharedPreferences.getInstance();
    final current = (prefs.getStringList(_prefsKey) ?? const []).toSet();
    final key = _keyFor(station);
    if (isFavorite) {
      current.add(key);
    } else {
      current.remove(key);
    }
    await prefs.setStringList(_prefsKey, current.toList());
    changes.value++;
  }
}
