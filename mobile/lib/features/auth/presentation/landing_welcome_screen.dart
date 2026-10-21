import 'dart:async';
import 'package:flutter/material.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wave_background_painter.dart';
import 'login_screen.dart';

class LandingWelcomeScreen extends StatefulWidget {
  final VoidCallback? onContinue;

  const LandingWelcomeScreen({super.key, this.onContinue});

  @override
  State<LandingWelcomeScreen> createState() => _LandingWelcomeScreenState();
}

class _LandingWelcomeScreenState extends State<LandingWelcomeScreen> {
  late final PageController _pageController;
  Timer? _autoScrollTimer;
  int _activeDot = 0;
  bool _isUserDragging = false;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(initialPage: 0);
    _startAutoScroll();
  }

  @override
  void dispose() {
    _autoScrollTimer?.cancel();
    _pageController.dispose();
    super.dispose();
  }

  void _startAutoScroll() {
    _autoScrollTimer?.cancel();
    _autoScrollTimer = Timer.periodic(const Duration(milliseconds: 3800), (_) {
      if (!_isUserDragging && _pageController.hasClients) {
        final nextPage = (_activeDot + 1) % 3;
        _pageController.animateToPage(
          nextPage,
          duration: const Duration(milliseconds: 650),
          curve: Curves.easeInOutCubic,
        );
      }
    });
  }

  void _navigateToLogin() {
    _autoScrollTimer?.cancel();
    if (widget.onContinue != null) {
      widget.onContinue!();
    } else {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      body: Stack(
        children: [
          // Background curved red & navy waves
          Positioned.fill(
            child: CustomPaint(
              painter: WaveBackgroundPainter(isDark: false),
            ),
          ),

          SafeArea(
            child: Column(
              children: [
                // Top Bar with Skip Button
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const SizedBox(width: 48), // Spacer to balance
                      TextButton(
                        onPressed: _navigateToLogin,
                        style: TextButton.styleFrom(
                          foregroundColor: const Color(0xFF64748B),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        ),
                        child: const Text(
                          'Skip',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                // Auto-scrolling PageView with 3 on-boarding slides
                Expanded(
                  child: NotificationListener<ScrollNotification>(
                    onNotification: (notification) {
                      if (notification is ScrollStartNotification) {
                        _isUserDragging = true;
                        _autoScrollTimer?.cancel();
                      } else if (notification is ScrollEndNotification) {
                        _isUserDragging = false;
                        _startAutoScroll();
                      }
                      return false;
                    },
                    child: PageView(
                      controller: _pageController,
                      onPageChanged: (index) {
                        setState(() => _activeDot = index);
                      },
                      children: [
                        _buildSlide1(),
                        _buildSlide2(),
                        _buildSlide3(),
                      ],
                    ),
                  ),
                ),

                // "Powered by CHN" Branding
                _buildPoweredByChn(),
                const SizedBox(height: 8),

                // Interactive Carousel Dots Indicator
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(3, (index) {
                    final isActive = index == _activeDot;
                    return GestureDetector(
                      onTap: () {
                        _pageController.animateToPage(
                          index,
                          duration: const Duration(milliseconds: 400),
                          curve: Curves.easeInOut,
                        );
                      },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 280),
                        margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
                        width: isActive ? 22 : 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: isActive ? const Color(0xFFE5252A) : const Color(0xFFFCA5A5).withValues(alpha: 0.6),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    );
                  }),
                ),

                const SizedBox(height: 12),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================
  // SLIDE 1: MANAGE LEADS, CLOSE DEALS
  // ==========================================
  Widget _buildSlide1() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: [
          // Logo & Title
          RichText(
            textAlign: TextAlign.center,
            text: const TextSpan(
              children: [
                TextSpan(
                  text: 'WA!',
                  style: TextStyle(
                    fontSize: 34,
                    fontWeight: FontWeight.w900,
                    color: Color(0xFFE5252A),
                    letterSpacing: -0.5,
                  ),
                ),
                TextSpan(
                  text: 'CRM',
                  style: TextStyle(
                    fontSize: 34,
                    fontWeight: FontWeight.w900,
                    color: Color(0xFF162A45),
                    letterSpacing: -0.5,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Manage Leads. Close Deals. Grow Together.',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Color(0xFF64748B),
              letterSpacing: -0.2,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 8),

          // Slide 1 Hero Illustration (Large Prominent Pingo)
          Expanded(
            child: Center(
              child: FittedBox(
                fit: BoxFit.contain,
                child: SizedBox(
                  width: 360,
                  height: 420,
                  child: Stack(
                    alignment: Alignment.center,
                    clipBehavior: Clip.none,
                    children: [
                      // 3D Podium Glow
                      Positioned(
                        bottom: 0,
                        left: 10,
                        right: 10,
                        height: 100,
                        child: Container(
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [
                                const Color(0xFFE5252A).withValues(alpha: 0.12),
                                const Color(0xFF2563EB).withValues(alpha: 0.08),
                              ],
                            ),
                            borderRadius: BorderRadius.circular(40),
                          ),
                        ),
                      ),

                      // Rising Red Growth Arrow
                      Positioned(
                        top: 15,
                        right: 20,
                        child: Transform.rotate(
                          angle: -0.2,
                          child: const Icon(
                            Icons.trending_up_rounded,
                            size: 105,
                            color: Color(0xFFE5252A),
                          ),
                        ),
                      ),

                      // 3D Bar Chart Pillars
                      Positioned(
                        right: 20,
                        bottom: 45,
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            _buildBar(52, const Color(0xFF93C5FD)),
                            const SizedBox(width: 8),
                            _buildBar(86, const Color(0xFF60A5FA)),
                            const SizedBox(width: 8),
                            _buildBar(130, const Color(0xFF3B82F6)),
                          ],
                        ),
                      ),

                      // Floating circular badges
                      Positioned(
                        top: 55,
                        right: 125,
                        child: _buildCircleBadge(Icons.flag_rounded, const Color(0xFFEF4444), const Color(0xFFFFEEEE)),
                      ),
                      Positioned(
                        bottom: 135,
                        right: 135,
                        child: _buildCircleBadge(Icons.person_rounded, const Color(0xFF2563EB), const Color(0xFFEFF6FF)),
                      ),
                      Positioned(
                        bottom: 50,
                        right: 90,
                        child: _buildCircleBadge(Icons.pie_chart_rounded, const Color(0xFFE11D48), const Color(0xFFFFF1F2)),
                      ),

                      // Large Pingo Mascot (Pointing high)
                      const Positioned(
                        bottom: 0,
                        left: 0,
                        child: PingoMascotWidget(
                          pose: PingoPoses.targetVictory,
                          height: 360,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 8),
        ],
      ),
    );
  }

  // ==========================================
  // SLIDE 2: YOUR LEADS, ALL IN ONE PLACE
  // ==========================================
  Widget _buildSlide2() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: [
          // Title
          RichText(
            textAlign: TextAlign.center,
            text: const TextSpan(
              style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, height: 1.25),
              children: [
                TextSpan(text: 'Your Leads,\n', style: TextStyle(color: Color(0xFF162A45))),
                TextSpan(text: 'All in One Place', style: TextStyle(color: Color(0xFFE5252A))),
              ],
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Track customers, manage follow-ups,\nand stay connected with your team.',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Color(0xFF64748B),
              height: 1.35,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 8),

          // Slide 2 Hero Illustration (Large Pingo with Metrics)
          Expanded(
            child: Center(
              child: FittedBox(
                fit: BoxFit.contain,
                child: SizedBox(
                  width: 360,
                  height: 420,
                  child: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      // Floating Metric Card 1: New Leads
                      Positioned(
                        top: 20,
                        right: 8,
                        child: _buildMetricCard(
                          icon: Icons.person_add_rounded,
                          iconColor: const Color(0xFFEF4444),
                          iconBg: const Color(0xFFFFEEEE),
                          title: 'New Leads',
                          value: '24',
                          change: '↑ 12%',
                          changeColor: const Color(0xFF16A34A),
                        ),
                      ),

                      // Floating Metric Card 2: Follow-ups
                      Positioned(
                        top: 140,
                        right: 0,
                        child: _buildMetricCard(
                          icon: Icons.phone_callback_rounded,
                          iconColor: const Color(0xFF2563EB),
                          iconBg: const Color(0xFFEFF6FF),
                          title: 'Follow-ups',
                          value: '18',
                          change: '↑ 8%',
                          changeColor: const Color(0xFF16A34A),
                        ),
                      ),

                      // Floating Metric Card 3: Converted
                      Positioned(
                        top: 260,
                        right: 12,
                        child: _buildMetricCard(
                          icon: Icons.handshake_rounded,
                          iconColor: const Color(0xFF059669),
                          iconBg: const Color(0xFFECFDF5),
                          title: 'Converted',
                          value: '5',
                          change: '↑ 25%',
                          changeColor: const Color(0xFF16A34A),
                        ),
                      ),

                      // Large Pingo Mascot (Working at laptop)
                      const Positioned(
                        bottom: 0,
                        left: -10,
                        child: PingoMascotWidget(
                          pose: PingoPoses.ideaPoint,
                          height: 360,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 8),
        ],
      ),
    );
  }

  // ==========================================
  // SLIDE 3: TURN OPPORTUNITIES INTO SUCCESS
  // ==========================================
  Widget _buildSlide3() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: [
          // Title
          RichText(
            textAlign: TextAlign.center,
            text: const TextSpan(
              style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, height: 1.25),
              children: [
                TextSpan(text: 'Turn Opportunities\n', style: TextStyle(color: Color(0xFF162A45))),
                TextSpan(text: 'into Success', style: TextStyle(color: Color(0xFFE5252A))),
              ],
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Manage calls, deals, quotations, and\ncustomer activities from one app.',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Color(0xFF64748B),
              height: 1.35,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 8),

          // Slide 3 Hero with Orbiting Module Icons & Large Thumbs-Up Pingo
          Expanded(
            child: Center(
              child: FittedBox(
                fit: BoxFit.contain,
                child: SizedBox(
                  width: 360,
                  height: 350,
                  child: Stack(
                    alignment: Alignment.center,
                    clipBehavior: Clip.none,
                    children: [
                      // Circular Orbit Path Guide (Subtle dashed look)
                      Container(
                        width: 310,
                        height: 310,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: const Color(0xFFE2E8F0).withValues(alpha: 0.9),
                            width: 1.5,
                          ),
                        ),
                      ),

                      // Large Center Mascot (Thumbs up victory)
                      const Positioned(
                        bottom: 10,
                        child: PingoMascotWidget(
                          pose: PingoPoses.victory,
                          height: 300,
                        ),
                      ),

                      // Orbit 1: Calls (Top Left)
                      Positioned(
                        top: 12,
                        left: 20,
                        child: _buildOrbitBadge(Icons.phone_in_talk_rounded, 'Calls', const Color(0xFF2563EB)),
                      ),

                      // Orbit 2: Leads (Mid Left)
                      Positioned(
                        top: 125,
                        left: 2,
                        child: _buildOrbitBadge(Icons.people_alt_rounded, 'Leads', const Color(0xFF6366F1)),
                      ),

                      // Orbit 3: Deals (Bottom Left)
                      Positioned(
                        bottom: 35,
                        left: 22,
                        child: _buildOrbitBadge(Icons.handshake_rounded, 'Deals', const Color(0xFF059669)),
                      ),

                      // Orbit 4: Quotation (Top Right)
                      Positioned(
                        top: 12,
                        right: 20,
                        child: _buildOrbitBadge(Icons.description_rounded, 'Quotation', const Color(0xFFE5252A)),
                      ),

                      // Orbit 5: Activities (Mid Right)
                      Positioned(
                        top: 125,
                        right: 2,
                        child: _buildOrbitBadge(Icons.calendar_month_rounded, 'Activities', const Color(0xFFD97706)),
                      ),

                      // Orbit 6: Reports (Bottom Right)
                      Positioned(
                        bottom: 35,
                        right: 22,
                        child: _buildOrbitBadge(Icons.bar_chart_rounded, 'Reports', const Color(0xFF0284C7)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 8),

          // Prominent Crimson "Get Started →" Button on Slide 3
          SizedBox(
            width: double.infinity,
            height: 52,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFE5252A),
                foregroundColor: Colors.white,
                elevation: 4,
                shadowColor: const Color(0xFFE5252A).withValues(alpha: 0.35),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(26),
                ),
              ),
              onPressed: _navigateToLogin,
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'Get Started',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.2,
                    ),
                  ),
                  SizedBox(width: 8),
                  Icon(Icons.arrow_forward_rounded, size: 20),
                ],
              ),
            ),
          ),

          const SizedBox(height: 8),
        ],
      ),
    );
  }

  // ==========================================
  // SHARED UI WIDGETS & BADGES
  // ==========================================

  Widget _buildBar(double height, Color color) {
    return Container(
      width: 18,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(6),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.3),
            blurRadius: 6,
            offset: const Offset(0, 3),
          ),
        ],
      ),
    );
  }

  Widget _buildCircleBadge(IconData icon, Color color, Color bgColor) {
    return Container(
      padding: const EdgeInsets.all(7),
      decoration: BoxDecoration(
        color: bgColor,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.2),
            blurRadius: 8,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Icon(icon, size: 15, color: color),
    );
  }

  Widget _buildMetricCard({
    required IconData icon,
    required Color iconColor,
    required Color iconBg,
    required String title,
    required String value,
    required String change,
    required Color changeColor,
  }) {
    return Container(
      width: 140,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 16, color: iconColor),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF64748B),
                  ),
                ),
                Row(
                  children: [
                    Text(
                      value,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF0F172A),
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      change,
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        color: changeColor,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOrbitBadge(IconData icon, String label, Color color) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(9),
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: const Color(0xFFE2E8F0)),
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: 0.15),
                blurRadius: 8,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(height: 3),
        Text(
          label,
          style: const TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w700,
            color: Color(0xFF475569),
          ),
        ),
      ],
    );
  }

  Widget _buildPoweredByChn() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text(
          'Powered by',
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w600,
            color: Color(0xFF64748B),
            letterSpacing: 0.2,
          ),
        ),
        const SizedBox(height: 2),
        // Stylized CHN Logo
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: const Color(0xFF0284C7).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFF0284C7).withValues(alpha: 0.25)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.hub_rounded, size: 12, color: Color(0xFF0284C7)),
                  SizedBox(width: 4),
                  Text(
                    'CHN',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w900,
                      color: Color(0xFF0284C7),
                      letterSpacing: 1.5,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}
