import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/network/token_storage.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../../../core/widgets/wave_background_painter.dart';
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
            Icon(Icons.settings_ethernet_rounded, color: AppColors.primary, size: 22),
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
              style: TextStyle(fontSize: 13, color: AppColors.textMuted),
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
                  avatar: const Icon(Icons.cloud_done_rounded, size: 14, color: AppColors.primary),
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
      backgroundColor: const Color(0xFF0F172A),
      body: Stack(
        children: [
          // Dark canvas with fluid red waves
          Positioned.fill(
            child: CustomPaint(
              painter: WaveBackgroundPainter(isDark: true),
            ),
          ),

          SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 440),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Server configuration button top-right
                        Align(
                          alignment: Alignment.topRight,
                          child: IconButton(
                            tooltip: 'Server Settings',
                            icon: const Icon(Icons.settings_outlined, color: Colors.white60, size: 20),
                            onPressed: _showServerConfigDialog,
                          ),
                        ),

                        // Authentic WA!CRM Logo
                        Center(
                          child: Image.asset(
                            'assets/images/logo.png',
                            height: 52,
                            fit: BoxFit.contain,
                            errorBuilder: (ctx, err, stack) => const Text(
                              'WA! CRM',
                              style: TextStyle(
                                fontSize: 32,
                                fontWeight: FontWeight.w900,
                                color: AppColors.primary,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 14),

                        // Welcome Back Header
                        const Text(
                          'Welcome Back',
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                            letterSpacing: -0.4,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Sign in to continue to your CRM',
                          style: TextStyle(
                            fontSize: 13,
                            color: Color(0xFF94A3B8),
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 24),

                        // Crisp White Login Card
                        Container(
                          padding: const EdgeInsets.all(22),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(20),
                            boxShadow: const [
                              BoxShadow(
                                color: Color(0x33000000),
                                blurRadius: 24,
                                offset: Offset(0, 10),
                              ),
                            ],
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              WacrmTextField(
                                controller: _usernameController,
                                label: 'Email or Username',
                                hintText: 'chandra@chntech.com',
                                prefixIcon: Icons.person_outline_rounded,
                                validator: (val) {
                                  if (val == null || val.trim().isEmpty) {
                                    return 'Please enter username or email';
                                  }
                                  return null;
                                },
                              ),
                              const SizedBox(height: 16),
                              WacrmTextField(
                                controller: _passwordController,
                                label: 'Password',
                                hintText: '••••••••',
                                prefixIcon: Icons.lock_outline_rounded,
                                obscureText: _obscurePassword,
                                suffixIcon: IconButton(
                                  icon: Icon(
                                    _obscurePassword ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                                    color: AppColors.textLight,
                                    size: 20,
                                  ),
                                  onPressed: () {
                                    setState(() {
                                      _obscurePassword = !_obscurePassword;
                                    });
                                  },
                                ),
                                validator: (val) {
                                  if (val == null || val.isEmpty) {
                                    return 'Please enter your password';
                                  }
                                  return null;
                                },
                              ),
                              const SizedBox(height: 14),

                              // Remember me & Forgot Password
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Row(
                                    children: [
                                      SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: Checkbox(
                                          value: _rememberMe,
                                          activeColor: AppColors.primary,
                                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                                          onChanged: (val) {
                                            setState(() {
                                              _rememberMe = val ?? true;
                                            });
                                          },
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      const Text(
                                        'Remember me',
                                        style: TextStyle(
                                          fontSize: 12.5,
                                          fontWeight: FontWeight.w500,
                                          color: Color(0xFF475569),
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
                                        fontSize: 12.5,
                                        fontWeight: FontWeight.w600,
                                        color: AppColors.primary,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 20),

                              // Prominent Red Login Button
                              SizedBox(
                                height: 50,
                                child: ElevatedButton(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.primary,
                                    foregroundColor: Colors.white,
                                    elevation: 2,
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                  ),
                                  onPressed: isLoading ? null : _handleLogin,
                                  child: isLoading
                                      ? const SizedBox(
                                          width: 22,
                                          height: 22,
                                          child: CircularProgressIndicator(
                                            color: Colors.white,
                                            strokeWidth: 2.5,
                                          ),
                                        )
                                      : const Text(
                                          'Login',
                                          style: TextStyle(
                                            fontSize: 16,
                                            fontWeight: FontWeight.w700,
                                            letterSpacing: 0.3,
                                          ),
                                        ),
                                ),
                              ),

                              const SizedBox(height: 16),

                              // OR Divider
                              Row(
                                children: [
                                  Expanded(child: Container(height: 1, color: const Color(0xFFE2E8F0))),
                                  const Padding(
                                    padding: EdgeInsets.symmetric(horizontal: 12),
                                    child: Text(
                                      'OR',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        color: Color(0xFF94A3B8),
                                      ),
                                    ),
                                  ),
                                  Expanded(child: Container(height: 1, color: const Color(0xFFE2E8F0))),
                                ],
                              ),

                              const SizedBox(height: 16),

                              // Secondary / Quick SSO Button
                              OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: const Color(0xFF334155),
                                  side: const BorderSide(color: Color(0xFFE2E8F0), width: 1.2),
                                  padding: const EdgeInsets.symmetric(vertical: 12),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                                onPressed: () {
                                  // Quick fill demo user
                                  setState(() {
                                    _usernameController.text = 'admin';
                                    _passwordController.text = 'admin123';
                                  });
                                  _handleLogin();
                                },
                                icon: const Icon(
                                  Icons.account_circle_outlined,
                                  size: 20,
                                  color: Color(0xFF475569),
                                ),
                                label: const Text(
                                  'Quick Demo Sign-in',
                                  style: TextStyle(
                                    fontSize: 13.5,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 24),

                        // Current Server indicator (No mention of Pingo)
                        Center(
                          child: TextButton.icon(
                            onPressed: _showServerConfigDialog,
                            icon: const Icon(Icons.dns_outlined, size: 14, color: Colors.white54),
                            label: Text(
                              'Server: ${ApiEndpoints.baseUrl}',
                              style: const TextStyle(fontSize: 12, color: Colors.white70),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
