import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/constants/app_colors.dart';
import '../../core/widgets/pingo_mascot_widget.dart';
import '../../core/widgets/wacrm_drawer.dart';
import '../../core/widgets/wacrm_wave_nav_bar.dart';
import '../activities/presentation/activities_screen.dart';
import '../auth/presentation/profile_screen.dart';
import '../auth/providers/auth_provider.dart';
import '../calls/presentation/call_logs_screen.dart';
import '../customers/presentation/customers_list_screen.dart';
import '../dashboard/presentation/dashboard_screen.dart';
import '../deals/presentation/deals_list_screen.dart';
import '../field_visits/presentation/field_visits_list_screen.dart';
import '../followups/presentation/followups_list_screen.dart';
import '../leads/presentation/lead_create_edit_screen.dart';
import '../leads/presentation/leads_list_screen.dart';
import '../notifications/presentation/notifications_screen.dart';
import '../notifications/providers/notifications_provider.dart';
import '../quotations/presentation/quotations_list_screen.dart';
import '../reports/presentation/reports_screen.dart';
import '../support/presentation/support_tickets_screen.dart';

class MainNavigationShell extends StatefulWidget {
  const MainNavigationShell({super.key});

  static MainNavigationShellState? of(BuildContext context) {
    return context.findAncestorStateOfType<MainNavigationShellState>();
  }

  @override
  State<MainNavigationShell> createState() => MainNavigationShellState();
}

class MainNavigationShellState extends State<MainNavigationShell> {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationsProvider>().fetchNotifications();
    });
  }

  void navigateToTab(int index) {
    if (mounted) {
      setState(() => _currentIndex = index);
    }
  }

  void _navigateToTab(int index) => navigateToTab(index);

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

    return Scaffold(
      drawer: WacrmDrawer(currentTabIndex: _currentIndex),
      body: IndexedStack(
        index: _currentIndex.clamp(0, screens.length - 1),
        children: screens,
      ),
      bottomNavigationBar: WacrmWaveNavBar(
        currentIndex: _currentIndex,
        onTap: (idx) {
          if (idx == 0) {
            _navigateToTab(0);
          } else if (idx == 1) {
            _navigateToTab(1);
          } else if (idx == 2) {
            Navigator.push(context, MaterialPageRoute(builder: (_) => const CallLogsScreen()));
          } else if (idx == 3) {
            _showMoreMenu(context);
          }
        },
        onAdd: () {
          Navigator.push(context, MaterialPageRoute(builder: (_) => const LeadCreateEditScreen()));
        },
      ),
    );
  }
}
