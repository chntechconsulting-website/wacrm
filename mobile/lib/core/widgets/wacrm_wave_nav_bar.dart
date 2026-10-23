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

  // Reference Design Color Palette:
  // #0F2351: Navbar Background (Dark Navy Blue)
  // #FF1F2D: Active Icon / Button (Vibrant Red)
  // #AFC0E0: Inactive Icon & Label (Muted Blue-Grey)
  // #FFFFFF: Active Label / Plus Icon (Pure White)
  static const Color navBackground = Color(0xFF0F2351);
  static const Color activeColor = Color(0xFFFF1F2D);
  static const Color inactiveColor = Color(0xFFAFC0E0);
  static const Color whiteColor = Color(0xFFFFFFFF);

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).padding.bottom;
    const baseNavHeight = 96.0;
    final totalHeight = baseNavHeight + bottomInset;

    return Container(
      color: Colors.transparent,
      height: totalHeight,
      child: Stack(
        alignment: Alignment.bottomCenter,
        clipBehavior: Clip.none,
        children: [
          // Wave Background extending through bottomInset for Android safe area
          Positioned.fill(
            child: CustomPaint(
              painter: _WaveNavBarPainter(bottomInset: bottomInset),
            ),
          ),

          // Navigation Items (Home, Leads, [Center Gap], Calls, Settings)
          Positioned(
            left: 0,
            right: 0,
            bottom: bottomInset + 8,
            height: 44,
            child: Row(
              children: [
                // 1. Home
                Expanded(
                  child: _buildNavItem(
                    index: 0,
                    icon: Icons.home_rounded,
                    label: 'Home',
                  ),
                ),

                // 2. Leads
                Expanded(
                  child: _buildNavItem(
                    index: 1,
                    icon: Icons.people_alt_rounded,
                    label: 'Leads',
                  ),
                ),

                // Center Spacer for 56px circular button
                const SizedBox(width: 56),

                // 3. Calls
                Expanded(
                  child: _buildNavItem(
                    index: 2,
                    icon: Icons.phone_rounded,
                    label: 'Calls',
                  ),
                ),

                // 4. Settings
                Expanded(
                  child: _buildNavItem(
                    index: 3,
                    icon: Icons.settings_rounded,
                    label: 'Settings',
                  ),
                ),
              ],
            ),
          ),

          // Center Elevated Circular Red (+) Button (56px, overlapping top by 28px)
          Positioned(
            bottom: bottomInset + 40,
            child: GestureDetector(
              onTap: onAdd,
              behavior: HitTestBehavior.opaque,
              child: Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: activeColor,
                  boxShadow: [
                    BoxShadow(
                      color: activeColor.withValues(alpha: 0.45),
                      blurRadius: 16,
                      spreadRadius: 2,
                      offset: const Offset(0, 4),
                    ),
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.18),
                      blurRadius: 8,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
                child: const Center(
                  child: Icon(
                    Icons.add_rounded,
                    color: whiteColor,
                    size: 32,
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
    return GestureDetector(
      onTap: () => onTap(index),
      behavior: HitTestBehavior.opaque,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            icon,
            size: 22,
            color: isSelected ? activeColor : inactiveColor,
          ),
          const SizedBox(height: 2),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 11,
              fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
              color: isSelected ? whiteColor : inactiveColor,
              letterSpacing: -0.2,
            ),
          ),
          // Active Indicator Line Pill under selected tab
          Container(
            margin: const EdgeInsets.only(top: 2.5),
            width: 18,
            height: 2.5,
            decoration: BoxDecoration(
              color: isSelected ? activeColor : Colors.transparent,
              borderRadius: BorderRadius.circular(1.5),
            ),
          ),
        ],
      ),
    );
  }
}

class _WaveNavBarPainter extends CustomPainter {
  final double bottomInset;

  const _WaveNavBarPainter({this.bottomInset = 0});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Vertical wave profile coordinates in logical pixels
    const crestY = 28.0;
    const cornerY = 26.0;
    const valleyY = 38.0;
    const cradleY = 65.0;

    final path = Path();
    path.moveTo(0, cornerY);

    // 1. From left edge to valley above Home
    path.cubicTo(
      w * 0.04, 31.0,
      w * 0.08, valleyY,
      w * 0.13, valleyY,
    );

    // 2. From valley above Home to crest peak over Leads
    path.cubicTo(
      w * 0.19, valleyY,
      w * 0.24, crestY,
      w * 0.31, crestY,
    );

    // 3. From crest peak over Leads curving down towards center cradle
    path.cubicTo(
      w * 0.37, crestY,
      w * 0.40, 33.0,
      w * 0.42, 40.0,
    );

    // 4. Down into cradle scoop under center (+) button
    path.cubicTo(
      w * 0.44, 50.0,
      w * 0.46, cradleY,
      w * 0.50, cradleY,
    );

    // Symmetrical right half:
    // 5. Rising up from center cradle scoop
    path.cubicTo(
      w * 0.54, cradleY,
      w * 0.56, 50.0,
      w * 0.58, 40.0,
    );

    // 6. Up to crest peak over Calls
    path.cubicTo(
      w * 0.60, 33.0,
      w * 0.63, crestY,
      w * 0.69, crestY,
    );

    // 7. From crest peak over Calls to valley above Settings
    path.cubicTo(
      w * 0.76, crestY,
      w * 0.81, valleyY,
      w * 0.87, valleyY,
    );

    // 8. From valley above Settings to right corner
    path.cubicTo(
      w * 0.92, valleyY,
      w * 0.96, 31.0,
      w, cornerY,
    );

    // Close path down through bottom including bottomInset
    path.lineTo(w, h);
    path.lineTo(0, h);
    path.close();

    // Ambient drop shadow along the upper wave edge
    final shadowPaint = Paint()
      ..color = const Color(0xFF0F2351).withValues(alpha: 0.16)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
    canvas.drawPath(path.shift(const Offset(0, -2)), shadowPaint);

    // Solid Deep Navy Blue Fill (#0F2351)
    final fillPaint = Paint()
      ..color = WacrmWaveNavBar.navBackground
      ..style = PaintingStyle.fill;
    canvas.drawPath(path, fillPaint);
  }

  @override
  bool shouldRepaint(covariant _WaveNavBarPainter oldDelegate) =>
      oldDelegate.bottomInset != bottomInset;
}
