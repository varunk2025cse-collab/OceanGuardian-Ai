/// Boat Detail Screen — comprehensive single-boat view.
///
/// Shows:
///  - Boat overview card (name, reg, status, verification, owner)
///  - Quick action grid (documents, crew, equipment, QR, readiness, edit)
///  - Crew summary (captain + count)
///  - Equipment summary (mandatory items status)
///  - Document status (verified count, expiring docs)
///  - Trip readiness (safety score, blocking issues, warnings)
///  - QR code
///  - Activity timeline (status history)
///  - Full offline support with cache-first loading

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/boat.dart';
import '../models/boat_document.dart';
import '../models/boat_crew.dart';
import '../models/boat_equipment.dart';
import '../services/api_client.dart';
import '../services/boat_service.dart';
import '../theme/app_theme.dart';
import '../widgets/boat_status_badge.dart';
import 'boat_crew_screen.dart';
import 'boat_documents_screen.dart';
import 'boat_equipment_screen.dart';
import 'boat_qr_screen.dart';
import 'trip_readiness_screen.dart';

class BoatDetailScreen extends StatefulWidget {
  final int boatId;

  const BoatDetailScreen({super.key, required this.boatId});

  @override
  State<BoatDetailScreen> createState() => _BoatDetailScreenState();
}

class _BoatDetailScreenState extends State<BoatDetailScreen> {
  bool _loading = true;
  Boat? _boat;
  List<BoatDocument> _documents = [];
  List<BoatCrewMember> _crew = [];
  List<BoatEquipmentItem> _equipment = [];
  Map<String, dynamic>? _readiness;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      // Load boat
      final boatResult =
          await BoatService.instance.getBoat(widget.boatId, forceRefresh: true);
      if (boatResult.data != null) {
        _boat = boatResult.data;
      }

      // Load documents in parallel
      try {
        final docResult =
            await BoatService.instance.getDocuments(widget.boatId);
        _documents = docResult.data;
      } catch (_) {}

      // Load crew in parallel
      try {
        final crewResult = await BoatService.instance.getCrew(widget.boatId);
        _crew = crewResult.data;
      } catch (_) {}

      // Load equipment and attach it to the detail view.
      try {
        final equipmentResult =
            await BoatService.instance.getEquipment(widget.boatId);
        _equipment = equipmentResult.data;
      } catch (_) {}

      // Load readiness
      try {
        final data =
            await ApiClient.instance.getV2('/boats/${widget.boatId}/readiness');
        _readiness = data as Map<String, dynamic>?;
      } catch (_) {}
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: Text(_boat?.name ?? 'Boat Details'),
        actions: [
          if (_boat != null)
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              tooltip: 'Edit boat',
              onPressed: () {
                // TODO: Navigate to edit boat screen
              },
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _boat == null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.directions_boat_outlined,
                          size: 64, color: AppColors.textDisabled),
                      const SizedBox(height: 16),
                      Text('Boat not found',
                          style: Theme.of(context).textTheme.titleLarge),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _BoatOverviewCard(boat: _boat!),
                      const SizedBox(height: 16),
                      _QuickActionGrid(boat: _boat!),
                      const SizedBox(height: 16),
                      _buildReadinessCard(),
                      if (_readiness != null) const SizedBox(height: 16),
                      _buildCrewCard(),
                      const SizedBox(height: 16),
                      _buildDocumentsCard(),
                      const SizedBox(height: 16),
                      _buildEquipmentCard(),
                      const SizedBox(height: 16),
                      _buildQRCard(),
                      const SizedBox(height: 16),
                      _buildTimelineCard(),
                      const SizedBox(height: 32),
                    ],
                  ),
                ),
    );
  }

  Widget _buildReadinessCard() {
    if (_readiness == null) return const SizedBox.shrink();

    final allowed = _readiness!['trip_allowed'] as bool? ?? false;
    final score = (_readiness!['safety_score'] as num?)?.toDouble() ?? 0;
    final status = _readiness!['overall_status'] as String? ?? 'UNSAFE';
    final blocking =
        (_readiness!['blocking_issues'] as List?)?.cast<String>() ?? [];
    final warnings = (_readiness!['warnings'] as List?)?.cast<String>() ?? [];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.shield_outlined, color: AppColors.deepSea),
                const SizedBox(width: 8),
                Text('Trip Readiness',
                    style: Theme.of(context).textTheme.titleLarge),
                const Spacer(),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: _readinessColor(status).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(16),
                    border:
                        Border.all(color: _readinessColor(status), width: 2),
                  ),
                  child: Text(status,
                      style: TextStyle(
                          color: _readinessColor(status),
                          fontWeight: FontWeight.w800)),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Safety score bar
            Row(
              children: [
                Text('Safety Score: ',
                    style: Theme.of(context).textTheme.titleMedium),
                Text(
                  score.toStringAsFixed(0),
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: _scoreColor(score),
                        fontWeight: FontWeight.w900,
                      ),
                ),
                const Spacer(),
                if (allowed)
                  Chip(
                    avatar: const Icon(Icons.check_circle,
                        size: 16, color: AppColors.safeGreen),
                    label: const Text('Trip Allowed',
                        style: TextStyle(
                            fontSize: 12, fontWeight: FontWeight.w700)),
                    backgroundColor: AppColors.safeGreen.withValues(alpha: 0.1),
                  )
                else
                  Chip(
                    avatar: const Icon(Icons.cancel,
                        size: 16, color: AppColors.coral),
                    label: const Text('Not Allowed',
                        style: TextStyle(
                            fontSize: 12, fontWeight: FontWeight.w700)),
                    backgroundColor: AppColors.coral.withValues(alpha: 0.1),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: score / 100,
                backgroundColor: AppColors.border,
                valueColor: AlwaysStoppedAnimation(_scoreColor(score)),
                minHeight: 10,
              ),
            ),
            if (blocking.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Blocking Issues',
                  style: TextStyle(
                      fontWeight: FontWeight.w800, color: AppColors.coral)),
              const SizedBox(height: 4),
              ...blocking.map((issue) => Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.cancel,
                            size: 18, color: AppColors.coral),
                        const SizedBox(width: 8),
                        Expanded(
                            child: Text(issue,
                                style:
                                    const TextStyle(color: AppColors.coral))),
                      ],
                    ),
                  )),
            ],
            if (warnings.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Warnings',
                  style: TextStyle(
                      fontWeight: FontWeight.w800,
                      color: AppColors.warningAmber)),
              const SizedBox(height: 4),
              ...warnings.map((w) => Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.warning_amber_rounded,
                            size: 18, color: AppColors.warningAmber),
                        const SizedBox(width: 8),
                        Expanded(child: Text(w)),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildCrewCard() {
    final captain = _crew.where((c) => c.isCaptain && c.isActive).toList();
    final activeCrew = _crew.where((c) => c.isActive).toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.groups, color: AppColors.deepSea),
                const SizedBox(width: 8),
                Text('Crew (${activeCrew.length})',
                    style: Theme.of(context).textTheme.titleLarge),
                const Spacer(),
                TextButton.icon(
                  onPressed: () {
                    Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => BoatCrewScreen(boatId: widget.boatId)));
                  },
                  icon: const Icon(Icons.edit, size: 18),
                  label: const Text('Manage'),
                ),
              ],
            ),
            if (captain.isNotEmpty) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.star,
                      color: AppColors.warningAmber, size: 20),
                  const SizedBox(width: 8),
                  Text('Captain: ${captain.first.fullName}',
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                ],
              ),
            ],
            if (!_crew.any((c) => c.isCaptain && c.isActive))
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded,
                        color: AppColors.coral, size: 18),
                    const SizedBox(width: 8),
                    const Text('No captain assigned',
                        style: TextStyle(
                            color: AppColors.coral,
                            fontWeight: FontWeight.w700)),
                  ],
                ),
              ),
            ...activeCrew
                .where((c) => !c.isCaptain)
                .take(3)
                .map((member) => Padding(
                      padding: const EdgeInsets.only(top: 6, left: 8),
                      child: Row(
                        children: [
                          const Icon(Icons.person,
                              size: 18, color: AppColors.textSecondary),
                          const SizedBox(width: 8),
                          Text('${member.fullName} — ${member.role}'),
                        ],
                      ),
                    )),
            if (activeCrew.length > 4)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('+${activeCrew.length - 4} more crew members',
                    style: const TextStyle(color: AppColors.textSecondary)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildDocumentsCard() {
    final verified = _documents.where((d) => d.isVerified).length;
    final expired = _documents.where((d) => d.isExpired).length;
    final expiring = _documents
        .where((d) =>
            d.daysUntilExpiry != null &&
            d.daysUntilExpiry! <= 30 &&
            !d.isExpired)
        .length;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.description, color: AppColors.deepSea),
                const SizedBox(width: 8),
                Text('Documents (${_documents.length})',
                    style: Theme.of(context).textTheme.titleLarge),
                const Spacer(),
                TextButton.icon(
                  onPressed: () {
                    Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) =>
                            BoatDocumentsScreen(boatId: widget.boatId)));
                  },
                  icon: const Icon(Icons.visibility, size: 18),
                  label: const Text('View'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _StatBox(
                    label: 'Verified',
                    value: '$verified/${_documents.length}',
                    color: AppColors.safeGreen),
                const SizedBox(width: 12),
                _StatBox(
                    label: 'Expired',
                    value: '$expired',
                    color: expired > 0 ? AppColors.coral : AppColors.safeGreen),
                const SizedBox(width: 12),
                _StatBox(
                    label: 'Expiring Soon',
                    value: '$expiring',
                    color: expiring > 0
                        ? AppColors.warningAmber
                        : AppColors.safeGreen),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEquipmentCard() {
    final mandatoryItems = _equipment.where((e) => e.isMandatory).toList();
    final usable = mandatoryItems.where((e) => e.isUsable).length;
    final needsReplace =
        mandatoryItems.where((e) => e.needsReplacement || e.isExpired).length;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.inventory_2, color: AppColors.deepSea),
                const SizedBox(width: 8),
                Text('Equipment (${_equipment.length})',
                    style: Theme.of(context).textTheme.titleLarge),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _StatBox(
                    label: 'Mandatory Items',
                    value: '${mandatoryItems.length}',
                    color: AppColors.primary),
                const SizedBox(width: 12),
                _StatBox(
                    label: 'Usable',
                    value: '$usable',
                    color: AppColors.safeGreen),
                const SizedBox(width: 12),
                _StatBox(
                    label: 'Needs Repair',
                    value: '$needsReplace',
                    color: needsReplace > 0
                        ? AppColors.coral
                        : AppColors.safeGreen),
              ],
            ),
            if (_equipment.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text('Items',
                  style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              ..._equipment.take(5).map((item) => Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      children: [
                        Icon(
                          item.isUsable ? Icons.check_circle : Icons.cancel,
                          size: 16,
                          color: item.isUsable
                              ? AppColors.safeGreen
                              : AppColors.coral,
                        ),
                        const SizedBox(width: 8),
                        Text(item.itemName),
                        const Spacer(),
                        Text(item.condition,
                            style: TextStyle(
                              color: item.isUsable
                                  ? AppColors.safeGreen
                                  : AppColors.coral,
                              fontWeight: FontWeight.w700,
                            )),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildQRCard() {
    if (_boat?.qrCodeToken == null) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.border),
              ),
              child: const Icon(Icons.qr_code, size: 64, color: Colors.black),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('QR Code',
                      style:
                          TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                  const SizedBox(height: 4),
                  Text('Scan to identify this boat',
                      style: TextStyle(color: AppColors.textSecondary)),
                  const SizedBox(height: 8),
                  Semantics(
                    label: 'Copy QR code token',
                    button: true,
                    child: InkWell(
                      onTap: () {
                        Clipboard.setData(
                            ClipboardData(text: _boat!.qrCodeToken!));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                              content: Text('QR token copied to clipboard')),
                        );
                      },
                      child: Row(
                        children: [
                          const Icon(Icons.copy,
                              size: 16, color: AppColors.primary),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              _boat!.qrCodeToken!,
                              style: const TextStyle(
                                  color: AppColors.primary, fontSize: 12),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimelineCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.timeline, color: AppColors.deepSea),
                const SizedBox(width: 8),
                Text('Activity', style: Theme.of(context).textTheme.titleLarge),
              ],
            ),
            const SizedBox(height: 8),
            _buildTimelineItem(
              icon: Icons.add_circle,
              title: 'Boat registered',
              subtitle: 'Created ${_formatDate(_boat!.createdAt)}',
              color: AppColors.primary,
              isLast: true,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimelineItem({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
    bool isLast = false,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, size: 16, color: color),
            ),
            if (!isLast)
              Container(
                width: 2,
                height: 24,
                color: AppColors.border,
              ),
          ],
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Padding(
            padding: EdgeInsets.only(bottom: isLast ? 0 : 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                Text(subtitle,
                    style: TextStyle(
                        color: AppColors.textSecondary, fontSize: 13)),
              ],
            ),
          ),
        ),
      ],
    );
  }

  String _formatDate(DateTime dt) {
    final months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec'
    ];
    return '${dt.day} ${months[dt.month - 1]} ${dt.year}';
  }

  Color _readinessColor(String status) {
    switch (status) {
      case 'SAFE':
        return AppColors.safeGreen;
      case 'CAUTION':
        return AppColors.warningAmber;
      default:
        return AppColors.coral;
    }
  }

  Color _scoreColor(double score) {
    if (score >= 80) return AppColors.safeGreen;
    if (score >= 50) return AppColors.warningAmber;
    return AppColors.coral;
  }
}

/// Boat overview card with status badge, owner info, and key metadata.
class _BoatOverviewCard extends StatelessWidget {
  final Boat boat;

  const _BoatOverviewCard({required this.boat});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Boat name + status
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(boat.name,
                          style: Theme.of(context)
                              .textTheme
                              .headlineSmall
                              ?.copyWith(fontWeight: FontWeight.w900)),
                      if (boat.registrationNumber != null)
                        Text(boat.registrationNumber!,
                            style: Theme.of(context).textTheme.bodyMedium),
                    ],
                  ),
                ),
                BoatStatusBadge(boat.status, fontSize: 14),
              ],
            ),
            const SizedBox(height: 16),
            // Key info grid
            Row(
              children: [
                Expanded(
                    child: _DetailTile(
                        icon: Icons.verified,
                        label: 'Verification',
                        value: boat.verificationStatus)),
                Expanded(
                    child: _DetailTile(
                        icon: Icons.calendar_today,
                        label: 'Year Built',
                        value: boat.yearBuilt?.toString() ?? '-')),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                    child: _DetailTile(
                        icon: Icons.build,
                        label: 'Engine',
                        value: boat.engineMake ?? boat.engineType ?? '-')),
                Expanded(
                    child: _DetailTile(
                        icon: Icons.speed,
                        label: 'HP',
                        value: boat.engineHorsepower?.toString() ?? '-')),
              ],
            ),
            if (boat.vesselClass != null || boat.hullMaterial != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  if (boat.vesselClass != null)
                    Expanded(
                        child: _DetailTile(
                            icon: Icons.category,
                            label: 'Class',
                            value: boat.vesselClass!)),
                  if (boat.hullMaterial != null)
                    Expanded(
                        child: _DetailTile(
                            icon: Icons.directions_boat,
                            label: 'Hull',
                            value: boat.hullMaterial!)),
                ],
              ),
            ],
            if (boat.lengthMeters != null ||
                boat.fuelCapacityLiters != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  if (boat.lengthMeters != null)
                    Expanded(
                        child: _DetailTile(
                            icon: Icons.straighten,
                            label: 'Length',
                            value:
                                '${boat.lengthMeters!.toStringAsFixed(1)}m')),
                  if (boat.fuelCapacityLiters != null)
                    Expanded(
                        child: _DetailTile(
                            icon: Icons.local_gas_station,
                            label: 'Fuel',
                            value:
                                '${boat.fuelCapacityLiters!.toStringAsFixed(0)}L')),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Small detail tile for metadata display.
class _DetailTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _DetailTile(
      {required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        children: [
          Icon(icon, size: 16, color: AppColors.textSecondary),
          const SizedBox(width: 6),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textDisabled,
                      fontWeight: FontWeight.w600)),
              Text(value,
                  style: const TextStyle(
                      fontSize: 14, fontWeight: FontWeight.w600)),
            ],
          ),
        ],
      ),
    );
  }
}

/// Quick action grid for the boat detail screen.
class _QuickActionGrid extends StatelessWidget {
  final Boat boat;

  const _QuickActionGrid({required this.boat});

  @override
  Widget build(BuildContext context) {
    final actions = [
      _QuickAction(
          icon: Icons.description,
          label: 'Documents',
          color: AppColors.primary,
          onTap: () {
            Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => BoatDocumentsScreen(boatId: boat.id)));
          }),
      _QuickAction(
          icon: Icons.groups,
          label: 'Crew',
          color: AppColors.safeGreen,
          onTap: () {
            Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => BoatCrewScreen(boatId: boat.id)));
          }),
      _QuickAction(
          icon: Icons.inventory_2,
          label: 'Equipment',
          color: AppColors.warningAmber,
          onTap: () {
            Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => BoatEquipmentScreen(boatId: boat.id)));
          }),
      _QuickAction(
          icon: Icons.qr_code,
          label: 'QR Code',
          color: Colors.black87,
          onTap: () {
            if (boat.qrCodeToken != null) {
              Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => BoatQRScreen(boatId: boat.id)));
            }
          }),
      _QuickAction(
          icon: Icons.shield_outlined,
          label: 'Readiness',
          color: AppColors.coral,
          onTap: () {
            Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => TripReadinessScreen(boatId: boat.id)));
          }),
      _QuickAction(
          icon: Icons.edit,
          label: 'Edit',
          color: AppColors.deepSea,
          onTap: () {}),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.only(left: 4, bottom: 8),
              child: Text('Quick Actions',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
            ),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                crossAxisSpacing: 8,
                mainAxisSpacing: 8,
                childAspectRatio: 1.0,
              ),
              itemCount: actions.length,
              itemBuilder: (context, index) {
                final action = actions[index];
                return Semantics(
                  label: action.label,
                  button: true,
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(16),
                      onTap: action.onTap,
                      child: Container(
                        decoration: BoxDecoration(
                          color: action.color.withValues(alpha: 0.06),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                              color: action.color.withValues(alpha: 0.15)),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(action.icon, color: action.color, size: 28),
                            const SizedBox(height: 6),
                            Text(
                              action.label,
                              style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: action.color),
                              textAlign: TextAlign.center,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// Data class for quick actions.
class _QuickAction {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  _QuickAction(
      {required this.icon,
      required this.label,
      required this.color,
      required this.onTap});
}

/// Simple stat box for count display.
class _StatBox extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatBox(
      {required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Column(
          children: [
            Text(value,
                style: TextStyle(
                    fontSize: 22, fontWeight: FontWeight.w900, color: color)),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textSecondary)),
          ],
        ),
      ),
    );
  }
}
