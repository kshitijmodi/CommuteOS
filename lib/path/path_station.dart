import '../transit/transit_models.dart';

/// A PATH station. Unlike MTA's ~496 stations (bundled from a CSV), PATH
/// only has 13 stations that essentially never change, so they're
/// hardcoded here rather than parsed from a data file.
///
/// Station codes and names match the `consideredStation` field in PATH's
/// real-time JSON feed (see PathService) and PATH's own line branding.
class PathStation implements TransitStation {
  const PathStation({required this.code, required this.name, required this.state});

  /// PATH's own station code, e.g. "JSQ", "WTC", "33S". This is what the
  /// real-time feed's `consideredStation`/`target` fields use.
  final String code;
  @override
  final String name;

  /// "NJ" or "NY" — PATH crosses state lines, unlike MTA subway.
  final String state;

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
    PathStation(code: 'NWK', name: 'Newark', state: 'NJ'),
    PathStation(code: 'HAR', name: 'Harrison', state: 'NJ'),
    PathStation(code: 'JSQ', name: 'Journal Square', state: 'NJ'),
    PathStation(code: 'GRV', name: 'Grove Street', state: 'NJ'),
    PathStation(code: 'EXP', name: 'Exchange Place', state: 'NJ'),
    PathStation(code: 'HOB', name: 'Hoboken', state: 'NJ'),
    PathStation(code: 'NEW', name: 'Newport', state: 'NJ'),
    PathStation(code: 'WTC', name: 'World Trade Center', state: 'NY'),
    PathStation(code: 'CHR', name: 'Christopher St', state: 'NY'),
    // Named to match MTA's exact station-name convention (no ordinal
    // suffix) for "9 St"/"14 St"/"23 St"/"33 St" so StationGroup.groupByName
    // merges the PATH and MTA stations at the same physical location into
    // one row instead of two separate ones. Verified against MTA's
    // Stations.csv — MTA has an exact "33 St" (6 train) but no matching "9
    // St"; kept "9 St" (not "9th St") anyway for naming consistency across
    // the group, since it doesn't currently collide either way.
    PathStation(code: '09S', name: '9 St', state: 'NY'),
    PathStation(code: '14S', name: '14 St', state: 'NY'),
    PathStation(code: '23S', name: '23 St', state: 'NY'),
    PathStation(code: '33S', name: '33 St', state: 'NY'),
  ];

  @override
  String toString() => name;
}
