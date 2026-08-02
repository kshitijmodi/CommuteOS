import 'package:flutter/material.dart';

import '../design/components.dart';
import '../design/theme.dart';
import '../favorites/favorites_repository.dart';
import '../mta/mta_station.dart';
import '../njt/njt_bus_stop.dart';
import '../njt/njt_rail_station.dart';
import '../path/path_station.dart';
import '../transit/station_directory.dart';
import '../transit/transit_models.dart';
import 'recommendation_repository.dart';

/// Phase 3: pick two or more favorited stations to compare, and get a
/// single recommendation for which to take right now. This is a narrow
/// first version of the PRD's recommendation flow - it compares whatever
/// favorites the user selects, rather than automatically knowing "your
/// usual commute options," since the app doesn't yet infer that (see
/// OPEN_QUESTIONS.md on home/office inference being unbuilt).
class RecommendationScreen extends StatefulWidget {
  const RecommendationScreen({super.key});

  @override
  State<RecommendationScreen> createState() => _RecommendationScreenState();
}

class _RecommendationScreenState extends State<RecommendationScreen> {
  final _stationDirectory = StationDirectory();
  final _favoritesRepository = FavoritesRepository();
  final _recommendationRepository = RecommendationRepository();

  late Future<List<TransitStation>> _favoritesFuture;
  final _selected = <TransitStation>{};
  Future<Recommendation>? _recommendationFuture;

  @override
  void initState() {
    super.initState();
    _favoritesFuture = _loadFavoriteStations();
  }

  Future<List<TransitStation>> _loadFavoriteStations() async {
    final all = await _stationDirectory.loadAllStations();
    final favoriteKeys = await _favoritesRepository.loadFavoriteKeys();
    return all
        .where((s) => _favoritesRepository.isFavorite(favoriteKeys, s))
        .toList();
  }

  /// A single default route/direction per station for this first version -
  /// see the class doc for why this doesn't yet let the user pick among a
  /// station's multiple routes. NJT rail/bus have no route/direction to
  /// pick - one call returns every line at the stop - so it's always "".
  String? _defaultRouteOrDirection(TransitStation station) {
    if (station is MtaStation) {
      return station.routes.isNotEmpty ? station.routes.first : null;
    }
    if (station is PathStation) {
      return station.directions.isNotEmpty
          ? station.directions.first.key
          : null;
    }
    if (station is NjtRailStation || station is NjtBusStop) {
      return '';
    }
    return null;
  }

  Future<void> _getRecommendation() async {
    final candidates = _selected
        .map((station) {
          final routeOrDirection = _defaultRouteOrDirection(station);
          if (routeOrDirection == null) return null;
          return RecommendationCandidate(
            station: station,
            routeOrDirection: routeOrDirection,
          );
        })
        .whereType<RecommendationCandidate>()
        .toList();

    setState(() {
      _recommendationFuture = _recommendationRepository.getRecommendation(
        candidates,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('What should I take?')),
      body: FutureBuilder<List<TransitStation>>(
        future: _favoritesFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const AppLoader();
          }

          final favorites = snapshot.data ?? const <TransitStation>[];
          if (favorites.length < 2) {
            return const EmptyState(
              icon: Icons.alt_route_rounded,
              title: 'Not enough favorites yet',
              message: 'Favorite at least two stations to compare them here.',
            );
          }

          return Column(
            children: [
              const SectionHeader('Compare right now'),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                child: Text(
                  'Select two or more favorites to compare.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  children: [
                    for (final station in favorites)
                      _SelectableStationRow(
                        station: station,
                        selected: _selected.contains(station),
                        onChanged: (checked) {
                          setState(() {
                            if (checked) {
                              _selected.add(station);
                            } else {
                              _selected.remove(station);
                            }
                          });
                        },
                      ),
                    const SizedBox(height: AppSpacing.sm),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  0,
                  AppSpacing.md,
                  AppSpacing.md,
                ),
                child: SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _selected.length >= 2 ? _getRecommendation : null,
                    child: const Text('Get recommendation'),
                  ),
                ),
              ),
              if (_recommendationFuture != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md,
                    0,
                    AppSpacing.md,
                    AppSpacing.lg,
                  ),
                  child: _RecommendationResult(future: _recommendationFuture!),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _SelectableStationRow extends StatelessWidget {
  const _SelectableStationRow({
    required this.station,
    required this.selected,
    required this.onChanged,
  });

  final TransitStation station;
  final bool selected;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final chips = station.agency == Agency.path
        ? [RouteChip(agency: Agency.path, label: 'PATH')]
        : [
            for (final route in station.routes)
              RouteChip(agency: station.agency, label: route),
          ];

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: AppCard(
        onTap: () => onChanged(!selected),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(station.name, style: Theme.of(context).textTheme.bodyLarge),
                  const SizedBox(height: 6),
                  Wrap(spacing: 6, runSpacing: 6, children: chips),
                ],
              ),
            ),
            Checkbox(value: selected, onChanged: (v) => onChanged(v ?? false)),
          ],
        ),
      ),
    );
  }
}

class _RecommendationResult extends StatelessWidget {
  const _RecommendationResult({required this.future});

  final Future<Recommendation> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Recommendation>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: AppSpacing.md),
            child: AppLoader(),
          );
        }
        if (snapshot.hasError) {
          return AppCard(
            child: Text(
              '${snapshot.error}',
              style: const TextStyle(color: AppColors.error),
            ),
          );
        }

        final recommendation = snapshot.data!;
        return AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Icon(Icons.bolt_rounded, color: AppColors.accent),
                  LiveStatusPill(isLive: recommendation.isLive),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                recommendation.message,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Confidence: ${(recommendation.confidence * 100).round()}%',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        );
      },
    );
  }
}
