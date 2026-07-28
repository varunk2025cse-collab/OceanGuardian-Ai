import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';
import '../l10n/app_localizations.dart';
import '../services/local_db_service.dart';
import '../services/location_service.dart';
import '../theme/app_theme.dart';
import '../widgets/freshness_badge.dart';

/// Map view backed by OpenStreetMap tiles.
///
/// Two modes:
///  - No args: shows the logged-in fisherman's own offline GPS trail
///    (read straight from the local outbox, so it works mid-trip with
///    zero signal - only the OSM *tiles* need a connection, the trail
///    data itself does not). When a trip is active, the trail is scoped
///    to that trip's points rather than the whole device history.
///  - focusLatitude/focusLongitude supplied: a family member viewing one
///    fisherman's last known position from the Family dashboard, with the
///    server-computed freshness state so a stale point is never shown as
///    if it were live.
///
/// Note: this MVP does not cache map tiles for fully offline viewing -
/// the trail/marker logic works offline, but you'll see blank grey tiles
/// without a connection. Offline tile caching (e.g. via
/// flutter_map_tile_caching) is a natural Stage 2 addition once the MVP
/// is validated.
class LocationScreen extends StatefulWidget {
  final double? focusLatitude;
  final double? focusLongitude;
  final String? title;
  final String? focusFreshness;
  final DateTime? focusLastSeenAt;

  const LocationScreen({
    super.key,
    this.focusLatitude,
    this.focusLongitude,
    this.title,
    this.focusFreshness,
    this.focusLastSeenAt,
  });

  @override
  State<LocationScreen> createState() => _LocationScreenState();
}

class _LocationScreenState extends State<LocationScreen> {
  List<LatLng> _trail = [];
  int _pendingCount = 0;
  bool _loading = true;
  DateTime? _lastRecordedAt;

  bool get _isFocusMode => widget.focusLatitude != null && widget.focusLongitude != null;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (_isFocusMode) {
      setState(() => _loading = false);
      return;
    }
    final rows = await LocalDbService.instance.recentLocations(limit: 500);
    final currentTripId = LocationService.instance.currentTripId;
    // If a trip is active, scope the drawn trail to that trip's points so
    // the map reads as "this voyage's route", not the whole device history.
    final scoped = currentTripId == null ? rows : rows.where((r) => r['trip_id'] == currentTripId).toList();
    final points = scoped.isNotEmpty ? scoped : rows;
    final pendingCount = await LocalDbService.instance.unsyncedLocationCount();
    setState(() {
      // recentLocations() is newest-first; the polyline wants oldest-first.
      _trail = points.reversed.map((r) => LatLng(r['latitude'] as double, r['longitude'] as double)).toList();
      _lastRecordedAt = points.isNotEmpty ? DateTime.parse(points.first['recorded_at'] as String) : null;
      _pendingCount = pendingCount;
      _loading = false;
    });
  }

  Future<void> _captureNow() async {
    await LocationService.instance.captureOnce();
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final center = _isFocusMode
        ? LatLng(widget.focusLatitude!, widget.focusLongitude!)
        : (_trail.isNotEmpty ? _trail.last : const LatLng(11.0, 79.85)); // Tamil Nadu coast default

    return Scaffold(
      appBar: AppBar(title: Text(widget.title ?? t.locationTitle)),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                if (_isFocusMode && widget.focusFreshness != null)
                  Container(
                    width: double.infinity,
                    color: AppColors.deepSea,
                    padding: const EdgeInsets.all(12),
                    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      FreshnessBadge(widget.focusFreshness!),
                      if (widget.focusLastSeenAt != null) ...[
                        const SizedBox(width: 8),
                        Text(
                          DateFormat('dd MMM, hh:mm a').format(widget.focusLastSeenAt!.toLocal()),
                          style: const TextStyle(color: Colors.white),
                        ),
                      ],
                    ]),
                  ),
                if (!_isFocusMode)
                  Container(
                    width: double.infinity,
                    color: AppColors.deepSea,
                    padding: const EdgeInsets.all(12),
                    child: Column(children: [
                      Text(
                        t.locationPendingSync(_pendingCount),
                        style: const TextStyle(color: Colors.white),
                        textAlign: TextAlign.center,
                      ),
                      if (_lastRecordedAt != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            DateFormat('dd MMM, hh:mm a').format(_lastRecordedAt!.toLocal()),
                            style: const TextStyle(color: Colors.white70, fontSize: 12),
                          ),
                        ),
                    ]),
                  ),
                Expanded(
                  child: FlutterMap(
                    options: MapOptions(initialCenter: center, initialZoom: 11),
                    children: [
                      TileLayer(
                        urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                        userAgentPackageName: 'com.oceanguardian.mvp',
                      ),
                      if (!_isFocusMode && _trail.length > 1)
                        PolylineLayer(polylines: [
                          Polyline(points: _trail, strokeWidth: 4, color: AppColors.seaFoam),
                        ]),
                      MarkerLayer(markers: [
                        Marker(
                          point: center,
                          width: 44,
                          height: 44,
                          child: const Icon(Icons.directions_boat, color: AppColors.coral, size: 36),
                        ),
                      ]),
                    ],
                  ),
                ),
              ],
            ),
      floatingActionButton: _isFocusMode
          ? null
          : FloatingActionButton(onPressed: _captureNow, backgroundColor: AppColors.deepSea, child: const Icon(Icons.my_location, color: Colors.white)),
    );
  }
}
