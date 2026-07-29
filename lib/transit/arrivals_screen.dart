import 'dart:async';

import 'package:flutter/material.dart';

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
  Timer? _timer;
  Future<TransitArrivalsResult>? _future;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _refresh());
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
          title: Text(widget.station.name),
          bottom: directions.isEmpty
              ? null
              : TabBar(
                  tabs: [for (final d in directions) Tab(text: d.label)],
                ),
        ),
        body: RefreshIndicator(
          onRefresh: () async => _refresh(),
          child: FutureBuilder<TransitArrivalsResult>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return _messageList(
                  'Live data unavailable:\n${snapshot.error}',
                );
              }
              if (directions.isEmpty) {
                return _messageList('No direction data for this station.');
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
      color: Theme.of(context).colorScheme.errorContainer,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        'Live data unavailable — showing the last known estimate.',
        style: TextStyle(
          color: Theme.of(context).colorScheme.onErrorContainer,
        ),
      ),
    );
  }

  Widget _messageList(String message) {
    return ListView(
      children: [
        Padding(
          padding: const EdgeInsets.all(24),
          child: Text(message, textAlign: TextAlign.center),
        ),
      ],
    );
  }
}

class _ArrivalsList extends StatelessWidget {
  const _ArrivalsList({required this.arrivals});

  final List<TransitArrival> arrivals;

  @override
  Widget build(BuildContext context) {
    if (arrivals.isEmpty) {
      return ListView(
        children: const [
          Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'No upcoming arrivals found.',
              textAlign: TextAlign.center,
            ),
          ),
        ],
      );
    }

    return ListView.separated(
      itemCount: arrivals.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final arrival = arrivals[index];
        final minutes = arrival.timeUntilArrival.inMinutes;
        return ListTile(
          leading: CircleAvatar(
            child: Text(
              arrival.routeLabel,
              style: TextStyle(
                fontSize: arrival.routeLabel.length > 2 ? 11 : null,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              softWrap: false,
            ),
          ),
          title: Text(minutes <= 0 ? 'Arriving now' : '$minutes min'),
          subtitle: Text(
            arrival.headSign ??
                '${arrival.arrivalTime.hour.toString().padLeft(2, '0')}:'
                    '${arrival.arrivalTime.minute.toString().padLeft(2, '0')}',
          ),
        );
      },
    );
  }
}
