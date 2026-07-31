import 'package:flutter/material.dart';

import 'preferences_repository.dart';

/// Phase 2 exit criteria per the PRD: "the app can state, in plain data,
/// this user prefers reliability over speed, tolerates 0.3mi walks,
/// prefers direct routes - demonstrably derived from real usage." This
/// screen is that plain-data statement, shown before Phase 3's LLM
/// phrasing gets involved anywhere.
class PreferencesScreen extends StatefulWidget {
  const PreferencesScreen({super.key});

  @override
  State<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends State<PreferencesScreen> {
  final _repository = PreferencesRepository();
  late Future<LearnedPreferences?> _preferencesFuture;
  bool _isRecomputing = false;

  @override
  void initState() {
    super.initState();
    _preferencesFuture = _repository.getMyPreferences();
  }

  Future<void> _recompute() async {
    setState(() => _isRecomputing = true);
    final updated = await _repository.recomputeMyPreferences();
    setState(() {
      _isRecomputing = false;
      _preferencesFuture = Future.value(updated);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('What CommuteOS has learned')),
      body: FutureBuilder<LearnedPreferences?>(
        future: _preferencesFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          final preferences = snapshot.data;
          if (preferences == null) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Log in to see what CommuteOS has learned about your commute.',
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }

          final walkingMiles = preferences.walkingToleranceM / 1609.34;
          final reliabilityLabel = preferences.reliabilityPref < 0.4
              ? 'You prefer arriving on time over arriving fastest.'
              : preferences.reliabilityPref > 0.6
              ? 'You prefer the fastest option, even if less certain.'
              : 'You weigh speed and reliability about evenly.';

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _PreferenceTile(
                icon: Icons.directions_walk,
                title: 'Walking tolerance',
                value: '${walkingMiles.toStringAsFixed(2)} mi',
              ),
              _PreferenceTile(
                icon: Icons.compare_arrows,
                title: 'Transfer aversion',
                value:
                    '${(preferences.transferAversionScore * 100).round()}%',
              ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Text(reliabilityLabel),
              ),
              const SizedBox(height: 24),
              OutlinedButton.icon(
                onPressed: _isRecomputing ? null : _recompute,
                icon: _isRecomputing
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh),
                label: const Text('Recompute from recent activity'),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _PreferenceTile extends StatelessWidget {
  const _PreferenceTile({
    required this.icon,
    required this.title,
    required this.value,
  });

  final IconData icon;
  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon),
      title: Text(title),
      trailing: Text(
        value,
        style: Theme.of(context).textTheme.titleMedium,
      ),
    );
  }
}
