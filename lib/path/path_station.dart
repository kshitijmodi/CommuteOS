import '../transit/transit_models.dart';

/// A PATH station. Unlike MTA's ~496 stations (bundled from a CSV), PATH
/// only has 13 stations that essentially never change, so they're
/// hardcoded here rather than parsed from a data file.
///
/// Station codes and names match the `consideredStation` field in PATH's
/// real-time JSON feed (see PathService) and PATH's own line branding.
class PathStation implements TransitStation {
  const PathStation({
    required this.code,
    required this.name,
    required this.state,
    required this.lat,
    required this.lng,
  });

  /// PATH's own station code, e.g. "JSQ", "WTC", "33S". This is what the
  /// real-time feed's `consideredStation`/`target` fields use.
  final String code;
  @override
  final String name;

  /// "NJ" or "NY" — PATH crosses state lines, unlike MTA subway.
  final String state;

  /// Real coordinates, added 2026-08-08 - PATH previously had none
  /// anywhere in this app (unlike MTA/NJT rail/bus/LIRR, which all
  /// bundle real lat/lng in their station CSVs), which meant nothing
  /// PATH-related could ever be used for a "nearest station" lookup.
  /// Verified from two independent sources (OpenStreetMap's real
  /// `railway=station, network=PATH` nodes, cross-checked against each
  /// station's Wikipedia infobox coordinate) - both agreed within
  /// 5-110m for every station, well within tolerance for this purpose.
  @override
  final double lat;
  @override
  final double lng;

  @override
  Agency get agency => Agency.path;

  @override
  String get id => code;

  @override
  String get area => state;

  @override
  List<String> get routes => const ['PATH'];

  /// PATH's real-time feed labels directions "ToNY"/"ToNJ" per station,
  /// not a fixed pair of directions system-wide — a station near one end
  /// of the system (e.g. WTC) may only ever have one meaningful direction.
  /// The service resolves which direction keys actually have data at fetch
  /// time; this list is used for UI tab labels when both are plausible.
  @override
  List<TransitDirection> get directions => const [
    TransitDirection(label: 'To New York', key: 'ToNY'),
    TransitDirection(label: 'To New Jersey', key: 'ToNJ'),
  ];

  static const all = <PathStation>[
    PathStation(code: 'NWK', name: 'Newark', state: 'NJ', lat: 40.7344963, lng: -74.1638550),
    PathStation(code: 'HAR', name: 'Harrison', state: 'NJ', lat: 40.7393434, lng: -74.1556748),
    PathStation(code: 'JSQ', name: 'Journal Square', state: 'NJ', lat: 40.7318097, lng: -74.0628655),
    PathStation(code: 'GRV', name: 'Grove Street', state: 'NJ', lat: 40.7192583, lng: -74.0421003),
    PathStation(code: 'EXP', name: 'Exchange Place', state: 'NJ', lat: 40.7167341, lng: -74.0324551),
    PathStation(code: 'HOB', name: 'Hoboken', state: 'NJ', lat: 40.7354944, lng: -74.0286157),
    PathStation(code: 'NEW', name: 'Newport', state: 'NJ', lat: 40.7267989, lng: -74.0347553),
    PathStation(code: 'WTC', name: 'World Trade Center', state: 'NY', lat: 40.7119004, lng: -74.0125270),
    PathStation(code: 'CHR', name: 'Christopher St', state: 'NY', lat: 40.7329877, lng: -74.0069062),
    // Named to match MTA's exact station-name convention (no ordinal
    // suffix) for "9 St"/"14 St"/"23 St"/"33 St" so StationGroup.groupByName
    // merges the PATH and MTA stations at the same physical location into
    // one row instead of two separate ones. Verified against MTA's
    // Stations.csv — MTA has an exact "33 St" (6 train) but no matching "9
    // St"; kept "9 St" (not "9th St") anyway for naming consistency across
    // the group, since it doesn't currently collide either way.
    PathStation(code: '09S', name: '9 St', state: 'NY', lat: 40.7340749, lng: -73.9996395),
    PathStation(code: '14S', name: '14 St', state: 'NY', lat: 40.7370478, lng: -73.9970695),
    PathStation(code: '23S', name: '23 St', state: 'NY', lat: 40.7428534, lng: -73.9928340),
    PathStation(code: '33S', name: '33 St', state: 'NY', lat: 40.7485384, lng: -73.9887001),
  ];

  @override
  String toString() => name;
}
