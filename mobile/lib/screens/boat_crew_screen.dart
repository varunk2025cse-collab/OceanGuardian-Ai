import 'package:flutter/material.dart';
import '../models/boat_crew.dart';
import '../services/boat_service.dart';
import '../theme/app_theme.dart';

class BoatCrewScreen extends StatefulWidget {
  final int boatId;
  const BoatCrewScreen({super.key, required this.boatId});

  @override
  State<BoatCrewScreen> createState() => _BoatCrewScreenState();
}

class _BoatCrewScreenState extends State<BoatCrewScreen> {
  bool _loading = true;
  List<BoatCrewMember> _crew = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final result = await BoatService.instance.getCrew(widget.boatId);
      _crew = result.data;
    } catch (e) {
      _error = e.toString();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _removeCrew(BoatCrewMember member) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove crew member?'),
        content: Text('${member.fullName} (${member.role}) will be removed.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.coral),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    setState(() => _loading = true);
    try {
      await BoatService.instance.removeCrew(widget.boatId, member.id);
      await _load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Crew member removed')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _showAddCrewDialog() async {
    final nameCtrl = TextEditingController();
    final phoneCtrl = TextEditingController();
    String selectedRole = 'deckhand';
    bool isPrimary = false;

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Add Crew Member', style: TextStyle(fontWeight: FontWeight.w800)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: nameCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Full Name *',
                    prefixIcon: Icon(Icons.person),
                  ),
                  textCapitalization: TextCapitalization.words,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: phoneCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Phone Number',
                    prefixIcon: Icon(Icons.phone),
                    hintText: '+91-XXXXXXXXXX',
                  ),
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: selectedRole,
                  decoration: const InputDecoration(labelText: 'Role', prefixIcon: Icon(Icons.work)),
                  items: const [
                    DropdownMenuItem(value: 'captain', child: Text('Captain ★')),
                    DropdownMenuItem(value: 'deckhand', child: Text('Deckhand')),
                    DropdownMenuItem(value: 'engineer', child: Text('Engineer')),
                    DropdownMenuItem(value: 'navigator', child: Text('Navigator')),
                    DropdownMenuItem(value: 'cook', child: Text('Cook')),
                    DropdownMenuItem(value: 'helper', child: Text('Helper')),
                    DropdownMenuItem(value: 'other', child: Text('Other')),
                  ],
                  onChanged: (v) {
                    if (v != null) {
                      setDialogState(() {
                        selectedRole = v;
                      });
                    }
                  },
                ),
                const SizedBox(height: 8),
                SwitchListTile(
                  title: const Text('Primary Emergency Contact'),
                  subtitle: const Text('Family will be notified via this person'),
                  value: isPrimary,
                  onChanged: (v) => setDialogState(() => isPrimary = v),
                  contentPadding: EdgeInsets.zero,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Cancel')),
            FilledButton(
              onPressed: () async {
                if (nameCtrl.text.trim().isEmpty) {
                  ScaffoldMessenger.of(ctx).showSnackBar(const SnackBar(content: Text('Name is required')));
                  return;
                }
                Navigator.of(ctx).pop();
                setState(() => _loading = true);
                try {
                  await BoatService.instance.assignCrew(widget.boatId, {
                    'full_name': nameCtrl.text.trim(),
                    if (phoneCtrl.text.trim().isNotEmpty) 'phone_number': phoneCtrl.text.trim(),
                    'role': selectedRole,
                    'is_primary_contact': isPrimary,
                  });
                  await _load();
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Crew member added')));
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
    final activeCrew = _crew.where((c) => c.isActive).toList();
    final captain = activeCrew.where((c) => c.isCaptain).toList();

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: const Text('Crew'),
        actions: [
          Semantics(
            label: 'Add crew member',
            button: true,
            child: IconButton(
              icon: const Icon(Icons.person_add),
              tooltip: 'Add crew member',
              onPressed: _showAddCrewDialog,
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showAddCrewDialog,
        icon: const Icon(Icons.person_add),
        label: const Text('Add Crew'),
        backgroundColor: AppColors.deepSea,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null && _crew.isEmpty
              ? _ErrorState(error: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
                    children: [
                      // Captain warning
                      if (captain.isEmpty)
                        _WarningBanner(
                          icon: Icons.warning_amber_rounded,
                          message: 'No captain assigned — required for trip start',
                          color: AppColors.coral,
                        ),
                      // Crew count summary
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          children: [
                            const Icon(Icons.groups, color: AppColors.deepSea, size: 20),
                            const SizedBox(width: 8),
                            Text(
                              '${activeCrew.length} active crew member${activeCrew.length == 1 ? '' : 's'}',
                              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
                            ),
                          ],
                        ),
                      ),
                      if (activeCrew.isEmpty)
                        _EmptyState(
                          icon: Icons.groups_outlined,
                          message: 'No crew members yet\nAdd crew to enable trip start',
                          onAction: _showAddCrewDialog,
                          actionLabel: 'Add First Crew Member',
                        )
                      else
                        ...activeCrew.map((member) => _CrewCard(
                          member: member,
                          onRemove: () => _removeCrew(member),
                        )),
                    ],
                  ),
                ),
    );
  }
}

class _CrewCard extends StatelessWidget {
  final BoatCrewMember member;
  final VoidCallback onRemove;

  const _CrewCard({required this.member, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '${member.fullName}, role ${member.role}${member.isCaptain ? ', Captain' : ''}',
      child: Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: member.isCaptain
                    ? AppColors.warningAmber.withValues(alpha: 0.15)
                    : AppColors.deepSea.withValues(alpha: 0.1),
                child: Icon(
                  member.isCaptain ? Icons.star : Icons.person,
                  color: member.isCaptain ? AppColors.warningAmber : AppColors.deepSea,
                  size: 28,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            member.fullName,
                            style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
                          ),
                        ),
                        if (member.isCaptain)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppColors.warningAmber.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Text('CAPTAIN', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.warningAmber)),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(member.role.toUpperCase(), style: const TextStyle(color: AppColors.textSecondary, fontSize: 13, fontWeight: FontWeight.w600)),
                    if (member.phoneNumber != null) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.phone, size: 14, color: AppColors.textSecondary),
                          const SizedBox(width: 4),
                          Text(member.phoneNumber!, style: const TextStyle(fontSize: 14)),
                        ],
                      ),
                    ],
                    if (member.isPrimaryContact) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.emergency, size: 14, color: AppColors.coral),
                          const SizedBox(width: 4),
                          const Text('Primary Emergency Contact', style: TextStyle(fontSize: 12, color: AppColors.coral, fontWeight: FontWeight.w700)),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline, color: AppColors.coral),
                tooltip: 'Remove crew member',
                onPressed: onRemove,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _WarningBanner extends StatelessWidget {
  final IconData icon;
  final String message;
  final Color color;

  const _WarningBanner({required this.icon, required this.message, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(message, style: TextStyle(color: color, fontWeight: FontWeight.w700))),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final IconData icon;
  final String message;
  final VoidCallback? onAction;
  final String? actionLabel;

  const _EmptyState({required this.icon, required this.message, this.onAction, this.actionLabel});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 72, color: AppColors.textDisabled),
          const SizedBox(height: 16),
          Text(message, style: const TextStyle(color: AppColors.textSecondary, fontSize: 16), textAlign: TextAlign.center),
          if (onAction != null && actionLabel != null) ...[
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: onAction,
              icon: const Icon(Icons.add),
              label: Text(actionLabel!),
            ),
          ],
        ],
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;

  const _ErrorState({required this.error, required this.onRetry});

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
