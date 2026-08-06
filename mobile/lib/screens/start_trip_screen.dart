import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../models/boat.dart';
import '../services/boat_service.dart';
import '../services/trip_service.dart';
import '../theme/app_theme.dart';

/// Trip start form with boat selection and optional ETA.
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
  bool _loadingBoats = true;
  List<Boat> _boats = [];
  Boat? _selectedBoat;
  String? _error;

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
      if (_boats.isNotEmpty) {
        if (widget.boatId != null) {
          _selectedBoat = _boats.firstWhere(
            (boat) => boat.id == widget.boatId,
            orElse: () => _boats.first,
          );
        } else {
          _selectedBoat = _boats.first;
        }
      }
    } catch (_) {
      _boats = [];
      _selectedBoat = null;
    } finally {
      if (mounted) setState(() => _loadingBoats = false);
    }
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
    setState(() {
      _submitting = true;
      _error = null;
    });
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
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: Text(t.tripStartTitle)),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_loadingBoats)
              const Center(child: CircularProgressIndicator())
            else if (_boats.isNotEmpty)
              DropdownButtonFormField<int>(
                value: _selectedBoat?.id,
                decoration: const InputDecoration(labelText: 'Boat'),
                items: _boats
                    .map((boat) => DropdownMenuItem<int>(
                          value: boat.id,
                          child: Text(boat.name),
                        ))
                    .toList(),
                onChanged: (value) {
                  if (value == null) return;
                  setState(() {
                    _selectedBoat = _boats.firstWhere(
                      (boat) => boat.id == value,
                      orElse: () => _boats.first,
                    );
                  });
                },
              ),
            const SizedBox(height: 16),
            TextField(
              controller: _destinationController,
              decoration: InputDecoration(labelText: t.tripDestination),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _notesController,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Notes (optional)'),
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
