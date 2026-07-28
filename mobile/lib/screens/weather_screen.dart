import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../models/weather_alert.dart';
import '../services/location_service.dart';
import '../services/reference_data_service.dart';
import '../theme/app_theme.dart';

class WeatherScreen extends StatefulWidget {
  const WeatherScreen({super.key});

  @override
  State<WeatherScreen> createState() => _WeatherScreenState();
}

class _WeatherScreenState extends State<WeatherScreen> {
  bool _loading = true;
  bool _fromCache = false;
  DateTime? _asOf;
  List<WeatherAlertInfo> _alerts = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final lastFix = await LocationService.instance.lastKnownLocal();
    final result = await ReferenceDataService.instance.weatherAlerts(
      lat: lastFix?.latitude,
      lon: lastFix?.longitude,
    );
    if (!mounted) return;
    setState(() {
      _alerts = result.items;
      _fromCache = result.fromCache;
      _asOf = result.asOf;
      _loading = false;
    });
  }

  Color _severityColor(String severity) {
    switch (severity) {
      case 'danger':
        return AppColors.coral;
      case 'warning':
        return AppColors.warningAmber;
      default:
        return AppColors.seaFoam;
    }
  }

  String _severityLabel(AppLocalizations t, String severity) {
    switch (severity) {
      case 'danger':
        return t.severityDanger;
      case 'warning':
        return t.severityWarning;
      default:
        return t.severityAdvisory;
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: Text(t.weatherTitle)),
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
                        Expanded(
                          child: Text(
                            _asOf == null ? t.weatherOffline : '${t.weatherOffline} (${_asOf!.toLocal()})',
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                        ),
                      ]),
                    ),
                  if (_alerts.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 48),
                      child: Column(children: [
                        const Icon(Icons.check_circle, color: AppColors.safeGreen, size: 48),
                        const SizedBox(height: 12),
                        Text(t.weatherNoAlerts, textAlign: TextAlign.center),
                      ]),
                    )
                  else
                    ..._alerts.map((alert) => Card(
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: _severityColor(alert.severity),
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Text(_severityLabel(t, alert.severity),
                                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12)),
                                  ),
                                ]),
                                const SizedBox(height: 8),
                                Text(alert.title, style: Theme.of(context).textTheme.titleLarge),
                                const SizedBox(height: 4),
                                Text(alert.description, style: Theme.of(context).textTheme.bodyLarge),
                                if (alert.source != null) ...[
                                  const SizedBox(height: 8),
                                  Text('Source: ${alert.source}', style: Theme.of(context).textTheme.bodyMedium),
                                ],
                              ],
                            ),
                          ),
                        )),
                ],
              ),
      ),
    );
  }
}
