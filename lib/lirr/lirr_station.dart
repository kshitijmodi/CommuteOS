import '../transit/transit_models.dart';

/// A short abbreviation for a LIRR branch, for the small circular
/// [RouteChip] badge (which has no room for a full branch name like
/// "Babylon Branch"). Not an official LIRR/MTA code - LIRR's own GTFS has
/// no short-name field for branches (unlike NJT rail's LINECODE) - chosen
/// to be recognizable and distinct. Falls back to the first 3 letters of
/// an unrecognized branch name rather than erroring, since new branches
/// are added rarely but not never (e.g. a future extension).
String lirrBranchAbbreviation(String branchName) {
  const known = {
    'Babylon Branch': 'BAB',
    'Hempstead Branch': 'HEM',
    'Oyster Bay Branch': 'OYS',
    'Ronkonkoma Branch': 'RON',
    'Montauk Branch': 'MTK',
    'Long Beach Branch': 'LB',
    'Far Rockaway Branch': 'FR',
    'West Hempstead Branch': 'WH',
    'Port Washington Branch': 'PW',
    'Port Jefferson Branch': 'PJ',
    'Belmont Park': 'BP',
    'City Terminal Zone': 'CTZ',
    'Greenport Service': 'GRN',
  };
  return known[branchName] ??
      branchName.substring(0, branchName.length < 3 ? branchName.length : 3).toUpperCase();
}

/// A Long Island Rail Road station. Unlike MTA subway (a station has a
/// small fixed line-group set) or NJT rail (one call returns everything,
/// no branch concept at all), LIRR stations aren't tied to one branch - a
/// hub like Jamaica is served by most of the system's 13 branches, and
/// trains terminate at one of several distinct terminals (Penn Station,
/// Grand Central, Atlantic Terminal, Hunterspoint Avenue). [directions]
/// still returns a single synthetic "Arrivals" entry (real-time fetching
/// is one call per station, same shape as NJT rail) - the actual
/// branch/destination breakdown comes from each arrival's own real
/// routeLabel/headSign (see LirrService), grouped by destination the same
/// way PATH's multi-destination directions already are
/// (groupArrivalsByDestination), not from anything static here.
class LirrStation implements TransitStation {
  const LirrStation({
    required this.stopId,
    required this.code,
    required this.name,
    required this.branches,
  });

  /// The real-time GTFS-RT feed's numeric stop_id (e.g. "102" for
  /// Jamaica) - NOT the same as [code]. A real gotcha found while
  /// integrating: LIRR's real-time feed matches stop_time_updates against
  /// this numeric id, not the 3-letter stop_code every other part of the
  /// app (and every other agency in this app) uses as a station's public
  /// identifier - confirmed by inspecting a real feed response and
  /// cross-referencing stops.txt. LirrService needs this field
  /// specifically to fetch arrivals; nothing else should use it.
  final String stopId;

  /// LIRR's own 3-char station code, e.g. "JAM" for Jamaica - the
  /// station's public id everywhere else in the app (favorites keys,
  /// search, etc.), matching every other agency's convention here. Sourced
  /// from LIRR's static GTFS feed's stops.txt `stop_code` column (see
  /// backend/scripts/build_lirr_stations.py).
  final String code;
  @override
  final String name;

  /// Full branch names serving this station, e.g. ["Babylon Branch",
  /// "Montauk Branch"] - from LIRR's static GTFS routes.txt, joined
  /// against stops.txt via stop_times.txt/trips.txt (see the build
  /// script). Real-time arrivals report their own route per trip, which
  /// is the actual source of truth shown to the user; this list is only
  /// for search/browse route-chip badges.
  final List<String> branches;

  @override
  Agency get agency => Agency.lirr;

  @override
  String get id => code;

  @override
  String get area => 'NY';

  @override
  List<String> get routes => [for (final b in branches) lirrBranchAbbreviation(b)];

  @override
  List<TransitDirection> get directions => const [
    TransitDirection(label: 'Arrivals', key: 'arrivals'),
  ];

  @override
  String toString() => '$name (${branches.join(", ")})';
}
