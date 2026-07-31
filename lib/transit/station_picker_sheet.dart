import 'package:flutter/material.dart';

import '../design/components.dart';
import '../design/theme.dart';
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
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                0,
                AppSpacing.md,
                AppSpacing.sm,
              ),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Which "${group.name}"?',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: group.stations.length,
                itemBuilder: (context, index) {
                  final station = group.stations[index];
                  return Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: () => Navigator.of(context).pop(station),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.md,
                          vertical: 12,
                        ),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Wrap(
                                    spacing: 6,
                                    runSpacing: 6,
                                    children: station.agency == Agency.path
                                        ? [RouteChip(agency: Agency.path, label: 'PATH')]
                                        : [
                                            for (final route in station.routes)
                                              RouteChip(agency: Agency.mta, label: route),
                                          ],
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    station.area,
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                            const Icon(
                              Icons.chevron_right_rounded,
                              color: AppColors.textTertiary,
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
          ],
        ),
      );
    },
  );
}
