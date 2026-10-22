import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/widgets/wacrm_drawer.dart';
import '../../core/widgets/wacrm_wave_nav_bar.dart';
import '../auth/presentation/profile_screen.dart';
import '../auth/providers/auth_provider.dart';
import '../calls/presentation/call_logs_screen.dart';
import '../dashboard/presentation/dashboard_screen.dart';
import '../followups/presentation/followups_list_screen.dart';
import '../leads/presentation/lead_create_edit_screen.dart';
import '../leads/presentation/leads_list_screen.dart';
import '../notifications/providers/notifications_provider.dart';
import '../settings/presentation/settings_screen.dart';
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

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;

    // 4 Primary Bottom Navigation Tabs:
    // 0: Home (Dashboard)
    // 1: Leads (or Support Tickets if Support Executive/Manager)
    // 2: Calls (Call Logs)
    // 3: Settings (Settings & Enterprise Profile)
    final List<Widget> screens = [
      DashboardScreen(
        onNavigateToLeads: () => _navigateToTab(1),
        onNavigateToFollowups: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const FollowupsListScreen()),
        ),
        onNavigateToCalls: () => _navigateToTab(2),
        onNavigateToProfile: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const ProfileScreen()),
        ),
      ),
      if (user?.isSupportExecutive == true || user?.isSupportManager == true)
        const SupportTicketsScreen()
      else
        const LeadsListScreen(),
      const CallLogsScreen(),
      const SettingsScreen(),
    ];

    return Scaffold(
      drawer: WacrmDrawer(currentTabIndex: _currentIndex),
      body: IndexedStack(
        index: _currentIndex.clamp(0, screens.length - 1),
        children: screens,
      ),
      bottomNavigationBar: WacrmWaveNavBar(
        currentIndex: _currentIndex,
        onTap: (idx) => _navigateToTab(idx),
        onAdd: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const LeadCreateEditScreen()),
          );
        },
      ),
    );
  }
}
