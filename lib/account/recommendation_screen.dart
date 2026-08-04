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

/// Phase 3: get a single recommendation for which route to take right now.
/// Defaults to auto-discovery from the user's confirmed home/office
/// stations (GET /recommendations/from-home-office) - no setup needed once
/// home/office is confirmed (see the preferences screen). Falls back to
/// manually picking two or more favorited stations to compare when
/// auto-discovery isn't available yet (home/office unconfirmed, or not yet
/// resolvable to a real candidate route - see
/// recommendation_builder.specs_from_home_office on the backend).
class RecommendationScreen extends StatefulWidget {
  const RecommendationScreen({super.key});

  @override
  State<RecommendationScreen> createState() => _RecommendationScreenState();
}

enum _Mode { loadingAuto, auto, manual }

class _RecommendationScreenState extends State<RecommendationScreen> {
  final _stationDirectory = StationDirectory();
  final _favoritesRepository = FavoritesRepository();
  final _recommendationRepository = RecommendationRepository();

  _Mode _mode = _Mode.loadingAuto;
  Future<Recommendation>? _autoRecommendationFuture;

  late Future<List<TransitStation>> _favoritesFuture;
  final _selected = <TransitStation>{};
  Future<Recommendation>? _recommendationFuture;

  @override
  void initState() {
    super.initState();
    _favoritesFuture = _loadFavoriteStations();
    _tryAutoDiscovery();
  }

  Future<void> _tryAutoDiscovery() async {
    final future = _recommendationRepository.getRecommendationFromHomeOffice();
    final result = await future.catchError((_) => null);

    if (!mounted) return;
    if (result == null) {
      setState(() => _mode = _Mode.manual);
    } else {
      setState(() {
        _mode = _Mode.auto;
        _autoRecommendationFuture = Future.value(result);
      });
    }
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
      body: switch (_mode) {
        _Mode.loadingAuto => const AppLoader(),
        _Mode.auto => _buildAuto(context),
        _Mode.manual => _buildManual(context),
      },
    );
  }

  Widget _buildAuto(BuildContext context) {
    return Column(
      children: [
        const SectionHeader('Your usual commute'),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
          child: Text(
            'Based on your confirmed home and office stations.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
          child: _RecommendationResult(future: _autoRecommendationFuture!),
        ),
        const Spacer(),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: TextButton(
            onPressed: () => setState(() => _mode = _Mode.manual),
            child: const Text('Compare different stations instead'),
          ),
        ),
      ],
    );
  }

  Widget _buildManual(BuildContext context) {
    return FutureBuilder<List<TransitStation>>(
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
              const SectionHeader('Compare specific options'),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                child: Text(
                  // This mode doesn't know your actual origin/destination -
                  // it only ranks whichever specific stations you select
                  // against each other by soonest live arrival. It's meant
                  // for comparing two real alternatives to the same place
                  // (e.g. two stations near the same destination), not for
                  // picking stations that don't relate to one trip - that
                  // will look like a "random" pick, since it has no way to
                  // know they're unrelated. Confirm home/office in "What
                  // CommuteOS has learned" for a recommendation that
                  // actually knows where you're commuting to.
                  'Select two or more favorites that are real alternatives to each other '
                  '(e.g. two ways to reach the same place) - this compares them by live '
                  'arrival time only, without knowing your actual commute.',
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
