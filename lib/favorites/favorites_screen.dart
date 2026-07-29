import 'package:flutter/material.dart';

import '../transit/natural_sort.dart';
import '../transit/station_directory.dart';
import '../transit/station_group.dart';
import '../transit/station_list_tile.dart';
import '../transit/station_search_screen.dart';
import '../transit/transit_models.dart';
import 'favorites_repository.dart';

/// Home screen: the user's favorited stations, with a way to reach the full
/// searchable station list to add more.
class FavoritesScreen extends StatefulWidget {
  const FavoritesScreen({super.key});

  @override
  State<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends State<FavoritesScreen> {
  final _stationDirectory = StationDirectory();
  final _favoritesRepository = FavoritesRepository();
  late Future<List<TransitStation>> _stationsFuture;
  Set<String> _favoriteKeys = {};

  @override
  void initState() {
    super.initState();
    _stationsFuture = _stationDirectory.loadAllStations();
    _loadFavorites();
  }

  Future<void> _loadFavorites() async {
    final keys = await _favoritesRepository.loadFavoriteKeys();
    if (mounted) setState(() => _favoriteKeys = keys);
  }

  Future<void> _removeFavorite(TransitStation station) async {
    await _favoritesRepository.setFavorite(station, false);
    await _loadFavorites();
  }

  Future<void> _openSearch() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const StationSearchScreen()),
    );
    // Favorites may have changed while the search screen was open.
    await _loadFavorites();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CommuteOS'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            tooltip: 'Search all stations',
            onPressed: _openSearch,
          ),
        ],
      ),
      body: FutureBuilder<List<TransitStation>>(
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

          final stations = snapshot.data ?? const <TransitStation>[];
          // Each favorited station is its own row here — the user already
          // picked a specific station when favoriting, even if its name is
          // shared with another (unconnected) station elsewhere.
          final favorites =
              stations
                  .where(
                    (s) => _favoritesRepository.isFavorite(_favoriteKeys, s),
                  )
                  .toList()
                ..sort((a, b) => compareStationNames(a.name, b.name));

          if (favorites.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'No favorite stations yet.',
                      style: TextStyle(fontSize: 18),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Search for a station and tap the star to add it here.',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 16),
                    FilledButton.icon(
                      onPressed: _openSearch,
                      icon: const Icon(Icons.search),
                      label: const Text('Search stations'),
                    ),
                  ],
                ),
              ),
            );
          }

          return ListView.separated(
            itemCount: favorites.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final station = favorites[index];
              return StationListTile(
                group: StationGroup(name: station.name, stations: [station]),
                isStationFavorite: (_) => true,
                onStationFavoriteToggle: (s, isFav) {
                  if (!isFav) _removeFavorite(s);
                },
              );
            },
          );
        },
      ),
    );
  }
}
