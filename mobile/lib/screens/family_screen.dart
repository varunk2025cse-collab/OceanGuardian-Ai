import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../l10n/app_localizations.dart';
import '../models/family_status.dart';
import '../services/api_client.dart';
import '../services/reference_data_service.dart';
import '../theme/app_theme.dart';
import '../widgets/freshness_badge.dart';
import '../widgets/safety_state_badge.dart';
import 'location_screen.dart';

class FamilyScreen extends StatefulWidget {
  const FamilyScreen({super.key});

  @override
  State<FamilyScreen> createState() => _FamilyScreenState();
}

class _FamilyScreenState extends State<FamilyScreen> {
  bool _loading = true;
  bool _fromCache = false;
  List<FishermanStatus> _statuses = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final result = await ReferenceDataService.instance.familyStatus();
    if (!mounted) return;
    setState(() {
      _statuses = result.items;
      _fromCache = result.fromCache;
      _loading = false;
    });
  }

  Future<void> _showAddFishermanDialog() async {
    final t = AppLocalizations.of(context)!;
    final phoneController = TextEditingController();
    final relationController = TextEditingController();

    final added = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(t.familyAddFisherman),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: phoneController, decoration: InputDecoration(labelText: t.phoneNumber)),
            const SizedBox(height: 8),
            TextField(controller: relationController, decoration: InputDecoration(labelText: t.familyRelationLabel)),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(t.cancel)),
          FilledButton(
            onPressed: () async {
              try {
                await ReferenceDataService.instance
                    .linkFisherman(phoneNumber: phoneController.text.trim(), relation: relationController.text.trim());
                if (ctx.mounted) Navigator.pop(ctx, true);
              } on ApiException catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(e.message)));
                }
              }
            },
            child: Text(t.save),
          ),
        ],
      ),
    );

    if (added == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: Text(t.familyTitle),
        actions: [IconButton(icon: const Icon(Icons.person_add), onPressed: _showAddFishermanDialog)],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_fromCache)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Row(children: [
                        const Icon(Icons.cloud_off, size: 16, color: AppColors.slate),
                        const SizedBox(width: 6),
                        Text(t.familyOffline, style: Theme.of(context).textTheme.bodyMedium),
                      ]),
                    ),
                  if (_statuses.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 48),
                      child: Column(children: [
                        const Icon(Icons.family_restroom, color: AppColors.slate, size: 48),
                        const SizedBox(height: 12),
                        Text(t.familyAddFisherman, textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        FilledButton(onPressed: _showAddFishermanDialog, child: Text(t.familyAddFisherman)),
                      ]),
                    )
                  else
                    ..._statuses.map((s) {
                      // Safety semantics audit finding (Final Release
                      // Engineering Phase G): this row used to derive its
                      // "All clear" / green-checkmark styling from
                      // `activeSos` alone, ignoring `safetyState` entirely
                      // — a fisherman could be HIGH_RISK/CRITICAL (stale
                      // GPS + weather, no formal SOS triggered yet) and
                      // still show a reassuring green "All clear", directly
                      // contradicting the SafetyStateBadge right next to it.
                      // `urgent` now reflects both signals.
                      final urgent = s.activeSos || s.safetyState == 'HIGH_RISK' || s.safetyState == 'CRITICAL';
                      final reassuring = !s.activeSos && (s.safetyState == 'SAFE' || s.safetyState == 'MONITOR');
                      return Card(
                          color: urgent ? AppColors.coral.withOpacity(0.08) : null,
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: urgent ? AppColors.coral : AppColors.safeGreen,
                              child: Icon(urgent ? Icons.warning : Icons.check, color: Colors.white),
                            ),
                            title: Row(children: [
                              Flexible(child: Text(s.fullName, style: const TextStyle(fontWeight: FontWeight.w700))),
                              const SizedBox(width: 8),
                              FreshnessBadge(s.freshness),
                            ]),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  [
                                    if (s.boatName != null) s.boatName!,
                                    s.lastSeenAt == null
                                        ? t.familyNeverSeen
                                        : '${t.familyLastSeen}: ${DateFormat('dd MMM, hh:mm a').format(s.lastSeenAt!.toLocal())}',
                                  ].join(' · '),
                                ),
                                const SizedBox(height: 6),
                                Row(children: [
                                  SafetyStateBadge(s.safetyState),
                                  if (s.incidentStatus != null) ...[
                                    const SizedBox(width: 6),
                                    Text('· ${s.incidentStatus!.replaceAll('_', ' ')}',
                                        style: const TextStyle(fontSize: 11, color: AppColors.slate)),
                                  ],
                                ]),
                              ],
                            ),
                            isThreeLine: true,
                            trailing: s.activeSos
                                ? Text(t.familyActiveSos,
                                    style: const TextStyle(color: AppColors.coral, fontWeight: FontWeight.w800, fontSize: 11))
                                : reassuring
                                    ? Text(t.familyAllSafe, style: const TextStyle(color: AppColors.safeGreen, fontWeight: FontWeight.w700))
                                    : null, // CAUTION/HIGH_RISK/CRITICAL/UNKNOWN: let SafetyStateBadge speak for itself, never show a reassuring label that contradicts it
                            onTap: s.lastLatitude == null
                                ? null
                                : () => Navigator.of(context).push(MaterialPageRoute(
                                    builder: (_) => LocationScreen(
                                          focusLatitude: s.lastLatitude,
                                          focusLongitude: s.lastLongitude,
                                          title: s.fullName,
                                          focusFreshness: s.freshness,
                                          focusLastSeenAt: s.lastSeenAt,
                                        ))),
                          ),
                        );
                    }),
                ],
              ),
      ),
    );
  }
}
