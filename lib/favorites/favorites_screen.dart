import 'package:flutter/material.dart';

import '../account/recommendation_card.dart';
import '../account/recommendation_repository.dart';
import '../design/components.dart';
import '../design/theme.dart';
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
  final _recommendationRepository = RecommendationRepository();
  late Future<List<TransitStation>> _stationsFuture;
  Set<String> _favoriteKeys = {};

  // Null while still loading or when there's genuinely nothing to show
  // (home/office not confirmed yet, or not resolvable to a live candidate -
  // see RecommendationRepository.getRecommendationFromHomeOffice's docs) -
  // the card is simply omitted in that case rather than showing an error,
  // since a user who hasn't set up home/office yet shouldn't see a failure
  // for a feature they haven't opted into.
  Future<Recommendation?>? _recommendationFuture;

  @override
  void initState() {
    super.initState();
    _stationsFuture = _stationDirectory.loadAllStations();
    _loadFavorites();
    _recommendationFuture = _recommendationRepository
        .getRecommendationFromHomeOffice()
        .catchError((_) => null);
    // Favoriting/unfavoriting from the separate bottom-nav Search tab (a
    // persistent sibling widget, not something pushed on top of this one -
    // see root_shell.dart) doesn't touch this screen's state at all by
    // itself, since IndexedStack keeps both tabs alive without rebuilding
    // one when the other changes. Listening here is what picks that up.
    FavoritesRepository.changes.addListener(_loadFavorites);
  }

  @override
  void dispose() {
    FavoritesRepository.changes.removeListener(_loadFavorites);
    super.dispose();
  }

  Future<void> _loadFavorites() async {
    final keys = await _favoritesRepository.loadFavoriteKeys();
    if (mounted) setState(() => _favoriteKeys = keys);
  }

  Future<void> _removeFavorite(TransitStation station) async {
    await _favoritesRepository.setFavorite(station, false);
  }

  Future<void> _openSearch() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const StationSearchScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CommuteOS'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search_rounded),
            tooltip: 'Search stations',
            onPressed: _openSearch,
          ),
        ],
      ),
      body: FutureBuilder<List<TransitStation>>(
        future: _stationsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const AppLoader();
          }
          if (snapshot.hasError) {
            return EmptyState(
              icon: Icons.error_outline_rounded,
              title: 'Failed to load stations',
              message: '${snapshot.error}',
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

          return ListView(
            padding: const EdgeInsets.only(bottom: AppSpacing.lg),
            children: [
              FutureBuilder<Recommendation?>(
                future: _recommendationFuture,
                builder: (context, snapshot) {
                  final recommendation = snapshot.data;
                  if (recommendation == null) return const SizedBox.shrink();
                  return Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.md,
                      AppSpacing.md,
                      AppSpacing.md,
                      0,
                    ),
                    child: RecommendationCard(recommendation: recommendation),
                  );
                },
              ),
              if (favorites.isEmpty)
                EmptyState(
                  icon: Icons.star_border_rounded,
                  title: 'No favorite stations yet',
                  message: 'Search for a station and tap the star to add it here.',
                  action: FilledButton.icon(
                    onPressed: _openSearch,
                    icon: const Icon(Icons.search_rounded),
                    label: const Text('Search stations'),
                  ),
                )
              else ...[
                SectionHeader('Favorites · ${favorites.length}'),
                for (final station in favorites)
                  StationListTile(
                    group: StationGroup(name: station.name, stations: [station]),
                    isStationFavorite: (_) => true,
                    onStationFavoriteToggle: (s, isFav) {
                      if (!isFav) _removeFavorite(s);
                    },
                  ),
              ],
            ],
          );
        },
      ),
    );
  }
}
