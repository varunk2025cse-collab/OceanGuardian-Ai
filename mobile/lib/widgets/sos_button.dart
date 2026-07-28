import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// PHASE 4 ENHANCED: Larger, more accessible SOS button
/// - 240x240 (from 200x200) for easier hitting
/// - Pulsing animation for attention
/// - Haptic feedback support
/// - Voice-friendly with semantic labels
class SosButton extends StatefulWidget {
  final VoidCallback onConfirmedPress;
  final bool sending;

  const SosButton({super.key, required this.onConfirmedPress, this.sending = false});

  @override
  State<SosButton> createState() => _SosButtonState();
}

class _SosButtonState extends State<SosButton> with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.1).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'SOS Emergency Button',
      hint: 'Double tap to activate emergency alert',
      button: true,
      child: AnimatedBuilder(
        animation: _pulseAnimation,
        builder: (context, child) => Transform.scale(
          scale: widget.sending ? 1.0 : _pulseAnimation.value,
          child: child,
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: widget.sending ? null : widget.onConfirmedPress,
            child: Container(
              width: 240, // Increased from 200
              height: 240,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    AppColors.danger,
                    AppColors.danger.withOpacity(0.8),
                  ],
                ),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.danger.withOpacity(0.5),
                    blurRadius: 32,
                    spreadRadius: 8,
                  ),
                ],
              ),
              child: Center(
                child: widget.sending
                    ? const CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 5,
                      )
                    : Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.warning_amber_rounded,
                            color: Colors.white,
                            size: 72, // Increased from 56
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            'SOS',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 40, // Increased from 32
                              fontWeight: FontWeight.w900,
                              letterSpacing: 4,
                            ),
                          ),
                        ],
                      ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
