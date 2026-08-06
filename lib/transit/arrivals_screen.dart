import 'dart:async';

import 'package:flutter/material.dart';

import '../account/trip_logger.dart';
import '../design/components.dart';
import '../design/theme.dart';
import '../lirr/lirr_service.dart';
import '../mta/mta_service.dart';
import '../njt/njt_bus_service.dart';
import '../njt/njt_rail_service.dart';
import '../path/path_service.dart';
import 'transit_models.dart';

/// Shows live arrivals for a station, split into direction tabs. Works for
/// any agency — the concrete [TransitService] is chosen based on
/// [TransitStation.agency].
///
/// Refresh interval is a compromise across agencies: MTA's feed updates
/// ~30s server-side; PATH's updates ~15s. Polling every 30s avoids hammering
/// either feed while staying well within "fresh enough for a next-train
/// display."
class ArrivalsScreen extends StatefulWidget {
  const ArrivalsScreen({super.key, required this.station});

  final TransitStation station;

  @override
  State<ArrivalsScreen> createState() => _ArrivalsScreenState();
}

class _ArrivalsScreenState extends State<ArrivalsScreen> {
  late final TransitService _service = switch (widget.station.agency) {
    Agency.mta => MtaService(),
    Agency.path => PathService(),
    Agency.njtRail => NjtRailService(),
    Agency.njtBus => NjtBusService(),
    Agency.lirr => LirrService(),
  };
  final _tripLogger = TripLogger();
  Timer? _timer;
  bool _hasLoggedTrip = false;

  // The 30s background refresh polls flaky/best-effort feeds (PATH has no
  // documented SLA, NJT rail/bus proxy through a free-tier backend that can
  // cold-start-timeout - see the class doc). A single transient failure
  // used to blank the whole screen with a hard error and repeat every 30s
  // for as long as the screen stayed open. Now: only the very first load
  // (no data shown yet) can show the error state; once real data has
  // loaded once, a failed background refresh just leaves it on screen
  // (with a small "couldn't refresh" banner) instead of replacing it.
  TransitArrivalsResult? _lastGoodResult;
  Object? _initialLoadError;
  bool _refreshFailed = false;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _refresh());
  }

  void _refresh() {
    _service
        .getArrivals(widget.station)
        .then((rawResult) {
          final result = dropPastArrivals(rawResult);
          _logTripOnce(result);
          if (!mounted) return;

          // A background refresh (we already have real data on screen)
          // that comes back with nothing in any direction is treated the
          // same as a failed refresh, not adopted - NJT's live GTFS-RT
          // snapshot can genuinely have a momentary gap between updates
          // (e.g. a bus that just departed, no new one posted yet) and
          // still return a real, successful, empty response. Without this,
          // that one flaky poll would replace a real arrivals list with
          // "no arrivals found" for 30s, then flip back on the next poll -
          // a real bug a user hit in practice. The very first load is
          // exempt: a genuinely empty result then (e.g. no more service
          // tonight) is a real state worth showing, not a hiccup to hide.
          final isEmptyAcrossAllDirections = result.arrivalsByDirectionKey.values
              .every((arrivals) => arrivals.isEmpty);
          if (_lastGoodResult != null && isEmptyAcrossAllDirections) {
            setState(() => _refreshFailed = true);
            return;
          }

          setState(() {
            _lastGoodResult = result;
            _initialLoadError = null;
            _refreshFailed = false;
          });
        })
        .catchError((error) {
          if (!mounted) return;
          setState(() {
            if (_lastGoodResult == null) {
              _initialLoadError = error;
            } else {
              _refreshFailed = true;
            }
          });
        });
  }

  /// Logs the trip once real arrivals data has actually loaded (not in
  /// initState, before anything is known) - see
  /// soonestRouteOrDirectionForTripLog's docs on why this is the only
  /// point a real route_or_direction value can be captured. Fire-and-
  /// forget: a no-op for logged-out users (the common case today - see
  /// OPEN_QUESTIONS.md on auth being opt-in, not required to browse).
  void _logTripOnce(TransitArrivalsResult result) {
    if (_hasLoggedTrip) return;
    _hasLoggedTrip = true;

    _tripLogger.logStationView(
      mode: wireAgencyName(widget.station.agency),
      originStop: widget.station.id,
      routeOrDirection: soonestRouteOrDirectionForTripLog(widget.station.agency, result),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    _service.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final directions = widget.station.directions;
    final tabCount = directions.isEmpty ? 1 : directions.length;

    return DefaultTabController(
      length: tabCount,
      child: Scaffold(
        appBar: AppBar(
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(widget.station.name, style: Theme.of(context).textTheme.titleLarge),
              Row(
                children: [
                  AppBadge(
                    agencyLabel(widget.station.agency),
                    color: agencyColor(widget.station.agency),
                    dense: true,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    widget.station.area,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ],
          ),
          bottom: directions.isEmpty
              ? null
              : TabBar(
                  tabs: [for (final d in directions) Tab(text: d.label)],
                ),
        ),
        body: RefreshIndicator(
          color: AppColors.accent,
          backgroundColor: AppColors.surfaceRaised,
          onRefresh: () async => _refresh(),
          child: _buildBody(context, directions),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context, List<TransitDirection> directions) {
    final result = _lastGoodResult;

    if (result == null) {
      if (_initialLoadError != null) {
        return _errorState();
      }
      // NJT rail/bus are the only two agencies proxied through our own
      // backend (see the class doc) - a free-tier Render service that's
      // been idle can take up to a minute to wake up on the first request,
      // which otherwise reads as the app being stuck rather than a known,
      // expected wait.
      final isNjt = widget.station.agency == Agency.njtRail || widget.station.agency == Agency.njtBus;
      return AppLoader(
        message: isNjt ? 'Waking up the server — this can take up to a minute.' : null,
      );
    }

    if (directions.isEmpty) {
      return _messageList(
        Icons.info_outline_rounded,
        'No direction data',
        'This station has no direction data available.',
      );
    }

    return Column(
      children: [
        if (!result.isLive) _staleBanner(context),
        if (result.isLive && _refreshFailed) _refreshFailedBanner(context),
        Expanded(
          child: TabBarView(
            children: [
              for (final d in directions)
                _ArrivalsList(
                  agency: widget.station.agency,
                  arrivals: result.arrivalsByDirectionKey[d.key] ?? const [],
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _staleBanner(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColors.warning.withValues(alpha: 0.12),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          const Icon(Icons.schedule_rounded, size: 16, color: AppColors.warning),
          const SizedBox(width: AppSpacing.sm),
          const Expanded(
            child: Text(
              'Live data unavailable — showing the last known estimate.',
              style: TextStyle(color: AppColors.warning, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  /// Shown when a background refresh (the 30s poll or a manual
  /// pull-to-refresh) fails but we already have a good result on screen -
  /// distinct from [_staleBanner] (which reflects the feed itself reporting
  /// non-live data). Here the feed may well be fine; our attempt to reach it
  /// just failed, so we keep showing what we already had instead of
  /// blanking the screen with a hard error.
  Widget _refreshFailedBanner(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColors.warning.withValues(alpha: 0.12),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          const Icon(Icons.wifi_off_rounded, size: 16, color: AppColors.warning),
          const SizedBox(width: AppSpacing.sm),
          const Expanded(
            child: Text(
              "Couldn't refresh — showing the last update.",
              style: TextStyle(color: AppColors.warning, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _messageList(IconData icon, String title, String message) {
    return EmptyState(icon: icon, title: title, message: message);
  }

  /// Shown when the very first load fails outright (see [_lastGoodResult]/
  /// [_initialLoadError]'s docs) - unlike a background-refresh failure,
  /// there's no data on screen to fall back to, so this needs its own way
  /// forward rather than just waiting for the next 30s poll. Most likely
  /// cause for NJT rail/bus is the 60s cold-start timeout itself expiring
  /// (see NjtBusService/NjtRailService's docs) - retrying immediately after
  /// the backend has already started waking up from the first attempt
  /// should succeed much faster than waiting a fresh cold start out again.
  Widget _errorState() {
    return EmptyState(
      icon: Icons.wifi_off_rounded,
      title: 'Live data unavailable',
      message: '$_initialLoadError',
      action: OutlinedButton(
        onPressed: _refresh,
        child: const Text('Retry'),
      ),
    );
  }
}

/// The route/direction of whichever arrival was soonest across every
/// direction in [result] — a real, observed signal (not guessed) for
/// "what this user was actually shown" when the arrivals screen loaded,
/// logged as the trip's route_or_direction (see ArrivalsScreen) so it can
/// be used later to re-fetch arrivals for this exact station (e.g. the
/// commute notification job).
///
/// MTA needs a route ID here (its arrivals carry one per entry); PATH
/// needs a direction key instead (its arrivals don't distinguish routes
/// the same way) — see RecommendationCandidate's docs for the same split.
/// NJT rail/bus/LIRR need neither (a station code alone is enough to fetch
/// arrivals there), so this returns null for all three rather than logging
/// a value nothing will ever use.
String? soonestRouteOrDirectionForTripLog(Agency agency, TransitArrivalsResult result) {
  switch (agency) {
    case Agency.njtRail:
    case Agency.njtBus:
    case Agency.lirr:
      // A station code alone is enough to fetch LIRR arrivals (see
      // LirrService) - same reasoning as NJT rail/bus, no route/direction
      // filter needed the way MTA/PATH need one.
      return null;
    case Agency.path:
      String? soonestDirectionKey;
      DateTime? soonestTime;
      for (final entry in result.arrivalsByDirectionKey.entries) {
        for (final arrival in entry.value) {
          if (soonestTime == null || arrival.arrivalTime.isBefore(soonestTime)) {
            soonestTime = arrival.arrivalTime;
            soonestDirectionKey = entry.key;
          }
        }
      }
      return soonestDirectionKey;
    case Agency.mta:
      String? soonestRoute;
      DateTime? soonestTime;
      for (final arrivals in result.arrivalsByDirectionKey.values) {
        for (final arrival in arrivals) {
          if (soonestTime == null || arrival.arrivalTime.isBefore(soonestTime)) {
            soonestTime = arrival.arrivalTime;
            soonestRoute = arrival.routeLabel;
          }
        }
      }
      return soonestRoute;
  }
}

/// Groups [arrivals] by destination (headsign), alphabetically by
/// destination name — stable across refreshes, unlike first-seen order,
/// which could otherwise jitter the chip/section order every ~30s poll if
/// which destination happens to appear first in the feed changes. E.g. so
/// a direction serving both Newark and Hoboken (WTC's "To New Jersey") can
/// be shown as two clearly separated clusters instead of one interleaved
/// list. Returns null if grouping wouldn't help — fewer than 2 distinct
/// destinations, or no headsign data at all (MTA never provides one) —
/// so callers can fall back to the plain flat list unchanged.
Map<String, List<TransitArrival>>? groupArrivalsByDestination(
  List<TransitArrival> arrivals,
) {
  if (arrivals.any((a) => a.headSign == null)) return null;
  final byDestination = <String, List<TransitArrival>>{};
  for (final arrival in arrivals) {
    byDestination.putIfAbsent(arrival.headSign!, () => []).add(arrival);
  }
  if (byDestination.length <= 1) return null;
  final sortedKeys = byDestination.keys.toList()..sort();
  return {for (final key in sortedKeys) key: byDestination[key]!};
}

class _ArrivalsList extends StatefulWidget {
  const _ArrivalsList({required this.agency, required this.arrivals});

  final Agency agency;
  final List<TransitArrival> arrivals;

  @override
  State<_ArrivalsList> createState() => _ArrivalsListState();
}

class _ArrivalsListState extends State<_ArrivalsList> {
  /// null means "All destinations" — the filter chip row's default.
  String? _selectedDestination;

  @override
  Widget build(BuildContext context) {
    if (widget.arrivals.isEmpty) {
      return const EmptyState(
        icon: Icons.train_outlined,
        title: 'No upcoming arrivals found',
      );
    }

    final groups = groupArrivalsByDestination(widget.arrivals);
    if (groups == null) {
      return _FlatArrivalsList(agency: widget.agency, arrivals: widget.arrivals);
    }

    // Reset back to "All" if a previously-selected destination disappears
    // from the feed (e.g. the last Hoboken train of the night departs).
    if (_selectedDestination != null && !groups.containsKey(_selectedDestination)) {
      _selectedDestination = null;
    }

    final destinations = groups.keys.toList();
    final visibleGroups = _selectedDestination == null
        ? groups
        : {_selectedDestination!: groups[_selectedDestination]!};

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.md,
            AppSpacing.sm,
            AppSpacing.md,
            0,
          ),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _DestinationChip(
                  label: 'All',
                  selected: _selectedDestination == null,
                  onTap: () => setState(() => _selectedDestination = null),
                ),
                for (final destination in destinations) ...[
                  const SizedBox(width: 8),
                  _DestinationChip(
                    label: destination,
                    selected: _selectedDestination == destination,
                    onTap: () => setState(() => _selectedDestination = destination),
                  ),
                ],
              ],
            ),
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
            children: [
              for (final entry in visibleGroups.entries) ...[
                if (_selectedDestination == null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.md,
                      AppSpacing.md,
                      AppSpacing.md,
                      4,
                    ),
                    child: Text(
                      entry.key.toUpperCase(),
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                  ),
                for (final arrival in entry.value)
                  _ArrivalRow(agency: widget.agency, arrival: arrival),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _DestinationChip extends StatelessWidget {
  const _DestinationChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppColors.accent : AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          border: Border.all(
            color: selected ? AppColors.accent : AppColors.border,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: selected ? const Color(0xFF00201A) : AppColors.textPrimary,
          ),
        ),
      ),
    );
  }
}

class _FlatArrivalsList extends StatelessWidget {
  const _FlatArrivalsList({required this.agency, required this.arrivals});

  final Agency agency;
  final List<TransitArrival> arrivals;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      itemCount: arrivals.length,
      itemBuilder: (context, index) =>
          _ArrivalRow(agency: agency, arrival: arrivals[index]),
    );
  }
}

class _ArrivalRow extends StatelessWidget {
  const _ArrivalRow({required this.agency, required this.arrival});

  final Agency agency;
  final TransitArrival arrival;

  @override
  Widget build(BuildContext context) {
    final minutes = arrival.timeUntilArrival.inMinutes;
    final color = routeColor(
      agency: agency,
      routeLabel: arrival.routeLabel,
      routeColors: arrival.routeColors,
    );
    // Real line color drives text-on-color contrast decisions too -
    // MTA's yellow (N/Q/R/W) and light gray (L) both need dark text,
    // everything else here reads fine in white.
    final onColor = color.computeLuminance() > 0.5
        ? const Color(0xFF0B0E11)
        : Colors.white;
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: 6,
      ),
      child: AppCard(
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              alignment: Alignment.center,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              child: Text(
                arrival.routeLabel,
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: arrival.routeLabel.length > 2 ? 11 : 15,
                  color: onColor,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                softWrap: false,
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (arrival.headSign != null)
                    Text(
                      arrival.headSign!,
                      style: Theme.of(context).textTheme.bodyMedium,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  Text(
                    formatClockTime(arrival.arrivalTime),
                    style: Theme.of(context).textTheme.bodySmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            MinutesAway(minutes: minutes),
          ],
        ),
      ),
    );
  }
}
