import 'package:flutter/material.dart';
import '../models/boat_equipment.dart';
import '../services/boat_service.dart';
import '../theme/app_theme.dart';

class BoatEquipmentScreen extends StatefulWidget {
  final int boatId;
  const BoatEquipmentScreen({super.key, required this.boatId});

  @override
  State<BoatEquipmentScreen> createState() => _BoatEquipmentScreenState();
}

class _BoatEquipmentScreenState extends State<BoatEquipmentScreen> {
  bool _loading = true;
  List<BoatEquipmentItem> _equipment = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final result = await BoatService.instance.getEquipment(widget.boatId);
      _equipment = result.data;
    } catch (e) {
      _error = e.toString();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Color _conditionColor(String condition) {
    switch (condition) {
      case 'good': return AppColors.safeGreen;
      case 'fair': return AppColors.warningAmber;
      case 'poor': return AppColors.warning;
      case 'missing': return AppColors.coral;
      default: return AppColors.textSecondary;
    }
  }

  IconData _conditionIcon(String condition) {
    switch (condition) {
      case 'good': return Icons.check_circle;
      case 'fair': return Icons.warning_amber_rounded;
      case 'poor': return Icons.error_outline;
      case 'missing': return Icons.cancel;
      default: return Icons.help_outline;
    }
  }

  Future<void> _showAddEquipmentDialog() async {
    final nameCtrl = TextEditingController();
    final qtyCtrl = TextEditingController(text: '1');
    String category = 'life_saving';
    String condition = 'good';
    bool isMandatory = false;

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Add Equipment', style: TextStyle(fontWeight: FontWeight.w800)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  decoration: const InputDecoration(labelText: 'Item Name *', prefixIcon: Icon(Icons.inventory_2)),
                  textCapitalization: TextCapitalization.words,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: category,
                  decoration: const InputDecoration(labelText: 'Category', prefixIcon: Icon(Icons.category)),
                  items: const [
                    DropdownMenuItem(value: 'life_saving', child: Text('Life Saving')),
                    DropdownMenuItem(value: 'fire_safety', child: Text('Fire Safety')),
                    DropdownMenuItem(value: 'communication', child: Text('Communication')),
                    DropdownMenuItem(value: 'navigation', child: Text('Navigation')),
                    DropdownMenuItem(value: 'fishing_gear', child: Text('Fishing Gear')),
                    DropdownMenuItem(value: 'engine', child: Text('Engine')),
                    DropdownMenuItem(value: 'other', child: Text('Other')),
                  ],
                  onChanged: (v) { if (v != null) setDialogState(() => category = v); },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: condition,
                  decoration: const InputDecoration(labelText: 'Condition', prefixIcon: Icon(Icons.health_and_safety)),
                  items: const [
                    DropdownMenuItem(value: 'good', child: Text('Good ●')),
                    DropdownMenuItem(value: 'fair', child: Text('Fair ●')),
                    DropdownMenuItem(value: 'poor', child: Text('Poor ●')),
                    DropdownMenuItem(value: 'missing', child: Text('Missing ●')),
                  ],
                  onChanged: (v) { if (v != null) setDialogState(() => condition = v); },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: qtyCtrl,
                  decoration: const InputDecoration(labelText: 'Quantity', prefixIcon: Icon(Icons.numbers)),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 8),
                SwitchListTile(
                  title: const Text('Mandatory Safety Item'),
                  value: isMandatory,
                  onChanged: (v) => setDialogState(() => isMandatory = v),
                  contentPadding: EdgeInsets.zero,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Cancel')),
            FilledButton(
              onPressed: () async {
                if (nameCtrl.text.trim().isEmpty) return;
                Navigator.of(ctx).pop();
                setState(() => _loading = true);
                try {
                  await BoatService.instance.assignCrew(widget.boatId, {
                    'item_name': nameCtrl.text.trim(),
                    'category': category,
                    'condition': condition,
                    'quantity': int.tryParse(qtyCtrl.text) ?? 1,
                    'is_mandatory': isMandatory,
                  });
                  await _load();
                } catch (e) {
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
                } finally {
                  if (mounted) setState(() => _loading = false);
                }
              },
              child: const Text('Add'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final grouped = <String, List<BoatEquipmentItem>>{};
    for (final item in _equipment) {
      grouped.putIfAbsent(item.category, () => []).add(item);
    }
    final totalItems = _equipment.length;
    final okItems = _equipment.where((e) => e.isUsable).length;
    final mandatoryTotal = _equipment.where((e) => e.isMandatory).length;
    final mandatoryOk = _equipment.where((e) => e.isMandatory && e.isUsable).length;

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: const Text('Equipment'),
        actions: [
          IconButton(icon: const Icon(Icons.add), tooltip: 'Add equipment', onPressed: _showAddEquipmentDialog),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showAddEquipmentDialog,
        icon: const Icon(Icons.add),
        label: const Text('Add Equipment'),
        backgroundColor: AppColors.deepSea,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null && _equipment.isEmpty
              ? _ErrorRetry(error: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _equipment.isEmpty
                      ? _EmptyEquipment(onAdd: _showAddEquipmentDialog)
                      : ListView(
                          padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
                          children: [
                            // Checklist score card
                            Card(
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        const Icon(Icons.checklist, color: AppColors.deepSea),
                                        const SizedBox(width: 8),
                                        Text('Checklist Score', style: Theme.of(context).textTheme.titleMedium),
                                        const Spacer(),
                                        Text(
                                          '$okItems / $totalItems',
                                          style: TextStyle(
                                            fontSize: 22,
                                            fontWeight: FontWeight.w900,
                                            color: okItems == totalItems ? AppColors.safeGreen : AppColors.warningAmber,
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    ClipRRect(
                                      borderRadius: BorderRadius.circular(8),
                                      child: LinearProgressIndicator(
                                        value: totalItems > 0 ? okItems / totalItems : 0,
                                        backgroundColor: AppColors.border,
                                        valueColor: AlwaysStoppedAnimation(
                                          okItems == totalItems ? AppColors.safeGreen : AppColors.warningAmber,
                                        ),
                                        minHeight: 8,
                                      ),
                                    ),
                                    if (mandatoryTotal > 0) ...[
                                      const SizedBox(height: 8),
                                      Text(
                                        'Mandatory: $mandatoryOk/$mandatoryTotal items OK',
                                        style: TextStyle(
                                          color: mandatoryOk == mandatoryTotal ? AppColors.safeGreen : AppColors.coral,
                                          fontWeight: FontWeight.w700,
                                          fontSize: 13,
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            // Grouped equipment
                            ...grouped.entries.map((entry) => Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Padding(
                                  padding: const EdgeInsets.only(top: 8, bottom: 6),
                                  child: Text(
                                    entry.key.replaceAll('_', ' ').toUpperCase(),
                                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, color: AppColors.textSecondary),
                                  ),
                                ),
                                ...entry.value.map((item) => _EquipmentCard(item: item, conditionColor: _conditionColor(item.condition), conditionIcon: _conditionIcon(item.condition))),
                                const SizedBox(height: 4),
                              ],
                            )),
                          ],
                        ),
                ),
    );
  }
}

class _EquipmentCard extends StatelessWidget {
  final BoatEquipmentItem item;
  final Color conditionColor;
  final IconData conditionIcon;

  const _EquipmentCard({required this.item, required this.conditionColor, required this.conditionIcon});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '${item.itemName}, condition ${item.condition}, quantity ${item.quantity}',
      child: Card(
        margin: const EdgeInsets.only(bottom: 8),
        child: ListTile(
          minVerticalPadding: 12,
          leading: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: conditionColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(conditionIcon, color: conditionColor, size: 22),
          ),
          title: Row(
            children: [
              Expanded(child: Text(item.itemName, style: const TextStyle(fontWeight: FontWeight.w700))),
              if (item.isMandatory)
                const Icon(Icons.star, size: 14, color: AppColors.warningAmber),
            ],
          ),
          subtitle: Text('Qty: ${item.quantity}  ·  ${item.condition.toUpperCase()}'),
          trailing: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: conditionColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              item.condition,
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: conditionColor),
            ),
          ),
        ),
      ),
    );
  }
}

class _EmptyEquipment extends StatelessWidget {
  final VoidCallback onAdd;
  const _EmptyEquipment({required this.onAdd});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.inventory_2_outlined, size: 72, color: AppColors.textDisabled),
            const SizedBox(height: 16),
            const Text('No equipment records yet', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            const Text('Track life jackets, fire extinguishers, VHF radio and more', textAlign: TextAlign.center, style: TextStyle(color: AppColors.textSecondary)),
            const SizedBox(height: 24),
            FilledButton.icon(onPressed: onAdd, icon: const Icon(Icons.add), label: const Text('Add Equipment')),
          ],
        ),
      ),
    );
  }
}

class _ErrorRetry extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;
  const _ErrorRetry({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: AppColors.coral),
            const SizedBox(height: 16),
            Text(error, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}
