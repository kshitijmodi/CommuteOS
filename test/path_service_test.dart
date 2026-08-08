import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:commuteos/path/path_service.dart';
import 'package:commuteos/path/path_station.dart';

const _jsq = PathStation(code: 'JSQ', name: 'Journal Square', state: 'NJ', lat: 40.7318097, lng: -74.0628655);

String _fixture(String lastUpdated) => '''
{
  "results": [
    {
      "consideredStation": "JSQ",
      "destinations": [
        {
          "label": "ToNY",
          "messages": [
            {
              "target": "WTC",
              "secondsToArrival": "300",
              "arrivalTimeMessage": "5 min",
              "lineColor": "D93A30",
              "headSign": "World Trade Center",
              "lastUpdated": "$lastUpdated"
            },
            {
              "target": "33S",
              "secondsToArrival": "900",
              "arrivalTimeMessage": "15 min",
              "lineColor": "4D92FB,FF9900",
              "headSign": "33rd Street via Hoboken",
              "lastUpdated": "$lastUpdated"
            }
          ]
        },
        {
          "label": "ToNJ",
          "messages": [
            {
              "target": "NWK",
              "secondsToArrival": "600",
              "arrivalTimeMessage": "10 min",
              "lineColor": "D93A30",
              "headSign": "Newark",
              "lastUpdated": "$lastUpdated"
            }
          ]
        }
      ]
    }
  ]
}
''';

void main() {
  test('parses arrivals per direction and marks fresh data as live', () async {
    final fresh = DateTime.now().toIso8601String();
    final service = PathService(
      client: MockClient((request) async => http.Response(_fixture(fresh), 200)),
    );

    final result = await service.getArrivals(_jsq);

    expect(result.isLive, isTrue);
    expect(result.arrivalsByDirectionKey['ToNY']!.length, 2);
    expect(result.arrivalsByDirectionKey['ToNJ']!.length, 1);
    expect(result.arrivalsByDirectionKey['ToNY']!.first.routeLabel, 'PATH');
    expect(result.arrivalsByDirectionKey['ToNY']!.first.routeColors, ['D93A30']);
    expect(
      result.arrivalsByDirectionKey['ToNY']!.last.routeColors,
      ['4D92FB', 'FF9900'],
    );
    expect(
      result.arrivalsByDirectionKey['ToNJ']!.first.headSign,
      'Newark',
    );
  });

  test('sorts each direction soonest-first', () async {
    final fresh = DateTime.now().toIso8601String();
    final service = PathService(
      client: MockClient((request) async => http.Response(_fixture(fresh), 200)),
    );

    final result = await service.getArrivals(_jsq);
    final toNy = result.arrivalsByDirectionKey['ToNY']!;

    expect(toNy[0].arrivalTime.isBefore(toNy[1].arrivalTime), isTrue);
  });

  test('flags stale data as not live', () async {
    final stale = DateTime.now()
        .subtract(const Duration(minutes: 30))
        .toIso8601String();
    final service = PathService(
      client: MockClient((request) async => http.Response(_fixture(stale), 200)),
    );

    final result = await service.getArrivals(_jsq);

    expect(result.isLive, isFalse);
  });

  test('throws PathFeedException on non-200 response', () async {
    final service = PathService(
      client: MockClient((request) async => http.Response('', 503)),
    );

    expect(() => service.getArrivals(_jsq), throwsA(isA<PathFeedException>()));
  });

  test('throws PathFeedException on malformed JSON', () async {
    final service = PathService(
      client: MockClient((request) async => http.Response('not json', 200)),
    );

    expect(() => service.getArrivals(_jsq), throwsA(isA<PathFeedException>()));
  });

  test('returns empty arrivals for a station absent from the feed', () async {
    final fresh = DateTime.now().toIso8601String();
    final service = PathService(
      client: MockClient((request) async => http.Response(_fixture(fresh), 200)),
    );

    const otherStation = PathStation(code: 'HOB', name: 'Hoboken', state: 'NJ', lat: 40.7354944, lng: -74.0286157);
    final result = await service.getArrivals(otherStation);

    expect(result.arrivalsByDirectionKey['ToNY'], isEmpty);
    expect(result.arrivalsByDirectionKey['ToNJ'], isEmpty);
    // No arrivals at all isn't itself evidence of staleness.
    expect(result.isLive, isTrue);
  });
}
