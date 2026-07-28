import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../services/trip_service.dart';
import '../theme/app_theme.dart';

/// Minimal trip-start form: destination + optional ETA. Deliberately does
/// not ask for a boat here — the mobile app has no boat management UI yet
/// (that's a separate, not-yet-built feature; the backend's boat_id on
/// TripStart stays optional and unset from this screen).
class StartTripScreen extends StatefulWidget {
  const StartTripScreen({super.key});

  @override
  State<StartTripScreen> createState() => _StartTripScreenState();
}

class _StartTripScreenState extends State<StartTripScreen> {
  final _destinationController = TextEditingController();
  DateTime? _eta;
  bool _submitting = false;
  String? _error;

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
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await TripService.instance.startTrip(
        destination: _destinationController.text.trim(),
        estimatedReturnAt: _eta,
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
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: Text(t.tripStartTitle)),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _destinationController,
              decoration: InputDecoration(labelText: t.tripDestination),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _pickEta,
              icon: const Icon(Icons.schedule),
              label: Text(_eta == null ? t.tripEta : _eta!.toLocal().toString()),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              Text(_error!, style: const TextStyle(color: AppColors.coral)),
            ],
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _submitting ? null : _submit,
              child: _submitting
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(t.tripStartCta),
            ),
          ],
        ),
      ),
    );
  }
}
