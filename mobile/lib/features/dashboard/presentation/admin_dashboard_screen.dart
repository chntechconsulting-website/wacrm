import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_drawer.dart';
import '../../auth/providers/auth_provider.dart';
import '../../support/models/support_models.dart';
import '../../support/presentation/support_backup_screen.dart';
import '../../support/presentation/support_customers_screen.dart';
import '../../support/presentation/support_tickets_screen.dart';
import '../../support/presentation/support_widgets.dart';
import '../models/dashboard_stats_model.dart';
import '../providers/dashboard_provider.dart';

enum _AdminView { overview, sales, support, finance }

/// Admin-only consolidated dashboard. It renders the real
/// `/reports/dashboard` payload: the Sales section is the same data the Sales
/// dashboard uses, and the Support and Finance sections come from the backend
/// payload returned for the Admin (`dashboard_type == "both"`).
class AdminDashboardScreen extends StatefulWidget {
  final VoidCallback? onNavigateToLeads;
  final VoidCallback? onNavigateToProfile;

  const AdminDashboardScreen({
    super.key,
    this.onNavigateToLeads,
    this.onNavigateToProfile,
  });

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  _AdminView _view = _AdminView.overview;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DashboardProvider>().fetchDashboardStats();
    });
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final provider = context.watch<DashboardProvider>();
    final stats = provider.stats;

    if (provider.isLoading && stats == null) {
      return const Scaffold(
        body: LoadingIndicator(message: 'Loading Admin dashboard...'),
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

    if (stats == null) {
      return const Scaffold(
        body: ErrorView(
          message: 'Admin dashboard data is not available.',
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
                      : 'A',
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
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 110),
          children: [
            _buildGreeting(user?.name ?? 'Administrator', stats),
            const SizedBox(height: 14),
            _buildViewSelector(),
            const SizedBox(height: 16),
            if (_view == _AdminView.overview)
              ..._buildOverview(stats)
            else if (_view == _AdminView.sales)
              ..._buildSales(stats)
            else if (_view == _AdminView.support)
              ..._buildSupport(stats)
            else
              ..._buildFinance(stats),
          ],
        ),
      ),
    );
  }

  Widget _buildGreeting(String name, DashboardStatsModel stats) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0F2351), Color(0xFF7F1D1D)],
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
                  'Hello, $name!',
                  style: const TextStyle(
                    color: AppColors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${(stats.department ?? 'Administration')} • Administrator',
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
                    '${stats.totalLeads} leads • ${stats.totalCustomers} customers',
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
          const PingoMascotWidget(pose: PingoPoses.salute, height: 54),
        ],
      ),
    );
  }

  Widget _buildViewSelector() {
    const labels = {
      _AdminView.overview: 'Overview',
      _AdminView.sales: 'Sales',
      _AdminView.support: 'Support',
      _AdminView.finance: 'Finance',
    };
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: _AdminView.values.map((view) {
          final selected = _view == view;
          return Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _view = view),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                padding: const EdgeInsets.symmetric(vertical: 9),
                decoration: BoxDecoration(
                  color: selected ? AppColors.card : Colors.transparent,
                  borderRadius: BorderRadius.circular(9),
                  boxShadow: selected ? AppColors.softShadow : null,
                ),
                child: Text(
                  labels[view]!,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                    color: selected
                        ? AppColors.textMain
                        : AppColors.textMuted,
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  List<Widget> _buildOverview(DashboardStatsModel stats) {
    final support = stats.support;
    final finance = stats.finance;
    return [
      _sectionHeader('Sales Snapshot', 'Open Sales', widget.onNavigateToLeads),
      const SizedBox(height: 8),
      _kpiGrid([
        _AdminKpi(
          title: 'Total Leads',
          value: '${stats.totalLeads}',
          subtitle: '${stats.assignedLeads} assigned',
          icon: Icons.people_alt_outlined,
          color: AppColors.primary,
          onTap: widget.onNavigateToLeads,
        ),
        _AdminKpi(
          title: 'Converted',
          value: '${stats.convertedLeads}',
          subtitle: '${stats.qualifiedLeads} qualified',
          icon: Icons.handshake_outlined,
          color: const Color(0xFF16A34A),
          onTap: widget.onNavigateToLeads,
        ),
        _AdminKpi(
          title: 'Connected Calls',
          value: '${stats.connectedCalls}',
          subtitle: 'CRM call logs',
          icon: Icons.phone_in_talk_rounded,
          color: const Color(0xFF2563EB),
        ),
        _AdminKpi(
          title: 'Customers',
          value: '${stats.totalCustomers}',
          subtitle: 'Company-wide',
          icon: Icons.business_rounded,
          color: const Color(0xFF0D9488),
        ),
      ]),
      const SizedBox(height: 18),
      _sectionHeader(
        'Support Snapshot',
        support != null ? 'Open Support' : null,
        support != null ? _openSupportCustomers : null,
      ),
      const SizedBox(height: 8),
      if (support == null)
        const _UnavailableCard(
          message: 'Support dashboard data is not available for this account.',
        )
      else
        _kpiGrid([
          _AdminKpi(
            title: 'Assigned Customers',
            value: '${support.assignedCustomers}',
            subtitle: '${support.totalTickets} support records',
            icon: Icons.support_agent_rounded,
            color: const Color(0xFFE11D48),
            onTap: _openSupportCustomers,
          ),
          _AdminKpi(
            title: 'Open Issues',
            value: '${support.openTickets}',
            subtitle: '${support.pendingTickets} pending onboarding',
            icon: Icons.report_problem_outlined,
            color: const Color(0xFFDC2626),
            onTap: _openSupportTickets,
          ),
          _AdminKpi(
            title: 'Pending Follow-ups',
            value: '${support.customerFollowups}',
            subtitle: '${support.overdueFollowUps} overdue',
            icon: Icons.alarm_rounded,
            color: const Color(0xFFD97706),
          ),
          _AdminKpi(
            title: "Today's Support Calls",
            value: '${support.todaySupportCalls}',
            subtitle: 'Logged from Support',
            icon: Icons.phone_callback_rounded,
            color: const Color(0xFF4F46E5),
          ),
        ]),
      const SizedBox(height: 18),
      _sectionHeader('Finance Snapshot', null, null),
      const SizedBox(height: 8),
      if (finance == null)
        const _UnavailableCard(
          message: 'Finance dashboard data is not available for this account.',
        )
      else
        _kpiGrid([
          _AdminKpi(
            title: 'Total Revenue',
            value: _money(finance.totalRevenue),
            subtitle: 'Net ${_money(finance.netRevenue)}',
            icon: Icons.account_balance_wallet_outlined,
            color: const Color(0xFF16A34A),
          ),
          _AdminKpi(
            title: 'Pending Payments',
            value: '${finance.pendingPaymentsCount}',
            subtitle: _money(finance.pendingPaymentsAmount),
            icon: Icons.pending_actions_rounded,
            color: const Color(0xFFD97706),
          ),
          _AdminKpi(
            title: 'Overdue Payments',
            value: '${finance.overduePaymentsCount}',
            subtitle: _money(finance.overduePaymentsAmount),
            icon: Icons.warning_amber_rounded,
            color: const Color(0xFFDC2626),
          ),
          _AdminKpi(
            title: 'Active Subscriptions',
            value: '${finance.activeSubscriptionsCount}',
            subtitle: '${finance.upcomingRenewalsCount} renewals soon',
            icon: Icons.autorenew_rounded,
            color: const Color(0xFF2563EB),
          ),
        ]),
      const SizedBox(height: 18),
      _sectionHeader('Admin Quick Actions', null, null),
      const SizedBox(height: 8),
      _actionTile(
        icon: Icons.business_rounded,
        color: const Color(0xFFE11D48),
        title: 'Support Customers',
        subtitle: 'Assigned customers, POCs and Support history',
        onTap: _openSupportCustomers,
      ),
      const SizedBox(height: 8),
      _actionTile(
        icon: Icons.support_agent_rounded,
        color: const Color(0xFF2563EB),
        title: 'Support & Onboarding Queue',
        subtitle: 'Onboarding stages and customer calls',
        onTap: _openSupportTickets,
      ),
      const SizedBox(height: 8),
      _actionTile(
        icon: Icons.swap_horiz_rounded,
        color: const Color(0xFF0D9488),
        title: 'Backup & Handover',
        subtitle: 'Coverage, leave and Support handover records',
        onTap: _openSupportBackup,
      ),
    ];
  }

  List<Widget> _buildSales(DashboardStatsModel stats) {
    return [
      _sectionHeader('Sales Performance', null, null),
      const SizedBox(height: 8),
      _kpiGrid([
        _AdminKpi(
          title: 'Total Leads',
          value: '${stats.totalLeads}',
          subtitle: '${stats.newLeads} new',
          icon: Icons.people_alt_outlined,
          color: AppColors.primary,
        ),
        _AdminKpi(
          title: 'Assigned Leads',
          value: '${stats.assignedLeads}',
          subtitle: '${stats.contactedLeads} contacted',
          icon: Icons.assignment_ind_outlined,
          color: const Color(0xFF2563EB),
        ),
        _AdminKpi(
          title: 'Follow-up Leads',
          value: '${stats.followupLeads}',
          subtitle: '${stats.qualifiedLeads} qualified',
          icon: Icons.alarm_rounded,
          color: const Color(0xFFD97706),
        ),
        _AdminKpi(
          title: 'Converted',
          value: '${stats.convertedLeads}',
          subtitle: '${stats.lostLeads} lost',
          icon: Icons.handshake_outlined,
          color: const Color(0xFF16A34A),
        ),
        _AdminKpi(
          title: 'Connected Calls',
          value: '${stats.connectedCalls}',
          subtitle: 'CRM call logs',
          icon: Icons.phone_in_talk_rounded,
          color: const Color(0xFF4F46E5),
        ),
        _AdminKpi(
          title: 'Customers',
          value: '${stats.totalCustomers}',
          subtitle: 'Company-wide',
          icon: Icons.business_rounded,
          color: const Color(0xFF0D9488),
        ),
      ]),
      const SizedBox(height: 18),
      _sectionHeader('Upcoming Follow-ups', 'Open', widget.onNavigateToLeads),
      const SizedBox(height: 8),
      if (stats.upcomingFollowups.isEmpty)
        const _UnavailableCard(message: 'No upcoming Sales follow-ups.')
      else
        ...stats.upcomingFollowups.take(5).map(_followupTile),
      const SizedBox(height: 18),
      _sectionHeader('Team Performance', null, null),
      const SizedBox(height: 8),
      if (stats.teamPerformance.isEmpty)
        const _UnavailableCard(message: 'No team performance data yet.')
      else
        ...stats.teamPerformance.take(6).map(
          (member) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: WacrmCard(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 17,
                    backgroundColor: AppColors.primaryLight,
                    child: Text(
                      member.name.isNotEmpty
                          ? member.name[0].toUpperCase()
                          : 'S',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: AppColors.primary,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          member.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textMain,
                          ),
                        ),
                        Text(
                          '${member.totalLeads} leads • ${member.calls} calls • ${member.followups} follow-ups',
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    '${member.conversionRate.toStringAsFixed(1)}%',
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF16A34A),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      const SizedBox(height: 18),
      _sectionHeader('Lead Sources', null, null),
      const SizedBox(height: 8),
      if (stats.sourceCounts.isEmpty)
        const _UnavailableCard(message: 'No lead source data yet.')
      else
        WacrmCard(
          child: Column(
            children: stats.sourceCounts.take(6).map((source) {
              final total = stats.sourceCounts.fold<int>(
                0,
                (sum, item) => sum + item.count,
              );
              final ratio = total == 0 ? 0.0 : source.count / total;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            source.source,
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.textMain,
                            ),
                          ),
                          const SizedBox(height: 4),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(4),
                            child: LinearProgressIndicator(
                              value: ratio,
                              minHeight: 5,
                              backgroundColor: const Color(0xFFF1F5F9),
                              color: AppColors.primary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      '${source.count}',
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
    ];
  }

  List<Widget> _buildSupport(DashboardStatsModel stats) {
    final support = stats.support;
    if (support == null) {
      return const [
        _UnavailableCard(
          message: 'Support dashboard data is not available for this account.',
        ),
      ];
    }
    return [
      _sectionHeader('Support Performance', null, _openSupportCustomers),
      const SizedBox(height: 8),
      _kpiGrid([
        _AdminKpi(
          title: 'Assigned Customers',
          value: '${support.assignedCustomers}',
          subtitle: '${support.totalTickets} support records',
          icon: Icons.people_alt_outlined,
          color: AppColors.primary,
          onTap: _openSupportCustomers,
        ),
        _AdminKpi(
          title: 'Active Customers',
          value: '${support.activeCustomers}',
          subtitle: 'Currently active',
          icon: Icons.verified_user_outlined,
          color: const Color(0xFF16A34A),
          onTap: _openSupportCustomers,
        ),
        _AdminKpi(
          title: 'Pending Follow-ups',
          value: '${support.customerFollowups}',
          subtitle: '${support.overdueFollowUps} overdue',
          icon: Icons.alarm_rounded,
          color: const Color(0xFFD97706),
        ),
        _AdminKpi(
          title: 'Open Issues',
          value: '${support.openTickets}',
          subtitle: '${support.pendingTickets} pending onboarding',
          icon: Icons.support_agent_rounded,
          color: const Color(0xFFE11D48),
          onTap: _openSupportTickets,
        ),
        _AdminKpi(
          title: 'Completed Activities',
          value: '${support.completedSupportActivities}',
          subtitle: '${support.resolvedTickets} resolved tickets',
          icon: Icons.task_alt_rounded,
          color: const Color(0xFF0D9488),
        ),
        _AdminKpi(
          title: "Today's Support Calls",
          value: '${support.todaySupportCalls}',
          subtitle: 'Logged from Support',
          icon: Icons.phone_in_talk_rounded,
          color: const Color(0xFF2563EB),
        ),
      ]),
      const SizedBox(height: 18),
      _sectionHeader('Upcoming Support Follow-ups', null, null),
      const SizedBox(height: 8),
      if (support.upcomingFollowups.isEmpty)
        const _UnavailableCard(message: 'No upcoming Support follow-ups.')
      else
        ...support.upcomingFollowups.take(5).map(_supportFollowupTile),
      const SizedBox(height: 18),
      _sectionHeader(
        'Recent Support Records',
        'Open Queue',
        _openSupportTickets,
      ),
      const SizedBox(height: 8),
      if (support.recentTickets.isEmpty)
        const _UnavailableCard(message: 'No recent Support records yet.')
      else
        ...support.recentTickets.take(5).map(
          (ticket) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: WacrmCard(
              padding: const EdgeInsets.all(12),
              onTap: ticket.leadId == null
                  ? _openSupportTickets
                  : () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => SupportCustomersScreen(),
                        ),
                      );
                    },
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          ticket.companyName?.trim().isNotEmpty == true
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
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: supportStatusColor(ticket.supportStatus)
                          .withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      ticket.statusLabel,
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        color: supportStatusColor(ticket.supportStatus),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      const SizedBox(height: 18),
      _sectionHeader('Support Status Overview', null, null),
      const SizedBox(height: 8),
      if (support.statusBreakdown.isEmpty)
        const _UnavailableCard(message: 'No Support status data yet.')
      else
        WacrmCard(
          child: Column(
            children: support.statusBreakdown.map((item) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: supportStatusColor(item.status),
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
    ];
  }

  List<Widget> _buildFinance(DashboardStatsModel stats) {
    final finance = stats.finance;
    if (finance == null) {
      return const [
        _UnavailableCard(
          message: 'Finance dashboard data is not available for this account.',
        ),
      ];
    }
    final growth = finance.revenueGrowthPct;
    return [
      _sectionHeader('Revenue', null, null),
      const SizedBox(height: 8),
      _kpiGrid([
        _AdminKpi(
          title: 'Total Revenue',
          value: _money(finance.totalRevenue),
          subtitle: 'Net ${_money(finance.netRevenue)}',
          icon: Icons.account_balance_wallet_outlined,
          color: const Color(0xFF16A34A),
        ),
        _AdminKpi(
          title: 'This Month',
          value: _money(finance.currentMonthRevenue),
          subtitle:
              '${growth >= 0 ? '+' : ''}${growth.toStringAsFixed(1)}% vs last month',
          icon: Icons.trending_up_rounded,
          color: growth >= 0
              ? const Color(0xFF2563EB)
              : const Color(0xFFDC2626),
        ),
        _AdminKpi(
          title: 'Paid Invoices',
          value: '${finance.paidInvoicesCount}',
          subtitle: _money(finance.paidInvoicesAmount),
          icon: Icons.receipt_long_outlined,
          color: const Color(0xFF0D9488),
        ),
        _AdminKpi(
          title: 'Total Invoices',
          value: '${finance.totalInvoicesCount}',
          subtitle: 'All finance invoices',
          icon: Icons.description_outlined,
          color: const Color(0xFF4F46E5),
        ),
      ]),
      const SizedBox(height: 18),
      _sectionHeader('Collections & Risk', null, null),
      const SizedBox(height: 8),
      _kpiGrid([
        _AdminKpi(
          title: 'Pending Payments',
          value: '${finance.pendingPaymentsCount}',
          subtitle: _money(finance.pendingPaymentsAmount),
          icon: Icons.pending_actions_rounded,
          color: const Color(0xFFD97706),
        ),
        _AdminKpi(
          title: 'Pending Handoffs',
          value: '${finance.pendingHandoffsCount}',
          subtitle: _money(finance.pendingHandoffsAmount),
          icon: Icons.swap_horiz_rounded,
          color: const Color(0xFF2563EB),
        ),
        _AdminKpi(
          title: 'Overdue Payments',
          value: '${finance.overduePaymentsCount}',
          subtitle: _money(finance.overduePaymentsAmount),
          icon: Icons.warning_amber_rounded,
          color: const Color(0xFFDC2626),
        ),
        _AdminKpi(
          title: 'Refunds',
          value: '${finance.totalRefundsCount}',
          subtitle:
              '${finance.pendingRefundsCount} pending • ${_money(finance.totalRefundsAmount)}',
          icon: Icons.currency_exchange_rounded,
          color: const Color(0xFF9333EA),
        ),
      ]),
      const SizedBox(height: 18),
      _sectionHeader('Subscriptions', null, null),
      const SizedBox(height: 8),
      _kpiGrid([
        _AdminKpi(
          title: 'Active',
          value: '${finance.activeSubscriptionsCount}',
          subtitle: 'Currently subscribed',
          icon: Icons.verified_outlined,
          color: const Color(0xFF16A34A),
        ),
        _AdminKpi(
          title: 'Renewals (30d)',
          value: '${finance.upcomingRenewalsCount}',
          subtitle: 'Upcoming renewals',
          icon: Icons.autorenew_rounded,
          color: const Color(0xFFD97706),
        ),
        _AdminKpi(
          title: 'Expired',
          value: '${finance.expiredSubscriptionsCount}',
          subtitle: 'Need follow-up',
          icon: Icons.event_busy_rounded,
          color: const Color(0xFFDC2626),
        ),
        _AdminKpi(
          title: 'Last Month',
          value: _money(finance.prevMonthRevenue),
          subtitle: 'Previous month revenue',
          icon: Icons.calendar_month_outlined,
          color: const Color(0xFF64748B),
        ),
      ]),
    ];
  }

  Widget _sectionHeader(String title, String? actionLabel, VoidCallback? onTap) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppColors.textMain,
            ),
          ),
        ),
        if (actionLabel != null && onTap != null)
          TextButton(
            onPressed: onTap,
            style: TextButton.styleFrom(
              padding: EdgeInsets.zero,
              minimumSize: const Size(0, 28),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: Text(
              actionLabel,
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
            ),
          ),
      ],
    );
  }

  Widget _kpiGrid(List<_AdminKpi> items) {
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      childAspectRatio: 1.42,
      children: items
          .map(
            (item) => WacrmCard(
              padding: const EdgeInsets.all(12),
              onTap: item.onTap,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 30,
                    height: 30,
                    decoration: BoxDecoration(
                      color: item.color.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(9),
                    ),
                    child: Icon(item.icon, size: 17, color: item.color),
                  ),
                  const Spacer(),
                  Text(
                    item.value,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      color: AppColors.textMain,
                    ),
                  ),
                  Text(
                    item.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textMuted,
                    ),
                  ),
                  Text(
                    item.subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 9,
                      color: AppColors.textLight,
                    ),
                  ),
                ],
              ),
            ),
          )
          .toList(),
    );
  }

  Widget _followupTile(UpcomingFollowupItem followup) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: WacrmCard(
        padding: const EdgeInsets.all(12),
        onTap: widget.onNavigateToLeads,
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
                    '${followup.followupDate} • ${followup.followupTime} • ${followup.priority}',
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textMuted,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _supportFollowupTile(SupportFollowupSummary followup) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: WacrmCard(
        padding: const EdgeInsets.all(12),
        onTap: _openSupportCustomers,
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: followup.isOverdue
                    ? const Color(0xFFFEE2E2)
                    : const Color(0xFFFEF3C7),
                borderRadius: BorderRadius.circular(9),
              ),
              child: Icon(
                followup.isOverdue
                    ? Icons.warning_amber_rounded
                    : Icons.alarm_rounded,
                size: 18,
                color: followup.isOverdue
                    ? const Color(0xFFDC2626)
                    : const Color(0xFFD97706),
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
            if (followup.isOverdue)
              const Text(
                'OVERDUE',
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFFDC2626),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _actionTile({
    required IconData icon,
    required Color color,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return WacrmCard(
      padding: const EdgeInsets.all(12),
      onTap: onTap,
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textMain,
                  ),
                ),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 10,
                    color: AppColors.textMuted,
                  ),
                ),
              ],
            ),
          ),
          const Icon(
            Icons.chevron_right_rounded,
            color: AppColors.textLight,
            size: 20,
          ),
        ],
      ),
    );
  }

  void _openSupportCustomers() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const SupportCustomersScreen()),
    );
  }

  void _openSupportTickets() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const SupportTicketsScreen()),
    );
  }

  void _openSupportBackup() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const SupportBackupScreen()),
    );
  }

  String _money(double value) {
    final formatter = NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: value.abs() >= 100000 ? 0 : 2,
    );
    return formatter.format(value);
  }
}

class _AdminKpi {
  final String title;
  final String value;
  final String subtitle;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  const _AdminKpi({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.icon,
    required this.color,
    this.onTap,
  });
}

class _UnavailableCard extends StatelessWidget {
  final String message;

  const _UnavailableCard({required this.message});

  @override
  Widget build(BuildContext context) {
    return WacrmCard(
      child: Text(
        message,
        style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
      ),
    );
  }
}
