import 'package:flutter/material.dart';

import '../design/components.dart';
import '../design/theme.dart';
import '../transit/transit_models.dart';
import 'commute_repository.dart';

/// Commute AI's card, shown on a station's arrivals screen when the
/// backend found a real recommendation for it - see
/// backend/app/commute_engine.py. Deliberately similar to
/// RecommendationCard (same "show the real numbers, not just a
/// sentence" trust-preserving pattern) but visually distinct enough to
/// read as "this station's own options," not "your home/office compare."
class CommuteCard extends StatelessWidget {
  const CommuteCard({super.key, required this.agency, required this.recommendation});

  final Agency agency;
  final CommuteRecommendation recommendation;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Icon(
                    recommendation.differsFromUsual
                        ? Icons.swap_horiz_rounded
                        : Icons.bolt_rounded,
                    color: AppColors.accent,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    recommendation.differsFromUsual
                        ? 'Take this instead'
                        : 'Best option right now',
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
              LiveStatusPill(isLive: recommendation.isLive),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            recommendation.message,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              AppBadge(agencyLabel(agency), color: agencyColor(agency), dense: true),
              const SizedBox(width: 6),
              Text(
                '${recommendation.label} · ${formatClockTime(recommendation.predictedArrival)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          if (recommendation.alternatives.isNotEmpty) ...[
            const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
              child: Divider(height: 1, color: AppColors.border),
            ),
            Text(
              'Compared against',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: AppColors.textTertiary,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            for (final alt in recommendation.alternatives)
              _AlternativeRow(agency: agency, alternative: alt),
          ],
        ],
      ),
    );
  }
}

class _AlternativeRow extends StatelessWidget {
  const _AlternativeRow({required this.agency, required this.alternative});

  final Agency agency;
  final CommuteAlternative alternative;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          AppBadge(alternative.label, color: agencyColor(agency), dense: true),
          const SizedBox(width: 6),
          const Spacer(),
          Text(
            formatClockTime(alternative.predictedArrival),
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
