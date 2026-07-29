/// A single predicted arrival at a stop, parsed out of a GTFS-RT TripUpdate.
class MtaArrival {
  const MtaArrival({
    required this.routeId,
    required this.stopId,
    required this.arrivalTime,
  });

  final String routeId;
  final String stopId;
  final DateTime arrivalTime;

  Duration get timeUntilArrival => arrivalTime.difference(DateTime.now());
}
