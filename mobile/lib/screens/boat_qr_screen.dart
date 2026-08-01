import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/boat_service.dart';
import '../theme/app_theme.dart';

class BoatQRScreen extends StatefulWidget {
  final int boatId;
  const BoatQRScreen({super.key, required this.boatId});

  @override
  State<BoatQRScreen> createState() => _BoatQRScreenState();
}

class _BoatQRScreenState extends State<BoatQRScreen> {
  Map<String, dynamic>? _qrData;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final result = await BoatService.instance.getQR(widget.boatId);
      _qrData = result.data.isNotEmpty ? result.data : null;
    } catch (_) {
      _qrData = null;
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _copyToken() async {
    final token = _qrData?['qr_code_token'] as String?;
    if (token == null) return;
    await Clipboard.setData(ClipboardData(text: token));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('QR token copied to clipboard'), backgroundColor: AppColors.safeGreen),
    );
  }

  Future<void> _shareQR() async {
    final token = _qrData?['qr_code_token'] as String?;
    final boatName = _qrData?['boat_name'] as String? ?? 'Boat';
    if (token == null) return;
    final url = _qrData?['qr_url'] as String? ?? 'https://oceanguardian.ai/boat/$token';
    await Clipboard.setData(ClipboardData(text: 'OceanGuardian Boat: $boatName\nID: $token\n$url'));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('QR info copied — paste to share')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final token = _qrData?['qr_code_token'] as String? ?? '';
    final boatName = _qrData?['boat_name'] as String? ?? '';
    final qrUrl = _qrData?['qr_url'] as String? ?? '';

    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: const Text('QR Code')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  // QR code display
                  Semantics(
                    label: 'QR code for boat identification',
                    child: Container(
                      width: 240,
                      height: 240,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: AppColors.border, width: 2),
                        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.08), blurRadius: 16, offset: const Offset(0, 4))],
                      ),
                      child: token.isEmpty
                          ? const Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.qr_code_2_rounded, size: 100, color: AppColors.textDisabled),
                                SizedBox(height: 8),
                                Text('No QR token', style: TextStyle(color: AppColors.textSecondary)),
                              ],
                            )
                          : Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.qr_code_2_rounded, size: 120, color: Colors.black87),
                                const SizedBox(height: 8),
                                const Icon(Icons.directions_boat, size: 32, color: AppColors.deepSea),
                              ],
                            ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  if (boatName.isNotEmpty)
                    Text(boatName, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
                  const SizedBox(height: 8),

                  Text(
                    token.isEmpty ? 'No QR token assigned yet' : 'Scan to identify this boat',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 16),
                    textAlign: TextAlign.center,
                  ),

                  if (token.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.border.withValues(alpha: 0.3),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: SelectableText(
                        token,
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
                        textAlign: TextAlign.center,
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Action buttons
                    Row(
                      children: [
                        Expanded(
                          child: SizedBox(
                            height: 52,
                            child: OutlinedButton.icon(
                              onPressed: _copyToken,
                              icon: const Icon(Icons.copy),
                              label: const Text('Copy Token', style: TextStyle(fontSize: 15)),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: SizedBox(
                            height: 52,
                            child: FilledButton.icon(
                              onPressed: _shareQR,
                              icon: const Icon(Icons.share),
                              label: const Text('Share', style: TextStyle(fontSize: 15)),
                              style: FilledButton.styleFrom(backgroundColor: AppColors.deepSea),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),

                    // Info card
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Row(
                              children: [
                                Icon(Icons.info_outline, color: AppColors.deepSea, size: 18),
                                SizedBox(width: 8),
                                Text('How to use', style: TextStyle(fontWeight: FontWeight.w800)),
                              ],
                            ),
                            const SizedBox(height: 8),
                            const Text('• Coast Guard and rescue teams can scan this QR code to instantly identify your boat', style: TextStyle(fontSize: 14)),
                            const SizedBox(height: 4),
                            const Text('• Print and laminate this code — keep it on the boat', style: TextStyle(fontSize: 14)),
                            const SizedBox(height: 4),
                            Row(
                              children: [
                                const Icon(Icons.cloud_off, size: 14, color: AppColors.safeGreen),
                                const SizedBox(width: 4),
                                const Text('Works fully offline', style: TextStyle(fontSize: 14, color: AppColors.safeGreen, fontWeight: FontWeight.w700)),
                              ],
                            ),
                            if (qrUrl.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Text(qrUrl, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
    );
  }
}
