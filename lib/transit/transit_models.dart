/// Cross-agency abstractions so the UI (search, favorites, arrivals) doesn't
/// need to know whether a station is MTA subway, PATH, or (eventually) NJ
/// Transit. Each agency module (lib/mta/, lib/path/, ...) adapts its own
/// data shape to these interfaces; agency-specific details (GTFS stop_ids,
/// PATH station codes, feed lookup tables) stay inside that agency's module.
library;

enum Agency { mta, path, njtRail, njtBus, lirr }

/// Dart's Agency.name is camelCase (e.g. "njtRail"), but the backend's
/// mode/agency fields (Trip.mode, CandidateRequest.agency) are snake_case
/// matching its Python module names ("njt_rail") - this is the single
/// source of truth for that mapping, used anywhere an Agency crosses the
/// wire to the backend. A silent mismatch here would either get stored as
/// a slightly-wrong Trip.mode string, or fail request validation outright
/// (CandidateRequest.agency is a strict Literal) - never use
/// station.agency.name directly for anything the backend reads.
const Map<Agency, String> _agencyWireNames = {
  Agency.mta: 'mta',
  Agency.path: 'path',
  Agency.njtRail: 'njt_rail',
  Agency.njtBus: 'njt_bus',
  Agency.lirr: 'lirr',
};

String wireAgencyName(Agency agency) => _agencyWireNames[agency]!;

/// A physical station, agency-agnostic. Implemented by MtaStation and
/// PathStation.
abstract class TransitStation {
  Agency get agency;

  /// Unique within this agency, but NOT guaranteed unique across agencies —
  /// always pair with [agency] when using as a lookup/storage key (see
  /// FavoritesRepository).
  String get id;
  String get name;

  /// e.g. a borough (MTA) or "NJ"/"NY" (PATH) — a short descriptive tag
  /// shown in list subtitles, not a strict schema across agencies.
  String get area;

  /// Route/line identifiers serving this station, e.g. ["N", "Q", "R", "W"]
  /// for MTA, or PATH's line labels.
  List<String> get routes;

  /// The directions arrivals can be split into for this station (e.g. two
  /// for a simple MTA local station, or PATH's "To NY"/"To NJ"). A station
  /// with no meaningful direction split (rare) returns a single entry.
  List<TransitDirection> get directions;
}

/// One direction/platform at a station, e.g. "Uptown & The Bronx" for MTA
/// or "To New York" for PATH. Just a label + an opaque key the agency's
/// service uses internally to fetch that direction's arrivals — the UI
/// never needs to know what the key means.
class TransitDirection {
  const TransitDirection({required this.label, required this.key});

  final String label;
  final String key;
}

/// A single predicted arrival, agency-agnostic.
class TransitArrival {
  const TransitArrival({
    required this.routeLabel,
    required this.arrivalTime,
    this.headSign,
    this.routeColors = const [],
  });

  /// e.g. "N", "6" (MTA) or "PATH" (PATH doesn't label individual arrivals
  /// by line today - see routeColors).
  final String routeLabel;
  final DateTime arrivalTime;

  /// Destination/headsign text if the agency provides one (PATH does;
  /// MTA's base GTFS-RT spec doesn't reliably).
  final String? headSign;

  /// The real line color(s) for this specific arrival, as "RRGGBB" hex
  /// strings (no leading '#') - straight from PATH's own feed, which
  /// publishes an authentic `lineColor` per arrival (occasionally more
  /// than one, comma-separated, for a train that runs via more than one
  /// PATH line). Empty for MTA, whose GTFS-RT feed carries no color data -
  /// MTA's routeLabel is instead looked up against a hardcoded table of
  /// NYCT's own published line colors (see mtaRouteColor in
  /// lib/design/components.dart), since the official colors are a small,
  /// fixed set that essentially never changes.
  final List<String> routeColors;

  Duration get timeUntilArrival => arrivalTime.difference(DateTime.now());
}

/// Result of fetching arrivals for a station: per-direction arrival lists,
/// plus whether the data should be trusted as live.
///
/// [isLive] is how agencies with unreliable/unofficial feeds (PATH) signal
/// graceful degradation — the UI shows a "live data unavailable" flag
/// instead of silently presenting stale data as current. MTA's feed is
/// always live when the fetch succeeds at all, so it's always true there.
class TransitArrivalsResult {
  const TransitArrivalsResult({
    required this.arrivalsByDirectionKey,
    required this.isLive,
  });

  final Map<String, List<TransitArrival>> arrivalsByDirectionKey;
  final bool isLive;
}

/// Fetches real-time arrivals for a station. Implemented per-agency
/// (MtaService, PathService) so a failure in one agency's feed can never
/// affect another's — each service owns its own error handling.
abstract class TransitService {
  Future<TransitArrivalsResult> getArrivals(TransitStation station);
  void dispose();
}
