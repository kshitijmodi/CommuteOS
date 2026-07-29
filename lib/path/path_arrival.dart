/// A single predicted arrival, parsed from PATH's real-time JSON feed.
class PathArrival {
  const PathArrival({
    required this.destinationCode,
    required this.headSign,
    required this.arrivalTime,
    required this.lastUpdated,
  });

  /// e.g. "WTC" — the `target` field in the feed.
  final String destinationCode;
  final String headSign;
  final DateTime arrivalTime;

  /// When PATH's backend last refreshed this specific prediction. Used to
  /// detect staleness (see PathService) — if every prediction returned is
  /// old relative to now, the feed is likely stuck/degraded rather than
  /// genuinely reporting no trains.
  final DateTime lastUpdated;

  Duration get timeUntilArrival => arrivalTime.difference(DateTime.now());
}
