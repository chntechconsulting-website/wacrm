import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/services/automatic_call_sync_service.dart';
import '../../core/services/device_call_log_sync_service.dart';
import '../../core/services/mobile_sim_call_service.dart';
import '../../core/services/recording_upload_service.dart';
import '../../core/widgets/wacrm_drawer.dart';
import '../../core/widgets/wacrm_wave_nav_bar.dart';
import '../auth/presentation/profile_screen.dart';
import '../auth/providers/auth_provider.dart';
import '../calls/presentation/call_logs_screen.dart';
import '../calls/providers/calls_provider.dart';
import '../dashboard/presentation/admin_dashboard_screen.dart';
import '../dashboard/presentation/dashboard_screen.dart';
import '../followups/presentation/followups_list_screen.dart';
import '../followups/providers/followups_provider.dart';
import '../leads/presentation/lead_create_edit_screen.dart';
import '../leads/presentation/leads_list_screen.dart';
import '../notifications/providers/notifications_provider.dart';
import '../settings/presentation/settings_screen.dart';
import '../support/presentation/support_customers_screen.dart';
import '../support/presentation/support_backup_screen.dart';
import '../support/presentation/support_dashboard_screen.dart';
import '../support/presentation/support_dialogs.dart';
import '../support/presentation/support_followups_screen.dart';
import '../support/presentation/support_manager_dashboard_screen.dart';
import '../support/providers/support_customers_provider.dart';

class MainNavigationShell extends StatefulWidget {
  const MainNavigationShell({super.key});

  static MainNavigationShellState? of(BuildContext context) {
    return context.findAncestorStateOfType<MainNavigationShellState>();
  }

  @override
  State<MainNavigationShell> createState() => MainNavigationShellState();
}

class MainNavigationShellState extends State<MainNavigationShell>
    with WidgetsBindingObserver {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationsProvider>().fetchNotifications();
      _attachMobileSimCallSync();
      _runDeviceSync();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _runDeviceSync();
    }
  }

  /// The live result always syncs first; only then may native history run, so
  /// the same call cannot be logged twice.
  Future<void> _runDeviceSync() async {
    await _recoverPendingMobileSimCall();
    await _syncDeviceCallHistory();
    await _repairMobileCallDirections();
  }

  Future<void> _syncDeviceCallHistory() async {
    if (!mounted || !DeviceCallLogSyncService.isSupported) return;
    final user = context.read<AuthProvider>().currentUser;
    try {
      await DeviceCallLogSyncService.sync(
        context.read<CallsProvider>(),
        employeeKey: user?.id.toString() ?? 'default',
      );
    } catch (_) {
      // Optional sync; never disturb the UI when the OS denies access.
    }
  }

  void _attachMobileSimCallSync() {
    if (!mounted) return;
    MobileSimCallService.attach(onCallEnded: _syncMobileSimCall);
  }

  /// One-time, evidence-only correction of historical directions. A row is
  /// re-sent only when this device previously synced it and the rebuilt
  /// direction comes from Android's own CallLog.Calls.TYPE.
  Future<void> _repairMobileCallDirections() async {
    if (!mounted || !DeviceCallLogSyncService.isSupported) return;
    final user = context.read<AuthProvider>().currentUser;
    try {
      await DeviceCallLogSyncService.repairHistoricalDirections(
        context.read<CallsProvider>(),
        employeeKey: user?.id.toString() ?? 'default',
      );
    } catch (_) {
      // Optional repair; never disturb the UI when the OS denies access.
    }
  }

  Future<void> _recoverPendingMobileSimCall() async {
    if (!mounted || !MobileSimCallService.isSupported) return;
    try {
      final result = await MobileSimCallService.consumePendingResult();
      if (result != null) {
        await _syncMobileSimCall(result);
      }
    } catch (_) {
      // Native channel unavailable (for example hot restart); retry on resume.
    }
  }

  String get _employeeKey =>
      context.read<AuthProvider>().currentUser?.id.toString() ?? 'default';

  Future<void> _syncMobileSimCall(MobileSimCallResult result) async {
    if (!mounted) return;
    final callsProvider = context.read<CallsProvider>();
    final synced = await MobileSimCallService.syncResult(
      result,
      callsProvider,
      employeeKey: _employeeKey,
    );
    if (!mounted) return;
    if (synced) {
      // The call row now exists and the recording task was persisted. Try the
      // OEM file immediately; if the dialer has not finalized/indexed it yet,
      // the durable queue keeps the task and WorkManager retries it.
      final recordingResult = await RecordingUploadService.processQueue(
        employeeKey: _employeeKey,
        callsProvider: callsProvider,
      );
      if (recordingResult.retryablePending > 0) {
        await AutomaticCallSyncService.scheduleOneOffSync();
      }
    }
    if (!mounted) return;

    final contact = (result.contactName?.trim().isNotEmpty ?? false)
        ? result.contactName!.trim()
        : result.customerPhone;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          synced
              ? 'Call with $contact saved to CRM Call Logs (${result.durationSeconds}s).'
              : 'Call ended, but CRM sync failed. It will retry when the app resumes.',
        ),
        backgroundColor: synced
            ? const Color(0xFF10B981)
            : const Color(0xFFE5252A),
        duration: const Duration(seconds: 3),
      ),
    );
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
    final isSupport = user?.isSupportWorkspace == true;
    final isSupportManager = user?.isSupportManagerWorkspace == true;
    final isAdmin = user?.isAdmin == true;

    // Role-specific workspace:
    // Admin  (Admin Dashboard, Leads, Calls, Settings)
    // Sales  (Home, Leads, Calls, Settings)
    // Support (Home, Customers, Follow-ups, Settings)
    final List<Widget> screens = isSupport
        ? [
            if (isSupportManager)
              SupportManagerDashboardScreen(
                onNavigateToCustomers: () => _navigateToTab(1),
                onNavigateToFollowups: () => _navigateToTab(2),
                onNavigateToBackup: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const SupportBackupScreen(),
                  ),
                ),
                onNavigateToCalls: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const CallLogsScreen()),
                ),
                onNavigateToProfile: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const ProfileScreen()),
                ),
              )
            else
              SupportDashboardScreen(
                onNavigateToCustomers: () => _navigateToTab(1),
                onNavigateToFollowups: () => _navigateToTab(2),
                onNavigateToCalls: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const CallLogsScreen()),
                ),
                onNavigateToProfile: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const ProfileScreen()),
                ),
              ),
            const SupportCustomersScreen(),
            const SupportFollowupsScreen(),
            const SettingsScreen(),
          ]
        : [
            if (isAdmin)
              AdminDashboardScreen(
                onNavigateToLeads: () => _navigateToTab(1),
                onNavigateToProfile: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const ProfileScreen()),
                ),
              )
            else
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
        secondLabel: isSupport ? 'Customers' : 'Leads',
        thirdLabel: isSupport ? 'Follow-ups' : 'Calls',
        secondIcon: isSupport
            ? Icons.business_rounded
            : Icons.people_alt_rounded,
        thirdIcon: isSupport ? Icons.alarm_rounded : Icons.phone_rounded,
        centerIcon: isSupport
            ? Icons.event_available_rounded
            : Icons.add_rounded,
        centerTooltip: isSupport ? 'Schedule Support Follow-up' : 'Create Lead',
        showCenterAction: isSupport
            ? (user?.canCreateSupportFollowup ?? false)
            : true,
        onAdd: () async {
          if (!isSupport) {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const LeadCreateEditScreen()),
            );
            return;
          }
          final supportProvider = context.read<SupportCustomersProvider>();
          final followupsProvider = context.read<FollowupsProvider>();
          final saved = await SupportFollowupSheet.show(
            context,
            customers: supportProvider.customers,
          );
          if (!mounted || saved != true) return;
          await followupsProvider.fetchFollowups(showLoading: false);
        },
      ),
    );
  }
}
