import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';

/// Shared Support presentation helpers. These only format data supplied by the
/// existing Support APIs; no values are inferred or fabricated.

Color supportStatusColor(String status) {
  switch (status.trim().toUpperCase()) {
    case 'NEW':
    case 'PENDING_ONBOARDING':
      return const Color(0xFF2563EB);
    case 'ONBOARDING':
      return const Color(0xFF4F46E5);
    case 'INSTALLATION_PENDING':
      return const Color(0xFFD97706);
    case 'INSTALLATION_COMPLETED':
      return const Color(0xFF0D9488);
    case 'TRAINING':
      return const Color(0xFF9333EA);
    case 'ACTIVE':
    case 'RESOLVED':
    case 'COMPLETED':
      return const Color(0xFF16A34A);
    case 'ISSUE_RAISED':
    case 'OVERDUE':
      return const Color(0xFFDC2626);
    default:
      return const Color(0xFF64748B);
  }
}

String supportStatusLabel(String status) {
  final value = status.trim();
  if (value.isEmpty) return 'Unknown';
  return value
      .split('_')
      .where((part) => part.isNotEmpty)
      .map((part) => part[0].toUpperCase() + part.substring(1).toLowerCase())
      .join(' ');
}

class SupportStatusBadge extends StatelessWidget {
  final String status;
  final String? label;

  const SupportStatusBadge({super.key, required this.status, this.label});

  @override
  Widget build(BuildContext context) {
    final color = supportStatusColor(status);
    return WacrmBadge(
      label: label ?? supportStatusLabel(status),
      backgroundColor: color.withValues(alpha: 0.12),
      textColor: color,
      fontSize: 10,
    );
  }
}

String supportFormatDateTime(String? raw, {String fallback = 'Not set'}) {
  final value = (raw ?? '').trim();
  if (value.isEmpty) return fallback;
  try {
    final parsed = DateTime.parse(value).toLocal();
    return DateFormat('dd MMM yyyy, h:mm a').format(parsed);
  } catch (_) {
    try {
      final parsed = DateTime.parse(value);
      return DateFormat('dd MMM yyyy').format(parsed);
    } catch (_) {
      return value;
    }
  }
}

String supportFormatDate(String? raw, {String fallback = 'Not set'}) {
  final value = (raw ?? '').trim();
  if (value.isEmpty) return fallback;
  try {
    return DateFormat('dd MMM yyyy').format(DateTime.parse(value).toLocal());
  } catch (_) {
    return value;
  }
}

class SupportKpiCard extends StatelessWidget {
  final String title;
  final String value;
  final String subtitle;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  const SupportKpiCard({
    super.key,
    required this.title,
    required this.value,
    required this.subtitle,
    required this.icon,
    required this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return WacrmCard(
      padding: const EdgeInsets.all(12),
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(icon, size: 17, color: color),
              ),
              const Spacer(),
              if (onTap != null)
                const Icon(
                  Icons.chevron_right_rounded,
                  size: 17,
                  color: AppColors.textLight,
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: color,
              height: 1,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: AppColors.textMain,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
          ),
        ],
      ),
    );
  }
}

class SupportSectionHeader extends StatelessWidget {
  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  const SupportSectionHeader({
    super.key,
    required this.title,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppColors.textMain,
            ),
          ),
        ),
        if (actionLabel != null && onAction != null)
          TextButton(
            onPressed: onAction,
            style: TextButton.styleFrom(
              foregroundColor: AppColors.primary,
              padding: const EdgeInsets.symmetric(horizontal: 6),
              minimumSize: const Size(0, 30),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: Text(
              actionLabel!,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
            ),
          ),
      ],
    );
  }
}

class SupportInfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;

  const SupportInfoRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: AppColors.textLight),
          const SizedBox(width: 8),
          SizedBox(
            width: 118,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 11,
                color: AppColors.textMuted,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 12,
                color: valueColor ?? AppColors.textMain,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
