import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../models/sos_alert.dart';
import '../services/local_db_service.dart';
import '../services/sos_service.dart';
import '../theme/app_theme.dart';
import '../widgets/sos_button.dart';

class SosScreen extends StatefulWidget {
  const SosScreen({super.key});

  @override
  State<SosScreen> createState() => _SosScreenState();
}

class _SosScreenState extends State<SosScreen> {
  bool _sending = false;
  List<Map<String, dynamic>> _localHistory = [];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final db = await LocalDbService.instance.database;
    final rows = await db.query('pending_sos', orderBy: 'triggered_at DESC', limit: 20);
    if (mounted) setState(() => _localHistory = rows);
  }

  String _typeLabel(AppLocalizations t, String type) => switch (type) {
        EmergencyType.manOverboard => t.sosTypeManOverboard,
        EmergencyType.medical => t.sosTypeMedical,
        EmergencyType.fire => t.sosTypeFire,
        EmergencyType.capsize => t.sosTypeCapsize,
        EmergencyType.collision => t.sosTypeCollision,
        EmergencyType.engineFailure => t.sosTypeEngineFailure,
        EmergencyType.severeWeather => t.sosTypeSevereWeather,
        EmergencyType.fuelShortage => t.sosTypeFuelShortage,
        EmergencyType.communicationFailure => t.sosTypeCommsFailure,
        EmergencyType.unknown => t.sosTypeUnknown,
        _ => t.sosTypeManual,
      };

  Future<void> _confirmAndSend() async {
    final t = AppLocalizations.of(context)!;
    // Defaults to a general SOS so the primary Send action never requires
    // picking a type first — selecting one is a quick, fully optional
    // refinement within the same confirmation step (SOS must stay
    // reachable in one motion; see docs/SOS_ARCHITECTURE.md).
    String selectedType = EmergencyType.manual;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text(t.sosConfirmTitle),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(t.sosConfirmBody),
              const SizedBox(height: 16),
              Text(t.sosEmergencyTypeTitle, style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: EmergencyType.all.map((type) {
                  final selected = type == selectedType;
                  return ChoiceChip(
                    label: Text(_typeLabel(t, type)),
                    selected: selected,
                    onSelected: (_) => setDialogState(() => selectedType = type),
                    selectedColor: AppColors.coral,
                    labelStyle: TextStyle(color: selected ? Colors.white : null, fontSize: 12),
                  );
                }).toList(),
              ),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(t.sosCancel)),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: AppColors.coral),
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(t.sosConfirmSend),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true) return;

    setState(() => _sending = true);
    try {
      final alert = await SosService.instance.trigger(alertType: selectedType);
      await _loadHistory();
      if (!mounted) return;

      // Whether or not the network call actually succeeded, the alert is
      // safely on-device the instant trigger() returns - so the user
      // always sees a confirmation, never a spinner that implies failure.
      final wasSyncedImmediately = _localHistory.any((r) => r['client_uuid'] == alert.clientUuid && r['synced'] == 1);

      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Row(children: [
            const Icon(Icons.check_circle, color: AppColors.safeGreen),
            const SizedBox(width: 8),
            Text(AppLocalizations.of(ctx)!.sosSentTitle),
          ]),
          content: Text(wasSyncedImmediately
              ? AppLocalizations.of(ctx)!.sosSentOnline
              : AppLocalizations.of(ctx)!.sosSentOffline),
          actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: Text(t.navSos)),
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 32),
            SosButton(onConfirmedPress: _confirmAndSend, sending: _sending),
            const SizedBox(height: 16),
            Text(t.sosHoldToSend, style: Theme.of(context).textTheme.bodyMedium, textAlign: TextAlign.center),
            const SizedBox(height: 24),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Align(alignment: Alignment.centerLeft, child: Text(t.sosHistory, style: Theme.of(context).textTheme.titleLarge)),
            ),
            Expanded(
              child: _localHistory.isEmpty
                  ? const Center(child: Icon(Icons.history, color: AppColors.slate, size: 40))
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      itemCount: _localHistory.length,
                      itemBuilder: (context, i) {
                        final row = _localHistory[i];
                        final synced = row['synced'] == 1;
                        return Card(
                          child: ListTile(
                            leading: Icon(
                              synced ? Icons.cloud_done : Icons.cloud_off,
                              color: synced ? AppColors.safeGreen : AppColors.warningAmber,
                            ),
                            title: Text('${row['status']}'.toUpperCase()),
                            subtitle: Text(
                              '${_typeLabel(t, row['alert_type'] as String? ?? EmergencyType.manual)} · ${row['triggered_at']}',
                            ),
                            trailing: Text(synced ? 'Sent' : 'Pending'),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
