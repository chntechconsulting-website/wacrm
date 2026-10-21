import 'package:flutter/material.dart';

class AppColors {
  // Brand WA!CRM Palette (Authentic Red & Corporate Navy)
  static const Color primary = Color(0xFFE5252A); // WA! Brand Crimson Red
  static const Color primaryDark = Color(0xFFC81E23);
  static const Color primaryLight = Color(0x1AE5252A); // 10% opacity

  // Corporate Navy & Dark Accents
  static const Color navy = Color(0xFF162A45); // Deep Corporate Navy
  static const Color navyDark = Color(0xFF0F172A);
  static const Color navyLight = Color(0x1A162A45);

  // Accent Blue
  static const Color accent = Color(0xFF2563EB);
  static const Color accentLight = Color(0x1A2563EB);

  // Status & Utility Colors
  static const Color success = Color(0xFF10B981);
  static const Color successLight = Color(0x1A10B981);

  static const Color warning = Color(0xFFF59E0B);
  static const Color warningLight = Color(0x1AF59E0B);

  static const Color danger = Color(0xFFDC2626);
  static const Color dangerLight = Color(0x1ADC2626);

  static const Color info = Color(0xFF0284C7);
  static const Color infoLight = Color(0x1A0284C7);

  // Background & Surface
  static const Color background = Color(0xFFF8FAFC); // Slate 50
  static const Color card = Color(0xFFFFFFFF);
  static const Color cardHover = Color(0xFFF1F5F9);
  static const Color inputBackground = Color(0xFFFFFFFF);

  // Border & Divider
  static const Color border = Color(0xFFE2E8F0); // Slate 200
  static const Color borderFocus = Color(0xFFE5252A);

  // Typography
  static const Color textMain = Color(0xFF0F172A); // Slate 900
  static const Color textMuted = Color(0xFF64748B); // Slate 500
  static const Color textLight = Color(0xFF94A3B8); // Slate 400
  static const Color white = Color(0xFFFFFFFF);

  // Shadows
  static const List<BoxShadow> softShadow = [
    BoxShadow(
      color: Color(0x0A0F172A),
      blurRadius: 8,
      offset: Offset(0, 2),
    ),
  ];

  static const List<BoxShadow> cardShadow = [
    BoxShadow(
      color: Color(0x0D0F172A),
      blurRadius: 10,
      offset: Offset(0, 4),
    ),
  ];
}
