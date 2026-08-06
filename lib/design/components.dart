import 'package:flutter/material.dart';

import '../transit/transit_models.dart';
import 'theme.dart';

/// Per-agency accent used for small identifying badges (e.g. next to a
/// station name) — distinct from the app's single accent color, which is
/// reserved for live data/primary actions so agency color-coding doesn't
/// compete with it.
Color agencyColor(Agency agency) => switch (agency) {
  Agency.mta => const Color(0xFF5B8DEF),
  Agency.path => const Color(0xFFE8794D),
  Agency.njtRail => const Color(0xFF9B5DE0),
  Agency.njtBus => const Color(0xFF5DBE8A),
  // LIRR has no single official "brand color" the way subway lines do -
  // this is a deep indigo/navy distinct from the other four agencies'
  // colors, in the same family MTA's own LIRR signage/marketing uses.
  Agency.lirr => const Color(0xFF3D4B94),
};

String agencyLabel(Agency agency) => switch (agency) {
  Agency.mta => 'MTA',
  Agency.path => 'PATH',
  Agency.njtRail => 'NJT',
  Agency.njtBus => 'NJT Bus',
  Agency.lirr => 'LIRR',
};

/// Distinct from [agencyLabel] - "NJT" alone is fine for a single-agency
/// badge (e.g. the arrivals app bar), but reads ambiguously next to "NJT
/// Bus" in a filter row that shows both at once, so rail gets its own
/// clearer label here. Shared by the station search screen's and the
/// station picker sheet's agency filter chips.
String agencyFilterLabel(Agency agency) => switch (agency) {
  Agency.mta => 'MTA',
  Agency.path => 'PATH',
  Agency.njtRail => 'NJT Rail',
  Agency.njtBus => 'NJT Bus',
  Agency.lirr => 'LIRR',
};

/// Formats an arrival's absolute time as 12-hour clock time, e.g. "5:24 PM".
/// Shown as a secondary detail alongside the "N min" countdown per user
/// feedback that a relative-only countdown wasn't enough — a real station
/// clock/Google Maps both show the actual time too, not just minutes-away.
///
/// Always converts to local time first - NJT rail/bus arrivals arrive here
/// as UTC-flagged DateTimes (parsed from the backend's ISO timestamps),
/// and reading .hour/.minute off a UTC value directly displays the raw UTC
/// wall-clock time instead of the device's real local time (off by the
/// UTC/Eastern offset, ~4-5h) - a real bug that shipped because the "N min"
/// countdown next to it (a timezone-agnostic instant difference) looked
/// correct, masking that this label didn't. MTA/PATH build already-local
/// DateTimes, so .toLocal() is a no-op for them - safe to call
/// unconditionally here rather than relying on every call site to remember.
String formatClockTime(DateTime time) {
  final local = time.toLocal();
  final hour12 = local.hour % 12 == 0 ? 12 : local.hour % 12;
  final minute = local.minute.toString().padLeft(2, '0');
  final period = local.hour < 12 ? 'AM' : 'PM';
  return '$hour12:$minute $period';
}

/// NYCT's own published subway line colors (from their brand guidelines /
/// GTFS `routes.txt` route_color field), keyed by route ID. MTA's GTFS-RT
/// feed doesn't carry color data itself, so this is a small, hardcoded
/// lookup rather than something parsed at runtime — the official set is
/// fixed and essentially never changes.
const Map<String, Color> _mtaRouteColors = {
  '1': Color(0xFFEE352E), '2': Color(0xFFEE352E), '3': Color(0xFFEE352E),
  '4': Color(0xFF00933C), '5': Color(0xFF00933C), '6': Color(0xFF00933C),
  '6X': Color(0xFF00933C),
  '7': Color(0xFFB933AD), '7X': Color(0xFFB933AD),
  'A': Color(0xFF0039A6), 'C': Color(0xFF0039A6), 'E': Color(0xFF0039A6),
  'B': Color(0xFFFF6319), 'D': Color(0xFFFF6319), 'F': Color(0xFFFF6319),
  'FX': Color(0xFFFF6319), 'M': Color(0xFFFF6319),
  'G': Color(0xFF6CBE45),
  'J': Color(0xFF996633), 'Z': Color(0xFF996633),
  'L': Color(0xFFA7A9AC),
  'N': Color(0xFFFCCC0A), 'Q': Color(0xFFFCCC0A), 'R': Color(0xFFFCCC0A),
  'W': Color(0xFFFCCC0A),
  'S': Color(0xFF808183), 'GS': Color(0xFF808183), 'FS': Color(0xFF808183),
  'H': Color(0xFF808183),
  'SI': Color(0xFF0039A6),
};

/// NJ Transit's own published rail line colors (from their static GTFS
/// feed's routes.txt route_color field - see
/// backend/scripts/build_njt_rail_stations.py), keyed by route_short_name.
/// NJT's real-time API reports a train's line as a LINECODE (e.g. "NE")
/// that matches route_short_name in some cases but not others (e.g. the
/// live feed's "AM"/Amtrak trains aren't in NJT's own GTFS at all, since
/// they're a different agency sharing NJT's tracks/stations) - falls back
/// to the agency color for anything unrecognized, same pattern as MTA.
const Map<String, Color> _njtRailLineColors = {
  'ACRL': Color(0xFF075AAA),
  'MNBTN': Color(0xFFE66859),
  'BERG': Color(0xFFFFD411),
  'MAIN': Color(0xFFFFD411),
  'MNE': Color(0xFF08A652),
  'MNEG': Color(0xFFA4C9AA),
  'NEC': Color(0xFFDD3439),
  'NJCL': Color(0xFF03A3DF),
  'PASC': Color(0xFF94219A),
  'PRIN': Color(0xFFE87725),
  'RARV': Color(0xFFF2A537),
  'MRL': Color(0xFFC1AA72),
};

/// The MTA's own published LIRR branch colors (from LIRR's static GTFS
/// feed's routes.txt route_color field - see
/// backend/scripts/build_lirr_stations.py), keyed by the branch's full
/// name (route_long_name, e.g. "Babylon Branch") since LIRR's real-time
/// feed identifies a trip's route the same way the static feed does (no
/// separate short-code system the way NJT rail's LINECODE is).
const Map<String, Color> _lirrBranchColors = {
  'Babylon Branch': Color(0xFF00985F),
  'Hempstead Branch': Color(0xFFCE8E00),
  'Oyster Bay Branch': Color(0xFF00AF3F),
  'Ronkonkoma Branch': Color(0xFFA626AA),
  'Montauk Branch': Color(0xFF00B2A9),
  'Long Beach Branch': Color(0xFFFF6319),
  'Far Rockaway Branch': Color(0xFF6E3219),
  'West Hempstead Branch': Color(0xFF00A1DE),
  'Port Washington Branch': Color(0xFFC60C30),
  'Port Jefferson Branch': Color(0xFF006EC7),
  'Belmont Park': Color(0xFF60269E),
  'City Terminal Zone': Color(0xFF4D5357),
  'Greenport Service': Color(0xFFA626AA),
};

/// A route's real display color: NYCT's published color for an MTA route
/// ID, the feed-provided hex color(s) for a PATH arrival, NJT's published
/// rail line color, or LIRR's published branch color. Falls back to the
/// agency's generic badge color if no real color is known (e.g. an
/// unrecognized MTA route ID, a PATH arrival missing/malformed lineColor
/// data, or an NJT LINECODE this table doesn't have - like Amtrak trains
/// sharing NJT's tracks).
Color routeColor({
  required Agency agency,
  required String routeLabel,
  List<String> routeColors = const [],
}) {
  if (agency == Agency.path && routeColors.isNotEmpty) {
    final hex = routeColors.first;
    return Color(int.parse('FF$hex', radix: 16));
  }
  if (agency == Agency.njtRail) {
    return _njtRailLineColors[routeLabel] ?? agencyColor(agency);
  }
  if (agency == Agency.lirr) {
    return _lirrBranchColors[routeLabel] ?? agencyColor(agency);
  }
  return _mtaRouteColors[routeLabel] ?? agencyColor(agency);
}

/// Shared visual building blocks used across screens, so the app reads as
/// one considered product rather than each screen inventing its own row/
/// card/empty-state style.

/// A small rounded label, e.g. a route badge ("A", "PATH") or a status pill
/// ("LIVE", "STALE"). [filled] uses the accent as a solid background
/// (for the strongest emphasis, like a live badge); otherwise it's an
/// outlined chip on the surface color.
class AppBadge extends StatelessWidget {
  const AppBadge(
    this.label, {
    super.key,
    this.color,
    this.filled = false,
    this.dense = false,
  });

  final String label;
  final Color? color;
  final bool filled;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final tint = color ?? AppColors.accent;
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: dense ? 8 : 10,
        vertical: dense ? 3 : 5,
      ),
      decoration: BoxDecoration(
        color: filled ? tint : tint.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        softWrap: false,
        style: TextStyle(
          fontSize: dense ? 10 : 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.3,
          color: filled ? const Color(0xFF00201A) : tint,
        ),
      ),
    );
  }
}

/// A small filled circle showing a route's real line color with its ID
/// inside — e.g. a green "4" or a yellow "N" — matching how the route
/// actually appears on real station signage/maps, not a generic agency
/// color. Used anywhere a station's routes are listed (search/favorites
/// rows), as opposed to [routeColor] applied to a single live arrival.
class RouteChip extends StatelessWidget {
  const RouteChip({super.key, required this.agency, required this.label});

  final Agency agency;
  final String label;

  @override
  Widget build(BuildContext context) {
    if (agency == Agency.path) {
      return AppBadge('PATH', color: agencyColor(agency), dense: true);
    }
    final color = routeColor(agency: agency, routeLabel: label);
    final onColor = color.computeLuminance() > 0.5
        ? const Color(0xFF0B0E11)
        : Colors.white;
    return Container(
      width: 22,
      height: 22,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        softWrap: false,
        style: TextStyle(
          fontSize: label.length > 2 ? 8 : 10,
          fontWeight: FontWeight.w700,
          color: onColor,
        ),
      ),
    );
  }
}

/// A tappable chip for filtering a list by agency/mode - "All" plus one
/// per agency. Shared by the station search screen and the multi-agency
/// station picker sheet, so both filter UIs look and behave identically.
class AgencyFilterChip extends StatelessWidget {
  const AgencyFilterChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
    this.color,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  /// Null for the "All" chip, which uses the app's single accent color
  /// rather than any one agency's.
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final chipColor = color ?? AppColors.accent;
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
      showCheckmark: false,
      selectedColor: chipColor,
      backgroundColor: AppColors.surfaceRaised,
      side: BorderSide(color: selected ? chipColor : AppColors.border),
      labelStyle: TextStyle(
        fontSize: 11,
        color: selected ? Colors.white : AppColors.textSecondary,
        fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
      ),
      labelPadding: const EdgeInsets.symmetric(horizontal: 2),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      visualDensity: VisualDensity.compact,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }
}

/// A pulsing-dot "LIVE" indicator vs. a plain "STALE" pill, used anywhere
/// the app shows real-time-vs-cached data (arrivals, recommendations).
class LiveStatusPill extends StatelessWidget {
  const LiveStatusPill({super.key, required this.isLive});

  final bool isLive;

  @override
  Widget build(BuildContext context) {
    if (!isLive) {
      return const AppBadge('STALE', color: AppColors.warning, dense: true);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.accent.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: const BoxDecoration(
              color: AppColors.accent,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          const Text(
            'LIVE',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.3,
              color: AppColors.accent,
            ),
          ),
        ],
      ),
    );
  }
}

/// A section label above a group of content, e.g. "FAVORITES" or "ACCOUNT".
class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.trailing});

  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.lg,
        AppSpacing.md,
        AppSpacing.sm,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(title.toUpperCase(), style: Theme.of(context).textTheme.titleSmall),
          ?trailing,
        ],
      ),
    );
  }
}

/// A full-bleed empty state: icon, message, optional CTA. Used whenever a
/// list has nothing to show yet (no favorites, no results, not enough data).
class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.action,
  });

  final IconData icon;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: AppColors.surface,
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.border),
              ),
              child: Icon(icon, size: 28, color: AppColors.textSecondary),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              title,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (message != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                message!,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
            if (action != null) ...[
              const SizedBox(height: AppSpacing.lg),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}

/// A raised, bordered container used for cards throughout the app (favorite
/// rows, arrival rows, recommendation results) — consistent radius/border/
/// padding instead of each screen picking its own.
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.md),
    this.onTap,
    this.margin,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry? margin;

  @override
  Widget build(BuildContext context) {
    final content = Container(
      margin: margin,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: AppColors.border),
      ),
      child: onTap == null
          ? Padding(padding: padding, child: child)
          : Material(
              color: Colors.transparent,
              borderRadius: BorderRadius.circular(AppRadius.md),
              child: InkWell(
                onTap: onTap,
                borderRadius: BorderRadius.circular(AppRadius.md),
                child: Padding(padding: padding, child: child),
              ),
            ),
    );
    return content;
  }
}

/// A large, glanceable "N min" readout for an arrival — the single most
/// important number on the arrivals screen, so it gets its own component
/// rather than being just another ListTile title.
class MinutesAway extends StatelessWidget {
  const MinutesAway({super.key, required this.minutes});

  final int minutes;

  @override
  Widget build(BuildContext context) {
    if (minutes <= 0) {
      return const Text(
        'NOW',
        style: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w800,
          color: AppColors.accent,
          letterSpacing: 0.2,
        ),
      );
    }
    return RichText(
      text: TextSpan(
        children: [
          TextSpan(
            text: '$minutes',
            style: const TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
              height: 1,
            ),
          ),
          const TextSpan(
            text: ' min',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }
}

/// Centered loading indicator with consistent sizing/color, used in place
/// of a bare CircularProgressIndicator so every screen's loading state
/// looks identical.
class AppLoader extends StatelessWidget {
  const AppLoader({super.key, this.message});

  /// Optional caption shown below the spinner - e.g. explaining a load
  /// that's expected to take unusually long (NJT rail/bus's Render backend
  /// cold-starting after being idle), so a slow load reads as expected
  /// rather than the app looking stuck or broken.
  final String? message;

  @override
  Widget build(BuildContext context) {
    final message = this.message;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 28,
            height: 28,
            child: CircularProgressIndicator(strokeWidth: 2.5),
          ),
          if (message != null) ...[
            const SizedBox(height: AppSpacing.md),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
              child: Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
