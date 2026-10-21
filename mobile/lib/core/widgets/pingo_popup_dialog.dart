import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import 'pingo_mascot_widget.dart';
import 'wacrm_badge.dart';

class PingoPopupDialog {
  // Anti-duplicate tracker with 1400ms cooldown (matching web service)
  static String? _lastSignature;
  static int _lastTimestamp = 0;
  static const int _deduplicationCooldownMs = 1400;

  /// High-impact modal dialog for successful status updates and quotation actions
  static void showSuccessModal(
    BuildContext context, {
    required String title,
    required String subtitle,
    String pose = PingoPoses.celebrate,
    VoidCallback? onConfirm,
  }) {
    final now = DateTime.now().millisecondsSinceEpoch;
    final signature = 'modal_${title}_$subtitle';

    if (_lastSignature == signature && (now - _lastTimestamp) < _deduplicationCooldownMs) {
      return;
    }
    _lastSignature = signature;
    _lastTimestamp = now;

    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (ctx) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        backgroundColor: AppColors.card,
        elevation: 8,
        insetPadding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Header with brand and close
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Image.asset(
                        'assets/images/logo.png',
                        height: 22,
                        fit: BoxFit.contain,
                      ),
                    ],
                  ),
                  IconButton(
                    icon: const Icon(Icons.close_rounded, size: 20, color: AppColors.textLight),
                    onPressed: () => Navigator.of(ctx).pop(),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // 3D Pingo character with success badge
              Stack(
                alignment: Alignment.topRight,
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    child: PingoMascotWidget(
                      pose: pose,
                      height: 125,
                    ),
                  ),
                  Positioned(
                    top: 6,
                    right: 6,
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: const BoxDecoration(
                        color: AppColors.success,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(color: Color(0x3310B981), blurRadius: 6, offset: Offset(0, 2)),
                        ],
                      ),
                      child: const Icon(
                        Icons.check_rounded,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Title & Subtitle
              Text(
                title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textMain,
                  letterSpacing: -0.3,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 6),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.textMuted,
                  height: 1.4,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),

              // Action OK Button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 13),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    onConfirm?.call();
                  },
                  child: const Text(
                    'OK',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Compact floating top banner
  static void show(
    BuildContext context, {
    required String title,
    String? subtitle,
    String? badge,
    String pose = PingoPoses.salute,
    Duration duration = const Duration(milliseconds: 3200),
  }) {
    final now = DateTime.now().millisecondsSinceEpoch;
    final signature = '${title}_${subtitle ?? ''}_${badge ?? ''}_$pose';

    if (_lastSignature == signature && (now - _lastTimestamp) < _deduplicationCooldownMs) {
      return; // Deduplicate rapid multiple events
    }
    _lastSignature = signature;
    _lastTimestamp = now;

    showGeneralDialog(
      context: context,
      barrierDismissible: true,
      barrierLabel: 'Status Notification',
      barrierColor: Colors.black38,
      transitionDuration: const Duration(milliseconds: 250),
      pageBuilder: (context, anim1, anim2) {
        // Auto-dismiss after duration
        Future.delayed(duration, () {
          if (context.mounted && Navigator.canPop(context)) {
            Navigator.of(context, rootNavigator: true).pop();
          }
        });

        return SafeArea(
          child: Align(
            alignment: Alignment.topCenter,
            child: Padding(
              padding: const EdgeInsets.only(top: 24, left: 20, right: 20),
              child: Material(
                color: Colors.transparent,
                child: Container(
                  constraints: const BoxConstraints(maxWidth: 420),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: AppColors.card,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.primary.withValues(alpha: 0.25), width: 1.5),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x1F059669),
                        blurRadius: 18,
                        offset: Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      PingoMascotWidget(
                        pose: pose,
                        height: 64,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    title,
                                    style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w700,
                                      color: AppColors.textMain,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                if (badge != null) ...[
                                  const SizedBox(width: 6),
                                  WacrmBadge.status(badge),
                                ],
                              ],
                            ),
                            if (subtitle != null && subtitle.isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Text(
                                subtitle,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.textMuted,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ],
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close_rounded, size: 18, color: AppColors.textLight),
                        onPressed: () {
                          if (context.mounted) {
                            Navigator.of(context, rootNavigator: true).pop();
                          }
                        },
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
      transitionBuilder: (context, anim1, anim2, child) {
        return SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0, -0.2),
            end: Offset.zero,
          ).animate(CurvedAnimation(parent: anim1, curve: Curves.easeOutBack)),
          child: FadeTransition(
            opacity: anim1,
            child: child,
          ),
        );
      },
    );
  }
}
