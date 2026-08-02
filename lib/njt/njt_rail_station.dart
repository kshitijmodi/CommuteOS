import '../transit/transit_models.dart';

/// An NJ Transit rail station. Unlike MTA/PATH, NJT's real-time API
/// (getTrainSchedule19Rec) has no direction/platform split to query by -
/// one call returns every upcoming departure at the station, mixed
/// together, across every line serving it. [directions] returns a single
/// synthetic "Departures" entry so ArrivalsScreen's existing single-tab
/// path (already built for PATH-like agencies with fewer directions) just
/// works, without needing a special case for "no real directions."
class NjtRailStation implements TransitStation {
  const NjtRailStation({
    required this.code,
    required this.name,
    required this.lines,
  });

  /// NJT's own 2-char station code, e.g. "NP" for Newark Penn Station -
  /// what the real-time API's `station` parameter expects. Sourced from
  /// NJT's static GTFS rail feed's stops.txt `stop_code` column (see
  /// backend/scripts/build_njt_rail_stations.py), verified to match the
  /// real-time API by testing "NP" against both.
  final String code;
  @override
  final String name;

  /// Rail line short names serving this station, e.g. ["NEC", "NJCL"] -
  /// from NJT's static GTFS routes.txt, joined against stops.txt via
  /// stop_times.txt/trips.txt (see the build script). Real-time arrivals
  /// report their own LINECODE per train, which is the actual source of
  /// truth shown to the user; this list is only for search/browse.
  final List<String> lines;

  @override
  Agency get agency => Agency.njtRail;

  @override
  String get id => code;

  @override
  String get area => 'NJ';

  @override
  List<String> get routes => lines;

  @override
  List<TransitDirection> get directions => const [
    TransitDirection(label: 'Departures', key: 'departures'),
  ];

  @override
  String toString() => '$name ($code)';
}
