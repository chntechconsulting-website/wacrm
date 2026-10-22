import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class WacrmBadge extends StatelessWidget {
  final String label;
  final Color? backgroundColor;
  final Color? textColor;
  final IconData? icon;
  final double fontSize;

  const WacrmBadge({
    super.key,
    required this.label,
    this.backgroundColor,
    this.textColor,
    this.icon,
    this.fontSize = 11,
  });

  factory WacrmBadge.status(String status) {
    Color bg = AppColors.border;
    Color fg = AppColors.textMuted;
    final s = status.toUpperCase().replaceAll('-', '_');

    if (s == 'NEW' || s == 'OPEN') {
      bg = const Color(0xFFEFF6FF);
      fg = const Color(0xFF2563EB); // Blue
    } else if (s == 'ASSIGNED') {
      bg = const Color(0xFFF0FDF4);
      fg = const Color(0xFF16A34A); // Green
    } else if (s == 'CONTACTED' || s == 'IN_PROGRESS') {
      bg = const Color(0xFFFDF4FF);
      fg = const Color(0xFF9333EA); // Purple
    } else if (s == 'INTERESTED' || s == 'WARM') {
      bg = const Color(0xFFFEF3C7);
      fg = const Color(0xFFD97706); // Amber
    } else if (s == 'FOLLOW_UP') {
      bg = const Color(0xFFFFFBEB);
      fg = const Color(0xFFB45309);
    } else if (s == 'QUALIFIED' || s == 'HOT') {
      bg = const Color(0xFFECFDF5);
      fg = const Color(0xFF059669); // Emerald
    } else if (s == 'CONVERTED' || s == 'WON' || s == 'PAID' || s == 'COMPLETED' || s == 'ACTIVE') {
      bg = const Color(0xFFD1FAE5);
      fg = const Color(0xFF047857);
    } else if (s.contains('FIELD_VISIT') || s.contains('CHECKED_IN')) {
      bg = const Color(0xFFE0F2FE);
      fg = const Color(0xFF0284C7);
    } else if (s == 'LOST' || s == 'NOT_INTERESTED' || s == 'CANCELLED' || s == 'REJECTED' || s == 'INACTIVE') {
      bg = const Color(0xFFFEE2E2);
      fg = const Color(0xFFDC2626);
    }

    return WacrmBadge(
      label: status.replaceAll('_', ' '),
      backgroundColor: bg,
      textColor: fg,
    );
  }

  factory WacrmBadge.department(String department) {
    final d = department.toUpperCase().trim();
    Color bg;
    Color fg;
    String label = department;

    if (d == 'ADMIN' || d == 'ADMINISTRATION') {
      bg = const Color(0xFFF1F5F9);
      fg = const Color(0xFF0F172A);
      label = 'Administration';
    } else if (d == 'SALES') {
      bg = const Color(0xFFEFF6FF);
      fg = const Color(0xFF2563EB);
      label = 'Sales';
    } else if (d == 'SUPPORT') {
      bg = const Color(0xFFF0FDFA);
      fg = const Color(0xFF0D9488);
      label = 'Support';
    } else if (d == 'FINANCE') {
      bg = const Color(0xFFFFFBEB);
      fg = const Color(0xFFD97706);
      label = 'Finance';
    } else {
      bg = const Color(0xFFF1F5F9);
      fg = const Color(0xFF475569);
    }

    return WacrmBadge(
      label: label,
      backgroundColor: bg,
      textColor: fg,
      icon: Icons.apartment_rounded,
    );
  }

  factory WacrmBadge.priority(String priority) {
    Color bg = AppColors.border;
    Color fg = AppColors.textMuted;
    final p = priority.toUpperCase();

    if (p == 'HIGH' || p == 'URGENT') {
      bg = const Color(0xFFFEE2E2);
      fg = const Color(0xFFDC2626);
    } else if (p == 'MEDIUM') {
      bg = const Color(0xFFFEF3C7);
      fg = const Color(0xFFD97706);
    } else {
      bg = const Color(0xFFF1F5F9);
      fg = const Color(0xFF64748B);
    }

    return WacrmBadge(
      label: priority,
      backgroundColor: bg,
      textColor: fg,
      fontSize: 10,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: backgroundColor ?? AppColors.primaryLight,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: fontSize + 1, color: textColor ?? AppColors.primary),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              color: textColor ?? AppColors.primary,
              fontSize: fontSize,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }
}
