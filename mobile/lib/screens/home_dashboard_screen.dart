import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../models/trip.dart';
import '../models/weather_alert.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/local_db_service.dart';
import '../services/location_service.dart';
import '../services/reference_data_service.dart';
import '../services/sync_service.dart';
import '../services/trip_service.dart';
import '../theme/app_theme.dart';
import '../widgets/safety_state_badge.dart';
import 'auth/login_screen.dart';
import 'boat_list_screen.dart';
import 'location_screen.dart';
import 'sos_screen.dart';
import 'start_trip_screen.dart';

class HomeDashboardScreen extends StatefulWidget {
  const HomeDashboardScreen({super.key});

  @override
  State<HomeDashboardScreen> createState() => _HomeDashboardScreenState();
}

class _HomeDashboardScreenState extends State<HomeDashboardScreen> {
  List<WeatherAlertInfo> _topAlerts = [];
  int _pendingLocations = 0;
  int _pendingSos = 0;
  Map<String, dynamic>? _safety;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final lastFix = await LocationService.instance.lastKnownLocal();
    final weather =
        await ReferenceDataService.instance.weatherAlerts(lat: lastFix?.latitude, lon: lastFix?.longitude);
    final pendingLocations = await LocalDbService.instance.unsyncedLocationCount();
    final pendingSos = (await LocalDbService.instance.unsyncedSos()).length;
    await TripService.instance.refreshActiveTrip();
    Map<String, dynamic>? safety;
    try {
      safety = await ApiClient.instance.getV2('/safety/') as Map<String, dynamic>?;
    } catch (_) {
      safety = null; // Offline or server unreachable — card shows UNKNOWN, never a stale claim.
    }
    if (!mounted) return;
    setState(() {
      _topAlerts = weather.items.where((a) => a.severity != 'advisory').toList();
      _pendingLocations = pendingLocations;
      _pendingSos = pendingSos;
      _safety = safety;
    });
  }

  Future<void> _startTrip() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const StartTripScreen()));
    await TripService.instance.refreshActiveTrip();
  }

  Future<void> _endTrip() async {
    final t = AppLocalizations.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(t.tripEndConfirmTitle),
        content: Text(t.tripEndConfirmBody),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: Text(t.cancel)),
          FilledButton(onPressed: () => Navigator.of(ctx).pop(true), child: Text(t.tripEndCta)),
        ],
      ),
    );
    if (confirmed == true) {
      await TripService.instance.endTrip();
    }
  }

  Future<void> _markReturning() async {
    await TripService.instance.markReturning();
  }

  Future<void> _logout() async {
    LocationService.instance.stop();
    await AuthService.instance.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(MaterialPageRoute(builder: (_) => const LoginScreen()), (r) => false);
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final user = AuthService.instance.currentUser;

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: Text(t.appTitle),
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Center(child: _SyncStatusChip()),
          ),
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout, tooltip: t.logout),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(t.homeGreeting(user?.fullName ?? ''), style: Theme.of(context).textTheme.headlineMedium),
            if (user?.boatName != null) Text(user!.boatName!, style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 20),

            if (user?.isFisherman == true) ...[
              ValueListenableBuilder<Trip?>(
                valueListenable: TripService.instance.activeTrip,
                builder: (context, trip, _) => _TripCard(
                  trip: trip,
                  onStart: _startTrip,
                  onMarkReturning: _markReturning,
                  onEnd: _endTrip,
                ),
              ),
              const SizedBox(height: 12),
              if (_safety != null) _MySafetyCard(safety: _safety!),
              if (_safety != null) const SizedBox(height: 12),
              if (_safety != null && _safety!['nearest_harbor_name'] != null) ...[
                _NavigationCard(safety: _safety!),
                const SizedBox(height: 12),
              ],
            ],

            // Critical hazard banner - the one thing on this screen that
            // must never be missed if it's present.
            if (_topAlerts.isNotEmpty)
              Card(
                color: AppColors.coral,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(children: [
                    const Icon(Icons.warning_amber_rounded, color: Colors.white, size: 32),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(_topAlerts.first.title,
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                    ),
                  ]),
                ),
              ),
            const SizedBox(height: 12),

            if (_pendingSos > 0)
              Card(
                color: AppColors.warningAmber,
                child: ListTile(
                  leading: const Icon(Icons.cloud_off, color: Colors.white),
                  title: Text('$_pendingSos SOS alert(s) waiting for signal to send',
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
                ),
              ),

            Card(
              child: ListTile(
                leading: const Icon(Icons.directions_boat, color: AppColors.deepSea),
                title: const Text('My Boats', style: TextStyle(fontWeight: FontWeight.w700)),
                subtitle: const Text('Manage boats, documents, crew'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const BoatListScreen())),
              ),
            ),
            const SizedBox(height: 8),
            Card(
              child: ListTile(
                leading: const Icon(Icons.gps_fixed, color: AppColors.deepSea),
                title: Text(_pendingLocations == 0
                    ? 'GPS trail synced'
                    : '$_pendingLocations location point(s) waiting to sync'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const LocationScreen())),
              ),
            ),
            const SizedBox(height: 8),

            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(backgroundColor: AppColors.coral),
                icon: const Icon(Icons.sos),
                label: Text(t.sosButton),
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SosScreen())),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// ONLINE/OFFLINE/SYNCING/SYNC_ERROR — always visible, never inferred by
/// the fisherman from silence. See SyncService.status.
class _SyncStatusChip extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<SyncUiStatus>(
      valueListenable: SyncService.instance.status,
      builder: (context, status, _) {
        final t = AppLocalizations.of(context)!;
        final (label, color, icon) = switch (status) {
          SyncUiStatus.online => (t.syncOnline, AppColors.safeGreen, Icons.cloud_done),
          SyncUiStatus.offline => (t.syncOffline, AppColors.slate, Icons.cloud_off),
          SyncUiStatus.syncing => (t.syncSyncing, AppColors.deepSea, Icons.sync),
          SyncUiStatus.syncError => (t.syncError, AppColors.warningAmber, Icons.sync_problem),
        };
        return Chip(
          avatar: Icon(icon, size: 16, color: Colors.white),
          label: Text(label, style: const TextStyle(color: Colors.white, fontSize: 12)),
          backgroundColor: color,
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        );
      },
    );
  }
}

/// "MY SAFETY" — server-computed safety state (backend
/// app/services/safety_engine.py), never inferred client-side. Shown
/// whenever a state was successfully fetched; UNKNOWN (no trip in
/// progress, or nothing fetched yet) renders the same way as any other
/// state rather than being hidden, so silence never reads as "safe".
class _MySafetyCard extends StatelessWidget {
  final Map<String, dynamic> safety;
  const _MySafetyCard({required this.safety});

  @override
  Widget build(BuildContext context) {
    final reasons = (safety['reasons'] as List?)?.cast<String>() ?? const [];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.shield_outlined, color: AppColors.deepSea),
              const SizedBox(width: 8),
              const Text('My Safety', style: TextStyle(fontWeight: FontWeight.w800)),
              const Spacer(),
              SafetyStateBadge(safety['safety_state'] as String? ?? 'UNKNOWN'),
            ]),
            if (reasons.isNotEmpty) ...[
              const SizedBox(height: 8),
              ...reasons.take(2).map((r) => Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text('• $r', style: Theme.of(context).textTheme.bodySmall),
                  )),
            ],
          ],
        ),
      ),
    );
  }
}

/// Navigation AI (docs/NAVIGATION_AI.md) — straight-line bearing/distance
/// to the nearest known safe harbor, computed server-side and returned
/// alongside the safety state (no extra network call). Deliberately
/// simple: a compass heading and distance, not a route around obstacles —
/// exactly what a fisherman could plot by hand, computed for them.
class _NavigationCard extends StatelessWidget {
  final Map<String, dynamic> safety;
  const _NavigationCard({required this.safety});

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final name = safety['nearest_harbor_name'] as String;
    final km = (safety['nearest_harbor_km'] as num).toDouble();
    final bearing = (safety['nearest_harbor_bearing'] as num?)?.toDouble() ?? 0.0;
    final direction = safety['nearest_harbor_direction'] as String? ?? '-';
    final etaMinutes = safety['nearest_harbor_eta_minutes'] as int?;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            // A simple compass arrow rotated to the real bearing — readable
            // at a glance, no map-reading skill required.
            Transform.rotate(
              angle: bearing * (3.14159265 / 180),
              child: const Icon(Icons.navigation, color: AppColors.deepSea, size: 40),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(t.navNearestHarbor, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12, color: AppColors.slate)),
                  Text(name, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                  Text(t.navDirectionLabel(direction), style: const TextStyle(color: AppColors.deepSea, fontWeight: FontWeight.w700)),
                  Text(t.navDistanceAway(km.toStringAsFixed(1))),
                  if (etaMinutes != null)
                    Text(t.navEta(etaMinutes), style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Trip lifecycle CTA: start a trip when none is active, or show status +
/// returning/end actions when one is. See docs/V2_CORE_IMPLEMENTATION_PLAN.md
/// Step 6 — trip status is intentionally independent of connectivity, so
/// this card never claims a trip is inactive just because the phone is
/// offline right now.
class _TripCard extends StatelessWidget {
  final Trip? trip;
  final VoidCallback onStart;
  final VoidCallback onMarkReturning;
  final VoidCallback onEnd;

  const _TripCard({required this.trip, required this.onStart, required this.onMarkReturning, required this.onEnd});

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    if (trip == null) {
      return Card(
        child: ListTile(
          leading: const Icon(Icons.sailing, color: AppColors.deepSea),
          title: Text(t.tripNoActive),
          trailing: FilledButton(onPressed: onStart, child: Text(t.tripStartCta)),
        ),
      );
    }
    final statusLabel = switch (trip!.status) {
      'returning' => t.tripReturning,
      'emergency' => t.tripEmergency,
      _ => t.tripActive,
    };
    return Card(
      color: trip!.status == 'emergency' ? AppColors.coral.withOpacity(0.08) : null,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.sailing, color: AppColors.deepSea),
              const SizedBox(width: 8),
              Text(statusLabel, style: const TextStyle(fontWeight: FontWeight.w800)),
            ]),
            if (trip!.destination != null) Text(trip!.destination!),
            Text(t.tripStartedSince(trip!.startTime.toLocal().toString())),
            const SizedBox(height: 12),
            Row(children: [
              if (trip!.status == 'active')
                OutlinedButton(onPressed: onMarkReturning, child: Text(t.tripMarkReturning)),
              const SizedBox(width: 8),
              FilledButton(onPressed: onEnd, child: Text(t.tripEndCta)),
            ]),
          ],
        ),
      ),
    );
  }
}
