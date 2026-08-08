import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/account/trip_logger.dart';
import 'package:commuteos/behavior/departure_detector.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const methodChannelName = 'test/activity_transition';

  Map<String, dynamic> mockResponses = {};

  void mockMethodChannel() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          const MethodChannel(methodChannelName),
          (call) async => mockResponses[call.method],
        );
  }

  setUp(() {
    mockResponses = {'hasPermission': true, 'start': true, 'stop': true};
    mockMethodChannel();
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel(methodChannelName), null);
  });

  test('registerOpenTrip + a real walking event reports left_at', () async {
    String? reportedTripId;
    DateTime? reportedLeftAt;
    final controller = StreamController<dynamic>.broadcast();

    final detector = DepartureDetector.forTesting(
      tripLogger: _FakeTripLogger(
        onReportLeftAt: (id, at) {
          reportedTripId = id;
          reportedLeftAt = at;
        },
      ),
      methodChannel: const MethodChannel(methodChannelName),
      eventStream: controller.stream,
    );

    await detector.start();
    detector.registerOpenTrip('trip-123');
    controller.add('walking');
    await pumpEventQueue();

    expect(reportedTripId, 'trip-123');
    expect(reportedLeftAt, isNotNull);

    await controller.close();
  });

  test('an in_vehicle event also reports left_at', () async {
    String? reportedTripId;
    final controller = StreamController<dynamic>.broadcast();

    final detector = DepartureDetector.forTesting(
      tripLogger: _FakeTripLogger(onReportLeftAt: (id, _) => reportedTripId = id),
      methodChannel: const MethodChannel(methodChannelName),
      eventStream: controller.stream,
    );

    await detector.start();
    detector.registerOpenTrip('trip-456');
    controller.add('in_vehicle');
    await pumpEventQueue();

    expect(reportedTripId, 'trip-456');

    await controller.close();
  });

  test('an unrelated event type (e.g. "still") is ignored', () async {
    var wasCalled = false;
    final controller = StreamController<dynamic>.broadcast();

    final detector = DepartureDetector.forTesting(
      tripLogger: _FakeTripLogger(onReportLeftAt: (_, _) => wasCalled = true),
      methodChannel: const MethodChannel(methodChannelName),
      eventStream: controller.stream,
    );

    await detector.start();
    detector.registerOpenTrip('trip-789');
    controller.add('still');
    await pumpEventQueue();

    expect(wasCalled, isFalse);

    await controller.close();
  });

  test('a transition with no registered open trip is a no-op', () async {
    var wasCalled = false;
    final controller = StreamController<dynamic>.broadcast();

    final detector = DepartureDetector.forTesting(
      tripLogger: _FakeTripLogger(onReportLeftAt: (_, _) => wasCalled = true),
      methodChannel: const MethodChannel(methodChannelName),
      eventStream: controller.stream,
    );

    await detector.start();
    controller.add('walking'); // no registerOpenTrip call first
    await pumpEventQueue();

    expect(wasCalled, isFalse);

    await controller.close();
  });

  test('a transition arriving long after the trip was registered is stale, not reported', () async {
    var wasCalled = false;
    final controller = StreamController<dynamic>.broadcast();

    final detector = DepartureDetector.forTesting(
      tripLogger: _FakeTripLogger(onReportLeftAt: (_, _) => wasCalled = true),
      methodChannel: const MethodChannel(methodChannelName),
      eventStream: controller.stream,
    );

    await detector.start();
    detector.registerOpenTripAt('trip-old', DateTime.now().subtract(const Duration(minutes: 30)));
    controller.add('walking');
    await pumpEventQueue();

    expect(wasCalled, isFalse);

    await controller.close();
  });

  test('does not start listening when the permission is denied', () async {
    mockResponses = {'hasPermission': false, 'requestPermission': false};
    mockMethodChannel();

    var wasCalled = false;
    final controller = StreamController<dynamic>.broadcast();

    final detector = DepartureDetector.forTesting(
      tripLogger: _FakeTripLogger(onReportLeftAt: (_, _) => wasCalled = true),
      methodChannel: const MethodChannel(methodChannelName),
      eventStream: controller.stream,
    );

    await detector.start();
    detector.registerOpenTrip('trip-1');
    controller.add('walking');
    await pumpEventQueue();

    expect(wasCalled, isFalse);

    await controller.close();
  });

  test('a second transition after one already reported does not double-report', () async {
    var callCount = 0;
    final controller = StreamController<dynamic>.broadcast();

    final detector = DepartureDetector.forTesting(
      tripLogger: _FakeTripLogger(onReportLeftAt: (_, _) => callCount++),
      methodChannel: const MethodChannel(methodChannelName),
      eventStream: controller.stream,
    );

    await detector.start();
    detector.registerOpenTrip('trip-1');
    controller.add('walking');
    await pumpEventQueue();
    controller.add('walking');
    await pumpEventQueue();

    expect(callCount, 1);

    await controller.close();
  });
}

class _FakeTripLogger implements TripLogger {
  _FakeTripLogger({required this.onReportLeftAt});

  final void Function(String tripId, DateTime leftAt) onReportLeftAt;

  @override
  Future<void> reportLeftAt(String tripId, DateTime leftAt) async {
    onReportLeftAt(tripId, leftAt);
  }

  @override
  Future<String?> logStationView({
    required String mode,
    required String originStop,
    String? routeOrDirection,
  }) async => null;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
