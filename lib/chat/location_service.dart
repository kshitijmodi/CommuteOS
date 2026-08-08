import 'package:geolocator/geolocator.dart';

/// A real device coordinate pair, or the specific reason none was
/// available - callers (see chat_repository.dart) never need to guess why
/// a question went out without coordinates, and never fabricate a
/// location when one can't be obtained.
class LocationResult {
  const LocationResult.available(this.latitude, this.longitude)
    : unavailableReason = null;

  const LocationResult.unavailable(this.unavailableReason)
    : latitude = null,
      longitude = null;

  final double? latitude;
  final double? longitude;
  final String? unavailableReason;

  bool get hasCoordinates => latitude != null && longitude != null;
}

/// Fetches the device's real current GPS position, requesting the runtime
/// permission first if it hasn't been granted yet. Deliberately on-demand
/// only - called right before a location-dependent question is sent (see
/// ChatRepository.ask), never polled continuously in the background, and
/// never cached across calls since the whole point is the user's current
/// position, not a stale one.
class LocationService {
  /// Returns real coordinates when permission is granted and a location
  /// fix succeeds; otherwise a [LocationResult.unavailable] carrying the
  /// real reason (service disabled, permission denied, permission denied
  /// forever, or a timeout/error) - never a guessed or default position.
  Future<LocationResult> getCurrentLocation() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return const LocationResult.unavailable('location services are off');
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.denied) {
      return const LocationResult.unavailable('location permission denied');
    }
    if (permission == LocationPermission.deniedForever) {
      return const LocationResult.unavailable(
        'location permission permanently denied',
      );
    }

    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 10),
        ),
      );
      return LocationResult.available(position.latitude, position.longitude);
    } catch (_) {
      return const LocationResult.unavailable('could not get a location fix');
    }
  }
}
