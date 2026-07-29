import 'dart:async';

import 'package:flutter/material.dart';

import 'mta_arrival.dart';
import 'mta_service.dart';
import 'mta_station.dart';

/// Shows live arrivals for a station, split into north/south tabs.
///
/// MTA refreshes feed data roughly every 30s server-side; polling faster
/// than that just re-fetches the same snapshot.
class ArrivalsScreen extends StatefulWidget {
  const ArrivalsScreen({super.key, required this.station});

  final MtaStation station;

  @override
  State<ArrivalsScreen> createState() => _ArrivalsScreenState();
}

class _ArrivalsScreenState extends State<ArrivalsScreen> {
  final _service = MtaService();
  Timer? _timer;
  Future<Map<String, List<MtaArrival>>>? _future;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _refresh());
  }

  void _refresh() {
    setState(() {
      _future = _service.getArrivalsForStation(widget.station);
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
    final station = widget.station;
    final hasNorth = station.northLabel.isNotEmpty;
    final hasSouth = station.southLabel.isNotEmpty;
    final tabs = [
      if (hasNorth) (label: station.northLabel, stopId: station.northStopId),
      if (hasSouth) (label: station.southLabel, stopId: station.southStopId),
    ];

    return DefaultTabController(
      length: tabs.isEmpty ? 1 : tabs.length,
      child: Scaffold(
        appBar: AppBar(
          title: Text(station.name),
          bottom: tabs.isEmpty
              ? null
              : TabBar(tabs: [for (final t in tabs) Tab(text: t.label)]),
        ),
        body: RefreshIndicator(
          onRefresh: () async => _refresh(),
          child: FutureBuilder<Map<String, List<MtaArrival>>>(
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
              if (tabs.isEmpty) {
                return _messageList('No direction data for this station.');
              }

              final byDirection = snapshot.data ?? const {};
              return TabBarView(
                children: [
                  for (final t in tabs)
                    _ArrivalsList(
                      arrivals: byDirection[t.stopId] ?? const [],
                    ),
                ],
              );
            },
          ),
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

  final List<MtaArrival> arrivals;

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
          leading: CircleAvatar(child: Text(arrival.routeId)),
          title: Text(minutes <= 0 ? 'Arriving now' : '$minutes min'),
          subtitle: Text(
            '${arrival.arrivalTime.hour.toString().padLeft(2, '0')}:'
            '${arrival.arrivalTime.minute.toString().padLeft(2, '0')}',
          ),
        );
      },
    );
  }
}
