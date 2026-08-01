import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../models/boat.dart';
import '../services/boat_service.dart';
import '../services/trip_service.dart';
import '../theme/app_theme.dart';

class StartTripScreen extends StatefulWidget {
  final int? boatId;
  const StartTripScreen({super.key, this.boatId});

  @override
  State<StartTripScreen> createState() => _StartTripScreenState();
}

class _StartTripScreenState extends State<StartTripScreen> {
  final _destinationController = TextEditingController();
  final _notesController = TextEditingController();
  DateTime? _eta;
  bool _submitting = false;
  String? _error;
  Boat? _selectedBoat;
  List<Boat> _boats = [];
  bool _loadingBoats = true;
  Map<String, dynamic>? _readiness;
  bool _loadingReadiness = false;

  @override
  void initState() {
    super.initState();
    _loadBoats();
  }

  Future<void> _loadBoats() async {
    setState(() => _loadingBoats = true);
    try {
      final result = await BoatService.instance.getBoats();
      _boats = result.data;
      if (widget.boatId != null) {
        _selectedBoat = _boats.where((b) => b.id == widget.boatId).firstOrNull;
      } else if (_boats.isNotEmpty) {
        _selectedBoat = _boats.where((b) => b.isTripReady).firstOrNull ?? _boats.first;
      }
    } catch (_) {
      _boats = [];
    } finally {
      if (mounted) {
        setState(() => _loadingBoats = false);
        if (_selectedBoat != null) _loadReadiness(_selectedBoat!.id);
      }
    }
  }

  Future<void> _loadReadiness(int boatId) async {
    setState(() { _loadingReadiness = true; _readiness = null; });
    try {
      final result = await BoatService.instance.getReadiness(boatId);
      if (result.data.isNotEmpty) _readiness = result.data;
    } catch (_) {}
    if (mounted) setState(() => _loadingReadiness = false);
  }

  Future<void> _pickEta() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 3)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(now));
    if (time == null) return;
    setState(() => _eta = DateTime(date.year, date.month, date.day, time.hour, time.minute));
  }

  Future<void> _submit() async {
    final blocking = (_readiness?['blocking_issues'] as List?)?.cast<String>() ?? [];
    if (blocking.isNotEmpty) {
      final override = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Blocking Issues Detected', style: TextStyle(color: AppColors.coral, fontWeight: FontWeight.w800)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('The following issues must be resolved:'),
              const SizedBox(height: 8),
              ...blocking.map((i) => Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(children: [
                  const Icon(Icons.cancel, size: 16, color: AppColors.coral),
                  const SizedBox(width: 6),
                  Expanded(child: Text(i, style: const TextStyle(color: AppColors.coral))),
                ]),
              )),
              const SizedBox(height: 12),
              const Text('Are you sure you want to proceed anyway?', style: TextStyle(fontWeight: FontWeight.w700)),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: AppColors.coral),
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('Override & Start'),
            ),
          ],
        ),
      );
      if (override != true) return;
    }

    setState(() { _submitting = true; _error = null; });
    try {
      await TripService.instance.startTrip(
        destination: _destinationController.text.trim(),
        estimatedReturnAt: _eta,
        notes: _notesController.text.trim().isEmpty ? null : _notesController.text.trim(),
        boatId: _selectedBoat?.id,
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _destinationController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final allowed = _readiness?['trip_allowed'] as bool? ?? true;
    final score = (_readiness?['safety_score'] as num?)?.toDouble() ?? 0.0;
    final blocking = (_readiness?['blocking_issues'] as List?)?.cast<String>() ?? [];
    final warnings = (_readiness?['warnings'] as List?)?.cast<String>() ?? [];

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: Text(t.tripStartTitle)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Boat selector
            if (_loadingBoats)
              const Center(child: CircularProgressIndicator())
            else if (_boats.isNotEmpty) ...[
              const Text('Select Boat', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
              const SizedBox(height: 8),
              DropdownButtonFormField<int>(
                value: _selectedBoat?.id,
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.directions_boat),
                  labelText: 'Boat',
                ),
                items: _boats.map((boat) => DropdownMenuItem<int>(
                  value: boat.id,
                  child: Row(
                    children: [
                      Expanded(child: Text(boat.name)),
                      if (!boat.isTripReady)
                        const Icon(Icons.warning_amber_rounded, size: 16, color: AppColors.warningAmber),
                    ],
                  ),
                )).toList(),
                onChanged: (value) {
                  setState(() => _selectedBoat = _boats.where((b) => b.id == value).firstOrNull);
                  if (value != null) _loadReadiness(value);
                },
              ),
            ],

            // Readiness summary
            if (_loadingReadiness) ...[
              const SizedBox(height: 16),
              const Center(child: CircularProgressIndicator()),
            ] else if (_readiness != null) ...[
              const SizedBox(height: 16),
              Card(
                color: allowed
                    ? AppColors.safeGreen.withValues(alpha: 0.05)
                    : AppColors.coral.withValues(alpha: 0.05),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            allowed ? Icons.check_circle : Icons.cancel,
                            color: allowed ? AppColors.safeGreen : AppColors.coral,
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            allowed ? 'Ready to sail — Safety score: ${score.toStringAsFixed(0)}' : 'Not ready — ${blocking.length} blocking issue${blocking.length == 1 ? '' : 's'}',
                            style: TextStyle(
                              fontWeight: FontWeight.w800,
                              color: allowed ? AppColors.safeGreen : AppColors.coral,
                            ),
                          ),
                        ],
                      ),
                      if (blocking.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        ...blocking.map((i) => Padding(
                          padding: const EdgeInsets.only(top: 3),
                          child: Row(children: [
                            const Icon(Icons.cancel, size: 14, color: AppColors.coral),
                            const SizedBox(width: 6),
                            Expanded(child: Text(i, style: const TextStyle(color: AppColors.coral, fontSize: 13))),
                          ]),
                        )),
                      ],
                      if (warnings.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        ...warnings.take(2).map((w) => Padding(
                          padding: const EdgeInsets.only(top: 3),
                          child: Row(children: [
                            const Icon(Icons.warning_amber_rounded, size: 14, color: AppColors.warningAmber),
                            const SizedBox(width: 6),
                            Expanded(child: Text(w, style: const TextStyle(color: AppColors.warningAmber, fontSize: 13))),
                          ]),
                        )),
                      ],
                    ],
                  ),
                ),
              ),
            ],

            const SizedBox(height: 16),
            TextField(
              controller: _destinationController,
              decoration: InputDecoration(
                labelText: t.tripDestination,
                prefixIcon: const Icon(Icons.place),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _notesController,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Notes (optional)',
                prefixIcon: Icon(Icons.notes),
              ),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _pickEta,
              icon: const Icon(Icons.schedule),
              label: Text(
                _eta == null ? t.tripEta : 'Return: ${_eta!.toLocal().toString().split('.')[0]}',
                style: const TextStyle(fontSize: 15),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              Text(_error!, style: const TextStyle(color: AppColors.coral)),
            ],
            const SizedBox(height: 24),
            SizedBox(
              height: 56,
              child: FilledButton.icon(
                onPressed: _submitting || _loadingBoats ? null : _submit,
                icon: _submitting
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.sailing),
                label: Text(t.tripStartCta, style: const TextStyle(fontSize: 18)),
                style: FilledButton.styleFrom(
                  backgroundColor: allowed ? AppColors.deepSea : AppColors.warningAmber,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
