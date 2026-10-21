import 'package:flutter/material.dart';

class WacrmWaveNavBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;
  final VoidCallback onAdd;

  const WacrmWaveNavBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 78,
      child: Stack(
        alignment: Alignment.bottomCenter,
        clipBehavior: Clip.none,
        children: [
          // Wave Background
          Positioned.fill(
            child: CustomPaint(
              painter: _WaveNavBarPainter(),
            ),
          ),

          // Navigation Items (Home, Leads, [Center Gap], Calls, More)
          Positioned(
            left: 0,
            right: 0,
            bottom: 6,
            height: 56,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                // 1. Home
                _buildNavItem(
                  index: 0,
                  icon: currentIndex == 0 ? Icons.home_rounded : Icons.home_outlined,
                  label: 'Home',
                ),

                // 2. Leads
                _buildNavItem(
                  index: 1,
                  icon: Icons.people_alt_rounded,
                  label: 'Leads',
                ),

                // Center Spacer for FAB
                const SizedBox(width: 52),

                // 3. Calls
                _buildNavItem(
                  index: 2,
                  icon: currentIndex == 2 ? Icons.phone_rounded : Icons.phone_outlined,
                  label: 'Calls',
                ),

                // 4. More
                _buildNavItem(
                  index: 3,
                  icon: Icons.grid_view_rounded,
                  label: 'More',
                ),
              ],
            ),
          ),

          // Center Elevated Red FAB with White '+'
          Positioned(
            top: 0,
            child: GestureDetector(
              onTap: onAdd,
              child: Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFFE5252A),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFFE5252A).withValues(alpha: 0.45),
                      blurRadius: 10,
                      spreadRadius: 1,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Center(
                  child: Icon(
                    Icons.add_rounded,
                    color: Colors.white,
                    size: 30,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavItem({
    required int index,
    required IconData icon,
    required String label,
  }) {
    final isSelected = currentIndex == index;
    return InkWell(
      onTap: () => onTap(index),
      splashColor: Colors.transparent,
      highlightColor: Colors.transparent,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            icon,
            size: 22,
            color: isSelected ? const Color(0xFFE5252A) : const Color(0xFF94A3B8),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
              color: isSelected ? Colors.white : const Color(0xFF94A3B8),
            ),
          ),
          const SizedBox(height: 2),
          // Active Indicator Pill under selected tab
          Container(
            width: isSelected ? 16 : 0,
            height: 2.5,
            decoration: BoxDecoration(
              color: isSelected ? const Color(0xFFE5252A) : Colors.transparent,
              borderRadius: BorderRadius.circular(1.5),
            ),
          ),
        ],
      ),
    );
  }
}

class _WaveNavBarPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Navy Wave Background Path with Center Drip Cutout for FAB
    final path = Path();
    path.moveTo(0, 24);

    // Left curve towards center
    path.cubicTo(w * 0.20, 24, w * 0.32, 16, w * 0.38, 20);

    // Center cutout around FAB
    path.cubicTo(w * 0.42, 25, w * 0.44, 46, w * 0.50, 46);
    path.cubicTo(w * 0.56, 46, w * 0.58, 25, w * 0.62, 20);

    // Right curve towards right edge
    path.cubicTo(w * 0.68, 16, w * 0.80, 24, w, 24);

    // Close path along bottom
    path.lineTo(w, h);
    path.lineTo(0, h);
    path.close();

    // Top Drop Shadow
    final shadowPaint = Paint()
      ..color = Colors.black.withValues(alpha: 0.18)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
    canvas.drawPath(path.shift(const Offset(0, -2)), shadowPaint);

    // Solid Deep Corporate Navy Paint (#0B192C)
    final paint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Color(0xFF162A45),
          Color(0xFF0F172A),
        ],
      ).createShader(Rect.fromLTWH(0, 16, w, h - 16));

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
