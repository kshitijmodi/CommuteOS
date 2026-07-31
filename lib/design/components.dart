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
};

String agencyLabel(Agency agency) => switch (agency) {
  Agency.mta => 'MTA',
  Agency.path => 'PATH',
};

/// Formats an arrival's absolute time as 12-hour clock time, e.g. "5:24 PM".
/// Shown as a secondary detail alongside the "N min" countdown per user
/// feedback that a relative-only countdown wasn't enough — a real station
/// clock/Google Maps both show the actual time too, not just minutes-away.
String formatClockTime(DateTime time) {
  final hour12 = time.hour % 12 == 0 ? 12 : time.hour % 12;
  final minute = time.minute.toString().padLeft(2, '0');
  final period = time.hour < 12 ? 'AM' : 'PM';
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

/// A route's real display color: NYCT's published color for an MTA route
/// ID, or the feed-provided hex color(s) for a PATH arrival. Falls back to
/// the agency's generic badge color if no real color is known (e.g. an
/// MTA route ID this table doesn't recognize yet, or a PATH arrival
/// missing/malformed lineColor data).
Color routeColor({
  required Agency agency,
  required String routeLabel,
  List<String> routeColors = const [],
}) {
  if (agency == Agency.path && routeColors.isNotEmpty) {
    final hex = routeColors.first;
    return Color(int.parse('FF$hex', radix: 16));
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
  const AppLoader({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: SizedBox(
        width: 28,
        height: 28,
        child: CircularProgressIndicator(strokeWidth: 2.5),
      ),
    );
  }
}
