import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../account/trip_logger.dart';

/// Bridges the native Activity Recognition Transition listener
/// (android/.../ActivityTransitionPlugin.kt) to Dart and reports a
/// still->walking/in_vehicle transition as Behavior AI's timing-buffer
/// signal (backend Trip.left_at) - see that model's docstring.
///
/// Deliberately foreground-only for this first version: the native side
/// registers/unregisters with Play Services from MainActivity's lifecycle,
/// and this class only listens for events while something in the app has
/// called [start] (see ArrivalsScreen, which starts/stops it alongside its
/// own lifecycle). No background service, no GPS/location permission -
/// only the ACTIVITY_RECOGNITION runtime permission. See
/// ActivityTransitionPlugin.kt's class doc for why background reliability
/// was deliberately scoped out rather than attempted with a plugin that
/// has documented gaps there.
///
/// A single app-wide instance (not one per screen) since "which trip is
/// open" is inherently a single, app-wide piece of state - only one trip
/// can plausibly be "the one the user is about to leave for" at a time.
class DepartureDetector {
  DepartureDetector._({
    TripLogger? tripLogger,
    MethodChannel? methodChannel,
    Stream<dynamic>? eventStream,
  }) : _tripLogger = tripLogger ?? TripLogger(),
       _methodChannel = methodChannel ?? const MethodChannel('commuteos/activity_transition'),
       _eventStream =
           eventStream ??
           const EventChannel('commuteos/activity_transition_events').receiveBroadcastStream();

  static DepartureDetector instance = DepartureDetector._();

  /// Test-only escape hatch - real app code always uses [instance]. Takes
  /// a plain [Stream] rather than a real EventChannel so tests can feed
  /// fake events via a StreamController with no platform-channel mocking
  /// needed - `EventChannel.receiveBroadcastStream()` already returns
  /// `Stream<dynamic>`, so this loses no real capability.
  factory DepartureDetector.forTesting({
    required TripLogger tripLogger,
    required MethodChannel methodChannel,
    required Stream<dynamic> eventStream,
  }) => DepartureDetector._(
    tripLogger: tripLogger,
    methodChannel: methodChannel,
    eventStream: eventStream,
  );

  final TripLogger _tripLogger;
  final MethodChannel _methodChannel;
  final Stream<dynamic> _eventStream;

  String? _openTripId;
  DateTime? _openTripRegisteredAt;
  StreamSubscription<dynamic>? _subscription;

  /// A transition arriving more than this long after a trip was registered
  /// is treated as unrelated noise (e.g. the user browsed a station, put
  /// the phone away, and started walking for an unrelated reason much
  /// later) rather than a real departure signal for that specific trip.
  static const _maxTripAge = Duration(minutes: 20);

  /// Called by ArrivalsScreen once a trip has been logged for the station
  /// currently being viewed - see that screen's _logTripOnce. Overwrites
  /// any previously-registered trip; only the most recent one is a
  /// plausible candidate for "the trip the user is about to leave for."
  void registerOpenTrip(String tripId) => registerOpenTripAt(tripId, DateTime.now());

  /// Test-only variant of [registerOpenTrip] that takes an explicit
  /// registration time, so tests can exercise the [_maxTripAge] staleness
  /// check without a real 20-minute wait.
  @visibleForTesting
  void registerOpenTripAt(String tripId, DateTime registeredAt) {
    _openTripId = tripId;
    _openTripRegisteredAt = registeredAt;
  }

  /// Starts listening for real transition events. Requests the
  /// ACTIVITY_RECOGNITION permission if not already granted; a denial
  /// leaves this feature silently inactive (never blocks browsing/using
  /// the rest of the app - same non-blocking posture as push notification
  /// permission).
  Future<void> start() async {
    if (_subscription != null) return; // already listening

    final hasPermission = await _ensurePermission();
    if (!hasPermission) return;

    final started = await _methodChannel.invokeMethod<bool>('start') ?? false;
    if (!started) return;

    _subscription = _eventStream.listen(
      _onTransitionEvent,
      onError: (_) {}, // transient channel errors aren't user-facing
    );
  }

  Future<void> stop() async {
    await _subscription?.cancel();
    _subscription = null;
    try {
      await _methodChannel.invokeMethod('stop');
    } catch (_) {
      // Best-effort - nothing to recover if the native side is already gone.
    }
  }

  Future<bool> _ensurePermission() async {
    try {
      final hasPermission = await _methodChannel.invokeMethod<bool>('hasPermission') ?? false;
      if (hasPermission) return true;
      return await _methodChannel.invokeMethod<bool>('requestPermission') ?? false;
    } catch (_) {
      return false;
    }
  }

  void _onTransitionEvent(dynamic event) {
    if (event is! String) return;
    if (event != 'walking' && event != 'in_vehicle') return;

    final tripId = _openTripId;
    final registeredAt = _openTripRegisteredAt;
    if (tripId == null || registeredAt == null) return;

    if (DateTime.now().difference(registeredAt) > _maxTripAge) {
      _openTripId = null;
      _openTripRegisteredAt = null;
      return;
    }

    // One real transition is enough to explain this trip - clear it so a
    // second transition shortly after (e.g. walking, then stopping at a
    // corner, then walking again) doesn't re-report a later, less
    // accurate left_at over the real one.
    _openTripId = null;
    _openTripRegisteredAt = null;
    _tripLogger.reportLeftAt(tripId, DateTime.now());
  }
}
