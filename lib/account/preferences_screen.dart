import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../behavior/station_geofence_service.dart';
import '../design/components.dart';
import '../design/theme.dart';
import '../favorites/favorites_repository.dart';
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
  static const _geofencingEnabledKey = 'station_geofencing_enabled';

  final _repository = PreferencesRepository();
  final _homeOfficeRepository = HomeOfficeRepository();
  final _pushRegistrationService = PushRegistrationService();
  final _geofenceService = StationGeofenceService();
  late Future<LearnedPreferences?> _preferencesFuture;
  late Future<HomeOffice?> _homeOfficeFuture;
  bool _isRecomputing = false;
  bool _pushEnabled = false;
  bool _geofencingEnabled = false;

  @override
  void initState() {
    super.initState();
    _preferencesFuture = _repository.getMyPreferences();
    _homeOfficeFuture = _homeOfficeRepository.getMyHomeOffice();
    _loadPushState();
    _loadGeofencingState();
    FavoritesRepository.changes.addListener(_onFavoritesChanged);
  }

  @override
  void dispose() {
    FavoritesRepository.changes.removeListener(_onFavoritesChanged);
    super.dispose();
  }

  /// Keeps the geofenced station set current - a favorite removed should
  /// stop being geofenced, a newly added one should start being. A no-op
  /// while the feature is off (nothing registered to re-sync).
  void _onFavoritesChanged() {
    if (_geofencingEnabled) _geofenceService.syncGeofences();
  }

  Future<void> _loadPushState() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) {
      setState(() => _pushEnabled = prefs.getBool(_pushEnabledKey) ?? false);
    }
  }

  Future<void> _loadGeofencingState() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) {
      setState(() => _geofencingEnabled = prefs.getBool(_geofencingEnabledKey) ?? false);
    }
  }

  /// Real background geofencing (see StationGeofenceService's docs) - a
  /// stronger, more sensitive permission ask than push notifications
  /// (Android's ACCESS_BACKGROUND_LOCATION has its own dedicated Settings
  /// screen, not a simple dialog, starting Android 10+), so this is an
  /// explicit opt-in toggle here rather than something silently started
  /// at app launch - same posture as the push toggle above, just for a
  /// bigger ask.
  Future<void> _toggleGeofencing(bool enabled) async {
    if (enabled) {
      final granted = await _requestBackgroundLocationPermission();
      if (!granted) return; // denied - leave off, never silently retry
      await _geofenceService.initializeAndSync();
    } else {
      await _geofenceService.removeAllGeofences();
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_geofencingEnabledKey, enabled);
    setState(() => _geofencingEnabled = enabled);
  }

  /// Android requires foreground location to already be granted before
  /// ACCESS_BACKGROUND_LOCATION can even be requested - this is Android's
  /// own required two-step flow, not a choice made here. Returns false
  /// (never guesses/retries) for any denial at either step.
  Future<bool> _requestBackgroundLocationPermission() async {
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission != LocationPermission.whileInUse &&
        permission != LocationPermission.always) {
      return false;
    }
    if (permission == LocationPermission.always) return true;

    // Already whileInUse - the second, separate background-location ask.
    final upgraded = await Geolocator.requestPermission();
    return upgraded == LocationPermission.always;
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
    // A freshly (re-)inferred home/office station should join the
    // geofenced set immediately, not wait for the next unrelated trigger.
    if (_geofencingEnabled) _geofenceService.syncGeofences();
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
              // Deliberately NOT gated behind homeOffice.confirmed (unlike
              // the push toggle above) - background geofencing is useful
              // from favorites alone, and it's actually part of what
              // helps home/office get inferred in the first place (real
              // trips logged without needing to open an arrivals screen).
              AppCard(
                child: Row(
                  children: [
                    const Icon(
                      Icons.location_on_outlined,
                      color: AppColors.textSecondary,
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Background station tracking',
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Log a trip automatically when you arrive at a '
                            'favorited (or home/office) station - even with '
                            'the app closed. Needs background location.',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                    Switch(
                      value: _geofencingEnabled,
                      onChanged: _toggleGeofencing,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.md),
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
