/// A single predicted arrival, parsed from PATH's real-time JSON feed.
class PathArrival {
  const PathArrival({
    required this.destinationCode,
    required this.headSign,
    required this.arrivalTime,
    required this.lastUpdated,
    this.routeColors = const [],
  });

  /// e.g. "WTC" — the `target` field in the feed.
  final String destinationCode;
  final String headSign;
  final DateTime arrivalTime;

  /// Hex color(s) (no leading '#') from the feed's own `lineColor` field,
  /// e.g. ["D93A30"] for a Newark–WTC train. Occasionally more than one
  /// value, comma-separated in the raw feed, for trains that run via more
  /// than one PATH line (e.g. a Hoboken–33rd St train via Journal Square).
  final List<String> routeColors;

  /// When PATH's backend last refreshed this specific prediction. Used to
  /// detect staleness (see PathService) — if every prediction returned is
  /// old relative to now, the feed is likely stuck/degraded rather than
  /// genuinely reporting no trains.
  final DateTime lastUpdated;

  Duration get timeUntilArrival => arrivalTime.difference(DateTime.now());
}

/// Parses the feed's raw "D93A30" or "4D92FB,FF9900" color string into a
/// clean list of hex codes, dropping anything malformed rather than
/// guessing a color for a train.
List<String> parsePathRouteColors(String? raw) {
  if (raw == null || raw.isEmpty) return const [];
  final hex = RegExp(r'^[0-9A-Fa-f]{6}$');
  return raw
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .where(hex.hasMatch)
      .toList();
}
