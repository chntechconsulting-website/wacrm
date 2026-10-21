import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

enum WacrmButtonType { primary, secondary, outline, danger }

class WacrmButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final bool isLoading;
  final IconData? icon;
  final WacrmButtonType type;
  final double? width;
  final double height;

  const WacrmButton({
    super.key,
    required this.text,
    this.onPressed,
    this.isLoading = false,
    this.icon,
    this.type = WacrmButtonType.primary,
    this.width,
    this.height = 48,
  });

  @override
  Widget build(BuildContext context) {
    Color bg = AppColors.primary;
    Color fg = AppColors.white;
    BorderSide? borderSide;

    switch (type) {
      case WacrmButtonType.primary:
        bg = AppColors.primary;
        fg = AppColors.white;
        break;
      case WacrmButtonType.secondary:
        bg = AppColors.cardHover;
        fg = AppColors.textMain;
        break;
      case WacrmButtonType.outline:
        bg = Colors.transparent;
        fg = AppColors.textMain;
        borderSide = const BorderSide(color: AppColors.border, width: 1.2);
        break;
      case WacrmButtonType.danger:
        bg = AppColors.danger;
        fg = AppColors.white;
        break;
    }

    return SizedBox(
      width: width,
      height: height,
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: bg,
          foregroundColor: fg,
          elevation: 0,
          side: borderSide,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16),
        ),
        onPressed: isLoading ? null : onPressed,
        child: isLoading
            ? SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(fg),
                ),
              )
            : Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (icon != null) ...[
                    Icon(icon, size: 18, color: fg),
                    const SizedBox(width: 8),
                  ],
                  Text(
                    text,
                    style: TextStyle(
                      color: fg,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}
