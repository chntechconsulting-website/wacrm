import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/services/doocti_call_service.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_drawer.dart';
import '../../auth/providers/auth_provider.dart';
import '../../dashboard/providers/dashboard_provider.dart';
import '../presentation/support_customer_detail_screen.dart';
import '../presentation/support_tickets_screen.dart';
import 'support_widgets.dart';

class SupportDashboardScreen extends StatefulWidget {
  final VoidCallback? onNavigateToCustomers;
  final VoidCallback? onNavigateToFollowups;
  final VoidCallback? onNavigateToCalls;
  final VoidCallback? onNavigateToProfile;

  const SupportDashboardScreen({
    super.key,
    this.onNavigateToCustomers,
    this.onNavigateToFollowups,
    this.onNavigateToCalls,
    this.onNavigateToProfile,
  });

  @override
  State<SupportDashboardScreen> createState() => _SupportDashboardScreenState();
}

class _SupportDashboardScreenState extends State<SupportDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DashboardProvider>().fetchDashboardStats();
    });
  }

  void _openCustomer(int? leadId, {int? customerId}) {
    if (leadId == null) {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const SupportTicketsScreen()),
      );
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) =>
            SupportCustomerDetailScreen(leadId: leadId, customerId: customerId),
      ),
    );
  }

  void _call(String phone) {
    if (phone.trim().isEmpty) return;
    DooctiCallService.makeCall(context, phone: phone);
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final provider = context.watch<DashboardProvider>();
    final stats = provider.stats;

    if (provider.isLoading && stats == null) {
      return const Scaffold(
        body: LoadingIndicator(message: 'Loading Support dashboard...'),
      );
    }

    if (provider.errorMessage != null && stats == null) {
      return Scaffold(
        body: ErrorView(
          message: provider.errorMessage!,
          onRetry: () => provider.fetchDashboardStats(),
        ),
      );
    }

    final support = stats?.support;
    if (stats == null || support == null) {
      return Scaffold(
        backgroundColor: AppColors.background,
        drawer: const WacrmDrawer(currentTabIndex: 0),
        appBar: AppBar(title: const Text('Support Dashboard')),
        body: EmptyState(
          title: 'Support Workspace',
          subtitle:
              'Your Support dashboard is not available for this account yet. '
              'Pull to refresh or contact your administrator.',
          pingoPose: PingoPoses.inspect,
          actionLabel: 'Refresh',
          onAction: () => provider.fetchDashboardStats(),
        ),
      );
    }

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
            style: TextStyle(
              fontWeight: FontWeight.w900,
              color: AppColors.primary,
            ),
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: () => provider.fetchDashboardStats(),
          ),
          InkWell(
            onTap: widget.onNavigateToProfile,
            child: Padding(
              padding: const EdgeInsets.only(right: 14),
              child: CircleAvatar(
                radius: 16,
                backgroundColor: AppColors.primaryLight,
                child: Text(
                  user?.name.isNotEmpty == true
                      ? user!.name[0].toUpperCase()
                      : 'S',
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
        onRefresh: () => provider.fetchDashboardStats(showLoading: false),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 110),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF0F2351), Color(0xFF1E3A8A)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x261E3A8A),
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
                            'Hello, ${user?.name ?? 'Support Team'}!',
                            style: const TextStyle(
                              color: AppColors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            user != null
                                ? 'Support Workspace • ${supportStatusLabel(user.role)}'
                                : 'Support Workspace',
                            style: TextStyle(
                              color: AppColors.white.withValues(alpha: 0.82),
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 9,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              '${support.assignedCustomers} assigned customers',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                              ),
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
              const Text(
                'Support Snapshot',
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
                childAspectRatio: 1.42,
                children: [
                  SupportKpiCard(
                    title: 'Assigned Customers',
                    value: '${support.assignedCustomers}',
                    subtitle: '${support.totalTickets} support records',
                    icon: Icons.people_alt_outlined,
                    color: AppColors.primary,
                    onTap: widget.onNavigateToCustomers,
                  ),
                  SupportKpiCard(
                    title: 'Active Customers',
                    value: '${support.activeCustomers}',
                    subtitle: 'Currently active',
                    icon: Icons.verified_user_outlined,
                    color: const Color(0xFF16A34A),
                    onTap: widget.onNavigateToCustomers,
                  ),
                  SupportKpiCard(
                    title: 'Pending Follow-ups',
                    value: '${support.customerFollowups}',
                    subtitle: 'Support interactions due',
                    icon: Icons.alarm_rounded,
                    color: const Color(0xFFD97706),
                    onTap: widget.onNavigateToFollowups,
                  ),
                  SupportKpiCard(
                    title: 'Overdue Follow-ups',
                    value: '${support.overdueFollowUps}',
                    subtitle: 'Needs immediate action',
                    icon: Icons.warning_amber_rounded,
                    color: const Color(0xFFDC2626),
                    onTap: widget.onNavigateToFollowups,
                  ),
                  SupportKpiCard(
                    title: 'Open Support Issues',
                    value: '${support.openTickets}',
                    subtitle: '${support.pendingTickets} pending onboarding',
                    icon: Icons.support_agent_rounded,
                    color: const Color(0xFFE11D48),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const SupportTicketsScreen(),
                      ),
                    ),
                  ),
                  SupportKpiCard(
                    title: 'Completed Activities',
                    value: '${support.completedSupportActivities}',
                    subtitle: 'Resolved support work',
                    icon: Icons.task_alt_rounded,
                    color: const Color(0xFF0D9488),
                  ),
                  SupportKpiCard(
                    title: "Today's Support Calls",
                    value: '${support.todaySupportCalls}',
                    subtitle: 'Logged from Support',
                    icon: Icons.phone_in_talk_rounded,
                    color: const Color(0xFF2563EB),
                    onTap: widget.onNavigateToCalls,
                  ),
                  SupportKpiCard(
                    title: 'Resolved Tickets',
                    value: '${support.resolvedTickets}',
                    subtitle: support.averageResolutionDisplay != null
                        ? 'Avg ${support.averageResolutionDisplay}'
                        : 'Completed onboardings',
                    icon: Icons.check_circle_outline_rounded,
                    color: const Color(0xFF4F46E5),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const SupportTicketsScreen(),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              SupportSectionHeader(
                title: 'Upcoming Support Follow-ups',
                actionLabel: 'View all',
                onAction: widget.onNavigateToFollowups,
              ),
              const SizedBox(height: 8),
              if (support.upcomingFollowups.isEmpty)
                const WacrmCard(
                  child: Text(
                    'No upcoming Support follow-ups. Schedule one from a customer profile or the + button.',
                    style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                  ),
                )
              else
                ...support.upcomingFollowups
                    .take(4)
                    .map(
                      (followup) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: WacrmCard(
                          padding: const EdgeInsets.all(12),
                          onTap: () => _openCustomer(followup.leadId),
                          child: Row(
                            children: [
                              Container(
                                width: 34,
                                height: 34,
                                decoration: BoxDecoration(
                                  color: const Color(0xFFFEF3C7),
                                  borderRadius: BorderRadius.circular(9),
                                ),
                                child: const Icon(
                                  Icons.alarm_rounded,
                                  size: 18,
                                  color: Color(0xFFD97706),
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      followup.leadName,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.textMain,
                                      ),
                                    ),
                                    Text(
                                      '${supportFormatDateTime(followup.followupDate)}'
                                      '${followup.priority.trim().isNotEmpty ? ' • ${followup.priority}' : ''}',
                                      style: const TextStyle(
                                        fontSize: 11,
                                        color: AppColors.textMuted,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              if (user?.canCallSupportCustomer == true &&
                                  followup.leadPhone.trim().isNotEmpty)
                                IconButton(
                                  visualDensity: VisualDensity.compact,
                                  icon: const Icon(
                                    Icons.phone_rounded,
                                    size: 18,
                                    color: AppColors.success,
                                  ),
                                  onPressed: () => _call(followup.leadPhone),
                                ),
                            ],
                          ),
                        ),
                      ),
                    ),
              const SizedBox(height: 16),
              SupportSectionHeader(
                title: 'Recent Support Records',
                actionLabel: 'Open queue',
                onAction: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const SupportTicketsScreen(),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              if (support.recentTickets.isEmpty)
                const WacrmCard(
                  child: Text(
                    'No recent Support records yet.',
                    style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                  ),
                )
              else
                ...support.recentTickets
                    .take(4)
                    .map(
                      (ticket) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: WacrmCard(
                          padding: const EdgeInsets.all(12),
                          onTap: () => _openCustomer(
                            ticket.leadId,
                            customerId: ticket.customerId,
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      ticket.companyName?.trim().isNotEmpty ==
                                              true
                                          ? ticket.companyName!
                                          : ticket.customerName,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.textMain,
                                      ),
                                    ),
                                    const SizedBox(height: 3),
                                    Text(
                                      [
                                        if ((ticket.productService ?? '')
                                            .trim()
                                            .isNotEmpty)
                                          ticket.productService!,
                                        if ((ticket.assignedAgentName ?? '')
                                            .trim()
                                            .isNotEmpty)
                                          ticket.assignedAgentName!,
                                      ].join(' • '),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 11,
                                        color: AppColors.textMuted,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 8),
                              SupportStatusBadge(
                                status: ticket.supportStatus,
                                label: ticket.statusLabel,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
              const SizedBox(height: 16),
              if (support.statusBreakdown.isNotEmpty) ...[
                const SupportSectionHeader(title: 'Support Status Overview'),
                const SizedBox(height: 8),
                WacrmCard(
                  child: Column(
                    children: support.statusBreakdown.map((item) {
                      final color = supportStatusColor(item.status);
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 5),
                        child: Row(
                          children: [
                            Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                color: color,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                item.label,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.textMain,
                                ),
                              ),
                            ),
                            Text(
                              '${item.count}',
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: AppColors.textMain,
                              ),
                            ),
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
}
