import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import 'pingo_mascot_widget.dart';

class LoadingIndicator extends StatelessWidget {
  final String? message;
  final bool showMascot;
  final String mascotPose;

  const LoadingIndicator({
    super.key,
    this.message,
    this.showMascot = false,
    this.mascotPose = PingoPoses.run,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showMascot) ...[
            PingoMascotWidget(
              pose: mascotPose,
              height: 90,
            ),
            const SizedBox(height: 16),
          ],
          const CircularProgressIndicator(
            color: AppColors.primary,
            strokeWidth: 2.5,
          ),
          if (message != null) ...[
            const SizedBox(height: 12),
            Text(
              message!,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textMuted,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
