import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_drawer.dart';
import '../../auth/providers/auth_provider.dart';
import '../providers/dashboard_provider.dart';

class DashboardScreen extends StatefulWidget {
  final VoidCallback? onNavigateToLeads;
  final VoidCallback? onNavigateToFollowups;
  final VoidCallback? onNavigateToCalls;
  final VoidCallback? onNavigateToProfile;

  const DashboardScreen({
    super.key,
    this.onNavigateToLeads,
    this.onNavigateToFollowups,
    this.onNavigateToCalls,
    this.onNavigateToProfile,
  });

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DashboardProvider>().fetchDashboardStats();
    });
  }

  void _callNumber(String phone) async {
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final uri = Uri.parse('tel:$cleanPhone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final dashboardProvider = context.watch<DashboardProvider>();

    if (dashboardProvider.isLoading && dashboardProvider.stats == null) {
      return const Scaffold(
        body: LoadingIndicator(message: 'Loading CRM Dashboard...'),
      );
    }

    if (dashboardProvider.errorMessage != null && dashboardProvider.stats == null) {
      return Scaffold(
        body: ErrorView(
          message: dashboardProvider.errorMessage!,
          onRetry: () => dashboardProvider.fetchDashboardStats(),
        ),
      );
    }

    final stats = dashboardProvider.stats;

    return Scaffold(
      backgroundColor: AppColors.background,
      drawer: const WacrmDrawer(currentTabIndex: 0),
      appBar: AppBar(
        title: Image.asset(
          'assets/images/logo.png',
          height: 30,
          fit: BoxFit.contain,
          errorBuilder: (_, _, _) => const Text(
            'WA! CRM',
            style: TextStyle(fontWeight: FontWeight.w900, color: AppColors.primary),
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: () => dashboardProvider.fetchDashboardStats(),
          ),
          InkWell(
            onTap: widget.onNavigateToProfile,
            child: Padding(
              padding: const EdgeInsets.only(right: 14),
              child: CircleAvatar(
                radius: 16,
                backgroundColor: AppColors.primaryLight,
                child: Text(
                  user?.name.isNotEmpty == true ? user!.name[0].toUpperCase() : 'U',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: AppColors.primary,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        color: AppColors.primary,
        onRefresh: () => dashboardProvider.fetchDashboardStats(showLoading: false),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // User Greeting Banner
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF065F46), Color(0xFF059669)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x26059669),
                      blurRadius: 14,
                      offset: Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Hello, ${user?.name ?? 'Sales Representative'}!',
                            style: const TextStyle(
                              color: AppColors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            user != null
                                ? 'Role: ${user.role} • ${user.department ?? 'CRM'}'
                                : 'Welcome to Mobile CRM',
                            style: TextStyle(
                              color: AppColors.white.withValues(alpha: 0.85),
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const PingoMascotWidget(
                      pose: PingoPoses.salute,
                      height: 54,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),

              // KPI Stats Grid
              const Text(
                'Performance Snapshot',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textMain,
                ),
              ),
              const SizedBox(height: 12),

              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 1.5,
                children: [
                  _buildKpiCard(
                    title: 'Total Leads',
                    value: '${stats?.totalLeads ?? 0}',
                    subtitle: '${stats?.newLeads ?? 0} new leads',
                    icon: Icons.people_alt_outlined,
                    color: AppColors.primary,
                    onTap: widget.onNavigateToLeads,
                  ),
                  _buildKpiCard(
                    title: 'Follow-ups',
                    value: '${stats?.followupLeads ?? 0}',
                    subtitle: 'Scheduled calls/visits',
                    icon: Icons.alarm_rounded,
                    color: AppColors.warning,
                    onTap: widget.onNavigateToFollowups,
                  ),
                  _buildKpiCard(
                    title: 'Converted / Won',
                    value: '${stats?.convertedLeads ?? 0}',
                    subtitle: '${stats?.totalCustomers ?? 0} total customers',
                    icon: Icons.check_circle_outline_rounded,
                    color: AppColors.success,
                  ),
                  _buildKpiCard(
                    title: 'Connected Calls',
                    value: '${stats?.connectedCalls ?? 0}',
                    subtitle: 'Logged interactions',
                    icon: Icons.phone_callback_rounded,
                    color: AppColors.accent,
                    onTap: widget.onNavigateToCalls,
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Upcoming Follow-ups Section
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Upcoming Follow-ups',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textMain,
                    ),
                  ),
                  if (widget.onNavigateToFollowups != null)
                    TextButton(
                      onPressed: widget.onNavigateToFollowups,
                      child: const Text('View All', style: TextStyle(fontSize: 13, color: AppColors.primary)),
                    ),
                ],
              ),
              const SizedBox(height: 8),

              if (stats == null || stats.upcomingFollowups.isEmpty)
                const WacrmCard(
                  child: EmptyState(
                    title: 'No Pending Follow-ups',
                    subtitle: 'You are all caught up on scheduled follow-ups!',
                    pingoPose: PingoPoses.celebrate,
                  ),
                )
              else
                ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: stats.upcomingFollowups.length > 4 ? 4 : stats.upcomingFollowups.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 8),
                  itemBuilder: (context, index) {
                    final item = stats.upcomingFollowups[index];
                    return WacrmCard(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: AppColors.warningLight,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Icon(Icons.schedule_rounded, color: AppColors.warning, size: 20),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        item.leadName,
                                        style: const TextStyle(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w700,
                                          color: AppColors.textMain,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                    WacrmBadge.priority(item.priority),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '${item.followupDate} at ${item.followupTime}',
                                  style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                                ),
                                if (item.notes != null && item.notes!.isNotEmpty) ...[
                                  const SizedBox(height: 2),
                                  Text(
                                    item.notes!,
                                    style: const TextStyle(fontSize: 11, color: AppColors.textLight),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ],
                              ],
                            ),
                          ),
                          if (item.leadPhone.isNotEmpty)
                            IconButton(
                              icon: const Icon(Icons.phone_rounded, color: AppColors.primary, size: 20),
                              onPressed: () => _callNumber(item.leadPhone),
                            ),
                        ],
                      ),
                    );
                  },
                ),
              const SizedBox(height: 20),

              // Team Performance (Admins & Sales Managers)
              if (user?.isAdmin == true || user?.isSalesManager == true) ...[
                if (stats != null && stats.teamPerformance.isNotEmpty) ...[
                  const Text(
                    'Team Performance Leaderboard',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textMain,
                    ),
                  ),
                  const SizedBox(height: 10),
                  WacrmCard(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      children: stats.teamPerformance.map((emp) {
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 8.0),
                          child: Row(
                            children: [
                              CircleAvatar(
                                radius: 18,
                                backgroundColor: AppColors.primaryLight,
                                child: Text(
                                  emp.name.isNotEmpty ? emp.name[0].toUpperCase() : 'E',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.primary,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      emp.name,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600,
                                        color: AppColors.textMain,
                                      ),
                                    ),
                                    Text(
                                      '${emp.totalLeads} leads • ${emp.calls} calls',
                                      style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                                    ),
                                  ],
                                ),
                              ),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(
                                    '${emp.converted} Won',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 13,
                                      color: AppColors.success,
                                    ),
                                  ),
                                  Text(
                                    '${emp.conversionRate.toStringAsFixed(1)}% rate',
                                    style: const TextStyle(fontSize: 11, color: AppColors.textLight),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
              ],

              // Today's Activity Feed
              if (stats != null && stats.todayActivities.isNotEmpty) ...[
                const Text(
                  'Recent Team Activity',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textMain,
                  ),
                ),
                const SizedBox(height: 10),
                WacrmCard(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    children: stats.todayActivities.take(5).map((act) {
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6.0),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              padding: const EdgeInsets.all(6),
                              decoration: BoxDecoration(
                                color: AppColors.cardHover,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Icon(
                                act.icon == 'call' ? Icons.phone_in_talk_rounded : Icons.history_rounded,
                                size: 16,
                                color: AppColors.primary,
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    act.title,
                                    style: const TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: AppColors.textMain,
                                    ),
                                  ),
                                  Text(
                                    act.createdAt,
                                    style: const TextStyle(fontSize: 10, color: AppColors.textLight),
                                  ),
                                ],
                              ),
                            ),
                            WacrmBadge.status(act.status),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildKpiCard({
    required String title,
    required String value,
    required String subtitle,
    required IconData icon,
    required Color color,
    VoidCallback? onTap,
  }) {
    return WacrmCard(
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textMuted,
                ),
              ),
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 16, color: color),
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                value,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: color,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 10,
                  color: AppColors.textLight,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
