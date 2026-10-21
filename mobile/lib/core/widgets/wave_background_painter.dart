import 'package:flutter/material.dart';

class WaveBackgroundPainter extends CustomPainter {
  final bool isDark;

  WaveBackgroundPainter({this.isDark = false});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    if (isDark) {
      // Dark navy gradient background
      final bgPaint = Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color(0xFF0F172A),
            Color(0xFF162A45),
            Color(0xFF0F172A),
          ],
        ).createShader(Rect.fromLTWH(0, 0, w, h));
      canvas.drawRect(Rect.fromLTWH(0, 0, w, h), bgPaint);

      // Top subtle red glow
      final topGlow = Paint()
        ..shader = RadialGradient(
          center: const Alignment(-0.8, -0.6),
          radius: 0.8,
          colors: [
            const Color(0xFFE5252A).withValues(alpha: 0.15),
            Colors.transparent,
          ],
        ).createShader(Rect.fromLTWH(0, 0, w, h * 0.4));
      canvas.drawRect(Rect.fromLTWH(0, 0, w, h * 0.4), topGlow);

      // Deep red bottom-left wave
      final wave1 = Path()
        ..moveTo(0, h * 0.72)
        ..cubicTo(w * 0.15, h * 0.68, w * 0.35, h * 0.78, w * 0.5, h * 0.86)
        ..cubicTo(w * 0.7, h * 0.94, w * 0.85, h * 0.92, w, h * 0.85)
        ..lineTo(w, h)
        ..lineTo(0, h)
        ..close();
      final paint1 = Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF881316),
            Color(0xFFB91C1C),
          ],
        ).createShader(Rect.fromLTWH(0, h * 0.68, w, h * 0.32));
      canvas.drawPath(wave1, paint1);

      // Bright crimson foreground wave
      final wave2 = Path()
        ..moveTo(0, h * 0.82)
        ..cubicTo(w * 0.25, h * 0.74, w * 0.45, h * 0.92, w * 0.75, h * 0.86)
        ..cubicTo(w * 0.88, h * 0.84, w * 0.95, h * 0.88, w, h * 0.92)
        ..lineTo(w, h)
        ..lineTo(0, h)
        ..close();
      final paint2 = Paint()
        ..shader = const LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [
            Color(0xFFDC2626),
            Color(0xFFE5252A),
          ],
        ).createShader(Rect.fromLTWH(0, h * 0.74, w, h * 0.26));
      canvas.drawPath(wave2, paint2);
    } else {
      // Light background
      final bgPaint = Paint()..color = const Color(0xFFFAFAFA);
      canvas.drawRect(Rect.fromLTWH(0, 0, w, h), bgPaint);

      // Soft ambient pink glow on top right
      final topGlow = Paint()
        ..shader = RadialGradient(
          center: const Alignment(0.85, -0.75),
          radius: 1.0,
          colors: [
            const Color(0xFFE5252A).withValues(alpha: 0.08),
            Colors.transparent,
          ],
        ).createShader(Rect.fromLTWH(0, 0, w, h * 0.45));
      canvas.drawRect(Rect.fromLTWH(0, 0, w, h * 0.45), topGlow);

      // Deep corporate navy bottom-right wave
      final navyWave = Path()
        ..moveTo(w * 0.45, h)
        ..cubicTo(w * 0.65, h * 0.94, w * 0.82, h * 0.92, w, h * 0.86)
        ..lineTo(w, h)
        ..close();
      final navyPaint = Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF1E3A5F),
            Color(0xFF162A45),
          ],
        ).createShader(Rect.fromLTWH(w * 0.45, h * 0.86, w * 0.55, h * 0.14));
      canvas.drawPath(navyWave, navyPaint);

      // Bold crimson red bottom-left curved wave
      final redWave = Path()
        ..moveTo(0, h * 0.88)
        ..cubicTo(w * 0.2, h * 0.82, w * 0.4, h * 0.94, w * 0.65, h * 0.96)
        ..cubicTo(w * 0.8, h * 0.97, w * 0.9, h * 0.98, w, h)
        ..lineTo(0, h)
        ..close();
      final redPaint = Paint()
        ..shader = const LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [
            Color(0xFFE5252A),
            Color(0xFFDC2626),
          ],
        ).createShader(Rect.fromLTWH(0, h * 0.82, w, h * 0.18));
      canvas.drawPath(redWave, redPaint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
