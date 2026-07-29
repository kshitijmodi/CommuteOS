import 'package:flutter/material.dart';

import '../mta/arrivals_screen.dart';
import '../mta/mta_station.dart';

/// A station row with a favorite-toggle star, used by both the search
/// screen and the favorites screen so favoriting behaves identically
/// wherever it's tapped.
class StationListTile extends StatelessWidget {
  const StationListTile({
    super.key,
    required this.station,
    required this.isFavorite,
    required this.onFavoriteToggle,
  });

  final MtaStation station;
  final bool isFavorite;
  final ValueChanged<bool> onFavoriteToggle;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(station.name),
      subtitle: Text('${station.borough} · ${station.routes.join(" ")}'),
      trailing: IconButton(
        icon: Icon(isFavorite ? Icons.star : Icons.star_border),
        color: isFavorite ? Colors.amber[700] : null,
        tooltip: isFavorite ? 'Remove from favorites' : 'Add to favorites',
        onPressed: () => onFavoriteToggle(!isFavorite),
      ),
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => ArrivalsScreen(station: station)),
        );
      },
    );
  }
}
