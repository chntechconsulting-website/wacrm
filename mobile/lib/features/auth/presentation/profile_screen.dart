import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../providers/auth_provider.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  void _showLogoutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirm Sign Out', style: TextStyle(fontWeight: FontWeight.w700)),
        content: const Text('Are you sure you want to sign out of WACRM?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () {
              Navigator.pop(ctx);
              context.read<AuthProvider>().logout();
            },
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;

    if (user == null) {
      return const Scaffold(
        body: Center(child: Text('Not signed in')),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('My Profile & Account'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // User Header Card
            WacrmCard(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 36,
                    backgroundColor: AppColors.primaryLight,
                    child: Text(
                      user.name.isNotEmpty ? user.name[0].toUpperCase() : 'U',
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w800,
                        color: AppColors.primary,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    user.name,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textMain,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '@${user.username}',
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppColors.textMuted,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      WacrmBadge.status(user.role),
                      const SizedBox(width: 8),
                      WacrmBadge.status(user.status),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Reporting Hierarchy Card
            WacrmCard(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.account_tree_outlined, size: 18, color: AppColors.primary),
                      SizedBox(width: 8),
                      Text(
                        'Organizational Reporting',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textMain,
                        ),
                      ),
                    ],
                  ),
                  const Divider(height: 24),
                  _buildProfileRow(
                    'Department',
                    user.department ?? 'N/A',
                    Icons.apartment_rounded,
                  ),
                  const SizedBox(height: 12),
                  _buildProfileRow(
                    'Reporting Manager',
                    user.reportingManagerName != null
                        ? '${user.reportingManagerName} (${user.reportingManagerRole ?? 'MANAGER'})'
                        : (user.isAdmin ? 'Direct to Executive Board (None required)' : 'Unassigned'),
                    Icons.supervisor_account_rounded,
                  ),
                  if (user.directReportsCount > 0) ...[
                    const SizedBox(height: 12),
                    _buildProfileRow(
                      'Direct Reports',
                      '${user.directReportsCount} active employee(s)',
                      Icons.groups_rounded,
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Contact & Details
            WacrmCard(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.badge_outlined, size: 18, color: AppColors.primary),
                      SizedBox(width: 8),
                      Text(
                        'Employee Details',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textMain,
                        ),
                      ),
                    ],
                  ),
                  const Divider(height: 24),
                  _buildProfileRow('Email', user.email, Icons.email_outlined),
                  const SizedBox(height: 12),
                  _buildProfileRow('Phone', user.phone ?? 'Not provided', Icons.phone_outlined),
                  const SizedBox(height: 12),
                  _buildProfileRow('Employee ID', user.employeeId != null ? '#${user.employeeId}' : 'N/A', Icons.pin_outlined),
                  const SizedBox(height: 12),
                  _buildProfileRow('CRM Server', ApiEndpoints.baseUrl, Icons.dns_outlined),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Sign out button
            WacrmButton(
              text: 'Sign Out',
              icon: Icons.logout_rounded,
              type: WacrmButtonType.danger,
              onPressed: () => _showLogoutDialog(context),
            ),
            const SizedBox(height: 24),

            // Pingo mascot and brand footer
            Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Image.asset(
                    'assets/images/logo.png',
                    height: 26,
                    fit: BoxFit.contain,
                  ),
                  const SizedBox(height: 10),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const PingoMascotWidget(pose: PingoPoses.salute, height: 42),
                      const SizedBox(width: 8),
                      const Text(
                        'WACRM Mobile v1.0.0 • CHN Technologies',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: AppColors.textLight),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProfileRow(String label, String value, IconData icon) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: AppColors.textMuted),
        const SizedBox(width: 10),
        SizedBox(
          width: 120,
          child: Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textMuted,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textMain,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }
}
