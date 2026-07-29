import 'package:flutter/material.dart';

import '../favorites/favorites_repository.dart';
import '../favorites/station_list_tile.dart';
import 'mta_station.dart';
import 'mta_station_repository.dart';

/// Full searchable list of every NYC subway station, reachable from the
/// favorites screen. Each row can also be favorited/unfavorited from here.
class StationSearchScreen extends StatefulWidget {
  const StationSearchScreen({super.key});

  @override
  State<StationSearchScreen> createState() => _StationSearchScreenState();
}

class _StationSearchScreenState extends State<StationSearchScreen> {
  final _stationRepository = MtaStationRepository();
  final _favoritesRepository = FavoritesRepository();
  final _searchController = TextEditingController();
  late Future<List<MtaStation>> _stationsFuture;
  Set<String> _favoriteIds = {};
  String _query = '';

  @override
  void initState() {
    super.initState();
    _stationsFuture = _stationRepository.loadStations();
    _loadFavorites();
  }

  Future<void> _loadFavorites() async {
    final ids = await _favoritesRepository.loadFavoriteIds();
    if (mounted) setState(() => _favoriteIds = ids);
  }

  Future<void> _toggleFavorite(MtaStation station, bool isFavorite) async {
    setState(() {
      if (isFavorite) {
        _favoriteIds.add(station.gtfsStopId);
      } else {
        _favoriteIds.remove(station.gtfsStopId);
      }
    });
    await _favoritesRepository.setFavorite(station.gtfsStopId, isFavorite);
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('All Stations'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(56),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                hintText: 'Search stations…',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
                isDense: true,
                filled: true,
              ),
              onChanged: (value) => setState(() => _query = value),
            ),
          ),
        ),
      ),
      body: FutureBuilder<List<MtaStation>>(
        future: _stationsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text('Failed to load stations:\n${snapshot.error}'),
              ),
            );
          }

          final stations = snapshot.data ?? const <MtaStation>[];
          final query = _query.trim().toLowerCase();
          final filtered = query.isEmpty
              ? stations
              : stations
                    .where((s) => s.name.toLowerCase().contains(query))
                    .toList();

          if (filtered.isEmpty) {
            return const Center(child: Text('No stations match your search.'));
          }

          return ListView.separated(
            itemCount: filtered.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final station = filtered[index];
              return StationListTile(
                station: station,
                isFavorite: _favoriteIds.contains(station.gtfsStopId),
                onFavoriteToggle: (isFav) => _toggleFavorite(station, isFav),
              );
            },
          );
        },
      ),
    );
  }
}
