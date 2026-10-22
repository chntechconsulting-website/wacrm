import 'dart:async';
import 'dart:math' as math;
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
      backgroundColor: Colors.white,
      body: Stack(
        children: [
          // Background dual curved red & navy waves
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
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 2),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const SizedBox(width: 48), // Spacer
                      InkWell(
                        onTap: _navigateToLogin,
                        borderRadius: BorderRadius.circular(20),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: const Color(0xFFE2E8F0)),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withValues(alpha: 0.04),
                                blurRadius: 6,
                                offset: const Offset(0, 2),
                              ),
                            ],
                          ),
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                'Skip',
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF475569),
                                ),
                              ),
                              SizedBox(width: 4),
                              Icon(Icons.chevron_right_rounded, size: 16, color: Color(0xFF475569)),
                            ],
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

                // BALANCED COMPACT FOOTER SECTION
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // 1. Get Started Button (Appears only on Slide 3)
                      AnimatedCrossFade(
                        firstChild: const SizedBox(height: 0),
                        secondChild: Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: SizedBox(
                            width: double.infinity,
                            height: 48,
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFFE5252A),
                                foregroundColor: Colors.white,
                                elevation: 3,
                                shadowColor: const Color(0xFFE5252A).withValues(alpha: 0.35),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(24),
                                ),
                              ),
                              onPressed: _navigateToLogin,
                              child: const Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    'Get Started',
                                    style: TextStyle(
                                      fontSize: 15.5,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: 0.2,
                                    ),
                                  ),
                                  SizedBox(width: 8),
                                  Icon(Icons.arrow_forward_rounded, size: 19),
                                ],
                              ),
                            ),
                          ),
                        ),
                        crossFadeState: _activeDot == 2 ? CrossFadeState.showSecond : CrossFadeState.showFirst,
                        duration: const Duration(milliseconds: 250),
                      ),

                      // 2. 3 Dot Indicators
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
                              duration: const Duration(milliseconds: 200),
                              margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
                              width: isActive ? 18 : 7,
                              height: 7,
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(4),
                                color: isActive
                                    ? const Color(0xFFE5252A)
                                    : const Color(0xFFFFCDD2).withValues(alpha: 0.85),
                              ),
                            ),
                          );
                        }),
                      ),
                      const SizedBox(height: 6),

                      // 3. "Powered by CHN" Branding
                      _buildPoweredByChn(),
                      const SizedBox(height: 6),
                    ],
                  ),
                ),
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
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          const SizedBox(height: 2),
          // WA!CRM Official 3D Ribbon Logo Asset
          Image.asset(
            'assets/images/logo.png',
            height: 44,
            fit: BoxFit.contain,
            errorBuilder: (ctx, err, stack) => RichText(
              textAlign: TextAlign.center,
              text: const TextSpan(
                children: [
                  TextSpan(
                    text: 'WA!',
                    style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.w900,
                      color: Color(0xFFE5252A),
                      letterSpacing: -0.5,
                    ),
                  ),
                  TextSpan(
                    text: 'CRM',
                    style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.w900,
                      color: Color(0xFF162A45),
                      letterSpacing: -0.5,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Manage Leads. Close Deals. Grow Together.',
            style: TextStyle(
              fontSize: 13.5,
              fontWeight: FontWeight.w500,
              color: Color(0xFF64748B),
              letterSpacing: -0.2,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 8),

          // Slide 1 Hero Illustration
          Expanded(
            child: Align(
              alignment: const Alignment(0, -0.15),
              child: FittedBox(
                fit: BoxFit.contain,
                child: SizedBox(
                  width: 340,
                  height: 330,
                  child: Stack(
                    alignment: Alignment.center,
                    clipBehavior: Clip.none,
                    children: [
                      // Floor Shadow under Pingo
                      Positioned(
                        bottom: 6,
                        left: 10,
                        width: 155,
                        height: 22,
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: const BorderRadius.all(Radius.elliptical(77, 11)),
                            color: Colors.black.withValues(alpha: 0.06),
                          ),
                        ),
                      ),

                      // 3D Glass Podium Stage under the 4 pillars
                      Positioned(
                        right: 8,
                        bottom: 22,
                        width: 156,
                        height: 40,
                        child: CustomPaint(
                          painter: _StagePodiumPainter(),
                        ),
                      ),

                      // 4 Glossy 3D Pillars
                      Positioned(
                        right: 36,
                        bottom: 38,
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            _buildGlossy3DBar(
                              height: 36,
                              lightColor: const Color(0xFFEFF6FF),
                              primaryColor: const Color(0xFFBFDBFE),
                              darkColor: const Color(0xFF93C5FD),
                            ),
                            const SizedBox(width: 8),
                            _buildGlossy3DBar(
                              height: 68,
                              lightColor: const Color(0xFFDBEAFE),
                              primaryColor: const Color(0xFF93C5FD),
                              darkColor: const Color(0xFF60A5FA),
                            ),
                            const SizedBox(width: 8),
                            _buildGlossy3DBar(
                              height: 104,
                              lightColor: const Color(0xFF93C5FD),
                              primaryColor: const Color(0xFF60A5FA),
                              darkColor: const Color(0xFF2563EB),
                            ),
                            const SizedBox(width: 8),
                            _buildGlossy3DBar(
                              height: 144,
                              lightColor: const Color(0xFF60A5FA),
                              primaryColor: const Color(0xFF2563EB),
                              darkColor: const Color(0xFF1D4ED8),
                            ),
                          ],
                        ),
                      ),

                      // 3D Curved Growth Arrow
                      Positioned(
                        right: 18,
                        bottom: 44,
                        width: 155,
                        height: 185,
                        child: CustomPaint(
                          painter: _GrowthArrowPainter(),
                        ),
                      ),

                      // 3 Floating White Badges with Colored Glows
                      // 1. Red Flag Badge (Top)
                      Positioned(
                        top: 18,
                        right: 82,
                        child: _buildFloatingWhiteBadge(
                          Icons.flag_rounded,
                          const Color(0xFFE5252A),
                        ),
                      ),

                      // 2. Blue Person Badge (Middle)
                      Positioned(
                        top: 112,
                        right: 130,
                        child: _buildFloatingWhiteBadge(
                          Icons.person_rounded,
                          const Color(0xFF2563EB),
                        ),
                      ),

                      // 3. Red Pie Chart Badge (Bottom)
                      Positioned(
                        bottom: 52,
                        right: 16,
                        child: _buildFloatingWhiteBadge(
                          Icons.pie_chart_rounded,
                          const Color(0xFFE5252A),
                        ),
                      ),

                      // Pingo Mascot (Pointing high in victory pose)
                      const Positioned(
                        bottom: 0,
                        left: 2,
                        child: PingoMascotWidget(
                          pose: PingoPoses.victory,
                          height: 295,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================
  // SLIDE 2: YOUR LEADS, ALL IN ONE PLACE
  // ==========================================
  Widget _buildSlide2() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          const SizedBox(height: 2),
          // Title
          RichText(
            textAlign: TextAlign.center,
            text: const TextSpan(
              style: TextStyle(fontSize: 27, fontWeight: FontWeight.w900, height: 1.15),
              children: [
                TextSpan(text: 'Your Leads,\n', style: TextStyle(color: Color(0xFF162A45))),
                TextSpan(text: 'All in One Place', style: TextStyle(color: Color(0xFFE5252A))),
              ],
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Track customers, manage follow-ups,\nand stay connected with your team.',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Color(0xFF64748B),
              height: 1.3,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 8),

          // Slide 2 Hero Illustration
          Expanded(
            child: Align(
              alignment: const Alignment(0, -0.15),
              child: FittedBox(
                fit: BoxFit.contain,
                child: SizedBox(
                  width: 350,
                  height: 320,
                  child: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      // Floor Ambient Shadow
                      Positioned(
                        bottom: 0,
                        left: 10,
                        width: 270,
                        height: 26,
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: const BorderRadius.all(Radius.elliptical(135, 13)),
                            color: Colors.black.withValues(alpha: 0.05),
                          ),
                        ),
                      ),

                      // Curved Dashed Path Guide Lines
                      Positioned.fill(
                        child: CustomPaint(
                          painter: _Slide2DashedPathPainter(),
                        ),
                      ),

                      // Floating Badge 1: Top-Left Speech Trend
                      Positioned(
                        top: 18,
                        left: 14,
                        child: _buildTopLeftTrendBadge(),
                      ),

                      // Floating Badge 2: Bottom-Right Pie Chart
                      Positioned(
                        bottom: 26,
                        right: 18,
                        child: _buildBottomRightPieBadge(),
                      ),

                      // Pingo Mascot (Sitting at laptop with WA!CRM logo & pointing with red idea sparks)
                      const Positioned(
                        bottom: 0,
                        left: 0,
                        child: PingoMascotWidget(
                          pose: PingoPoses.laptop,
                          height: 265,
                        ),
                      ),

                      // Floating Metric Card 1: New Leads
                      Positioned(
                        top: 12,
                        right: 6,
                        child: _buildMetricCard(
                          icon: Icons.person_rounded,
                          iconStartColor: const Color(0xFFFF5252),
                          iconEndColor: const Color(0xFFE5252A),
                          title: 'New Leads',
                          value: '24',
                          change: '↑ 12%',
                          changeColor: const Color(0xFF16A34A),
                        ),
                      ),

                      // Floating Metric Card 2: Follow-ups
                      Positioned(
                        top: 104,
                        right: 6,
                        child: _buildMetricCard(
                          icon: Icons.phone_rounded,
                          iconStartColor: const Color(0xFF60A5FA),
                          iconEndColor: const Color(0xFF2563EB),
                          title: 'Follow-ups',
                          value: '18',
                          change: '↑ 8%',
                          changeColor: const Color(0xFFE5252A),
                        ),
                      ),

                      // Floating Metric Card 3: Converted
                      Positioned(
                        top: 196,
                        right: 6,
                        child: _buildMetricCard(
                          icon: Icons.handshake_rounded,
                          iconStartColor: const Color(0xFF34D399),
                          iconEndColor: const Color(0xFF10B981),
                          title: 'Converted',
                          value: '5',
                          change: '↑ 25%',
                          changeColor: const Color(0xFF16A34A),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================
  // SLIDE 3: TURN OPPORTUNITIES INTO SUCCESS
  // ==========================================
  Widget _buildSlide3() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          const SizedBox(height: 2),
          // Title
          RichText(
            textAlign: TextAlign.center,
            text: const TextSpan(
              style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, height: 1.18),
              children: [
                TextSpan(text: 'Turn Opportunities\n', style: TextStyle(color: Color(0xFF162A45))),
                TextSpan(text: 'into Success', style: TextStyle(color: Color(0xFFE5252A))),
              ],
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Manage calls, deals, quotations, and\ncustomer activities from one app.',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Color(0xFF64748B),
              height: 1.3,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 8),

          // Slide 3 Hero with Orbiting Module Icons & Thumbs-Up Pingo
          Expanded(
            child: Align(
              alignment: const Alignment(0, -0.15),
              child: FittedBox(
                fit: BoxFit.contain,
                child: SizedBox(
                  width: 330,
                  height: 310,
                  child: Stack(
                    alignment: Alignment.center,
                    clipBehavior: Clip.none,
                    children: [
                      // Floor shadow under mascot
                      Positioned(
                        bottom: 0,
                        width: 140,
                        height: 18,
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: const BorderRadius.all(Radius.elliptical(70, 9)),
                            color: Colors.black.withValues(alpha: 0.05),
                          ),
                        ),
                      ),

                      // Circular Orbit Path Guide (Subtle dashed look)
                      Container(
                        width: 260,
                        height: 260,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: const Color(0xFFE2E8F0).withValues(alpha: 0.9),
                            width: 1.5,
                          ),
                        ),
                      ),

                      // Center Mascot (Thumbs up victory pose)
                      const Positioned(
                        bottom: 4,
                        child: PingoMascotWidget(
                          pose: PingoPoses.victory,
                          height: 250,
                        ),
                      ),

                      // Orbit 1: Calls (Top Left)
                      Positioned(
                        top: 10,
                        left: 22,
                        child: _buildOrbitBadge(Icons.phone_in_talk_rounded, 'Calls', const Color(0xFF2563EB)),
                      ),

                      // Orbit 2: Leads (Mid Left)
                      Positioned(
                        top: 110,
                        left: 4,
                        child: _buildOrbitBadge(Icons.people_alt_rounded, 'Leads', const Color(0xFF6366F1)),
                      ),

                      // Orbit 3: Deals (Bottom Left)
                      Positioned(
                        bottom: 22,
                        left: 22,
                        child: _buildOrbitBadge(Icons.handshake_rounded, 'Deals', const Color(0xFF10B981)),
                      ),

                      // Orbit 4: Quotation (Top Right)
                      Positioned(
                        top: 10,
                        right: 22,
                        child: _buildOrbitBadge(Icons.description_rounded, 'Quotation', const Color(0xFFE5252A)),
                      ),

                      // Orbit 5: Activities (Mid Right)
                      Positioned(
                        top: 110,
                        right: 4,
                        child: _buildOrbitBadge(Icons.calendar_month_rounded, 'Activities', const Color(0xFFF59E0B)),
                      ),

                      // Orbit 6: Reports (Bottom Right)
                      Positioned(
                        bottom: 22,
                        right: 22,
                        child: _buildOrbitBadge(Icons.bar_chart_rounded, 'Reports', const Color(0xFF0284C7)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================
  // SHARED UI WIDGETS & BADGES
  // ==========================================

  Widget _buildGlossy3DBar({
    required double height,
    required Color lightColor,
    required Color primaryColor,
    required Color darkColor,
  }) {
    return Container(
      width: 19,
      height: height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(9.5),
        gradient: LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [lightColor, primaryColor, darkColor],
          stops: const [0.0, 0.45, 1.0],
        ),
        boxShadow: [
          BoxShadow(
            color: darkColor.withValues(alpha: 0.35),
            blurRadius: 8,
            offset: const Offset(2, 4),
          ),
        ],
      ),
      child: Stack(
        children: [
          // Specular glossy vertical highlight
          Positioned(
            top: 3,
            left: 2.5,
            bottom: 3,
            width: 3,
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(1.5),
                color: Colors.white.withValues(alpha: 0.55),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFloatingWhiteBadge(IconData icon, Color color) {
    return Container(
      width: 34,
      height: 34,
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.25),
            blurRadius: 10,
            spreadRadius: 1,
            offset: const Offset(0, 3),
          ),
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 5,
            offset: const Offset(0, 1.5),
          ),
        ],
      ),
      child: Center(
        child: Icon(icon, size: 18, color: color),
      ),
    );
  }

  Widget _buildTopLeftTrendBadge() {
    return Container(
      width: 46,
      height: 46,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFF1F5F9)),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFE5252A).withValues(alpha: 0.15),
            blurRadius: 12,
            spreadRadius: 1,
            offset: const Offset(0, 4),
          ),
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Center(
        child: Container(
          width: 28,
          height: 24,
          decoration: BoxDecoration(
            color: const Color(0xFFE5252A),
            borderRadius: BorderRadius.circular(7),
          ),
          child: const Center(
            child: Icon(
              Icons.trending_up_rounded,
              color: Colors.white,
              size: 18,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildBottomRightPieBadge() {
    return Container(
      width: 46,
      height: 46,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFF1F5F9)),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFE5252A).withValues(alpha: 0.15),
            blurRadius: 12,
            spreadRadius: 1,
            offset: const Offset(0, 4),
          ),
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: const Center(
        child: Icon(
          Icons.pie_chart_rounded,
          color: Color(0xFFE5252A),
          size: 24,
        ),
      ),
    );
  }

  Widget _buildMetricCard({
    required IconData icon,
    required Color iconStartColor,
    required Color iconEndColor,
    required String title,
    required String value,
    required String change,
    required Color changeColor,
  }) {
    return Container(
      width: 156,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [iconStartColor, iconEndColor],
              ),
              boxShadow: [
                BoxShadow(
                  color: iconEndColor.withValues(alpha: 0.35),
                  blurRadius: 8,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Icon(icon, size: 20, color: Colors.white),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF64748B),
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF0F172A),
                    height: 1.15,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  change,
                  style: TextStyle(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w700,
                    color: changeColor,
                  ),
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
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: const Color(0xFFE2E8F0), width: 1.2),
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
            fontSize: 9.5,
            fontWeight: FontWeight.w700,
            color: Color(0xFF475569),
          ),
        ),
      ],
    );
  }

  Widget _buildPoweredByChn() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'Powered by',
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w600,
              color: Color(0xFF64748B),
              letterSpacing: 0.2,
            ),
          ),
          const SizedBox(width: 7),
          // Authentic CHN Corporate Logo
          Image.asset(
            'assets/images/chn_logo.png',
            height: 16,
            fit: BoxFit.contain,
            errorBuilder: (ctx, err, stack) => const Text(
              'CHN',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w900,
                color: Color(0xFF0065B3),
                letterSpacing: 1.2,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StagePodiumPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final ovalHeight = h * 0.55;
    final cylinderHeight = h * 0.45;

    // Floor contact shadow under the podium
    final shadowPaint = Paint()
      ..color = const Color(0xFF0284C7).withValues(alpha: 0.16)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(w / 2, h * 0.88),
        width: w * 0.95,
        height: ovalHeight * 0.8,
      ),
      shadowPaint,
    );

    // Cylinder side body
    final bodyPath = Path()
      ..moveTo(0, ovalHeight / 2)
      ..lineTo(0, ovalHeight / 2 + cylinderHeight)
      ..arcToPoint(
        Offset(w, ovalHeight / 2 + cylinderHeight),
        radius: Radius.elliptical(w / 2, ovalHeight / 2),
        clockwise: false,
      )
      ..lineTo(w, ovalHeight / 2)
      ..arcToPoint(
        Offset(0, ovalHeight / 2),
        radius: Radius.elliptical(w / 2, ovalHeight / 2),
        clockwise: true,
      )
      ..close();

    final bodyPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          const Color(0xFFBAE6FD).withValues(alpha: 0.88),
          const Color(0xFF7DD3FC).withValues(alpha: 0.72),
          const Color(0xFF38BDF8).withValues(alpha: 0.55),
        ],
      ).createShader(Rect.fromLTWH(0, ovalHeight / 2, w, cylinderHeight));
    canvas.drawPath(bodyPath, bodyPaint);

    // Top Oval surface
    final topOvalRect = Rect.fromLTWH(0, 0, w, ovalHeight);
    final topPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Colors.white.withValues(alpha: 0.95),
          const Color(0xFFE0F2FE).withValues(alpha: 0.90),
          const Color(0xFFBAE6FD).withValues(alpha: 0.82),
        ],
      ).createShader(topOvalRect);
    canvas.drawOval(topOvalRect, topPaint);

    // Top Oval glossy edge highlight rim
    final rimPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Colors.white,
          const Color(0xFF7DD3FC).withValues(alpha: 0.65),
        ],
      ).createShader(topOvalRect);
    canvas.drawOval(topOvalRect, rimPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _GrowthArrowPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Arrow curve path from bottom-left (base of Bar 1) to top-right (above Bar 4)
    final startPoint = Offset(w * 0.08, h * 0.90);
    final controlPoint1 = Offset(w * 0.38, h * 0.82);
    final controlPoint2 = Offset(w * 0.68, h * 0.32);
    final tipPoint = Offset(w * 0.94, h * 0.12);

    final arrowPath = Path()
      ..moveTo(startPoint.dx, startPoint.dy)
      ..cubicTo(
        controlPoint1.dx,
        controlPoint1.dy,
        controlPoint2.dx,
        controlPoint2.dy,
        tipPoint.dx,
        tipPoint.dy,
      );

    // 1. Soft glowing ribbon drop trail
    final glowPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12.0
      ..strokeCap = StrokeCap.round
      ..color = const Color(0xFFE5252A).withValues(alpha: 0.22)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5);
    canvas.drawPath(arrowPath, glowPaint);

    // 2. Main red curved arrow shaft
    final strokePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5.5
      ..strokeCap = StrokeCap.round
      ..shader = const LinearGradient(
        begin: Alignment.bottomLeft,
        end: Alignment.topRight,
        colors: [
          Color(0xFFE5252A),
          Color(0xFFFF3B30),
        ],
      ).createShader(Rect.fromLTWH(0, 0, w, h));
    canvas.drawPath(arrowPath, strokePaint);

    // 3. Arrowhead at tip pointing along tangent
    final dx = tipPoint.dx - controlPoint2.dx;
    final dy = tipPoint.dy - controlPoint2.dy;
    final angle = math.atan2(dy, dx);

    const headLength = 16.0;

    final headPath = Path();
    headPath.moveTo(tipPoint.dx, tipPoint.dy);
    headPath.lineTo(
      tipPoint.dx - headLength * math.cos(angle - 0.48),
      tipPoint.dy - headLength * math.sin(angle - 0.48),
    );
    headPath.lineTo(
      tipPoint.dx - (headLength * 0.65) * math.cos(angle),
      tipPoint.dy - (headLength * 0.65) * math.sin(angle),
    );
    headPath.lineTo(
      tipPoint.dx - headLength * math.cos(angle + 0.48),
      tipPoint.dy - headLength * math.sin(angle + 0.48),
    );
    headPath.close();

    final headPaint = Paint()
      ..style = PaintingStyle.fill
      ..shader = const LinearGradient(
        begin: Alignment.bottomLeft,
        end: Alignment.topRight,
        colors: [
          Color(0xFFE5252A),
          Color(0xFFFF3B30),
        ],
      ).createShader(Rect.fromLTWH(0, 0, w, h));

    final headShadow = Paint()
      ..style = PaintingStyle.fill
      ..color = const Color(0xFFE5252A).withValues(alpha: 0.35)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
    canvas.drawPath(headPath.shift(const Offset(1, 2)), headShadow);
    canvas.drawPath(headPath, headPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _Slide2DashedPathPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    final paint = Paint()
      ..color = const Color(0xFF93C5FD)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;

    // 1. Path 1: Curving up to the top-left badge
    final path1 = Path()
      ..moveTo(w * 0.07, h * 0.46)
      ..cubicTo(w * 0.05, h * 0.38, w * 0.06, h * 0.28, w * 0.14, h * 0.20);
    _drawDashedPath(canvas, path1, paint, 4, 3);

    // Arrowhead pointing towards top-left badge
    final arrowPaint = Paint()
      ..color = const Color(0xFF93C5FD)
      ..style = PaintingStyle.fill;
    final arrowPath1 = Path()
      ..moveTo(w * 0.14, h * 0.20)
      ..lineTo(w * 0.10, h * 0.21)
      ..lineTo(w * 0.13, h * 0.24)
      ..close();
    canvas.drawPath(arrowPath1, arrowPaint);

    // 2. Path 2: Curving down from the cards towards the bottom-right pie badge
    final path2 = Path()
      ..moveTo(w * 0.76, h * 0.70)
      ..cubicTo(w * 0.82, h * 0.74, w * 0.88, h * 0.69, w * 0.94, h * 0.63);
    _drawDashedPath(canvas, path2, paint, 4, 3);
  }

  void _drawDashedPath(Canvas canvas, Path path, Paint paint, double dashWidth, double dashSpace) {
    for (final metric in path.computeMetrics()) {
      double start = 0.0;
      while (start < metric.length) {
        final end = (start + dashWidth < metric.length) ? start + dashWidth : metric.length;
        canvas.drawPath(metric.extractPath(start, end), paint);
        start += dashWidth + dashSpace;
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
