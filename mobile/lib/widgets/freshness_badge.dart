import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../theme/app_theme.dart';

/// Renders the server-computed LIVE/RECENT/LAST_KNOWN/STALE/UNKNOWN state
/// (see backend app/services/tracking_service.py compute_freshness) as a
/// small labeled chip. Used anywhere a position is shown to family,
/// fisherman, or (eventually) the rescue dashboard, so a stale point is
/// never visually indistinguishable from a live one.
class FreshnessBadge extends StatelessWidget {
  final String freshness;
  const FreshnessBadge(this.freshness, {super.key});

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final (label, color, icon) = switch (freshness) {
      'LIVE' => (t.freshnessLive, AppColors.safeGreen, Icons.circle),
      'RECENT' => (t.freshnessRecent, AppColors.deepSea, Icons.circle_outlined),
      'LAST_KNOWN' => (t.freshnessLastKnown, AppColors.warningAmber, Icons.history),
      'STALE' => (t.freshnessStale, AppColors.coral, Icons.warning_amber_rounded),
      _ => (t.freshnessUnknown, AppColors.slate, Icons.help_outline),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(12)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 12, color: Colors.white),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700)),
      ]),
    );
  }
}
