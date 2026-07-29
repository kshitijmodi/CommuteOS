import 'mta_feed.dart';

/// A physical subway station (one or more platforms/entrances grouped
/// under a single parent GTFS stop_id), parsed from MTA's Stations.csv.
class MtaStation {
  const MtaStation({
    required this.gtfsStopId,
    required this.complexId,
    required this.name,
    required this.borough,
    required this.routes,
    required this.northLabel,
    required this.southLabel,
  });

  /// The parent GTFS stop_id, e.g. "R20" for 14 St-Union Sq.
  /// Real-time stop_ids for this station are this value with an "N" or "S"
  /// suffix appended (NYCT convention, e.g. "R20N", "R20S").
  final String gtfsStopId;

  /// MTA's own station-complex grouping ID. Stations that are physically
  /// connected (e.g. a free in-system transfer between lines) share the
  /// same complex ID even though each has its own `gtfsStopId` for
  /// real-time lookups. Two stations can share a `name` without sharing a
  /// complex ID — that means they're unrelated, separate physical stations
  /// that happen to have the same name (e.g. two unconnected "86 St"s).
  final String complexId;
  final String name;
  final String borough;

  /// Route IDs serving this station, e.g. ["N", "Q", "R", "W"].
  final List<String> routes;

  /// Human-readable direction labels, e.g. "Uptown & Queens" / "Downtown &
  /// Brooklyn". May be empty for terminal stations with no train that way.
  final String northLabel;
  final String southLabel;

  String get northStopId => '${gtfsStopId}N';
  String get southStopId => '${gtfsStopId}S';

  /// Distinct real-time feeds needed to cover every route at this station.
  Set<MtaFeed> get feeds => routes
      .map(MtaFeed.feedForRoute)
      .whereType<MtaFeed>()
      .toSet();

  @override
  String toString() => '$name (${routes.join(" ")})';
}
