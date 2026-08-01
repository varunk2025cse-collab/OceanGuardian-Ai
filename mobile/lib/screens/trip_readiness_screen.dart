import 'package:flutter/material.dart';
import '../services/boat_service.dart';
import '../theme/app_theme.dart';
import 'start_trip_screen.dart';

class TripReadinessScreen extends StatefulWidget {
  final int boatId;
  const TripReadinessScreen({super.key, required this.boatId});

  @override
  State<TripReadinessScreen> createState() => _TripReadinessScreenState();
}

class _TripReadinessScreenState extends State<TripReadinessScreen> {
  Map<String, dynamic>? _readiness;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final result = await BoatService.instance.getReadiness(widget.boatId);
      _readiness = result.data.isNotEmpty ? result.data : null;
    } catch (_) {
      _readiness = null;
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Color _scoreColor(double score) {
    if (score >= 80) return AppColors.safeGreen;
    if (score >= 50) return AppColors.warningAmber;
    return AppColors.coral;
  }

  Color _statusColor(String status) {
    switch (status.toUpperCase()) {
      case 'SAFE': return AppColors.safeGreen;
      case 'CAUTION': return AppColors.warningAmber;
      default: return AppColors.coral;
    }
  }

  @override
  Widget build(BuildContext context) {
    final score = (_readiness?['safety_score'] as num?)?.toDouble() ?? 0.0;
    final status = _readiness?['overall_status'] as String? ?? 'UNKNOWN';
    final allowed = _readiness?['trip_allowed'] as bool? ?? false;
    final blocking = (_readiness?['blocking_issues'] as List?)?.cast<String>() ?? [];
    final warnings = (_readiness?['warnings'] as List?)?.cast<String>() ?? [];
    final recommendations = (_readiness?['recommendations'] as List?)?.cast<String>() ?? [];
    final passed = (_readiness?['passed_checks'] as List?)?.cast<String>() ?? [];

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: const Text('Trip Readiness'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), tooltip: 'Refresh', onPressed: _load),
        ],
      ),
      bottomNavigationBar: _readiness != null
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: SizedBox(
                  height: 56,
                  child: allowed
                      ? FilledButton.icon(
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute(builder: (_) => StartTripScreen(boatId: widget.boatId)),
                          ),
                          icon: const Icon(Icons.sailing),
                          label: const Text('Start Trip Now', style: TextStyle(fontSize: 18)),
                          style: FilledButton.styleFrom(backgroundColor: AppColors.safeGreen),
                        )
                      : OutlinedButton.icon(
                          onPressed: null,
                          icon: const Icon(Icons.block),
                          label: const Text('Trip Blocked — Fix Issues First', style: TextStyle(fontSize: 16)),
                        ),
                ),
              ),
            )
          : null,
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _readiness == null
              ? _OfflineState(onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
                    children: [
                      // Status hero card
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            children: [
                              // Status badge
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                                decoration: BoxDecoration(
                                  color: _statusColor(status).withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(color: _statusColor(status), width: 2),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(
                                      allowed ? Icons.check_circle : Icons.cancel,
                                      color: _statusColor(status),
                                      size: 20,
                                    ),
                                    const SizedBox(width: 8),
                                    Text(
                                      allowed ? 'READY TO SAIL' : 'NOT READY',
                                      style: TextStyle(
                                        color: _statusColor(status),
                                        fontWeight: FontWeight.w900,
                                        fontSize: 16,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 20),
                              // Score
                              Text(
                                score.toStringAsFixed(0),
                                style: TextStyle(
                                  fontSize: 64,
                                  fontWeight: FontWeight.w900,
                                  color: _scoreColor(score),
                                ),
                              ),
                              Text('Safety Score', style: Theme.of(context).textTheme.titleMedium),
                              const SizedBox(height: 12),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: LinearProgressIndicator(
                                  value: score / 100,
                                  backgroundColor: AppColors.border,
                                  valueColor: AlwaysStoppedAnimation(_scoreColor(score)),
                                  minHeight: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),

                      // Blocking issues
                      if (blocking.isNotEmpty) ...[
                        _SectionHeader(title: 'Blocking Issues — Fix Before Trip', color: AppColors.coral, icon: Icons.cancel),
                        ...blocking.map((issue) => _IssueCard(text: issue, color: AppColors.coral, icon: Icons.cancel)),
                        const SizedBox(height: 8),
                      ],

                      // Warnings
                      if (warnings.isNotEmpty) ...[
                        _SectionHeader(title: 'Warnings', color: AppColors.warningAmber, icon: Icons.warning_amber_rounded),
                        ...warnings.map((w) => _IssueCard(text: w, color: AppColors.warningAmber, icon: Icons.warning_amber_rounded)),
                        const SizedBox(height: 8),
                      ],

                      // Recommendations
                      if (recommendations.isNotEmpty) ...[
                        _SectionHeader(title: 'Recommendations', color: AppColors.deepSea, icon: Icons.lightbulb_outlined),
                        ...recommendations.map((r) => _IssueCard(text: r, color: AppColors.deepSea, icon: Icons.lightbulb_outlined)),
                        const SizedBox(height: 8),
                      ],

                      // Passed checks
                      if (passed.isNotEmpty) ...[
                        _SectionHeader(title: 'Passed Checks (${passed.length})', color: AppColors.safeGreen, icon: Icons.check_circle),
                        ...passed.map((p) => _IssueCard(text: p, color: AppColors.safeGreen, icon: Icons.check_circle)),
                      ],

                      const SizedBox(height: 80),
                    ],
                  ),
                ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final Color color;
  final IconData icon;
  const _SectionHeader({required this.title, required this.color, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(title, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14, color: color)),
        ],
      ),
    );
  }
}

class _IssueCard extends StatelessWidget {
  final String text;
  final Color color;
  final IconData icon;
  const _IssueCard({required this.text, required this.color, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      color: color.withValues(alpha: 0.05),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 10),
            Expanded(child: Text(text, style: TextStyle(color: color.withValues(alpha: 0.9)))),
          ],
        ),
      ),
    );
  }
}

class _OfflineState extends StatelessWidget {
  final VoidCallback onRetry;
  const _OfflineState({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.shield_outlined, size: 72, color: AppColors.textDisabled),
            const SizedBox(height: 16),
            const Text('Could not load readiness data', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            const Text('Check your connection and try again', style: TextStyle(color: AppColors.textSecondary)),
            const SizedBox(height: 24),
            FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}
