import 'dart:async';

import 'package:flutter/material.dart';

import 'mta_arrival.dart';
import 'mta_feed.dart';
import 'mta_service.dart';

/// Shows live arrivals for a single hardcoded stop, refreshed periodically.
///
/// MTA refreshes feed data roughly every 30s server-side; polling faster
/// than that just re-fetches the same snapshot.
class ArrivalsScreen extends StatefulWidget {
  const ArrivalsScreen({
    super.key,
    required this.title,
    required this.feed,
    required this.stopId,
  });

  final String title;
  final MtaFeed feed;
  final String stopId;

  @override
  State<ArrivalsScreen> createState() => _ArrivalsScreenState();
}

class _ArrivalsScreenState extends State<ArrivalsScreen> {
  final _service = MtaService();
  Timer? _timer;
  Future<List<MtaArrival>>? _future;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _refresh());
  }

  void _refresh() {
    setState(() {
      _future = _service.getArrivalsForStop(widget.feed, widget.stopId);
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
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: RefreshIndicator(
        onRefresh: () async => _refresh(),
        child: FutureBuilder<List<MtaArrival>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(
                children: [
                  Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      'Live data unavailable:\n${snapshot.error}',
                      textAlign: TextAlign.center,
                    ),
                  ),
                ],
              );
            }

            final arrivals = snapshot.data ?? const <MtaArrival>[];
            if (arrivals.isEmpty) {
              return ListView(
                children: const [
                  Padding(
                    padding: EdgeInsets.all(24),
                    child: Text(
                      'No upcoming arrivals found for this stop.',
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
                  title: Text(
                    minutes <= 0 ? 'Arriving now' : '$minutes min',
                  ),
                  subtitle: Text(
                    '${arrival.arrivalTime.hour.toString().padLeft(2, '0')}:'
                    '${arrival.arrivalTime.minute.toString().padLeft(2, '0')}',
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
