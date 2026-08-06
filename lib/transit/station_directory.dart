import '../lirr/lirr_station_repository.dart';
import '../mta/mta_station_repository.dart';
import '../njt/njt_bus_stop_repository.dart';
import '../njt/njt_rail_station_repository.dart';
import '../path/path_station.dart';
import 'transit_models.dart';

/// Merges every agency's stations into one list for search/favorites, so
/// the UI never has to think about "which agency" — it just sees stations.
///
/// PATH's 13 stations are hardcoded (see PathStation.all) and effectively
/// free to load; MTA's ~496, NJT rail's ~172, NJT bus's ~5k (already
/// filtered to a NYC-metro core - see build_njt_bus_stops.py), and LIRR's
/// ~127 come from bundled CSV parses, the only meaningfully async part of
/// this.
class StationDirectory {
  StationDirectory({
    MtaStationRepository? mtaRepository,
    NjtRailStationRepository? njtRailRepository,
    NjtBusStopRepository? njtBusRepository,
    LirrStationRepository? lirrRepository,
  }) : _mtaRepository = mtaRepository ?? MtaStationRepository(),
       _njtRailRepository = njtRailRepository ?? NjtRailStationRepository(),
       _njtBusRepository = njtBusRepository ?? NjtBusStopRepository(),
       _lirrRepository = lirrRepository ?? LirrStationRepository();

  final MtaStationRepository _mtaRepository;
  final NjtRailStationRepository _njtRailRepository;
  final NjtBusStopRepository _njtBusRepository;
  final LirrStationRepository _lirrRepository;

  Future<List<TransitStation>> loadAllStations() async {
    final mtaStations = await _mtaRepository.loadStations();
    final njtRailStations = await _njtRailRepository.loadStations();
    final njtBusStops = await _njtBusRepository.loadStations();
    final lirrStations = await _lirrRepository.loadStations();
    return [
      ...mtaStations,
      ...PathStation.all,
      ...njtRailStations,
      ...njtBusStops,
      ...lirrStations,
    ];
  }
}
