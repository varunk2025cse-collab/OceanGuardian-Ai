import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../services/auth_service.dart';
import '../../services/api_client.dart';
import '../../services/sync_service.dart';
import '../../theme/app_theme.dart';
import '../home_shell.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _nameController = TextEditingController();
  final _boatController = TextEditingController();
  final _harborController = TextEditingController();
  final _emergencyNameController = TextEditingController();
  final _emergencyPhoneController = TextEditingController();

  String _role = 'fisherman';
  bool _loading = false;
  String? _error;

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await AuthService.instance.register(
        phoneNumber: _phoneController.text.trim(),
        password: _passwordController.text,
        fullName: _nameController.text.trim(),
        role: _role,
        preferredLanguage: 'ta',
        boatName: _role == 'fisherman' && _boatController.text.trim().isNotEmpty ? _boatController.text.trim() : null,
        homeHarbor: _role == 'fisherman' && _harborController.text.trim().isNotEmpty ? _harborController.text.trim() : null,
        emergencyContactName:
            _role == 'fisherman' && _emergencyNameController.text.trim().isNotEmpty ? _emergencyNameController.text.trim() : null,
        emergencyContactPhone:
            _role == 'fisherman' && _emergencyPhoneController.text.trim().isNotEmpty ? _emergencyPhoneController.text.trim() : null,
      );
      SyncService.instance.start();
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(MaterialPageRoute(builder: (_) => const HomeShell()), (r) => false);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = AppLocalizations.of(context)!.networkErrorGeneric);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.sand,
      appBar: AppBar(title: Text(t.registerTitle)),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SegmentedButton<String>(
                  segments: [
                    ButtonSegment(value: 'fisherman', label: Text(t.iAmAFisherman)),
                    ButtonSegment(value: 'family', label: Text(t.iAmFamily)),
                  ],
                  selected: {_role},
                  onSelectionChanged: (s) => setState(() => _role = s.first),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _nameController,
                  decoration: InputDecoration(labelText: t.fullName),
                  validator: (v) => (v == null || v.trim().length < 2) ? t.validatorRequired : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  decoration: InputDecoration(labelText: t.phoneNumber),
                  validator: (v) => (v == null || v.trim().length < 8) ? t.validatorInvalidPhone : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _passwordController,
                  obscureText: true,
                  decoration: InputDecoration(labelText: t.password),
                  validator: (v) => (v == null || v.length < 6) ? t.validatorMinPassword : null,
                ),
                if (_role == 'fisherman') ...[
                  const SizedBox(height: 12),
                  TextFormField(controller: _boatController, decoration: InputDecoration(labelText: t.boatName)),
                  const SizedBox(height: 12),
                  TextFormField(controller: _harborController, decoration: InputDecoration(labelText: t.homeHarbor)),
                  const SizedBox(height: 12),
                  TextFormField(
                      controller: _emergencyNameController, decoration: InputDecoration(labelText: t.emergencyContactName)),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _emergencyPhoneController,
                    keyboardType: TextInputType.phone,
                    decoration: InputDecoration(labelText: t.emergencyContactPhone),
                  ),
                ],
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: AppColors.coral)),
                ],
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _loading ? null : _submit,
                  child: _loading
                      ? const SizedBox(
                          height: 20, width: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                      : Text(t.register),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
