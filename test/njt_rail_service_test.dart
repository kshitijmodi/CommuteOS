import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:commuteos/njt/njt_rail_service.dart';
import 'package:commuteos/njt/njt_rail_station.dart';

const _np = NjtRailStation(
  code: 'NP',
  name: 'Newark Penn Station',
  lines: ['NEC', 'NJCL'],
  lat: 40.7342,
  lng: -74.1645,
);

String _fixture() => '''
{
  "arrivals": [
    {"route_label": "NE", "arrival_time": "2026-08-01T12:30:00+00:00"},
    {"route_label": "NJCL", "arrival_time": "2026-08-01T12:45:00+00:00"}
  ],
  "is_live": true
}
''';

void main() {
  test('parses arrivals from the backend proxy into a single "departures" direction', () async {
    final service = NjtRailService(
      client: MockClient((request) async => http.Response(_fixture(), 200)),
    );

    final result = await service.getArrivals(_np);

    expect(result.isLive, isTrue);
    expect(result.arrivalsByDirectionKey['departures']!.length, 2);
    expect(result.arrivalsByDirectionKey['departures']!.first.routeLabel, 'NE');
  });

  test('calls the proxy endpoint with the station code', () async {
    Uri? requestedUri;
    final service = NjtRailService(
      client: MockClient((request) async {
        requestedUri = request.url;
        return http.Response(_fixture(), 200);
      }),
    );

    await service.getArrivals(_np);

    expect(requestedUri!.path, endsWith('/transit/njt-rail/NP'));
  });

  test('throws NjtRailFeedException on non-200 response', () async {
    final service = NjtRailService(
      client: MockClient((request) async => http.Response('', 502)),
    );

    expect(() => service.getArrivals(_np), throwsA(isA<NjtRailFeedException>()));
  });

  test('throws NjtRailFeedException on malformed JSON', () async {
    final service = NjtRailService(
      client: MockClient((request) async => http.Response('not json', 200)),
    );

    expect(() => service.getArrivals(_np), throwsA(isA<NjtRailFeedException>()));
  });

  test('skips arrivals with an unparseable arrival_time', () async {
    const badFixture = '''
    {
      "arrivals": [
        {"route_label": "NE", "arrival_time": "garbage"},
        {"route_label": "NJCL", "arrival_time": "2026-08-01T12:45:00+00:00"}
      ],
      "is_live": true
    }
    ''';
    final service = NjtRailService(
      client: MockClient((request) async => http.Response(badFixture, 200)),
    );

    final result = await service.getArrivals(_np);

    expect(result.arrivalsByDirectionKey['departures']!.length, 1);
  });
}
