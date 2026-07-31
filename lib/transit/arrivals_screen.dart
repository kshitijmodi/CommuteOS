import 'dart:async';

import 'package:flutter/material.dart';

import '../account/trip_logger.dart';
import '../design/components.dart';
import '../design/theme.dart';
import '../mta/mta_service.dart';
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
  };
  final _tripLogger = TripLogger();
  Timer? _timer;
  Future<TransitArrivalsResult>? _future;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _refresh());
    // Fire-and-forget: a no-op for logged-out users (the common case today
    // - see OPEN_QUESTIONS.md on auth being opt-in, not required to browse).
    _tripLogger.logStationView(
      mode: widget.station.agency.name,
      originStop: widget.station.id,
    );
  }

  void _refresh() {
    setState(() {
      _future = _service.getArrivals(widget.station);
    });
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
          child: FutureBuilder<TransitArrivalsResult>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const AppLoader();
              }
              if (snapshot.hasError) {
                return _messageList(
                  Icons.wifi_off_rounded,
                  'Live data unavailable',
                  '${snapshot.error}',
                );
              }
              if (directions.isEmpty) {
                return _messageList(
                  Icons.info_outline_rounded,
                  'No direction data',
                  'This station has no direction data available.',
                );
              }

              final result = snapshot.data!;
              return Column(
                children: [
                  if (!result.isLive) _staleBanner(context),
                  Expanded(
                    child: TabBarView(
                      children: [
                        for (final d in directions)
                          _ArrivalsList(
                            agency: widget.station.agency,
                            arrivals:
                                result.arrivalsByDirectionKey[d.key] ??
                                const [],
                          ),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
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

  Widget _messageList(IconData icon, String title, String message) {
    return EmptyState(icon: icon, title: title, message: message);
  }
}

class _ArrivalsList extends StatelessWidget {
  const _ArrivalsList({required this.agency, required this.arrivals});

  final Agency agency;
  final List<TransitArrival> arrivals;

  @override
  Widget build(BuildContext context) {
    if (arrivals.isEmpty) {
      return const EmptyState(
        icon: Icons.train_outlined,
        title: 'No upcoming arrivals found',
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      itemCount: arrivals.length,
      itemBuilder: (context, index) {
        final arrival = arrivals[index];
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
                  child: Text(
                    arrival.headSign ??
                        '${arrival.arrivalTime.hour.toString().padLeft(2, '0')}:'
                            '${arrival.arrivalTime.minute.toString().padLeft(2, '0')}',
                    style: Theme.of(context).textTheme.bodyMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                MinutesAway(minutes: minutes),
              ],
            ),
          ),
        );
      },
    );
  }
}
