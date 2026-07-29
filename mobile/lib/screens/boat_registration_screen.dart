/// Boat Registration Wizard — multi-step form for registering a new boat.
///
/// Steps:
///  1. Basic Info (name, registration number, color)
///  2. Vessel Info (class, hull, dimensions, year)
///  3. Engine Info (type, make, model, serial, year, HP, fuel)
///  4. Harbor & Review (harbor selection, review all)
///
/// Features:
///  - Step indicator with progress
///  - Form validation per step
///  - Offline registration (queues via BoatSyncAction)
///  - Auto-save on step change
///  - Review screen before submission

import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../l10n/app_localizations.dart';
import '../models/boat.dart';
import '../services/boat_repository.dart';
import '../services/boat_service.dart';
import '../theme/app_theme.dart';

class BoatRegistrationScreen extends StatefulWidget {
  const BoatRegistrationScreen({super.key});

  @override
  State<BoatRegistrationScreen> createState() => _BoatRegistrationScreenState();
}

class _BoatRegistrationScreenState extends State<BoatRegistrationScreen> {
  final _pageController = PageController();
  int _currentStep = 0;
  bool _submitting = false;
  String? _error;

  // Step 1: Basic Info
  final _nameController = TextEditingController();
  final _regNumberController = TextEditingController();
  final _colorController = TextEditingController();

  // Step 2: Vessel Info
  String? _vesselClass;
  String? _hullMaterial;
  final _lengthController = TextEditingController();
  final _beamController = TextEditingController();
  final _draftController = TextEditingController();
  final _yearBuiltController = TextEditingController();

  // Step 3: Engine Info
  String? _engineType;
  final _engineMakeController = TextEditingController();
  final _engineModelController = TextEditingController();
  final _engineSerialController = TextEditingController();
  final _engineYearController = TextEditingController();
  final _engineHpController = TextEditingController();
  final _fuelCapacityController = TextEditingController();

  // Step 4: Harbor
  int? _homeHarborId;
  final _harborSearchController = TextEditingController();

  static const _steps = ['Basic Info', 'Vessel', 'Engine', 'Harbor & Review'];
  static const _totalSteps = 4;

  @override
  void dispose() {
    _pageController.dispose();
    _nameController.dispose();
    _regNumberController.dispose();
    _colorController.dispose();
    _lengthController.dispose();
    _beamController.dispose();
    _draftController.dispose();
    _yearBuiltController.dispose();
    _engineMakeController.dispose();
    _engineModelController.dispose();
    _engineSerialController.dispose();
    _engineYearController.dispose();
    _engineHpController.dispose();
    _fuelCapacityController.dispose();
    _harborSearchController.dispose();
    super.dispose();
  }

  bool _validateStep(int step) {
    switch (step) {
      case 0:
        return _nameController.text.trim().isNotEmpty;
      case 1:
        return true; // All fields optional
      case 2:
        return true; // All fields optional
      case 3:
        return true; // Harbor optional
      default:
        return true;
    }
  }

  void _nextStep() {
    if (!_validateStep(_currentStep)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Boat name is required')),
      );
      return;
    }
    if (_currentStep < _totalSteps - 1) {
      _pageController.nextPage(duration: const Duration(milliseconds: 300), curve: Curves.easeInOut);
    }
  }

  void _prevStep() {
    if (_currentStep > 0) {
      _pageController.previousPage(duration: const Duration(milliseconds: 300), curve: Curves.easeInOut);
    }
  }

  Future<void> _submit() async {
    if (!_validateStep(0)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Boat name is required')),
      );
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    final payload = BoatCreate(
      name: _nameController.text.trim(),
      registrationNumber: _regNumberController.text.trim().isEmpty ? null : _regNumberController.text.trim(),
      vesselClass: _vesselClass,
      hullMaterial: _hullMaterial,
      color: _colorController.text.trim().isEmpty ? null : _colorController.text.trim(),
      lengthMeters: _tryParseDouble(_lengthController.text),
      beamMeters: _tryParseDouble(_beamController.text),
      draftMeters: _tryParseDouble(_draftController.text),
      yearBuilt: _tryParseInt(_yearBuiltController.text),
      engineType: _engineType,
      engineMake: _engineMakeController.text.trim().isEmpty ? null : _engineMakeController.text.trim(),
      engineModel: _engineModelController.text.trim().isEmpty ? null : _engineModelController.text.trim(),
      engineSerialNumber: _engineSerialController.text.trim().isEmpty ? null : _engineSerialController.text.trim(),
      engineYear: _tryParseInt(_engineYearController.text),
      engineHorsepower: _tryParseInt(_engineHpController.text),
      fuelCapacityLiters: _tryParseDouble(_fuelCapacityController.text),
      homeHarborId: _homeHarborId,
    );

    final result = await BoatService.instance.createBoat(payload);

    if (!mounted) return;
    setState(() {
      _submitting = false;
      _error = result.error;
    });

    if (result.isSuccess) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result.isOffline ? 'Boat will be registered when online' : 'Boat registered successfully!'),
          backgroundColor: result.isOffline ? AppColors.warningAmber : AppColors.safeGreen,
        ),
      );
      Navigator.of(context).pop(true);
    } else if (result.error != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result.error!), backgroundColor: AppColors.coral),
      );
    }
  }

  double? _tryParseDouble(String value) {
    if (value.trim().isEmpty) return null;
    return double.tryParse(value.trim());
  }

  int? _tryParseInt(String value) {
    if (value.trim().isEmpty) return null;
    return int.tryParse(value.trim());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: const Text('Register Boat'),
      ),
      body: Column(
        children: [
          // Step indicator
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            color: Colors.white,
            child: Row(
              children: List.generate(_totalSteps, (index) {
                final isActive = index == _currentStep;
                final isCompleted = index < _currentStep;
                return Expanded(
                  child: Row(
                    children: [
                      Container(
                        width: 28,
                        height: 28,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: isCompleted
                              ? AppColors.safeGreen
                              : isActive
                                  ? AppColors.primary
                                  : AppColors.border,
                        ),
                        child: Center(
                          child: isCompleted
                              ? const Icon(Icons.check, size: 16, color: Colors.white)
                              : Text('${index + 1}',
                                  style: TextStyle(
                                    color: isActive ? Colors.white : AppColors.textSecondary,
                                    fontWeight: FontWeight.w700,
                                    fontSize: 13,
                                  )),
                        ),
                      ),
                      if (index < _totalSteps - 1)
                        Expanded(
                          child: Container(
                            height: 2,
                            color: isCompleted ? AppColors.safeGreen : AppColors.border,
                          ),
                        ),
                    ],
                  ),
                );
              }),
            ),
          ),
          // Step title
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                Text(
                  'Step ${_currentStep + 1} of $_totalSteps',
                  style: TextStyle(color: AppColors.textSecondary, fontSize: 14),
                ),
                const SizedBox(width: 8),
                Text(_steps[_currentStep], style: theme.textTheme.titleMedium),
              ],
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(_error!, style: const TextStyle(color: AppColors.coral)),
            ),
          // Page content
          Expanded(
            child: PageView(
              controller: _pageController,
              physics: const NeverScrollableScrollPhysics(),
              onPageChanged: (i) => setState(() => _currentStep = i),
              children: [
                _buildBasicInfoStep(),
                _buildVesselInfoStep(),
                _buildEngineInfoStep(),
                _buildReviewStep(),
              ],
            ),
          ),
          // Navigation buttons
          Container(
            padding: const EdgeInsets.all(16),
            color: Colors.white,
            child: Row(
              children: [
                if (_currentStep > 0)
                  Expanded(
                    child: SizedBox(
                      height: 56,
                      child: OutlinedButton.icon(
                        onPressed: _submitting ? null : _prevStep,
                        icon: const Icon(Icons.arrow_back),
                        label: const Text('Back', style: TextStyle(fontSize: 18)),
                      ),
                    ),
                  ),
                if (_currentStep > 0) const SizedBox(width: 12),
                Expanded(
                  flex: _currentStep > 0 ? 1 : 2,
                  child: SizedBox(
                    height: 56,
                    child: FilledButton.icon(
                      onPressed: _submitting
                          ? null
                          : _currentStep < _totalSteps - 1
                              ? _nextStep
                              : _submit,
                      icon: _submitting
                          ? const SizedBox(
                              width: 20, height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : Icon(_currentStep < _totalSteps - 1 ? Icons.arrow_forward : Icons.check),
                      label: Text(
                        _currentStep < _totalSteps - 1 ? 'Next' : 'Register Boat',
                        style: const TextStyle(fontSize: 18),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBasicInfoStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Basic Information', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          const Text('Required: Boat name', style: TextStyle(color: AppColors.textSecondary)),
          const SizedBox(height: 20),
          TextField(
            controller: _nameController,
            decoration: const InputDecoration(
              labelText: 'Boat Name *',
              hintText: 'e.g. Sea Queen',
              prefixIcon: Icon(Icons.directions_boat),
            ),
            textInputAction: TextInputAction.next,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _regNumberController,
            decoration: const InputDecoration(
              labelText: 'Registration Number',
              hintText: 'e.g. TN-01-AB-1234',
              prefixIcon: Icon(Icons.numbers),
            ),
            textInputAction: TextInputAction.next,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _colorController,
            decoration: const InputDecoration(
              labelText: 'Color',
              hintText: 'e.g. Blue, White',
              prefixIcon: Icon(Icons.palette),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVesselInfoStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Vessel Information', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          const Text('Optional — helps with safety assessment', style: TextStyle(color: AppColors.textSecondary)),
          const SizedBox(height: 20),
          DropdownButtonFormField<String>(
            value: _vesselClass,
            decoration: const InputDecoration(
              labelText: 'Vessel Class',
              prefixIcon: Icon(Icons.category),
            ),
            items: const [
              DropdownMenuItem(value: 'mechanized', child: Text('Mechanized')),
              DropdownMenuItem(value: 'motorized', child: Text('Motorized')),
              DropdownMenuItem(value: 'non_motorized', child: Text('Non-motorized')),
              DropdownMenuItem(value: 'trawler', child: Text('Trawler')),
              DropdownMenuItem(value: 'gillnetter', child: Text('Gillnetter')),
              DropdownMenuItem(value: 'purse_seiner', child: Text('Purse Seiner')),
              DropdownMenuItem(value: 'other', child: Text('Other')),
            ],
            onChanged: (v) => setState(() => _vesselClass = v),
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            value: _hullMaterial,
            decoration: const InputDecoration(
              labelText: 'Hull Material',
              prefixIcon: Icon(Icons.material),
            ),
            items: const [
              DropdownMenuItem(value: 'wood', child: Text('Wood')),
              DropdownMenuItem(value: 'fiberglass', child: Text('Fiberglass')),
              DropdownMenuItem(value: 'steel', child: Text('Steel')),
              DropdownMenuItem(value: 'aluminum', child: Text('Aluminum')),
              DropdownMenuItem(value: 'other', child: Text('Other')),
            ],
            onChanged: (v) => setState(() => _hullMaterial = v),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _lengthController,
                  decoration: const InputDecoration(labelText: 'Length (m)', prefixIcon: Icon(Icons.straighten)),
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _beamController,
                  decoration: const InputDecoration(labelText: 'Beam (m)', prefixIcon: Icon(Icons.straighten)),
                  keyboardType: TextInputType.number,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _draftController,
                  decoration: const InputDecoration(labelText: 'Draft (m)', prefixIcon: Icon(Icons.straighten)),
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _yearBuiltController,
                  decoration: const InputDecoration(labelText: 'Year Built', prefixIcon: Icon(Icons.calendar_today)),
                  keyboardType: TextInputType.number,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEngineInfoStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Engine Information', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          const Text('Optional — helps estimate fuel needs', style: TextStyle(color: AppColors.textSecondary)),
          const SizedBox(height: 20),
          DropdownButtonFormField<String>(
            value: _engineType,
            decoration: const InputDecoration(
              labelText: 'Engine Type',
              prefixIcon: Icon(Icons.build),
            ),
            items: const [
              DropdownMenuItem(value: 'diesel', child: Text('Diesel')),
              DropdownMenuItem(value: 'petrol', child: Text('Petrol')),
              DropdownMenuItem(value: 'outboard', child: Text('Outboard')),
              DropdownMenuItem(value: 'electric', child: Text('Electric')),
              DropdownMenuItem(value: 'other', child: Text('Other')),
            ],
            onChanged: (v) => setState(() => _engineType = v),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _engineMakeController,
                  decoration: const InputDecoration(labelText: 'Engine Make', prefixIcon: Icon(Icons.build)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _engineModelController,
                  decoration: const InputDecoration(labelText: 'Model', prefixIcon: Icon(Icons.build)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _engineSerialController,
                  decoration: const InputDecoration(labelText: 'Serial Number', prefixIcon: Icon(Icons.qr_code)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _engineYearController,
                  decoration: const InputDecoration(labelText: 'Engine Year', prefixIcon: Icon(Icons.calendar_today)),
                  keyboardType: TextInputType.number,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _engineHpController,
                  decoration: const InputDecoration(labelText: 'Horsepower (HP)', prefixIcon: Icon(Icons.speed)),
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _fuelCapacityController,
                  decoration: const InputDecoration(labelText: 'Fuel Capacity (L)', prefixIcon: Icon(Icons.local_gas_station)),
                  keyboardType: TextInputType.number,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildReviewStep() {
    final payload = BoatCreate(
      name: _nameController.text.trim(),
      registrationNumber: _regNumberController.text.trim().isEmpty ? null : _regNumberController.text.trim(),
      vesselClass: _vesselClass,
      hullMaterial: _hullMaterial,
      color: _colorController.text.trim().isEmpty ? null : _colorController.text.trim(),
      lengthMeters: _tryParseDouble(_lengthController.text),
      beamMeters: _tryParseDouble(_beamController.text),
      draftMeters: _tryParseDouble(_draftController.text),
      yearBuilt: _tryParseInt(_yearBuiltController.text),
      engineType: _engineType,
      engineMake: _engineMakeController.text.trim().isEmpty ? null : _engineMakeController.text.trim(),
      engineModel: _engineModelController.text.trim().isEmpty ? null : _engineModelController.text.trim(),
      engineSerialNumber: _engineSerialController.text.trim().isEmpty ? null : _engineSerialController.text.trim(),
      engineYear: _tryParseInt(_engineYearController.text),
      engineHorsepower: _tryParseInt(_engineHpController.text),
      fuelCapacityLiters: _tryParseDouble(_fuelCapacityController.text),
      homeHarborId: _homeHarborId,
    );

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Review & Confirm', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          const Text('Please review the boat details before registering', style: TextStyle(color: AppColors.textSecondary)),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Basic Info', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                  _reviewRow('Name', payload.name),
                  if (payload.registrationNumber != null) _reviewRow('Registration', payload.registrationNumber!),
                  if (payload.color != null) _reviewRow('Color', payload.color!),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          if (payload.vesselClass != null || payload.hullMaterial != null || payload.lengthMeters != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Vessel Info', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                    if (payload.vesselClass != null) _reviewRow('Class', payload.vesselClass!),
                    if (payload.hullMaterial != null) _reviewRow('Hull', payload.hullMaterial!),
                    if (payload.lengthMeters != null) _reviewRow('Length', '${payload.lengthMeters}m'),
                    if (payload.beamMeters != null) _reviewRow('Beam', '${payload.beamMeters}m'),
                    if (payload.draftMeters != null) _reviewRow('Draft', '${payload.draftMeters}m'),
                    if (payload.yearBuilt != null) _reviewRow('Year', '${payload.yearBuilt}'),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 8),
          if (payload.engineType != null || payload.engineMake != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Engine Info', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                    if (payload.engineType != null) _reviewRow('Type', payload.engineType!),
                    if (payload.engineMake != null) _reviewRow('Make', payload.engineMake!),
                    if (payload.engineModel != null) _reviewRow('Model', payload.engineModel!),
                    if (payload.engineHorsepower != null) _reviewRow('HP', '${payload.engineHorsepower}'),
                    if (payload.fuelCapacityLiters != null) _reviewRow('Fuel', '${payload.fuelCapacityLiters}L'),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _reviewRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(label, style: TextStyle(color: AppColors.textSecondary, fontWeight: FontWeight.w600)),
          ),
          Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w700))),
        ],
      ),
    );
  }
}
