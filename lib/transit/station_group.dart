import '../mta/mta_station.dart';
import 'natural_sort.dart';
import 'transit_models.dart';

/// One row in the station list UI: a station name, plus every
/// [TransitStation] (across any agency) that shares that name.
///
/// Most names map to exactly one station. When more than one exists —
/// multiple platforms of a connected complex, genuinely separate stations
/// that happen to share a name, or (in principle) a name collision across
/// agencies — tapping the row should let the user pick which one they mean
/// rather than guessing.
class StationGroup {
  const StationGroup({required this.name, required this.stations});

  final String name;
  final List<TransitStation> stations;

  bool get hasSingleStation => stations.length == 1;

  /// True when two or more stations in this group are MTA stations from
  /// genuinely different, unconnected complexes that just happen to share a
  /// plain name (e.g. four separate "23 St" stations on the N/R/W, A/C/E,
  /// F/M, and 1 lines) - as opposed to platforms of one real complex, or a
  /// PATH station intentionally merged with its co-located MTA counterpart
  /// (see the "33 St"/"14 St"/"23 St" PATH/MTA merge). A route-chip list
  /// combining routes across a name collision like this would show routes
  /// (e.g. "M") on stations that don't actually have them - see
  /// StationListTile, which uses this to avoid that.
  bool get hasUnconnectedMtaCollision {
    final complexIds = <String>{};
    for (final station in stations) {
      if (station is MtaStation) {
        complexIds.add(station.complexId);
      }
    }
    return complexIds.length > 1;
  }

  static List<StationGroup> groupByName(List<TransitStation> stations) {
    final byName = <String, List<TransitStation>>{};
    for (final station in stations) {
      byName.putIfAbsent(station.name, () => []).add(station);
    }

    final groups = byName.entries
        .map((e) => StationGroup(name: e.key, stations: e.value))
        .toList()
      ..sort((a, b) => compareStationNames(a.name, b.name));
    return groups;
  }
}
