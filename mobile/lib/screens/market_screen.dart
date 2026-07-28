import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../models/market_price.dart';
import '../services/reference_data_service.dart';
import '../theme/app_theme.dart';

class MarketScreen extends StatefulWidget {
  const MarketScreen({super.key});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> {
  bool _loading = true;
  bool _fromCache = false;
  List<MarketPriceInfo> _prices = [];
  final _regionController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final region = _regionController.text.trim();
    final result = await ReferenceDataService.instance.marketPrices(region: region.isEmpty ? null : region);
    if (!mounted) return;
    setState(() {
      _prices = result.items;
      _fromCache = result.fromCache;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: Text(t.marketTitle)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _regionController,
              decoration: InputDecoration(
                hintText: 'Filter by harbour / region',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: IconButton(icon: const Icon(Icons.arrow_forward), onPressed: _load),
              ),
              onSubmitted: (_) => _load(),
            ),
          ),
          if (_fromCache)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(children: [
                const Icon(Icons.cloud_off, size: 16, color: AppColors.slate),
                const SizedBox(width: 6),
                Text(t.marketOffline, style: Theme.of(context).textTheme.bodyMedium),
              ]),
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _load,
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _prices.length,
                      itemBuilder: (context, i) {
                        final p = _prices[i];
                        return Card(
                          child: ListTile(
                            leading: const CircleAvatar(
                              backgroundColor: AppColors.seaFoam,
                              child: Icon(Icons.set_meal, color: Colors.white),
                            ),
                            title: Text(p.species, style: const TextStyle(fontWeight: FontWeight.w700)),
                            subtitle: Text('${p.marketName} · ${p.harborRegion}'),
                            trailing: Text(
                              '${p.currency} ${p.pricePerKg.toStringAsFixed(0)}\n${t.marketPerKg}',
                              textAlign: TextAlign.right,
                              style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.deepSea),
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ),
        ],
      ),
    );
  }
}
