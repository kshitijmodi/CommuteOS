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
    this.toward,
    List<String>? mergedStopIds,
  }) : mergedStopIds = mergedStopIds ?? const [];

  /// NJT's own numeric stop_id, e.g. "1941" - what the real-time API's
  /// stop_time_update.stop_id matches against. Distinct numbering from
  /// NJT rail's 2-char station codes. For a merged multi-bay entry (see
  /// [mergedStopIds]), this is just the first/primary bay - arrivals still
  /// need every bay's id, not only this one.
  final String stopId;
  @override
  final String name;

  /// Bus route short names serving this stop, e.g. ["163", "753"] - from
  /// NJT's static GTFS bus feed, joined via stop_times.txt/trips.txt (see
  /// the build script). Real-time arrivals report their own route per
  /// trip (looked up backend-side from trip_id, since NJT's real-time
  /// feed leaves route_id empty - see backend/app/transit/njt_bus.py).
  final List<String> routeNames;

  /// Best-effort "toward `<terminus>`" hint (e.g. "Newark"), null when there
  /// wasn't a confident one to derive (see build_njt_bus_stops.py's
  /// _toward_by_stop_id). Only meaningful - and only ever populated - for
  /// an ordinary unmerged stop; a merged multi-bay terminal's arrivals
  /// already cover every direction together, so it has no single "toward"
  /// to show. Exists specifically so two same-named, unmerged stop_ids
  /// (e.g. two stops on opposite sides of an intersection, serving
  /// opposite directions of the same route - a real case found via phone
  /// testing at "1st Ave at Aldene Rd") read as distinguishable options in
  /// the station picker instead of two identical-looking rows.
  final String? toward;

  /// Every bay-level stop_id folded into this entry, when NJT's static
  /// GTFS models one physical terminal as several separate stop_ids
  /// sharing an identical name (e.g. Journal Square's ~26 bays) - see
  /// NjtBusStopRepository.loadStations. Empty for an ordinary single-bay
  /// stop (the common case) - callers needing "every stop_id this
  /// TransitStation represents" should use [allStopIds] instead of this
  /// field directly, since that also covers the empty/single-bay case.
  final List<String> mergedStopIds;

  /// Every real stop_id arrivals need to be fetched for - just [stopId]
  /// for an ordinary stop, or the full bay list for a merged terminal.
  List<String> get allStopIds => mergedStopIds.isEmpty ? [stopId] : mergedStopIds;

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
