import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../design/components.dart';
import '../design/theme.dart';
import 'commute_notification_service.dart';
import 'home_office_repository.dart';
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
  static const _reminderEnabledKey = 'commute_reminder_enabled';

  final _repository = PreferencesRepository();
  final _homeOfficeRepository = HomeOfficeRepository();
  final _notificationService = CommuteNotificationService();
  late Future<LearnedPreferences?> _preferencesFuture;
  late Future<HomeOffice?> _homeOfficeFuture;
  bool _isRecomputing = false;
  bool _reminderEnabled = false;

  @override
  void initState() {
    super.initState();
    _preferencesFuture = _repository.getMyPreferences();
    _homeOfficeFuture = _homeOfficeRepository.getMyHomeOffice();
    _notificationService.initialize();
    _loadReminderState();
  }

  Future<void> _loadReminderState() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) {
      setState(
        () => _reminderEnabled = prefs.getBool(_reminderEnabledKey) ?? false,
      );
    }
  }

  Future<void> _toggleReminder(bool enabled) async {
    if (enabled) {
      final granted = await _notificationService.requestPermission();
      if (!granted) return; // user declined - leave the toggle off
      await _notificationService.scheduleDailyReminder(
        hour: 7,
        minute: 45,
        title: 'Time to check your commute',
        body: 'Open CommuteOS to see what to take today.',
      );
    } else {
      await _notificationService.cancelDailyReminder();
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_reminderEnabledKey, enabled);
    setState(() => _reminderEnabled = enabled);
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
                                      'Daily commute reminder',
                                      style: Theme.of(context).textTheme.bodyLarge,
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      'A local notification each morning at 7:45 AM.',
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                              ),
                              Switch(
                                value: _reminderEnabled,
                                onChanged: _toggleReminder,
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
                      value: '${walkingMiles.toStringAsFixed(2)} mi',
                    ),
                    const Divider(height: AppSpacing.lg),
                    _PreferenceRow(
                      icon: Icons.compare_arrows_rounded,
                      title: 'Transfer aversion',
                      value: '${(preferences.transferAversionScore * 100).round()}%',
                    ),
                  ],
                ),
              ),
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
  final String value;

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
          value,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppColors.accent),
        ),
      ],
    );
  }
}
