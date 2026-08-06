import 'package:flutter/material.dart';

import '../design/components.dart';
import '../design/theme.dart';
import '../favorites/favorites_repository.dart';
import 'station_directory.dart';
import 'station_group.dart';
import 'station_list_tile.dart';
import 'transit_models.dart';

/// Full searchable list of every station across every agency, with an
/// agency filter (a station group spanning multiple agencies - e.g.
/// Journal Square's PATH/NJT rail/NJT bus - matches the filter if ANY of
/// its member stations do). Each row can also be favorited/unfavorited
/// from here.
class StationSearchScreen extends StatefulWidget {
  const StationSearchScreen({super.key});

  @override
  State<StationSearchScreen> createState() => _StationSearchScreenState();
}

class _StationSearchScreenState extends State<StationSearchScreen> {
  final _stationDirectory = StationDirectory();
  final _favoritesRepository = FavoritesRepository();
  final _searchController = TextEditingController();
  late Future<List<StationGroup>> _groupsFuture;
  Set<String> _favoriteKeys = {};
  String _query = '';

  /// null means "All agencies" - the filter row's default.
  Agency? _selectedAgency;

  @override
  void initState() {
    super.initState();
    _groupsFuture = _stationDirectory
        .loadAllStations()
        .then(StationGroup.groupByName);
    _loadFavorites();
    // See FavoritesScreen's identical listener - the Favorites tab is a
    // persistent sibling widget (IndexedStack), not something this screen
    // is pushed on top of, so a favorite removed there wouldn't otherwise
    // be reflected here until something else triggered a reload.
    FavoritesRepository.changes.addListener(_loadFavorites);
  }

  Future<void> _loadFavorites() async {
    final keys = await _favoritesRepository.loadFavoriteKeys();
    if (mounted) setState(() => _favoriteKeys = keys);
  }

  Future<void> _toggleFavorite(TransitStation station, bool isFavorite) async {
    await _favoritesRepository.setFavorite(station, isFavorite);
  }

  @override
  void dispose() {
    FavoritesRepository.changes.removeListener(_loadFavorites);
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Search'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(64),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              0,
              AppSpacing.md,
              AppSpacing.md,
            ),
            child: TextField(
              controller: _searchController,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: InputDecoration(
                hintText: 'Search all stations…',
                prefixIcon: const Icon(
                  Icons.search_rounded,
                  color: AppColors.textTertiary,
                ),
                // Only shown once there's text to clear - lets you wipe the
                // query in one tap without focusing the field (and raising
                // the keyboard) just to backspace it out manually.
                suffixIcon: _query.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(
                          Icons.close_rounded,
                          color: AppColors.textTertiary,
                        ),
                        tooltip: 'Clear search',
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _query = '');
                        },
                      ),
                isDense: true,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                  borderSide: BorderSide.none,
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                  borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
                ),
              ),
              onChanged: (value) => setState(() => _query = value),
            ),
          ),
        ),
      ),
      body: FutureBuilder<List<StationGroup>>(
        future: _groupsFuture,
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

          final groups = snapshot.data ?? const <StationGroup>[];
          final query = _query.trim().toLowerCase();
          final byQuery = query.isEmpty
              ? groups
              : groups
                    .where((g) => g.name.toLowerCase().contains(query))
                    .toList();
          final selectedAgency = _selectedAgency;
          final filtered = selectedAgency == null
              ? byQuery
              : byQuery
                    .where((g) => g.stations.any((s) => s.agency == selectedAgency))
                    .toList();

          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.sm,
                ),
                child: Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    AgencyFilterChip(
                      label: 'All',
                      selected: _selectedAgency == null,
                      onTap: () => setState(() => _selectedAgency = null),
                    ),
                    for (final agency in Agency.values)
                      AgencyFilterChip(
                        label: agencyFilterLabel(agency),
                        color: agencyColor(agency),
                        selected: _selectedAgency == agency,
                        onTap: () => setState(() => _selectedAgency = agency),
                      ),
                  ],
                ),
              ),
              Expanded(
                child: filtered.isEmpty
                    ? const EmptyState(
                        icon: Icons.search_off_rounded,
                        title: 'No stations match your search',
                      )
                    : ListView(
                        children: [
                          for (final group in filtered)
                            StationListTile(
                              group: group,
                              isStationFavorite: (s) =>
                                  _favoritesRepository.isFavorite(_favoriteKeys, s),
                              onStationFavoriteToggle: _toggleFavorite,
                            ),
                        ],
                      ),
              ),
            ],
          );
        },
      ),
    );
  }
}
