/// Boat Status Badge — color-coded lifecycle state badge for boat cards.
///
/// Mirrors the 8-state FSM from backend BoatStatus and displays each
/// status with a distinct color, icon, and label for quick visual scanning.
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class BoatStatusBadge extends StatelessWidget {
  final String status;
  final double fontSize;

  const BoatStatusBadge(this.status, {super.key, this.fontSize = 12});

  @override
  Widget build(BuildContext context) {
    final (label, color, icon) = switch (status) {
      'active' => ('Active', AppColors.safeGreen, Icons.check_circle),
      'registered' => ('Registered', AppColors.primary, Icons.edit_note),
      'inactive' => ('Inactive', AppColors.textDisabled, Icons.pause_circle),
      'maintenance' => ('Maint.', AppColors.warningAmber, Icons.build),
      'emergency' => ('Emergency', AppColors.coral, Icons.emergency),
      'damaged' => ('Damaged', AppColors.warning, Icons.report),
      'lost' => ('Lost', Colors.black87, Icons.live_help),
      'decommissioned' => ('Retired', AppColors.textSecondary, Icons.flag),
      _ => (status, AppColors.textSecondary, Icons.circle_outlined),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.4), width: 1.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: fontSize + 2, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: fontSize,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}
