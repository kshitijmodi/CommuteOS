import 'package:flutter/material.dart';

import '../favorites/favorites_repository.dart';
import '../mta/mta_station.dart';
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
  /// station's multiple routes.
  String? _defaultRouteOrDirection(TransitStation station) {
    if (station is MtaStation) {
      return station.routes.isNotEmpty ? station.routes.first : null;
    }
    if (station is PathStation) {
      return station.directions.isNotEmpty
          ? station.directions.first.key
          : null;
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
            return const Center(child: CircularProgressIndicator());
          }

          final favorites = snapshot.data ?? const <TransitStation>[];
          if (favorites.length < 2) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Favorite at least two stations to compare them here.',
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }

          return Column(
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'Select two or more favorites to compare right now:',
                ),
              ),
              Expanded(
                child: ListView(
                  children: [
                    for (final station in favorites)
                      CheckboxListTile(
                        title: Text(station.name),
                        subtitle: Text(station.routes.join(' ')),
                        value: _selected.contains(station),
                        onChanged: (checked) {
                          setState(() {
                            if (checked == true) {
                              _selected.add(station);
                            } else {
                              _selected.remove(station);
                            }
                          });
                        },
                      ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: FilledButton(
                  onPressed: _selected.length >= 2 ? _getRecommendation : null,
                  child: const Text('Get recommendation'),
                ),
              ),
              if (_recommendationFuture != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: _RecommendationResult(future: _recommendationFuture!),
                ),
            ],
          );
        },
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
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Text(
            '${snapshot.error}',
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          );
        }

        final recommendation = snapshot.data!;
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  recommendation.message,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Confidence: ${(recommendation.confidence * 100).round()}%'
                  '${recommendation.isLive ? '' : ' (live data unavailable)'}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
