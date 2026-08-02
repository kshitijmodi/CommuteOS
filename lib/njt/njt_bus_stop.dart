import '../transit/transit_models.dart';

/// An NJ Transit bus stop. Like NJT rail, the real-time API
/// (getTripUpdates) has no direction split to query by - a stop_id is
/// queried directly and returns whichever routes currently have a live
/// update there. [directions] returns a single synthetic "Arrivals" entry
/// so ArrivalsScreen's existing single-tab path just works.
///
/// Scoped to a NYC-metro "core" bounding box (Hudson/Essex/Union/Bergen,
/// roughly) rather than NJT's full statewide ~17k-stop bus network, per
/// the PRD's NYC-metro scope - see
/// backend/scripts/build_njt_bus_stops.py for the exact filter and why.
class NjtBusStop implements TransitStation {
  const NjtBusStop({
    required this.stopId,
    required this.name,
    required this.routeNames,
  });

  /// NJT's own numeric stop_id, e.g. "1941" - what the real-time API's
  /// stop_time_update.stop_id matches against. Distinct numbering from
  /// NJT rail's 2-char station codes.
  final String stopId;
  @override
  final String name;

  /// Bus route short names serving this stop, e.g. ["163", "753"] - from
  /// NJT's static GTFS bus feed, joined via stop_times.txt/trips.txt (see
  /// the build script). Real-time arrivals report their own route per
  /// trip (looked up backend-side from trip_id, since NJT's real-time
  /// feed leaves route_id empty - see backend/app/transit/njt_bus.py).
  final List<String> routeNames;

  @override
  Agency get agency => Agency.njtBus;

  @override
  String get id => stopId;

  @override
  String get area => 'NJ';

  @override
  List<String> get routes => routeNames;

  @override
  List<TransitDirection> get directions => const [
    TransitDirection(label: 'Arrivals', key: 'arrivals'),
  ];

  @override
  String toString() => '$name ($stopId)';
}
