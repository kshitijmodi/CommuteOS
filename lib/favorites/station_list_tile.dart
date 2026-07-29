import 'package:flutter/material.dart';

import '../mta/arrivals_screen.dart';
import '../mta/mta_station.dart';
import '../mta/station_group.dart';
import '../mta/station_picker_sheet.dart';

/// A station-name row with a favorite-toggle star, used by both the search
/// screen and the favorites screen so favoriting behaves identically
/// wherever it's tapped.
///
/// [group] may contain more than one physical station sharing this name
/// (e.g. two unconnected stations both called "86 St", or several
/// platforms of one connected complex) — tapping the row then shows a
/// picker instead of navigating straight to arrivals.
///
/// [isFavorite] and [onFavoriteToggle] operate per-[MtaStation], not per
/// name: for a multi-station group, the star reflects (and toggles) the
/// first station in the group for display purposes here, but the actual
/// favorite/unfavorite action always applies to the station the user
/// picks — see [onStationFavoriteToggle].
class StationListTile extends StatelessWidget {
  const StationListTile({
    super.key,
    required this.group,
    required this.isStationFavorite,
    required this.onStationFavoriteToggle,
  });

  final StationGroup group;
  final bool Function(MtaStation station) isStationFavorite;
  final void Function(MtaStation station, bool isFavorite)
  onStationFavoriteToggle;

  Future<void> _open(BuildContext context) async {
    MtaStation? station = group.hasSingleStation ? group.stations.first : null;
    station ??= await showStationPicker(context, group);
    if (station == null || !context.mounted) return;

    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ArrivalsScreen(station: station!)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final subtitle = group.hasSingleStation
        ? '${group.stations.first.borough} · ${group.stations.first.routes.join(" ")}'
        : '${group.stations.length} stations · ${group.allRoutes.join(" ")}';

    final isFavorite = group.stations.any(isStationFavorite);

    return ListTile(
      title: Text(group.name),
      subtitle: Text(subtitle),
      trailing: IconButton(
        icon: Icon(isFavorite ? Icons.star : Icons.star_border),
        color: isFavorite ? Colors.amber[700] : null,
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
      onTap: () => _open(context),
    );
  }
}
