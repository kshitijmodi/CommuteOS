import 'package:flutter/material.dart';

import 'station_group.dart';
import 'transit_models.dart';

/// Bottom sheet shown when a station name maps to more than one physical
/// station (e.g. several unconnected complexes, or several platforms of one
/// complex) — lets the user pick which specific one they mean.
Future<TransitStation?> showStationPicker(
  BuildContext context,
  StationGroup group,
) {
  return showModalBottomSheet<TransitStation>(
    context: context,
    showDragHandle: true,
    builder: (context) {
      return SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text(
                'Which "${group.name}"?',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Flexible(
              child: ListView.separated(
                shrinkWrap: true,
                itemCount: group.stations.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final station = group.stations[index];
                  return ListTile(
                    title: Text(station.routes.join(' ')),
                    subtitle: Text(station.area),
                    onTap: () => Navigator.of(context).pop(station),
                  );
                },
              ),
            ),
          ],
        ),
      );
    },
  );
}
