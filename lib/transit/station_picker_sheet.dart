import 'package:flutter/material.dart';

import '../design/components.dart';
import '../design/theme.dart';
import 'station_group.dart';
import 'transit_models.dart';

/// Distinct from [agencyLabel] (used for the single-station arrivals app
/// bar badge) - "NJT" alone is fine there, but reads ambiguously next to
/// "NJT Bus" in this sheet's filter row, so rail gets its own clearer label
/// here specifically.
String _pickerAgencyLabel(Agency agency) => switch (agency) {
  Agency.mta => 'MTA',
  Agency.path => 'PATH',
  Agency.njtRail => 'NJT Rail',
  Agency.njtBus => 'NJT Bus',
};

/// Bottom sheet shown when a station name maps to more than one physical
/// station (e.g. several unconnected complexes, or several platforms of one
/// complex) — lets the user pick which specific one they mean.
///
/// At a large multi-agency hub (e.g. Journal Square: PATH + many NJT bus
/// routes + NJT rail), the flat list of every station sharing that name
/// can run into dozens of rows - grouped into per-agency sections with
/// filter chips (mirroring the arrivals screen's destination-filter
/// pattern) so a user looking for, say, just PATH doesn't have to scan past
/// every NJT bus route first.
Future<TransitStation?> showStationPicker(
  BuildContext context,
  StationGroup group,
) {
  final agencies = group.stations.map((s) => s.agency).toSet().toList()
    ..sort((a, b) => _pickerAgencyLabel(a).compareTo(_pickerAgencyLabel(b)));

  return showModalBottomSheet<TransitStation>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (context) {
      return _StationPickerContent(
        title: 'Which "${group.name}"?',
        stations: group.stations,
        agencies: agencies,
      );
    },
  );
}

class _StationPickerContent extends StatefulWidget {
  const _StationPickerContent({
    required this.title,
    required this.stations,
    required this.agencies,
  });

  final String title;
  final List<TransitStation> stations;
  final List<Agency> agencies;

  @override
  State<_StationPickerContent> createState() => _StationPickerContentState();
}

class _StationPickerContentState extends State<_StationPickerContent> {
  /// null means "All agencies" — the filter row's default. Only shown at
  /// all when the group actually spans more than one agency; a single-
  /// agency collision (e.g. four unrelated MTA "23 St"s) has nothing to
  /// filter by agency, so the chip row would just be noise.
  Agency? _selectedAgency;

  @override
  Widget build(BuildContext context) {
    final showAgencyFilter = widget.agencies.length > 1;
    final visibleStations = _selectedAgency == null
        ? widget.stations
        : widget.stations.where((s) => s.agency == _selectedAgency).toList();

    // Grouped by agency (in the same stable order as the filter chips) so
    // stations of the same mode cluster together even with "All" selected,
    // rather than interleaving in whatever order the group happened to be
    // built in.
    final byAgency = <Agency, List<TransitStation>>{};
    for (final agency in widget.agencies) {
      final stations = visibleStations.where((s) => s.agency == agency).toList();
      if (stations.isNotEmpty) byAgency[agency] = stations;
    }

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
                widget.title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
          ),
          if (showAgencyFilter)
            SizedBox(
              height: 40,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                children: [
                  _AgencyFilterChip(
                    label: 'All',
                    selected: _selectedAgency == null,
                    onTap: () => setState(() => _selectedAgency = null),
                  ),
                  const SizedBox(width: 6),
                  for (final agency in widget.agencies) ...[
                    _AgencyFilterChip(
                      label: _pickerAgencyLabel(agency),
                      color: agencyColor(agency),
                      selected: _selectedAgency == agency,
                      onTap: () => setState(() => _selectedAgency = agency),
                    ),
                    const SizedBox(width: 6),
                  ],
                ],
              ),
            ),
          if (showAgencyFilter) const SizedBox(height: AppSpacing.sm),
          Flexible(
            child: ListView(
              shrinkWrap: true,
              children: [
                for (final entry in byAgency.entries) ...[
                  if (showAgencyFilter && _selectedAgency == null)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.md,
                        AppSpacing.sm,
                        AppSpacing.md,
                        4,
                      ),
                      child: Text(
                        _pickerAgencyLabel(entry.key),
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: AppColors.textTertiary,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  for (final station in entry.value)
                    _StationRow(station: station),
                ],
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
        ],
      ),
    );
  }
}

class _AgencyFilterChip extends StatelessWidget {
  const _AgencyFilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
    this.color,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final chipColor = color ?? AppColors.accent;
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: chipColor.withValues(alpha: 0.24),
      backgroundColor: AppColors.surfaceRaised,
      side: BorderSide(color: selected ? chipColor : AppColors.border),
      labelStyle: TextStyle(
        color: selected ? chipColor : AppColors.textSecondary,
        fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
      ),
    );
  }
}

class _StationRow extends StatelessWidget {
  const _StationRow({required this.station});

  final TransitStation station;

  @override
  Widget build(BuildContext context) {
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
                                RouteChip(agency: station.agency, label: route),
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
  }
}
