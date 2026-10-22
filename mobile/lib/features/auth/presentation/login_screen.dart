import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/network/token_storage.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _rememberMe = true;

  @override
  void initState() {
    super.initState();
    _loadSavedUsername();
  }

  Future<void> _loadSavedUsername() async {
    final saved = await TokenStorage.getRememberedUsername();
    if (saved != null && saved.isNotEmpty && saved != 'admin') {
      _usernameController.text = saved;
    } else {
      _usernameController.text = '';
      if (saved == 'admin') {
        await TokenStorage.saveRememberedUsername('');
      }
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;

    final authProvider = context.read<AuthProvider>();
    final success = await authProvider.login(
      _usernameController.text,
      _passwordController.text,
      rememberMe: _rememberMe,
    );

    if (!success && mounted) {
      final msg = authProvider.errorMessage ?? 'Invalid credentials';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(msg),
          backgroundColor: AppColors.danger,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  void _showServerConfigDialog() {
    final serverController = TextEditingController(text: ApiEndpoints.baseUrl);

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.settings_ethernet_rounded, color: Color(0xFFE5252A), size: 22),
            SizedBox(width: 8),
            Text('Server Configuration', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Set the backend FastAPI server URL:',
              style: TextStyle(fontSize: 13, color: Color(0xFF64748B)),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: serverController,
              decoration: const InputDecoration(
                hintText: 'e.g. http://10.0.2.2:8000',
                labelText: 'Base URL',
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              children: [
                ActionChip(
                  avatar: const Icon(Icons.cloud_done_rounded, size: 14, color: Color(0xFFE5252A)),
                  label: const Text('Production', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
                  onPressed: () {
                    serverController.text = ApiEndpoints.productionBaseUrl;
                  },
                ),
                ActionChip(
                  label: const Text('Emulator (10.0.2.2)', style: TextStyle(fontSize: 11)),
                  onPressed: () {
                    serverController.text = 'http://10.0.2.2:8000';
                  },
                ),
                ActionChip(
                  label: const Text('Localhost (127.0.0.1)', style: TextStyle(fontSize: 11)),
                  onPressed: () {
                    serverController.text = 'http://127.0.0.1:8000';
                  },
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFE5252A),
              foregroundColor: Colors.white,
            ),
            onPressed: () {
              context.read<AuthProvider>().updateServerUrl(serverController.text);
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Server updated to ${serverController.text}'),
                  backgroundColor: AppColors.success,
                  behavior: SnackBarBehavior.floating,
                ),
              );
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final isLoading = authProvider.status == AuthStatus.loading;

    return Scaffold(
      backgroundColor: Colors.white,
      body: Stack(
        children: [
          // Background dual brand waves (Crimson Red & Corporate Navy)
          Positioned.fill(
            child: CustomPaint(
              painter: _LoginWaveBackgroundPainter(),
            ),
          ),

          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Subtle top action row (Server settings)
                      Align(
                        alignment: Alignment.topRight,
                        child: IconButton(
                          tooltip: 'Server Settings',
                          icon: const Icon(Icons.settings_outlined, color: Color(0xFF94A3B8), size: 20),
                          onPressed: _showServerConfigDialog,
                        ),
                      ),

                      // TOP HEADER SECTION: Brand + Subtitle + 3 Mini Feature Badges & Pingo Mascot
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          // Left side: Brand title, subtitle, and 3 mini feature badges
                          Expanded(
                            flex: 6,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Image.asset(
                                  'assets/images/logo.png',
                                  height: 38,
                                  fit: BoxFit.contain,
                                  alignment: Alignment.centerLeft,
                                  errorBuilder: (ctx, err, stack) => RichText(
                                    text: const TextSpan(
                                      children: [
                                        TextSpan(
                                          text: 'WA!',
                                          style: TextStyle(
                                            fontSize: 32,
                                            fontWeight: FontWeight.w900,
                                            color: Color(0xFFE5252A),
                                            letterSpacing: -0.5,
                                          ),
                                        ),
                                        TextSpan(
                                          text: 'CRM',
                                          style: TextStyle(
                                            fontSize: 32,
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
                                  'Manage Leads. Close Deals.\nGrow Together.',
                                  style: TextStyle(
                                    fontSize: 12.5,
                                    fontWeight: FontWeight.w500,
                                    color: Color(0xFF64748B),
                                    height: 1.3,
                                  ),
                                ),
                                const SizedBox(height: 12),

                                // Row of 3 mini feature badges (Leads, Deals, Growth)
                                Row(
                                  children: [
                                    _buildMiniFeature(Icons.groups_rounded, 'Leads', const Color(0xFFE5252A), const Color(0xFFFFECEE)),
                                    const SizedBox(width: 8),
                                    _buildMiniFeature(Icons.handshake_rounded, 'Deals', const Color(0xFF2563EB), const Color(0xFFEFF6FF)),
                                    const SizedBox(width: 8),
                                    _buildMiniFeature(Icons.bar_chart_rounded, 'Growth', const Color(0xFFE11D48), const Color(0xFFFFF1F2)),
                                  ],
                                ),
                              ],
                            ),
                          ),

                          const SizedBox(width: 4),

                          // Right side: Pingo Mascot with Rising Red Arrow and Pillars
                          Expanded(
                            flex: 5,
                            child: SizedBox(
                              height: 175,
                              child: Stack(
                                alignment: Alignment.bottomCenter,
                                clipBehavior: Clip.none,
                                children: [
                                  // Rising Red Arrow
                                  Positioned(
                                    top: 0,
                                    right: 12,
                                    child: Transform.rotate(
                                      angle: -0.22,
                                      child: const Icon(
                                        Icons.trending_up_rounded,
                                        size: 64,
                                        color: Color(0xFFE5252A),
                                      ),
                                    ),
                                  ),

                                  // 3D Bar Chart Pillars
                                  Positioned(
                                    right: 8,
                                    bottom: 25,
                                    child: Row(
                                      crossAxisAlignment: CrossAxisAlignment.end,
                                      children: [
                                        _buildMiniBar(28, const Color(0xFFBFDBFE)),
                                        const SizedBox(width: 4),
                                        _buildMiniBar(45, const Color(0xFF93C5FD)),
                                        const SizedBox(width: 4),
                                        _buildMiniBar(68, const Color(0xFF60A5FA)),
                                      ],
                                    ),
                                  ),

                                  // Pingo Mascot (holding laptop and pointing up)
                                  const Positioned(
                                    bottom: -6,
                                    right: 0,
                                    child: PingoMascotWidget(
                                      pose: PingoPoses.ideaPoint,
                                      height: 165,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 18),

                      // PRISTINE WHITE LOGIN CARD
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 24),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(28),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(0xFF162A45).withValues(alpha: 0.08),
                              blurRadius: 28,
                              offset: const Offset(0, 10),
                            ),
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.03),
                              blurRadius: 8,
                              offset: const Offset(0, 2),
                            ),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            // Welcome Back Header
                            RichText(
                              textAlign: TextAlign.center,
                              text: const TextSpan(
                                children: [
                                  TextSpan(
                                    text: 'Welcome ',
                                    style: TextStyle(
                                      fontSize: 24,
                                      fontWeight: FontWeight.w800,
                                      color: Color(0xFF162A45),
                                      letterSpacing: -0.3,
                                    ),
                                  ),
                                  TextSpan(
                                    text: 'Back',
                                    style: TextStyle(
                                      fontSize: 24,
                                      fontWeight: FontWeight.w800,
                                      color: Color(0xFFE5252A),
                                      letterSpacing: -0.3,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 6),
                            const Text(
                              'Sign in to continue to your CRM',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w500,
                                color: Color(0xFF64748B),
                              ),
                            ),
                            const SizedBox(height: 22),

                            // Email / Username Input
                            Container(
                              decoration: BoxDecoration(
                                color: const Color(0xFFF1F5F9),
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(color: const Color(0xFFE2E8F0).withValues(alpha: 0.6)),
                              ),
                              child: TextFormField(
                                controller: _usernameController,
                                style: const TextStyle(fontSize: 14.5, color: Color(0xFF0F172A), fontWeight: FontWeight.w500),
                                decoration: const InputDecoration(
                                  hintText: 'chandra@chntech.com',
                                  hintStyle: TextStyle(fontSize: 14, color: Color(0xFF94A3B8), fontWeight: FontWeight.w400),
                                  prefixIcon: Icon(Icons.mail_outline_rounded, color: Color(0xFF1E293B), size: 21),
                                  border: InputBorder.none,
                                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 15),
                                ),
                                validator: (val) {
                                  if (val == null || val.trim().isEmpty) {
                                    return 'Please enter username or email';
                                  }
                                  return null;
                                },
                              ),
                            ),
                            const SizedBox(height: 14),

                            // Password Input
                            Container(
                              decoration: BoxDecoration(
                                color: const Color(0xFFF1F5F9),
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(color: const Color(0xFFE2E8F0).withValues(alpha: 0.6)),
                              ),
                              child: TextFormField(
                                controller: _passwordController,
                                obscureText: _obscurePassword,
                                style: const TextStyle(fontSize: 14.5, color: Color(0xFF0F172A), fontWeight: FontWeight.w500),
                                decoration: InputDecoration(
                                  hintText: '••••••••',
                                  hintStyle: const TextStyle(fontSize: 14, color: Color(0xFF94A3B8), letterSpacing: 2),
                                  prefixIcon: const Icon(Icons.lock_outline_rounded, color: Color(0xFF1E293B), size: 21),
                                  suffixIcon: IconButton(
                                    icon: Icon(
                                      _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                                      color: const Color(0xFF1E293B),
                                      size: 21,
                                    ),
                                    onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                                  ),
                                  border: InputBorder.none,
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
                                ),
                                validator: (val) {
                                  if (val == null || val.isEmpty) {
                                    return 'Please enter your password';
                                  }
                                  return null;
                                },
                              ),
                            ),
                            const SizedBox(height: 16),

                            // Remember Me & Forgot Password Row
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Row(
                                  children: [
                                    SizedBox(
                                      width: 22,
                                      height: 22,
                                      child: Checkbox(
                                        value: _rememberMe,
                                        activeColor: const Color(0xFFE5252A),
                                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                                        side: const BorderSide(color: Color(0xFFCBD5E1), width: 1.5),
                                        onChanged: (val) => setState(() => _rememberMe = val ?? true),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    const Text(
                                      'Remember me',
                                      style: TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w500,
                                        color: Color(0xFF1E293B),
                                      ),
                                    ),
                                  ],
                                ),
                                TextButton(
                                  onPressed: () {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                        content: Text('Contact your CRM Administrator to reset password.'),
                                        behavior: SnackBarBehavior.floating,
                                      ),
                                    );
                                  },
                                  style: TextButton.styleFrom(
                                    padding: EdgeInsets.zero,
                                    minimumSize: Size.zero,
                                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                  ),
                                  child: const Text(
                                    'Forgot Password?',
                                    style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w700,
                                      color: Color(0xFFE5252A),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 20),

                            // Prominent Crimson Login Button with arrow
                            Container(
                              width: double.infinity,
                              height: 52,
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(26),
                                gradient: const LinearGradient(
                                  colors: [
                                    Color(0xFFE5252A),
                                    Color(0xFFDC2626),
                                  ],
                                ),
                                boxShadow: [
                                  BoxShadow(
                                    color: const Color(0xFFE5252A).withValues(alpha: 0.38),
                                    blurRadius: 16,
                                    offset: const Offset(0, 6),
                                  ),
                                ],
                              ),
                              child: ElevatedButton(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.transparent,
                                  shadowColor: Colors.transparent,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(26)),
                                ),
                                onPressed: isLoading ? null : _handleLogin,
                                child: isLoading
                                    ? const SizedBox(
                                        width: 22,
                                        height: 22,
                                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
                                      )
                                    : const Row(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: [
                                          Text(
                                            'Login',
                                            style: TextStyle(
                                              fontSize: 16,
                                              fontWeight: FontWeight.w700,
                                              color: Colors.white,
                                              letterSpacing: 0.3,
                                            ),
                                          ),
                                          SizedBox(width: 10),
                                          Icon(Icons.arrow_forward_rounded, color: Colors.white, size: 20),
                                        ],
                                      ),
                              ),
                            ),

                            const SizedBox(height: 20),

                            // OR Divider
                            Row(
                              children: [
                                Expanded(child: Container(height: 1, color: const Color(0xFFE2E8F0))),
                                const Padding(
                                  padding: EdgeInsets.symmetric(horizontal: 14),
                                  child: Text(
                                    'OR',
                                    style: TextStyle(
                                      fontSize: 11.5,
                                      fontWeight: FontWeight.w600,
                                      color: Color(0xFF94A3B8),
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                ),
                                Expanded(child: Container(height: 1, color: const Color(0xFFE2E8F0))),
                              ],
                            ),

                            const SizedBox(height: 18),

                            // Sign in with Google Button
                            Container(
                              width: double.infinity,
                              height: 50,
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(color: const Color(0xFFE2E8F0), width: 1.2),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.black.withValues(alpha: 0.04),
                                    blurRadius: 10,
                                    offset: const Offset(0, 3),
                                  ),
                                ],
                              ),
                              child: InkWell(
                                borderRadius: BorderRadius.circular(16),
                                onTap: () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text('Google Sign-in is managed by your CRM Administrator.'),
                                      behavior: SnackBarBehavior.floating,
                                    ),
                                  );
                                },
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    CustomPaint(
                                      size: const Size(20, 20),
                                      painter: _GoogleLogoPainter(),
                                    ),
                                    const SizedBox(width: 12),
                                    const Text(
                                      'Sign in with Google',
                                      style: TextStyle(
                                        fontSize: 14.5,
                                        fontWeight: FontWeight.w600,
                                        color: Color(0xFF1E293B),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 24),

                      // Powered by CHN Branding Badge
                      _buildPoweredByChn(),

                      const SizedBox(height: 36),
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
  // HELPER WIDGETS
  // ==========================================

  Widget _buildMiniFeature(IconData icon, String label, Color color, Color bg) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: 0.12),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Icon(icon, size: 22, color: color),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            fontSize: 10.5,
            fontWeight: FontWeight.w600,
            color: Color(0xFF64748B),
          ),
        ),
      ],
    );
  }

  Widget _buildMiniBar(double height, Color color) {
    return Container(
      width: 12,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(4),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.3),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
    );
  }

  Widget _buildPoweredByChn() {
    return Center(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.08),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const Text(
              'Powered by',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: Color(0xFF64748B),
                letterSpacing: 0.2,
              ),
            ),
            const SizedBox(width: 8),
            Image.asset(
              'assets/images/chn_logo.png',
              height: 20,
              fit: BoxFit.contain,
              errorBuilder: (ctx, err, stack) => const Text(
                'CHN',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF0065B3),
                  letterSpacing: 1.5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==========================================
// BACKGROUND WAVES PAINTER FOR LOGIN SCREEN
// ==========================================

class _LoginWaveBackgroundPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Crisp white background
    final bgPaint = Paint()..color = const Color(0xFFFAFAFA);
    canvas.drawRect(Rect.fromLTWH(0, 0, w, h), bgPaint);

    // Subtle ambient top-right glow
    final topGlow = Paint()
      ..shader = RadialGradient(
        center: const Alignment(0.85, -0.75),
        radius: 0.9,
        colors: [
          const Color(0xFFE5252A).withValues(alpha: 0.08),
          Colors.transparent,
        ],
      ).createShader(Rect.fromLTWH(0, 0, w, h * 0.4));
    canvas.drawRect(Rect.fromLTWH(0, 0, w, h * 0.4), topGlow);

    // Mid-screen deep navy wave
    final midNavyWave = Path()
      ..moveTo(0, h * 0.32)
      ..cubicTo(w * 0.2, h * 0.36, w * 0.6, h * 0.38, w, h * 0.33)
      ..lineTo(w, h * 0.42)
      ..cubicTo(w * 0.5, h * 0.45, w * 0.2, h * 0.39, 0, h * 0.40)
      ..close();
    final midNavyPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Color(0xFF1E3A5F),
          Color(0xFF162A45),
        ],
      ).createShader(Rect.fromLTWH(0, h * 0.30, w, h * 0.16));
    canvas.drawPath(midNavyWave, midNavyPaint);

    // Mid-screen crimson red wave (flowing smoothly behind card)
    final midRedWave = Path()
      ..moveTo(0, h * 0.34)
      ..cubicTo(w * 0.25, h * 0.32, w * 0.7, h * 0.26, w, h * 0.28)
      ..lineTo(w, h * 0.34)
      ..cubicTo(w * 0.65, h * 0.32, w * 0.25, h * 0.40, 0, h * 0.36)
      ..close();
    final midRedPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [
          Color(0xFFE5252A),
          Color(0xFFDC2626),
        ],
      ).createShader(Rect.fromLTWH(0, h * 0.25, w, h * 0.16));
    canvas.drawPath(midRedWave, midRedPaint);

    // Bottom-right deep navy wave
    final bottomNavyWave = Path()
      ..moveTo(w * 0.4, h)
      ..cubicTo(w * 0.6, h * 0.93, w * 0.8, h * 0.90, w, h * 0.83)
      ..lineTo(w, h)
      ..close();
    final bottomNavyPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Color(0xFF1E3A5F),
          Color(0xFF162A45),
        ],
      ).createShader(Rect.fromLTWH(w * 0.4, h * 0.83, w * 0.6, h * 0.17));
    canvas.drawPath(bottomNavyWave, bottomNavyPaint);

    // Bottom-left crimson red wave
    final bottomRedWave = Path()
      ..moveTo(0, h * 0.88)
      ..cubicTo(w * 0.2, h * 0.84, w * 0.5, h * 0.96, w * 0.8, h * 0.94)
      ..cubicTo(w * 0.9, h * 0.95, w * 0.95, h * 0.96, w, h)
      ..lineTo(0, h)
      ..close();
    final bottomRedPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [
          Color(0xFFE5252A),
          Color(0xFFDC2626),
        ],
      ).createShader(Rect.fromLTWH(0, h * 0.84, w, h * 0.16));
    canvas.drawPath(bottomRedWave, bottomRedPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ==========================================
// GOOGLE "G" VECTOR LOGO PAINTER
// ==========================================

class _GoogleLogoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final center = Offset(w / 2, w / 2);
    final radius = w / 2;
    final strokeWidth = radius * 0.42;

    final rect = Rect.fromCircle(center: center, radius: radius - strokeWidth / 2);

    // Blue arc (top-right to right edge): -45° to 45°
    final bluePaint = Paint()
      ..color = const Color(0xFF4285F4)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.butt;
    canvas.drawArc(rect, -0.785, 1.57, false, bluePaint);

    // Green arc (bottom-right): 45° to 135°
    final greenPaint = Paint()
      ..color = const Color(0xFF34A853)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.butt;
    canvas.drawArc(rect, 0.785, 1.57, false, greenPaint);

    // Yellow arc (bottom-left): 135° to 225°
    final yellowPaint = Paint()
      ..color = const Color(0xFFFBBC05)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.butt;
    canvas.drawArc(rect, 2.356, 1.57, false, yellowPaint);

    // Red arc (top-left): 225° to 315°
    final redPaint = Paint()
      ..color = const Color(0xFFEA4335)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.butt;
    canvas.drawArc(rect, 3.927, 1.57, false, redPaint);

    // Blue center bar extending to right edge
    final barPaint = Paint()
      ..color = const Color(0xFF4285F4)
      ..style = PaintingStyle.fill;
    final barRect = Rect.fromLTRB(
      center.dx - 1,
      center.dy - strokeWidth / 2,
      w,
      center.dy + strokeWidth / 2,
    );
    canvas.drawRect(barRect, barPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
