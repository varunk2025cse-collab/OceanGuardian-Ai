import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';

/// Mirrors the rescue dashboard's SystemModeBanner — GET /api/v1/system-info
/// (unauthenticated, no secrets). Final Release Engineering Phase C/G:
/// simulated data must never be visually indistinguishable from real data.
class SystemModeBanner extends StatefulWidget {
  const SystemModeBanner({super.key});

  @override
  State<SystemModeBanner> createState() => _SystemModeBannerState();
}

class _SystemModeBannerState extends State<SystemModeBanner> {
  List<String> _bits = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final info = await ApiClient.instance.get('/system-info') as Map<String, dynamic>;
      final bits = <String>[];
      if (info['demo_mode'] == true) bits.add('DEMO MODE');
      if ((info['notification_provider'] as String?)?.startsWith('simulation') == true) {
        bits.add('notifications simulated');
      }
      if (info['weather_provider'] == 'simulated') bits.add('weather simulated');
      if ((info['ai_provider'] as String?)?.contains('falling back') == true) {
        bits.add('AI explanation is template-based');
      }
      if (mounted) setState(() => _bits = bits);
    } catch (_) {
      // Offline — say nothing rather than guess the system's mode.
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_bits.isEmpty) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      color: AppColors.warningAmber,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Text(
        '⚠ ${_bits.join(' · ')}',
        style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700),
        textAlign: TextAlign.center,
      ),
    );
  }
}
