import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/path/path_arrival.dart';

void main() {
  group('parsePathRouteColors', () {
    test('parses a single hex color', () {
      expect(parsePathRouteColors('D93A30'), ['D93A30']);
    });

    test('parses multiple comma-separated colors', () {
      expect(parsePathRouteColors('4D92FB,FF9900'), ['4D92FB', 'FF9900']);
    });

    test('uppercases lowercase hex', () {
      expect(parsePathRouteColors('d93a30'), ['D93A30']);
    });

    test('drops malformed entries rather than guessing', () {
      expect(parsePathRouteColors('D93A30,not-a-color'), ['D93A30']);
    });

    test('returns empty for null or empty input', () {
      expect(parsePathRouteColors(null), isEmpty);
      expect(parsePathRouteColors(''), isEmpty);
    });
  });
}
