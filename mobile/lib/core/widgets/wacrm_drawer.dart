import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../constants/app_colors.dart';
import 'pingo_mascot_widget.dart';
import '../../features/activities/presentation/activities_screen.dart';
import '../../features/auth/presentation/profile_screen.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../../features/calls/presentation/call_logs_screen.dart';
import '../../features/customers/presentation/customers_list_screen.dart';
import '../../features/deals/presentation/deals_list_screen.dart';
import '../../features/field_visits/presentation/field_visits_list_screen.dart';
import '../../features/navigation/main_navigation_shell.dart';
import '../../features/notifications/presentation/notifications_screen.dart';
import '../../features/quotations/presentation/quotations_list_screen.dart';
import '../../features/reports/presentation/reports_screen.dart';
import '../../features/support/presentation/support_tickets_screen.dart';

/// Shows standard WACRM sign out confirmation dialog and cleanly redirects to LoginScreen
Future<void> showWacrmLogoutDialog(BuildContext context) async {
  return showDialog(
    context: context,
    builder: (ctx) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: const Row(
        children: [
          Icon(Icons.logout_rounded, color: Color(0xFFE5252A), size: 24),
          SizedBox(width: 10),
          Text(
            'Confirm Sign Out',
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 17),
          ),
        ],
      ),
      content: const Text(
        'Are you sure you want to sign out of WACRM?',
        style: TextStyle(fontSize: 14, color: Color(0xFF475569)),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx),
          child: const Text(
            'Cancel',
            style: TextStyle(color: Color(0xFF64748B), fontWeight: FontWeight.w600),
          ),
        ),
        ElevatedButton(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFFE5252A),
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            elevation: 0,
          ),
          onPressed: () async {
            final nav = Navigator.of(ctx, rootNavigator: true);
            final auth = ctx.read<AuthProvider>();
            Navigator.pop(ctx); // Close dialog
            nav.popUntil((route) => route.isFirst);
            await auth.logout();
          },
          child: const Text('Sign Out', style: TextStyle(fontWeight: FontWeight.w700)),
        ),
      ],
    ),
  );
}

class WacrmDrawer extends StatelessWidget {
  final int? currentTabIndex;

  const WacrmDrawer({
    super.key,
    this.currentTabIndex,
  });

  String _getInitials(String name) {
    if (name.trim().isEmpty) return 'U';
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.length >= 2) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    }
    return name.substring(0, name.length >= 2 ? 2 : 1).toUpperCase();
  }

  void _onSelectTab(BuildContext context, int tabIndex) {
    Navigator.pop(context); // Close drawer
    final shell = MainNavigationShell.of(context);
    if (shell != null) {
      shell.navigateToTab(tabIndex);
    }
  }

  void _navigateToScreen(BuildContext context, Widget screen) {
    Navigator.pop(context); // Close drawer
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => screen),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final initials = user != null ? _getInitials(user.name) : 'U';

    return Drawer(
      backgroundColor: Colors.white,
      child: Column(
        children: [
          // Drawer Header with User Profile
          Container(
            width: double.infinity,
            padding: EdgeInsets.only(
              top: MediaQuery.of(context).padding.top + 16,
              left: 18,
              right: 18,
              bottom: 18,
            ),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF0F172A), Color(0xFF162A45)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Image.asset(
                      'assets/images/logo.png',
                      height: 26,
                      fit: BoxFit.contain,
                      errorBuilder: (_, _, _) => const Text(
                        'WA! CRM',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w900,
                          fontSize: 18,
                        ),
                      ),
                    ),
                    const PingoMascotWidget(
                      pose: PingoPoses.salute,
                      height: 36,
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                InkWell(
                  onTap: () => _navigateToScreen(context, const ProfileScreen()),
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
                    ),
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 20,
                          backgroundColor: const Color(0xFFE5252A),
                          child: Text(
                            initials,
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                user?.name ?? 'WA!CRM User',
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 2),
                              Text(
                                '@${user?.username ?? 'user'} • ${user?.role ?? 'Executive'}',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.white.withValues(alpha: 0.7),
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                        const Icon(
                          Icons.chevron_right_rounded,
                          color: Colors.white70,
                          size: 20,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Drawer Navigation Items
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 10),
              children: [
                _buildSectionLabel('MAIN NAVIGATION'),
                _buildDrawerTile(
                  icon: Icons.dashboard_rounded,
                  label: 'Dashboard',
                  isSelected: currentTabIndex == 0,
                  onTap: () => _onSelectTab(context, 0),
                ),
                _buildDrawerTile(
                  icon: Icons.leaderboard_rounded,
                  label: 'Leads Management',
                  isSelected: currentTabIndex == 1,
                  onTap: () => _onSelectTab(context, 1),
                ),
                _buildDrawerTile(
                  icon: Icons.alarm_rounded,
                  label: 'Follow-ups & Reminders',
                  isSelected: currentTabIndex == 2,
                  onTap: () => _onSelectTab(context, 2),
                ),

                const SizedBox(height: 12),
                _buildSectionLabel('CRM MODULES'),
                _buildDrawerTile(
                  icon: Icons.people_alt_outlined,
                  label: 'Customers',
                  color: AppColors.primary,
                  onTap: () => _navigateToScreen(context, const CustomersListScreen()),
                ),
                _buildDrawerTile(
                  icon: Icons.phone_callback_rounded,
                  label: 'Call Logs',
                  color: AppColors.accent,
                  onTap: () => _navigateToScreen(context, const CallLogsScreen()),
                ),
                _buildDrawerTile(
                  icon: Icons.add_location_alt_rounded,
                  label: 'Field Visits',
                  color: const Color(0xFF0284C7),
                  onTap: () => _navigateToScreen(context, const FieldVisitsListScreen()),
                ),
                _buildDrawerTile(
                  icon: Icons.history_rounded,
                  label: 'Activities',
                  color: const Color(0xFF8B5CF6),
                  onTap: () => _navigateToScreen(context, const ActivitiesScreen()),
                ),
                if (user?.canViewSales == true) ...[
                  _buildDrawerTile(
                    icon: Icons.description_outlined,
                    label: 'Quotations',
                    color: const Color(0xFF0D9488),
                    onTap: () => _navigateToScreen(context, const QuotationsListScreen()),
                  ),
                  _buildDrawerTile(
                    icon: Icons.handshake_outlined,
                    label: 'Deals & Handoff',
                    color: const Color(0xFFD97706),
                    onTap: () => _navigateToScreen(context, const DealsListScreen()),
                  ),
                ],
                if (user?.canViewSupport == true)
                  _buildDrawerTile(
                    icon: Icons.support_agent_rounded,
                    label: 'Support Tickets',
                    color: const Color(0xFFE11D48),
                    onTap: () => _navigateToScreen(context, const SupportTicketsScreen()),
                  ),
                _buildDrawerTile(
                  icon: Icons.bar_chart_rounded,
                  label: 'Reports & Funnel',
                  color: const Color(0xFF2563EB),
                  onTap: () => _navigateToScreen(context, const ReportsScreen()),
                ),

                const SizedBox(height: 12),
                _buildSectionLabel('ACCOUNT & PREFERENCES'),
                _buildDrawerTile(
                  icon: Icons.notifications_none_rounded,
                  label: 'Notifications',
                  color: const Color(0xFFF59E0B),
                  onTap: () => _navigateToScreen(context, const NotificationsScreen()),
                ),
                _buildDrawerTile(
                  icon: Icons.person_outline_rounded,
                  label: 'My Profile & Settings',
                  color: const Color(0xFF162A45),
                  onTap: () => _navigateToScreen(context, const ProfileScreen()),
                ),
              ],
            ),
          ),

          // Drawer Footer with Sign Out Button
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              border: Border(top: BorderSide(color: Colors.grey.shade200)),
            ),
            child: SafeArea(
              top: false,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  InkWell(
                    onTap: () => showWacrmLogoutDialog(context),
                    borderRadius: BorderRadius.circular(10),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 14),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF2F2),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: const Color(0xFFFECACA)),
                      ),
                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.logout_rounded, color: Color(0xFFE5252A), size: 20),
                          SizedBox(width: 8),
                          Text(
                            'Sign Out',
                            style: TextStyle(
                              color: Color(0xFFE5252A),
                              fontWeight: FontWeight.w700,
                              fontSize: 14,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'WA!CRM v1.0.0 • Powered by CHN',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF94A3B8),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionLabel(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 12, top: 4, bottom: 6),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: Color(0xFF94A3B8),
          letterSpacing: 0.8,
        ),
      ),
    );
  }

  Widget _buildDrawerTile({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    Color? color,
    bool isSelected = false,
  }) {
    final activeColor = color ?? const Color(0xFF162A45);

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 2),
      child: ListTile(
        onTap: onTap,
        dense: true,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        tileColor: isSelected ? activeColor.withValues(alpha: 0.1) : Colors.transparent,
        leading: Icon(
          icon,
          size: 22,
          color: isSelected ? activeColor : (color ?? const Color(0xFF475569)),
        ),
        title: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
            color: isSelected ? activeColor : const Color(0xFF1E293B),
          ),
        ),
        trailing: isSelected
            ? Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: activeColor,
                  shape: BoxShape.circle,
                ),
              )
            : null,
      ),
    );
  }
}
