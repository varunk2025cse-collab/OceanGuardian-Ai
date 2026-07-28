import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../theme/app_theme.dart';

/// Renders the server-computed SAFE/MONITOR/CAUTION/HIGH_RISK/CRITICAL/
/// UNKNOWN safety state (backend app/services/safety_engine.py). Distinct
/// from FreshnessBadge — a vessel can be HIGH_RISK while still ONLINE, or
/// UNKNOWN-safety while LIVE (no trip in progress) — the two are never
/// merged into one status.
class SafetyStateBadge extends StatelessWidget {
  final String safetyState;
  const SafetyStateBadge(this.safetyState, {super.key});

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final (label, color, icon) = switch (safetyState) {
      'SAFE' => (t.safetySafe, AppColors.safeGreen, Icons.check_circle),
      'MONITOR' => (t.safetyMonitor, AppColors.deepSea, Icons.visibility),
      'CAUTION' => (t.safetyCaution, AppColors.warningAmber, Icons.info),
      'HIGH_RISK' => (t.safetyHighRisk, const Color(0xFFFF8C42), Icons.warning_amber_rounded),
      'CRITICAL' => (t.safetyCritical, AppColors.coral, Icons.emergency),
      _ => (t.safetyUnknown, AppColors.slate, Icons.help_outline),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(14)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14, color: Colors.white),
        const SizedBox(width: 5),
        Text(label, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w800)),
      ]),
    );
  }
}
