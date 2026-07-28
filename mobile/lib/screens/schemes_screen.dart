import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../models/govt_scheme.dart';
import '../services/reference_data_service.dart';
import '../theme/app_theme.dart';

class SchemesScreen extends StatefulWidget {
  const SchemesScreen({super.key});

  @override
  State<SchemesScreen> createState() => _SchemesScreenState();
}

class _SchemesScreenState extends State<SchemesScreen> {
  bool _loading = true;
  bool _fromCache = false;
  List<GovtSchemeInfo> _schemes = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final result = await ReferenceDataService.instance.govtSchemes();
    if (!mounted) return;
    setState(() {
      _schemes = result.items;
      _fromCache = result.fromCache;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: Text(t.schemesTitle)),
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
                        Text(t.schemesOffline, style: Theme.of(context).textTheme.bodyMedium),
                      ]),
                    ),
                  ..._schemes.map((s) => Card(
                        child: ExpansionTile(
                          title: Text(s.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                          subtitle: Text('${s.category} · ${s.region}'),
                          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                          expandedCrossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(s.description),
                            const SizedBox(height: 12),
                            Text(t.schemesEligibility, style: const TextStyle(fontWeight: FontWeight.w700)),
                            Text(s.eligibility),
                            const SizedBox(height: 12),
                            Text(t.schemesHowToApply, style: const TextStyle(fontWeight: FontWeight.w700)),
                            Text(s.howToApply),
                            if (s.contactInfo != null) ...[
                              const SizedBox(height: 12),
                              Row(children: [
                                const Icon(Icons.phone, size: 16, color: AppColors.slate),
                                const SizedBox(width: 6),
                                Expanded(child: Text(s.contactInfo!)),
                              ]),
                            ],
                          ],
                        ),
                      )),
                ],
              ),
      ),
    );
  }
}
