import 'package:fixnum/fixnum.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gtfs_realtime_bindings/gtfs_realtime_bindings.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:commuteos/lirr/lirr_service.dart';
import 'package:commuteos/lirr/lirr_station.dart';

// A real trip_id/branch pair from the bundled
// assets/data/lirr_trip_routes.csv, confirmed against the actual static
// GTFS during development - using a real row (rather than a fabricated
// one) means these tests also catch a broken/empty bundled asset.
const _realTripId = 'GO201_26_2';
const _realBranch = 'Montauk Branch';

const _jamaica = LirrStation(
  stopId: '102',
  code: 'JAM',
  name: 'Jamaica',
  branches: ['Babylon Branch'],
);

List<int> _buildFeed(
  List<(String tripId, String stopId, int epochSeconds, bool canceled)> entities,
) {
  final feed = FeedMessage(
    header: FeedHeader(gtfsRealtimeVersion: '2.0'),
    entity: [
      for (final (i, (tripId, stopId, epochSeconds, canceled)) in entities.indexed)
        FeedEntity(
          id: '$i',
          tripUpdate: TripUpdate(
            trip: TripDescriptor(
              tripId: tripId,
              scheduleRelationship: canceled
                  ? TripDescriptor_ScheduleRelationship.CANCELED
                  : TripDescriptor_ScheduleRelationship.SCHEDULED,
            ),
            stopTimeUpdate: [
              TripUpdate_StopTimeUpdate(
                stopId: stopId,
                arrival: canceled ? null : TripUpdate_StopTimeEvent(time: Int64(epochSeconds)),
              ),
            ],
          ),
        ),
    ],
  );
  return feed.writeToBuffer();
}

void main() {
  // LirrService reads a real bundled asset (assets/data/lirr_trip_routes.csv)
  // via rootBundle - every test needs tester.runAsync (real async I/O the
  // fake test clock doesn't advance) the same way the repository tests do.

  testWidgets('parses arrivals matching the real bundled trip-routes CSV', (tester) async {
    final service = LirrService(
      client: MockClient(
        (request) async => http.Response.bytes(
          _buildFeed([(_realTripId, '102', 1900000000, false)]),
          200,
        ),
      ),
    );

    dynamic awaited;
    await tester.runAsync(() async => awaited = await service.getArrivals(_jamaica));

    expect(awaited.isLive, isTrue);
    expect(awaited.arrivalsByDirectionKey['arrivals']!.length, 1);
    expect(awaited.arrivalsByDirectionKey['arrivals']!.first.routeLabel, _realBranch);
  });

  testWidgets('matches against the numeric stop_id, not the station code', (tester) async {
    // Regression test for the real gotcha: the real-time feed's stop_id
    // is numeric ("102" for Jamaica), not the 3-letter station code
    // ("JAM") - a fetch matching against station.id directly would find
    // nothing here.
    final service = LirrService(
      client: MockClient(
        (request) async => http.Response.bytes(
          _buildFeed([(_realTripId, 'JAM', 1900000000, false)]),
          200,
        ),
      ),
    );

    dynamic awaited;
    await tester.runAsync(() async => awaited = await service.getArrivals(_jamaica));

    expect(awaited.arrivalsByDirectionKey['arrivals'], isEmpty);
  });

  testWidgets('skips canceled trips', (tester) async {
    final service = LirrService(
      client: MockClient(
        (request) async => http.Response.bytes(
          _buildFeed([(_realTripId, '102', 0, true)]),
          200,
        ),
      ),
    );

    dynamic awaited;
    await tester.runAsync(() async => awaited = await service.getArrivals(_jamaica));

    expect(awaited.arrivalsByDirectionKey['arrivals'], isEmpty);
  });

  testWidgets('falls back to "LIRR" label for a trip not in the bundled lookup', (tester) async {
    final service = LirrService(
      client: MockClient(
        (request) async => http.Response.bytes(
          _buildFeed([('totally-unknown-trip-id', '102', 1900000000, false)]),
          200,
        ),
      ),
    );

    dynamic awaited;
    await tester.runAsync(() async => awaited = await service.getArrivals(_jamaica));

    expect(awaited.arrivalsByDirectionKey['arrivals']!.first.routeLabel, 'LIRR');
  });

  testWidgets('throws LirrFeedException on non-200 response', (tester) async {
    final service = LirrService(
      client: MockClient((request) async => http.Response('', 502)),
    );

    await tester.runAsync(() async {
      await expectLater(
        () => service.getArrivals(_jamaica),
        throwsA(isA<LirrFeedException>()),
      );
    });
  });

  testWidgets('throws LirrFeedException on malformed feed bytes', (tester) async {
    final service = LirrService(
      client: MockClient(
        (request) async => http.Response.bytes([1, 2, 3, 4, 5], 200),
      ),
    );

    await tester.runAsync(() async {
      await expectLater(
        () => service.getArrivals(_jamaica),
        throwsA(isA<LirrFeedException>()),
      );
    });
  });
}
