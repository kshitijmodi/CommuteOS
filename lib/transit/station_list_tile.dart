import 'package:flutter/material.dart';

import '../design/components.dart';
import '../design/theme.dart';
import 'arrivals_screen.dart';
import 'station_group.dart';
import 'station_picker_sheet.dart';
import 'transit_models.dart';

/// A station-name row with a favorite-toggle star, used by both the search
/// screen and the favorites screen so favoriting behaves identically
/// wherever it's tapped.
///
/// [group] may contain more than one physical station sharing this name
/// (e.g. two unconnected stations both called "86 St", or several
/// platforms of one connected complex) — tapping the row then shows a
/// picker instead of navigating straight to arrivals.
///
/// [isStationFavorite] and [onStationFavoriteToggle] operate per-station,
/// not per name: for a multi-station group, the star reflects whether ANY
/// station in the group is favorited, but the actual favorite/unfavorite
/// action always applies to the specific station the user picks.
class StationListTile extends StatelessWidget {
  const StationListTile({
    super.key,
    required this.group,
    required this.isStationFavorite,
    required this.onStationFavoriteToggle,
  });

  final StationGroup group;
  final bool Function(TransitStation station) isStationFavorite;
  final void Function(TransitStation station, bool isFavorite)
  onStationFavoriteToggle;

  Future<void> _open(BuildContext context) async {
    TransitStation? station = group.hasSingleStation
        ? group.stations.first
        : null;
    station ??= await showStationPicker(context, group);
    if (station == null || !context.mounted) return;

    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ArrivalsScreen(station: station!)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isFavorite = group.stations.any(isStationFavorite);
    final agencies = group.hasSingleStation
        ? [group.stations.first.agency]
        : group.stations.map((s) => s.agency).toSet().toList();
    final subtitle = group.hasSingleStation
        ? '${group.stations.first.area} · ${group.stations.first.routes.join(" ")}'
        : '${group.stations.length} stations · ${group.allRoutes.join(" ")}';

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _open(context),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: 12,
          ),
          child: Row(
            children: [
              for (final agency in agencies) ...[
                AppBadge(agencyLabel(agency), color: agencyColor(agency), dense: true),
                const SizedBox(width: 6),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      group.name,
                      style: Theme.of(context).textTheme.bodyLarge,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: Icon(
                  isFavorite ? Icons.star_rounded : Icons.star_border_rounded,
                ),
                color: isFavorite ? AppColors.accent : AppColors.textTertiary,
                tooltip: isFavorite ? 'Remove from favorites' : 'Add to favorites',
                onPressed: () async {
                  if (group.hasSingleStation) {
                    final station = group.stations.first;
                    onStationFavoriteToggle(station, !isStationFavorite(station));
                    return;
                  }
                  final picked = await showStationPicker(context, group);
                  if (picked != null) {
                    onStationFavoriteToggle(picked, !isStationFavorite(picked));
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
