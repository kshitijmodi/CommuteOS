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
}
