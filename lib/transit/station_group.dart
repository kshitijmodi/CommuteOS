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

  /// All distinct route labels across every station in this group, for the
  /// list row's subtitle when there's more than one station to summarize.
  List<String> get allRoutes {
    final routes = <String>{};
    for (final station in stations) {
      routes.addAll(station.routes);
    }
    final sorted = routes.toList()..sort();
    return sorted;
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
