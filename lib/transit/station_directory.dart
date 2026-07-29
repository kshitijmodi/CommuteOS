import '../mta/mta_station_repository.dart';
import '../path/path_station.dart';
import 'transit_models.dart';

/// Merges every agency's stations into one list for search/favorites, so
/// the UI never has to think about "which agency" — it just sees stations.
///
/// PATH's 13 stations are hardcoded (see PathStation.all) and effectively
/// free to load; MTA's ~496 come from a bundled CSV parse, which is the
/// only part of this that's meaningfully async.
class StationDirectory {
  StationDirectory({MtaStationRepository? mtaRepository})
    : _mtaRepository = mtaRepository ?? MtaStationRepository();

  final MtaStationRepository _mtaRepository;

  Future<List<TransitStation>> loadAllStations() async {
    final mtaStations = await _mtaRepository.loadStations();
    return [...mtaStations, ...PathStation.all];
  }
}
