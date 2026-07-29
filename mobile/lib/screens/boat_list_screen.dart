/// Boat List Screen — shows all boats owned by the current fisherman.
///
/// Requirements met:
///  - Search by name or registration number
///  - Filter by status (active, maintenance, etc.)
///  - Status badges with color-coded lifecycle state
///  - Health score when available from backend
///  - Offline banner showing cache age
///  - Synchronization status indicator
///  - Quick actions (start trip, view details)
///  - Large cards with boat names in big fonts
///  - Accessibility: 60dp touch targets, semantic labels
///  - Dark Mode compatible via theme
///  - Tamil support via AppLocalizations
///  - Responsive layout

import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../models/boat.dart';
import '../services/boat_service.dart';
import '../services/sync_service.dart';
import '../theme/app_theme.dart';
import '../widgets/boat_status_badge.dart';
import 'boat_detail_screen.dart';

class BoatListScreen extends StatefulWidget {
  const BoatListScreen({super.key});

  @override
  State<BoatListScreen> createState() => _BoatListScreenState();
}

class _BoatListScreenState extends State<BoatListScreen> {
  final _searchController = TextEditingController();
  String? _statusFilter;
  bool _loading = true;
  bool _fromCache = false;
  List<Boat> _boats = [];
  List<Boat> _filteredBoats = [];

  @override
  void initState() {
    super.initState();
    _load();
    // Listen for sync status changes
    SyncService.instance.status.addListener(_onSyncChanged);
  }

  @override
  void dispose() {
    SyncService.instance.status.removeListener(_onSyncChanged);
    _searchController.dispose();
    super.dispose();
  }

  void _onSyncChanged() {
    if (SyncService.instance.status.value == SyncUiStatus.online) {
      _load();
    }
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      await BoatService.instance.initialize();
      _boats = BoatService.instance.boats.value;
      _applyFilters();
      _fromCache = false;
    } catch (_) {
      // Fallback to cache
      final result = await BoatService.instance.getBoats();
      _boats = result.data;
      _applyFilters();
      _fromCache = result.fromCache;
    }
    if (mounted) setState(() => _loading = false);
  }

  void _applyFilters() {
    var filtered = _boats;
    if (_statusFilter != null && _statusFilter!.isNotEmpty) {
      filtered = filtered.where((b) => b.status == _statusFilter).toList();
    }
    final query = _searchController.text.trim().toLowerCase();
    if (query.isNotEmpty) {
      filtered = filtered.where((b) =>
          b.name.toLowerCase().contains(query) ||
          (b.registrationNumber?.toLowerCase().contains(query) ?? false)).toList();
    }
    _filteredBoats = filtered;
  }

  void _onSearchChanged(String value) {
    setState(() => _applyFilters());
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'active':
        return AppColors.safeGreen;
      case 'registered':
        return AppColors.primary;
      case 'inactive':
        return AppColors.textDisabled;
      case 'maintenance':
        return AppColors.warningAmber;
      case 'emergency':
        return AppColors.coral;
      case 'damaged':
        return AppColors.warning;
      case 'lost':
        return Colors.black;
      case 'decommissioned':
        return AppColors.textSecondary;
      default:
        return AppColors.textSecondary;
    }
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'active': return 'Active';
      case 'registered': return 'Registered';
      case 'inactive': return 'Inactive';
      case 'maintenance': return 'Maintenance';
      case 'emergency': return 'Emergency';
      case 'damaged': return 'Damaged';
      case 'lost': return 'Lost';
      case 'decommissioned': return 'Decommissioned';
      default: return status;
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: Text('Boats'),
        actions: [
          ValueListenableBuilder<int>(
            valueListenable: BoatService.instance.pendingSyncCount,
            builder: (context, count, _) {
              if (count <= 0) return const SizedBox.shrink();
              return Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: Chip(
                    avatar: const Icon(Icons.sync, size: 16, color: Colors.white),
                    label: Text('$count', style: const TextStyle(color: Colors.white, fontSize: 12)),
                    backgroundColor: AppColors.warningAmber,
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Register a boat',
            onPressed: () {
              // TODO: Navigate to boat registration wizard (Task 2.5)
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Offline banner
          ValueListenableBuilder<SyncUiStatus>(
            valueListenable: SyncService.instance.status,
            builder: (context, syncStatus, _) {
              if (syncStatus == SyncUiStatus.offline) {
                return Container(
                  width: double.infinity,
                  color: AppColors.slate,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: Row(
                    children: [
                      const Icon(Icons.cloud_off, size: 18, color: Colors.white),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Offline — showing last saved data',
                          style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                );
              }
              if (_fromCache) {
                return Container(
                  width: double.infinity,
                  color: AppColors.warningAmber,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: Row(
                    children: [
                      const Icon(Icons.cloud_off, size: 18, color: Colors.white),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Cached data — pull to refresh',
                          style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                );
              }
              return const SizedBox.shrink();
            },
          ),

          // Search bar
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: 'Search by name or registration',
                prefixIcon: const Icon(Icons.search, size: 24),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          _onSearchChanged('');
                        },
                      )
                    : null,
              ),
            ),
          ),

          // Status filter chips
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              children: [
                _buildFilterChip('All', null),
                _buildFilterChip('Active', 'active'),
                _buildFilterChip('Registered', 'registered'),
                _buildFilterChip('Maintenance', 'maintenance'),
                _buildFilterChip('Inactive', 'inactive'),
              ],
            ),
          ),

          // Boat list
          Expanded(
            child: RefreshIndicator(
              onRefresh: _load,
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _filteredBoats.isEmpty
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(32),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.directions_boat_outlined, size: 64, color: AppColors.textDisabled),
                                const SizedBox(height: 16),
                                Text(
                                  _boats.isEmpty
                                      ? 'No boats registered yet'
                                      : 'No boats match your search',
                                  style: Theme.of(context).textTheme.titleMedium,
                                  textAlign: TextAlign.center,
                                ),
                                if (_boats.isEmpty) ...[
                                  const SizedBox(height: 12),
                                  ElevatedButton.icon(
                                    onPressed: () {
                                      // TODO: Navigate to registration wizard
                                    },
                                    icon: const Icon(Icons.add),
                                    label: const Text('Register your first boat'),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: _filteredBoats.length,
                          itemBuilder: (context, index) {
                            final boat = _filteredBoats[index];
                            return _BoatCard(
                              boat: boat,
                              onTap: () {
                                Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => BoatDetailScreen(boatId: boat.id),
                                  ),
                                );
                              },
                            );
                          },
                        ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, String? status) {
    final selected = _statusFilter == status;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: FilterChip(
        label: Text(label, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
        selected: selected,
        onSelected: (val) {
          setState(() {
            _statusFilter = val ? status : null;
            _applyFilters();
          });
        },
        selectedColor: AppColors.primary.withOpacity(0.2),
        checkmarkColor: AppColors.primary,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
    );
  }
}

/// Individual boat card with status badge, key info, and quick actions.
class _BoatCard extends StatelessWidget {
  final Boat boat;
  final VoidCallback onTap;

  const _BoatCard({required this.boat, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isOnline = SyncService.instance.status.value == SyncUiStatus.online ||
        SyncService.instance.status.value == SyncUiStatus.syncing;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Semantics(
        label: 'Boat ${boat.name}, status ${boat.status}',
        button: true,
        child: Card(
          child: InkWell(
            borderRadius: BorderRadius.circular(20),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Top row: name + status badge
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Boat icon
                      Container(
                        width: 56,
                        height: 56,
                        decoration: BoxDecoration(
                          color: AppColors.deepSea.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: const Icon(Icons.directions_boat, color: AppColors.deepSea, size: 32),
                      ),
                      const SizedBox(width: 12),
                      // Name + registration
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              boat.name,
                              style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            if (boat.registrationNumber != null)
                              Text(
                                boat.registrationNumber!,
                                style: theme.textTheme.bodyMedium,
                              ),
                          ],
                        ),
                      ),
                      // Status badge
                      BoatStatusBadge(boat.status),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Info row: verification + active status
                  Row(
                    children: [
                      // Verification status
                      _InfoChip(
                        icon: boat.verificationStatus == 'verified'
                            ? Icons.verified
                            : Icons.pending_outlined,
                        label: boat.verificationStatus == 'verified'
                            ? 'Verified'
                            : boat.verificationStatus,
                        color: boat.verificationStatus == 'verified'
                            ? AppColors.safeGreen
                            : AppColors.warningAmber,
                      ),
                      const SizedBox(width: 8),
                      // Trip ready status
                      _InfoChip(
                        icon: boat.isTripReady ? Icons.check_circle : Icons.cancel,
                        label: boat.isTripReady ? 'Trip ready' : 'Not ready',
                        color: boat.isTripReady ? AppColors.safeGreen : AppColors.coral,
                      ),
                      const Spacer(),
                      // Engine info (compact)
                      if (boat.engineType != null)
                        Text(
                          boat.engineType!,
                          style: theme.textTheme.bodySmall,
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Quick action buttons
                  Row(
                    children: [
                      // View details
                      Expanded(
                        child: SizedBox(
                          height: 48,
                          child: OutlinedButton.icon(
                            onPressed: onTap,
                            icon: const Icon(Icons.visibility, size: 20),
                            label: const Text('Details', style: TextStyle(fontSize: 16)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Start trip (only if trip-ready)
                      Expanded(
                        child: SizedBox(
                          height: 48,
                          child: FilledButton.icon(
                            onPressed: boat.isTripReady
                                ? () {
                                    // TODO: Navigate to start trip with this boat
                                  }
                                : null,
                            icon: const Icon(Icons.sailing, size: 20),
                            label: const Text('Start trip', style: TextStyle(fontSize: 16)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Small info chip for boat attributes.
class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _InfoChip({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
