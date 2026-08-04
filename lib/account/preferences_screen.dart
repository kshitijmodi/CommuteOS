import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../design/components.dart';
import '../design/theme.dart';
import 'home_office_repository.dart';
import 'preferences_repository.dart';
import 'push_registration_service.dart';

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
  static const _pushEnabledKey = 'commute_push_enabled';

  final _repository = PreferencesRepository();
  final _homeOfficeRepository = HomeOfficeRepository();
  final _pushRegistrationService = PushRegistrationService();
  late Future<LearnedPreferences?> _preferencesFuture;
  late Future<HomeOffice?> _homeOfficeFuture;
  bool _isRecomputing = false;
  bool _pushEnabled = false;

  @override
  void initState() {
    super.initState();
    _preferencesFuture = _repository.getMyPreferences();
    _homeOfficeFuture = _homeOfficeRepository.getMyHomeOffice();
    _loadPushState();
  }

  Future<void> _loadPushState() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) {
      setState(() => _pushEnabled = prefs.getBool(_pushEnabledKey) ?? false);
    }
  }

  /// Registers (or just remembers "off" locally) for the real proactive
  /// notification pipeline - a scheduled backend job that runs the
  /// decision engine + LLM phrasing and pushes an actual recommendation,
  /// replacing the earlier fixed-time local reminder. Push delivery
  /// itself is currently stubbed (see PushRegistrationService) pending a
  /// real Firebase project; this toggle exercises the whole registration
  /// pipeline regardless.
  Future<void> _togglePush(bool enabled) async {
    if (enabled) {
      final registered = await _pushRegistrationService.register();
      if (!registered) return; // not logged in / backend rejected - leave off
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_pushEnabledKey, enabled);
    setState(() => _pushEnabled = enabled);
  }

  Future<void> _recompute() async {
    setState(() => _isRecomputing = true);
    final updated = await _repository.recomputeMyPreferences();
    final homeOffice = await _homeOfficeRepository.inferMyHomeOffice();
    setState(() {
      _isRecomputing = false;
      _preferencesFuture = Future.value(updated);
      _homeOfficeFuture = Future.value(homeOffice);
    });
  }

  Future<void> _confirmHomeOffice() async {
    final updated = await _homeOfficeRepository.confirmMyHomeOffice();
    setState(() => _homeOfficeFuture = Future.value(updated));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('What CommuteOS has learned')),
      body: FutureBuilder<LearnedPreferences?>(
        future: _preferencesFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const AppLoader();
          }

          final preferences = snapshot.data;
          if (preferences == null) {
            return const EmptyState(
              icon: Icons.insights_outlined,
              title: 'Nothing learned yet',
              message: 'Log in to see what CommuteOS has learned about your commute.',
            );
          }

          final walkingMiles = preferences.walkingToleranceM / 1609.34;
          // reliability_pref is the PRD's one explicit onboarding input
          // (not derived from trip history the way walking tolerance is),
          // so it's always meaningful to show regardless of trip_count -
          // it just starts at a neutral default until the user changes it
          // somewhere else in the app.
          final reliabilityLabel = preferences.reliabilityPref < 0.4
              ? 'You prefer arriving on time over arriving fastest.'
              : preferences.reliabilityPref > 0.6
              ? 'You prefer the fastest option, even if less certain.'
              : 'You weigh speed and reliability about evenly.';

          return ListView(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              AppSpacing.md,
              AppSpacing.md,
              AppSpacing.xl,
            ),
            children: [
              FutureBuilder<HomeOffice?>(
                future: _homeOfficeFuture,
                builder: (context, homeOfficeSnapshot) {
                  final homeOffice = homeOfficeSnapshot.data;
                  if (homeOffice == null || !homeOffice.hasInference) {
                    return const SizedBox.shrink();
                  }
                  return Column(
                    children: [
                      _HomeOfficeCard(
                        homeOffice: homeOffice,
                        onConfirm: _confirmHomeOffice,
                      ),
                      if (homeOffice.confirmed) ...[
                        const SizedBox(height: AppSpacing.sm),
                        AppCard(
                          child: Row(
                            children: [
                              const Icon(
                                Icons.notifications_none_rounded,
                                color: AppColors.textSecondary,
                              ),
                              const SizedBox(width: AppSpacing.md),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Smart commute notifications',
                                      style: Theme.of(context).textTheme.bodyLarge,
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      'A real, live recommendation for your commute '
                                      '- not just a reminder to check.',
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                              ),
                              Switch(
                                value: _pushEnabled,
                                onChanged: _togglePush,
                              ),
                            ],
                          ),
                        ),
                      ],
                      const SizedBox(height: AppSpacing.md),
                    ],
                  );
                },
              ),
              const SectionHeader('Learned preferences'),
              AppCard(
                child: Column(
                  children: [
                    _PreferenceRow(
                      icon: Icons.directions_walk_rounded,
                      title: 'Walking tolerance',
                      value: preferences.walkingToleranceLearned
                          ? '${walkingMiles.toStringAsFixed(2)} mi'
                          : null,
                    ),
                    const Divider(height: AppSpacing.lg),
                    // transfer_aversion_score has no "learned" state at all
                    // yet (see LearnedPreferences' docstring) - always
                    // shown as not-yet-learned rather than a real number,
                    // regardless of trip_count.
                    const _PreferenceRow(
                      icon: Icons.compare_arrows_rounded,
                      title: 'Transfer aversion',
                      value: null,
                    ),
                  ],
                ),
              ),
              if (!preferences.walkingToleranceLearned) ...[
                const SizedBox(height: AppSpacing.sm),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Text(
                    preferences.tripCount == 0
                        ? "Still learning — browse a few commutes and this will personalize."
                        : 'Still learning — ${preferences.tripCount} trip'
                              '${preferences.tripCount == 1 ? '' : 's'} logged so far, '
                              'a few more will personalize this.',
                    style: Theme.of(
                      context,
                    ).textTheme.bodySmall?.copyWith(color: AppColors.textTertiary),
                  ),
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Text(
                  reliabilityLabel,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              OutlinedButton.icon(
                onPressed: _isRecomputing ? null : _recompute,
                icon: _isRecomputing
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh_rounded),
                label: const Text('Recompute from recent activity'),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _HomeOfficeCard extends StatelessWidget {
  const _HomeOfficeCard({required this.homeOffice, required this.onConfirm});

  final HomeOffice homeOffice;
  final VoidCallback onConfirm;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Looks like your commute is:', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: AppSpacing.sm),
          if (homeOffice.homeStation != null)
            _StationLine(icon: Icons.home_rounded, label: 'Home', value: homeOffice.homeStation!),
          if (homeOffice.officeStation != null) ...[
            const SizedBox(height: 6),
            _StationLine(
              icon: Icons.work_rounded,
              label: 'Office',
              value: homeOffice.officeStation!,
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          if (homeOffice.confirmed)
            const Row(
              children: [
                Icon(Icons.check_circle_rounded, size: 16, color: AppColors.success),
                SizedBox(width: 6),
                Text(
                  'Confirmed',
                  style: TextStyle(color: AppColors.success, fontWeight: FontWeight.w600),
                ),
              ],
            )
          else
            FilledButton(
              onPressed: onConfirm,
              child: const Text('Yes, that\'s right'),
            ),
        ],
      ),
    );
  }
}

class _StationLine extends StatelessWidget {
  const _StationLine({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: AppColors.textTertiary),
        const SizedBox(width: AppSpacing.sm),
        Text('$label: ', style: Theme.of(context).textTheme.bodyMedium),
        Text(
          value,
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

class _PreferenceRow extends StatelessWidget {
  const _PreferenceRow({
    required this.icon,
    required this.title,
    required this.value,
  });

  final IconData icon;
  final String title;

  /// Null when this preference hasn't actually been learned from real
  /// usage yet - shown as "Still learning" instead of a number that would
  /// otherwise look like a real, confident measurement.
  final String? value;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: AppColors.textSecondary),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.bodyLarge),
        ),
        Text(
          value ?? 'Still learning',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            color: value == null ? AppColors.textTertiary : AppColors.accent,
          ),
        ),
      ],
    );
  }
}
