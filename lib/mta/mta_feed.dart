/// MTA subway GTFS-realtime feed endpoints.
///
/// MTA publishes real-time subway data as unauthenticated GTFS-realtime
/// protobuf feeds, split by line group. No API key is required.
/// Reference: https://mta.info/developers
library;

enum MtaFeed {
  numbered('nyct%2Fgtfs', '1,2,3,4,5,6,7,S'),
  ace('nyct%2Fgtfs-ace', 'A,C,E,H,FS'),
  bdfm('nyct%2Fgtfs-bdfm', 'B,D,F,M'),
  g('nyct%2Fgtfs-g', 'G'),
  jz('nyct%2Fgtfs-jz', 'J,Z'),
  nqrw('nyct%2Fgtfs-nqrw', 'N,Q,R,W'),
  l('nyct%2Fgtfs-l', 'L'),
  sir('nyct%2Fgtfs-si', 'SIR');

  const MtaFeed(this.pathSuffix, this.lines);

  final String pathSuffix;
  final String lines;

  Uri get uri =>
      Uri.parse('https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/$pathSuffix');

  /// Maps a route ID (e.g. "N", "6", "SIR") to the feed that carries its
  /// real-time updates. Not derivable from static GTFS — MTA doesn't publish
  /// this mapping in routes.txt/stops.txt, so it's hardcoded here. Rarely
  /// changes (only when a whole new line/shuttle is added).
  static const Map<String, MtaFeed> _routeToFeed = {
    '1': numbered, '2': numbered, '3': numbered, '4': numbered,
    '5': numbered, '6': numbered, '7': numbered, 'S': numbered, 'GS': numbered,
    'A': ace, 'C': ace, 'E': ace, 'H': ace, 'SR': ace,
    'B': bdfm, 'D': bdfm, 'F': bdfm, 'M': bdfm, 'FS': bdfm, 'SF': bdfm,
    'G': g,
    'J': jz, 'Z': jz,
    'N': nqrw, 'Q': nqrw, 'R': nqrw, 'W': nqrw,
    'L': l,
    'SI': sir, 'SIR': sir,
  };

  static MtaFeed? feedForRoute(String routeId) => _routeToFeed[routeId];
}
