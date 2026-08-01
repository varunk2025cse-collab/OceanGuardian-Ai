import 'dart:convert';

import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';

class BoatMaintenanceScreen extends StatefulWidget {
  final int boatId;

  const BoatMaintenanceScreen({super.key, required this.boatId});

  @override
  State<BoatMaintenanceScreen> createState() => _BoatMaintenanceScreenState();
}

class _BoatMaintenanceScreenState extends State<BoatMaintenanceScreen> {
  bool _loading = true;
  List<dynamic> _records = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await ApiClient.instance.get('/api/v2/boat-health/${widget.boatId}/maintenance-due');
      if (data is Map) {
        final items = data['upcoming'] ?? data['maintenance'] ?? data;
        _records = (items is List) ? items.cast<dynamic>().toList() : [];
      } else if (data is List) {
        _records = data;
      } else {
        _records = [];
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: const Text('Maintenance')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null && _records.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline, size: 48, color: AppColors.coral),
                        const SizedBox(height: 16),
                        Text(_error!, textAlign: TextAlign.center),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _records.isEmpty
                      ? ListView(
                          children: const [
                            SizedBox(height: 120),
                            Icon(Icons.build_outlined, size: 64, color: AppColors.textDisabled),
                            SizedBox(height: 16),
                            Text('No maintenance records yet', style: TextStyle(color: AppColors.textSecondary)),
                          ],
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: _records.length,
                          itemBuilder: (context, index) {
                            final record = _records[index];
                            final title = record is Map
                                ? (record['title'] ?? record['description'] ?? record['task'] ?? record['status'] ?? 'Maintenance')
                                : record.toString();
                            final detail = record is Map ? jsonEncode(record) : '';
                            return Card(
                              margin: const EdgeInsets.only(bottom: 12),
                              child: ListTile(
                                leading: const Icon(Icons.build, color: AppColors.deepSea),
                                title: Text(title is String ? title : title.toString()),
                                subtitle: detail.isNotEmpty
                                    ? Text(
                                        detail,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(fontSize: 12),
                                      )
                                    : null,
                              ),
                            );
                          },
                        ),
                ),
    );
  }
}
