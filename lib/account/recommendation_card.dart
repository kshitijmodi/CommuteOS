import 'package:flutter/material.dart';

import '../design/components.dart';
import '../design/theme.dart';
import '../transit/transit_models.dart';
import 'recommendation_repository.dart';

/// The AI-reasoned recommendation, shown as a single card - the winning
/// route's phrased sentence up top, with every real alternative it beat
/// listed below in plain numbers. Showing the alternatives is deliberate:
/// the phrased sentence explains WHY the winner won (see the backend's
/// llm_phrasing.phrase_comparison), and a rider should be able to check
/// that reasoning against the real data instead of just trusting a
/// sentence - this is meant to read as "AI showing its work," not a black
/// box. Used by both the home screen (FavoritesScreen) and the dedicated
/// "What should I take?" screen (RecommendationScreen) so the same
/// component looks and behaves identically everywhere it appears.
class RecommendationCard extends StatelessWidget {
  const RecommendationCard({super.key, required this.recommendation});

  final Recommendation recommendation;

  @override
  Widget build(BuildContext context) {
    final winnerAgency = agencyFromWireName(recommendation.mode);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Icon(Icons.bolt_rounded, color: AppColors.accent),
                  const SizedBox(width: 6),
                  Text(
                    'Best option right now',
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
              if (winnerAgency != null) ...[
                AppBadge(
                  agencyLabel(winnerAgency),
                  color: agencyColor(winnerAgency),
                  dense: true,
                ),
                const SizedBox(width: 6),
              ],
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
            for (final alt in recommendation.alternatives) _AlternativeRow(alternative: alt),
          ],
        ],
      ),
    );
  }
}

class _AlternativeRow extends StatelessWidget {
  const _AlternativeRow({required this.alternative});

  final RecommendationAlternative alternative;

  @override
  Widget build(BuildContext context) {
    final agency = agencyFromWireName(alternative.mode);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          if (agency != null) ...[
            AppBadge(agencyLabel(agency), color: agencyColor(agency), dense: true),
            const SizedBox(width: 6),
          ],
          Expanded(
            child: Text(
              alternative.label,
              style: Theme.of(context).textTheme.bodySmall,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Text(
            formatClockTime(alternative.predictedArrival),
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
