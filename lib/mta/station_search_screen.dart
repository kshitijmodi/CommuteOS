import 'package:flutter/material.dart';

import 'arrivals_screen.dart';
import 'mta_station.dart';
import 'mta_station_repository.dart';

/// Home screen: search/browse every NYC subway station, tap one for its
/// live arrivals.
class StationSearchScreen extends StatefulWidget {
  const StationSearchScreen({super.key});

  @override
  State<StationSearchScreen> createState() => _StationSearchScreenState();
}

class _StationSearchScreenState extends State<StationSearchScreen> {
  final _repository = MtaStationRepository();
  final _searchController = TextEditingController();
  late Future<List<MtaStation>> _stationsFuture;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _stationsFuture = _repository.loadStations();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CommuteOS'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(56),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                hintText: 'Search stations…',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
                isDense: true,
                filled: true,
              ),
              onChanged: (value) => setState(() => _query = value),
            ),
          ),
        ),
      ),
      body: FutureBuilder<List<MtaStation>>(
        future: _stationsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text('Failed to load stations:\n${snapshot.error}'),
              ),
            );
          }

          final stations = snapshot.data ?? const <MtaStation>[];
          final query = _query.trim().toLowerCase();
          final filtered = query.isEmpty
              ? stations
              : stations
                    .where((s) => s.name.toLowerCase().contains(query))
                    .toList();

          if (filtered.isEmpty) {
            return const Center(child: Text('No stations match your search.'));
          }

          return ListView.separated(
            itemCount: filtered.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final station = filtered[index];
              return ListTile(
                title: Text(station.name),
                subtitle: Text('${station.borough} · ${station.routes.join(" ")}'),
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => ArrivalsScreen(station: station),
                    ),
                  );
                },
              );
            },
          );
        },
      ),
    );
  }
}
