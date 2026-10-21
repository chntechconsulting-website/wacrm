import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/constants/app_colors.dart';
import '../../core/widgets/pingo_mascot_widget.dart';
import '../activities/presentation/activities_screen.dart';
import '../auth/presentation/profile_screen.dart';
import '../auth/providers/auth_provider.dart';
import '../calls/presentation/call_logs_screen.dart';
import '../customers/presentation/customers_list_screen.dart';
import '../dashboard/presentation/dashboard_screen.dart';
import '../deals/presentation/deals_list_screen.dart';
import '../field_visits/presentation/field_visits_list_screen.dart';
import '../followups/presentation/followups_list_screen.dart';
import '../leads/presentation/leads_list_screen.dart';
import '../notifications/presentation/notifications_screen.dart';
import '../notifications/providers/notifications_provider.dart';
import '../quotations/presentation/quotations_list_screen.dart';
import '../reports/presentation/reports_screen.dart';
import '../support/presentation/support_tickets_screen.dart';

class MainNavigationShell extends StatefulWidget {
  const MainNavigationShell({super.key});

  @override
  State<MainNavigationShell> createState() => _MainNavigationShellState();
}

class _MainNavigationShellState extends State<MainNavigationShell> {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationsProvider>().fetchNotifications();
    });
  }

  void _navigateToTab(int index) {
    setState(() => _currentIndex = index);
  }

  void _showMoreMenu(BuildContext context) {
    final user = context.read<AuthProvider>().currentUser;

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => Container(
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Row(
                children: [
                  PingoMascotWidget(pose: PingoPoses.salute, height: 32),
                  SizedBox(width: 8),
                  Text(
                    'CRM Modules & Navigation',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textMain),
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Module Grid
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  _buildMenuCard(
                    icon: Icons.people_alt_outlined,
                    label: 'Customers',
                    color: AppColors.primary,
                    onTap: () {
                      Navigator.pop(ctx);
                      Navigator.push(context, MaterialPageRoute(builder: (_) => const CustomersListScreen()));
                    },
                  ),
                  _buildMenuCard(
                    icon: Icons.history_rounded,
                    label: 'Activities',
                    color: const Color(0xFF8B5CF6),
                    onTap: () {
                      Navigator.pop(ctx);
                      Navigator.push(context, MaterialPageRoute(builder: (_) => const ActivitiesScreen()));
                    },
                  ),
                  _buildMenuCard(
                    icon: Icons.add_location_alt_rounded,
                    label: 'Field Visits',
                    color: const Color(0xFF0284C7),
                    onTap: () {
                      Navigator.pop(ctx);
                      Navigator.push(context, MaterialPageRoute(builder: (_) => const FieldVisitsListScreen()));
                    },
                  ),
                  _buildMenuCard(
                    icon: Icons.phone_callback_rounded,
                    label: 'Call Logs',
                    color: AppColors.accent,
                    onTap: () {
                      Navigator.pop(ctx);
                      Navigator.push(context, MaterialPageRoute(builder: (_) => const CallLogsScreen()));
                    },
                  ),
                  if (user?.canViewSales == true) ...[
                    _buildMenuCard(
                      icon: Icons.description_outlined,
                      label: 'Quotations',
                      color: const Color(0xFF0D9488),
                      onTap: () {
                        Navigator.pop(ctx);
                        Navigator.push(context, MaterialPageRoute(builder: (_) => const QuotationsListScreen()));
                      },
                    ),
                    _buildMenuCard(
                      icon: Icons.handshake_outlined,
                      label: 'Deals & Handoff',
                      color: const Color(0xFFD97706),
                      onTap: () {
                        Navigator.pop(ctx);
                        Navigator.push(context, MaterialPageRoute(builder: (_) => const DealsListScreen()));
                      },
                    ),
                  ],
                  if (user?.canViewSupport == true)
                    _buildMenuCard(
                      icon: Icons.support_agent_rounded,
                      label: 'Support Tickets',
                      color: const Color(0xFFE11D48),
                      onTap: () {
                        Navigator.pop(ctx);
                        Navigator.push(context, MaterialPageRoute(builder: (_) => const SupportTicketsScreen()));
                      },
                    ),
                  _buildMenuCard(
                    icon: Icons.bar_chart_rounded,
                    label: 'Reports & Funnel',
                    color: const Color(0xFF2563EB),
                    onTap: () {
                      Navigator.pop(ctx);
                      Navigator.push(context, MaterialPageRoute(builder: (_) => const ReportsScreen()));
                    },
                  ),
                  _buildMenuCard(
                    icon: Icons.notifications_outlined,
                    label: 'Alerts',
                    color: const Color(0xFFF59E0B),
                    onTap: () {
                      Navigator.pop(ctx);
                      Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen()));
                    },
                  ),
                  _buildMenuCard(
                    icon: Icons.person_outline_rounded,
                    label: 'My Profile',
                    color: AppColors.textMain,
                    onTap: () {
                      Navigator.pop(ctx);
                      Navigator.push(context, MaterialPageRoute(builder: (_) => const ProfileScreen()));
                    },
                  ),
                ],
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMenuCard({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return SizedBox(
      width: (MediaQuery.of(context).size.width - 64) / 3,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: color.withValues(alpha: 0.2)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 24, color: color),
              const SizedBox(height: 6),
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textMain,
                ),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final unreadCount = context.watch<NotificationsProvider>().unreadCount;

    // Define bottom tabs based on role
    final List<Widget> screens = [
      DashboardScreen(
        onNavigateToLeads: () => _navigateToTab(1),
        onNavigateToFollowups: () => _navigateToTab(2),
        onNavigateToCalls: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const CallLogsScreen())),
        onNavigateToProfile: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ProfileScreen())),
      ),
      if (user?.isSupportExecutive == true || user?.isSupportManager == true)
        const SupportTicketsScreen()
      else
        const LeadsListScreen(),
      const FollowupsListScreen(),
      if (user?.canViewFinance == true)
        const DealsListScreen()
      else if (user?.canViewSales == true)
        const QuotationsListScreen()
      else
        const SupportTicketsScreen(),
    ];

    final List<BottomNavigationBarItem> navItems = [
      const BottomNavigationBarItem(
        icon: Icon(Icons.dashboard_outlined),
        activeIcon: Icon(Icons.dashboard_rounded),
        label: 'Dashboard',
      ),
      if (user?.isSupportExecutive == true || user?.isSupportManager == true)
        const BottomNavigationBarItem(
          icon: Icon(Icons.support_agent_outlined),
          activeIcon: Icon(Icons.support_agent_rounded),
          label: 'Support',
        )
      else
        const BottomNavigationBarItem(
          icon: Icon(Icons.people_alt_outlined),
          activeIcon: Icon(Icons.people_alt_rounded),
          label: 'Leads',
        ),
      const BottomNavigationBarItem(
        icon: Icon(Icons.alarm_outlined),
        activeIcon: Icon(Icons.alarm_rounded),
        label: 'Follow-ups',
      ),
      if (user?.canViewFinance == true)
        const BottomNavigationBarItem(
          icon: Icon(Icons.payments_outlined),
          activeIcon: Icon(Icons.payments_rounded),
          label: 'Deals',
        )
      else if (user?.canViewSales == true)
        const BottomNavigationBarItem(
          icon: Icon(Icons.receipt_long_outlined),
          activeIcon: Icon(Icons.receipt_long_rounded),
          label: 'Quotes',
        )
      else
        const BottomNavigationBarItem(
          icon: Icon(Icons.support_agent_outlined),
          activeIcon: Icon(Icons.support_agent_rounded),
          label: 'Support',
        ),
    ];

    return Scaffold(
      body: IndexedStack(
        index: _currentIndex.clamp(0, screens.length - 1),
        children: screens,
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AppColors.card,
          border: Border(top: BorderSide(color: AppColors.border, width: 1)),
        ),
        child: SafeArea(
          child: Row(
            children: [
              Expanded(
                child: BottomNavigationBar(
                  currentIndex: _currentIndex.clamp(0, navItems.length - 1),
                  onTap: (idx) => setState(() => _currentIndex = idx),
                  backgroundColor: Colors.transparent,
                  elevation: 0,
                  type: BottomNavigationBarType.fixed,
                  selectedItemColor: AppColors.primary,
                  unselectedItemColor: AppColors.textMuted,
                  selectedFontSize: 11,
                  unselectedFontSize: 11,
                  selectedLabelStyle: const TextStyle(fontWeight: FontWeight.w700),
                  items: navItems,
                ),
              ),
              // More / Modules Pill Button
              Padding(
                padding: const EdgeInsets.only(right: 12),
                child: InkWell(
                  onTap: () => _showMoreMenu(context),
                  borderRadius: BorderRadius.circular(10),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppColors.cardHover,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Stack(
                      clipBehavior: Clip.none,
                      children: [
                        const Icon(Icons.grid_view_rounded, size: 20, color: AppColors.textMain),
                        if (unreadCount > 0)
                          Positioned(
                            top: -4,
                            right: -4,
                            child: Container(
                              padding: const EdgeInsets.all(3),
                              decoration: const BoxDecoration(
                                color: AppColors.danger,
                                shape: BoxShape.circle,
                              ),
                              child: Text(
                                '$unreadCount',
                                style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
