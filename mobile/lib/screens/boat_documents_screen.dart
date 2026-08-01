import 'package:flutter/material.dart';
import '../models/boat_document.dart';
import '../services/boat_service.dart';
import '../theme/app_theme.dart';

class BoatDocumentsScreen extends StatefulWidget {
  final int boatId;
  const BoatDocumentsScreen({super.key, required this.boatId});

  @override
  State<BoatDocumentsScreen> createState() => _BoatDocumentsScreenState();
}

class _BoatDocumentsScreenState extends State<BoatDocumentsScreen> {
  bool _loading = true;
  List<BoatDocument> _documents = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final result = await BoatService.instance.getDocuments(widget.boatId);
      _documents = result.data;
    } catch (e) {
      _error = e.toString();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _showAddDocumentDialog() async {
    String docType = 'fishing_license';
    final numberCtrl = TextEditingController();
    final authorityCtrl = TextEditingController();
    DateTime? expiryDate;

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Add Document', style: TextStyle(fontWeight: FontWeight.w800)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: docType,
                  decoration: const InputDecoration(labelText: 'Document Type', prefixIcon: Icon(Icons.description)),
                  items: const [
                    DropdownMenuItem(value: 'fishing_license', child: Text('Fishing License')),
                    DropdownMenuItem(value: 'insurance', child: Text('Insurance')),
                    DropdownMenuItem(value: 'registration', child: Text('Registration Certificate')),
                    DropdownMenuItem(value: 'inspection', child: Text('Inspection Certificate')),
                    DropdownMenuItem(value: 'safety_certificate', child: Text('Safety Certificate')),
                    DropdownMenuItem(value: 'pollution_certificate', child: Text('Pollution Certificate')),
                    DropdownMenuItem(value: 'other', child: Text('Other')),
                  ],
                  onChanged: (v) { if (v != null) setDialogState(() => docType = v); },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: numberCtrl,
                  decoration: const InputDecoration(labelText: 'Document Number', prefixIcon: Icon(Icons.numbers)),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: authorityCtrl,
                  decoration: const InputDecoration(labelText: 'Issuing Authority', prefixIcon: Icon(Icons.account_balance)),
                ),
                const SizedBox(height: 12),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.calendar_today, color: AppColors.deepSea),
                  title: Text(
                    expiryDate == null
                        ? 'Set Expiry Date (optional)'
                        : 'Expires: ${expiryDate!.toLocal().toString().split(' ')[0]}',
                    style: TextStyle(
                      color: expiryDate == null ? AppColors.textSecondary : AppColors.deepSea,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  onTap: () async {
                    final picked = await showDatePicker(
                      context: ctx,
                      initialDate: DateTime.now().add(const Duration(days: 365)),
                      firstDate: DateTime.now(),
                      lastDate: DateTime.now().add(const Duration(days: 365 * 10)),
                    );
                    if (picked != null) setDialogState(() => expiryDate = picked);
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Cancel')),
            FilledButton(
              onPressed: () async {
                Navigator.of(ctx).pop();
                setState(() => _loading = true);
                try {
                  await BoatService.instance.createDocument(widget.boatId, {
                    'document_type': docType,
                    if (numberCtrl.text.trim().isNotEmpty) 'document_number': numberCtrl.text.trim(),
                    if (authorityCtrl.text.trim().isNotEmpty) 'issuing_authority': authorityCtrl.text.trim(),
                    if (expiryDate != null) 'expiry_date': expiryDate!.toIso8601String().split('T')[0],
                  });
                  await _load();
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Document added')));
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

  Future<void> _deleteDocument(BoatDocument doc) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete document?'),
        content: Text('${doc.documentType.replaceAll('_', ' ')} will be removed.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.coral),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    setState(() => _loading = true);
    try {
      await BoatService.instance.deleteDocument(widget.boatId, doc.id);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final expiring = _documents.where((d) => d.daysUntilExpiry != null && d.daysUntilExpiry! <= 60 && !d.isExpired).toList();
    final expired = _documents.where((d) => d.isExpired).toList();

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(
        title: const Text('Documents'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add document',
            onPressed: _showAddDocumentDialog,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showAddDocumentDialog,
        icon: const Icon(Icons.upload_file),
        label: const Text('Add Document'),
        backgroundColor: AppColors.deepSea,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null && _documents.isEmpty
              ? _ErrorRetry(error: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _documents.isEmpty
                      ? _EmptyDocuments(onAdd: _showAddDocumentDialog)
                      : ListView(
                          padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
                          children: [
                            // Expiry alerts section
                            if (expired.isNotEmpty) ...[
                              _SectionHeader(title: 'Expired Documents', color: AppColors.coral, icon: Icons.cancel),
                              ...expired.map((d) => _DocumentCard(doc: d, onDelete: () => _deleteDocument(d))),
                              const SizedBox(height: 8),
                            ],
                            if (expiring.isNotEmpty) ...[
                              _SectionHeader(title: 'Expiring Soon', color: AppColors.warningAmber, icon: Icons.warning_amber_rounded),
                              ...expiring.map((d) => _DocumentCard(doc: d, onDelete: () => _deleteDocument(d))),
                              const SizedBox(height: 8),
                            ],
                            // All documents
                            _SectionHeader(title: 'All Documents (${_documents.length})', color: AppColors.deepSea, icon: Icons.description),
                            ..._documents.map((d) => _DocumentCard(doc: d, onDelete: () => _deleteDocument(d))),
                          ],
                        ),
                ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final Color color;
  final IconData icon;

  const _SectionHeader({required this.title, required this.color, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, top: 4),
      child: Row(
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 6),
          Text(title, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14, color: color)),
        ],
      ),
    );
  }
}

class _DocumentCard extends StatelessWidget {
  final BoatDocument doc;
  final VoidCallback onDelete;

  const _DocumentCard({required this.doc, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final statusColor = doc.isExpired
        ? AppColors.coral
        : doc.daysUntilExpiry != null && doc.daysUntilExpiry! <= 60
            ? AppColors.warningAmber
            : doc.isVerified
                ? AppColors.safeGreen
                : AppColors.textSecondary;

    final statusIcon = doc.isExpired
        ? Icons.cancel
        : doc.daysUntilExpiry != null && doc.daysUntilExpiry! <= 60
            ? Icons.warning_amber_rounded
            : doc.isVerified
                ? Icons.verified
                : Icons.pending;

    final statusLabel = doc.isExpired
        ? 'Expired'
        : doc.isVerified
            ? 'Verified'
            : 'Pending';

    return Semantics(
      label: '${doc.documentType.replaceAll('_', ' ')}, status $statusLabel',
      child: Card(
        margin: const EdgeInsets.only(bottom: 10),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(statusIcon, color: statusColor, size: 24),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      doc.documentType.replaceAll('_', ' ').toUpperCase(),
                      style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14),
                    ),
                    if (doc.documentNumber != null) ...[
                      const SizedBox(height: 2),
                      Text(doc.documentNumber!, style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                    ],
                    if (doc.issuingAuthority != null) ...[
                      const SizedBox(height: 2),
                      Text(doc.issuingAuthority!, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                    ],
                    if (doc.expiryDate != null) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(Icons.calendar_today, size: 12, color: statusColor),
                          const SizedBox(width: 4),
                          Text(
                            doc.isExpired
                                ? 'Expired ${doc.expiryDate!.toLocal().toString().split(' ')[0]}'
                                : doc.daysUntilExpiry != null
                                    ? 'Expires in ${doc.daysUntilExpiry} days'
                                    : 'Expires ${doc.expiryDate!.toLocal().toString().split(' ')[0]}',
                            style: TextStyle(color: statusColor, fontSize: 12, fontWeight: FontWeight.w700),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              Column(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(statusLabel, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: statusColor)),
                  ),
                  const SizedBox(height: 8),
                  IconButton(
                    icon: const Icon(Icons.delete_outline, color: AppColors.coral, size: 20),
                    onPressed: onDelete,
                    tooltip: 'Delete document',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyDocuments extends StatelessWidget {
  final VoidCallback onAdd;
  const _EmptyDocuments({required this.onAdd});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.description_outlined, size: 72, color: AppColors.textDisabled),
            const SizedBox(height: 16),
            const Text('No documents yet', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            const Text(
              'Add fishing license, insurance, and other compliance documents',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(onPressed: onAdd, icon: const Icon(Icons.upload_file), label: const Text('Add First Document')),
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
