import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:commuteos/njt/njt_bus_service.dart';
import 'package:commuteos/njt/njt_bus_stop.dart';

const _stop = NjtBusStop(stopId: '1941', name: 'The Esplanade', routeNames: ['163', '753']);

String _fixture() => '''
{
  "arrivals": [
    {"route_label": "163", "arrival_time": "2026-08-02T18:21:07+00:00"},
    {"route_label": "163", "arrival_time": "2026-08-02T18:46:58+00:00"}
  ],
  "is_live": true
}
''';

void main() {
  test('parses arrivals from the backend proxy into a single "arrivals" direction', () async {
    final service = NjtBusService(
      client: MockClient((request) async => http.Response(_fixture(), 200)),
    );

    final result = await service.getArrivals(_stop);

    expect(result.isLive, isTrue);
    expect(result.arrivalsByDirectionKey['arrivals']!.length, 2);
    expect(result.arrivalsByDirectionKey['arrivals']!.first.routeLabel, '163');
  });

  test('calls the proxy endpoint with the stop id', () async {
    Uri? requestedUri;
    final service = NjtBusService(
      client: MockClient((request) async {
        requestedUri = request.url;
        return http.Response(_fixture(), 200);
      }),
    );

    await service.getArrivals(_stop);

    expect(requestedUri!.path, endsWith('/transit/njt-bus/1941'));
    expect(requestedUri!.queryParameters, isEmpty);
  });

  test('sends every bay\'s stop_id for a merged combined-terminal stop', () async {
    const combinedStop = NjtBusStop(
      stopId: '16792',
      name: 'Journal Square Transportation Center',
      routeNames: ['1', '2', '10'],
      mergedStopIds: ['16792', '16802', '16943'],
    );
    Uri? requestedUri;
    final service = NjtBusService(
      client: MockClient((request) async {
        requestedUri = request.url;
        return http.Response(_fixture(), 200);
      }),
    );

    await service.getArrivals(combinedStop);

    expect(requestedUri!.path, endsWith('/transit/njt-bus/16792'));
    expect(requestedUri!.queryParameters['extra_stop_ids'], '16802,16943');
  });

  test('throws NjtBusFeedException on non-200 response', () async {
    final service = NjtBusService(
      client: MockClient((request) async => http.Response('', 502)),
    );

    expect(() => service.getArrivals(_stop), throwsA(isA<NjtBusFeedException>()));
  });

  test('throws NjtBusFeedException on malformed JSON', () async {
    final service = NjtBusService(
      client: MockClient((request) async => http.Response('not json', 200)),
    );

    expect(() => service.getArrivals(_stop), throwsA(isA<NjtBusFeedException>()));
  });

  test('skips arrivals with an unparseable arrival_time', () async {
    const badFixture = '''
    {
      "arrivals": [
        {"route_label": "163", "arrival_time": "garbage"},
        {"route_label": "163", "arrival_time": "2026-08-02T18:46:58+00:00"}
      ],
      "is_live": true
    }
    ''';
    final service = NjtBusService(
      client: MockClient((request) async => http.Response(badFixture, 200)),
    );

    final result = await service.getArrivals(_stop);

    expect(result.arrivalsByDirectionKey['arrivals']!.length, 1);
  });
}
