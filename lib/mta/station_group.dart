import 'mta_station.dart';
import 'natural_sort.dart';

/// One row in the station list UI: a station name, plus every [MtaStation]
/// that shares that name (whether or not they share a physical complex).
///
/// Most names map to exactly one station. When more than one exists —
/// either multiple platforms of the same connected complex (e.g. Canal St's
/// N/Q/R/W/J/Z/6 complex) or genuinely separate, unconnected stations that
/// happen to share a name (e.g. two unrelated "86 St"s) — tapping the row
/// should let the user pick which one they mean rather than guessing.
class StationGroup {
  const StationGroup({required this.name, required this.stations});

  final String name;
  final List<MtaStation> stations;

  bool get hasSingleStation => stations.length == 1;

  /// All distinct route IDs across every station in this group, for the
  /// list row's subtitle when there's more than one station to summarize.
  List<String> get allRoutes {
    final routes = <String>{};
    for (final station in stations) {
      routes.addAll(station.routes);
    }
    final sorted = routes.toList()..sort();
    return sorted;
  }

  static List<StationGroup> groupByName(List<MtaStation> stations) {
    final byName = <String, List<MtaStation>>{};
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
