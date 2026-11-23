import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_drawer.dart';
import '../../auth/providers/auth_provider.dart';
import '../../dashboard/providers/dashboard_provider.dart';
import '../models/support_models.dart';
import '../providers/support_manager_provider.dart';
import 'support_backup_screen.dart';
import 'support_customer_detail_screen.dart';
import 'support_tickets_screen.dart';
import 'support_widgets.dart';

class SupportManagerDashboardScreen extends StatefulWidget {
  final VoidCallback? onNavigateToCustomers;
  final VoidCallback? onNavigateToFollowups;
  final VoidCallback? onNavigateToBackup;
  final VoidCallback? onNavigateToCalls;
  final VoidCallback? onNavigateToProfile;

  const SupportManagerDashboardScreen({
    super.key,
    this.onNavigateToCustomers,
    this.onNavigateToFollowups,
    this.onNavigateToBackup,
    this.onNavigateToCalls,
    this.onNavigateToProfile,
  });

  @override
  State<SupportManagerDashboardScreen> createState() =>
      _SupportManagerDashboardScreenState();
}

class _SupportManagerDashboardScreenState
    extends State<SupportManagerDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SupportManagerProvider>().fetchAll();
      context.read<DashboardProvider>().fetchDashboardStats();
    });
  }

  void _openBackup() {
    if (widget.onNavigateToBackup != null) {
      widget.onNavigateToBackup!();
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const SupportBackupScreen()),
    );
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

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final manager = context.watch<SupportManagerProvider>();
    final dashboard = context.watch<DashboardProvider>();
    final support = dashboard.stats?.support;
    final overview = manager.overview;

    if (manager.isLoading && overview == null && support == null) {
      return const Scaffold(
        body: LoadingIndicator(message: 'Loading Support Manager dashboard...'),
      );
    }

    if (manager.errorMessage != null && overview == null && support == null) {
      return Scaffold(
        body: ErrorView(
          message: manager.errorMessage!,
          onRetry: () async {
            await manager.fetchAll();
            await dashboard.fetchDashboardStats();
          },
        ),
      );
    }

    final openIssues =
        overview?.pendingIssues.length ?? support?.openTickets ?? 0;
    final overdue =
        overview?.overdueFollowUps.length ?? support?.overdueFollowUps ?? 0;
    final upcoming =
        overview?.upcomingFollowUps.length ??
        support?.upcomingFollowups.length ??
        0;
    final trials = manager.trialCustomers;

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
            onPressed: () async {
              await manager.fetchAll(showLoading: false);
              await dashboard.fetchDashboardStats(showLoading: false);
            },
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
                      : 'M',
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
        onRefresh: () async {
          await manager.fetchAll(showLoading: false);
          await dashboard.fetchDashboardStats(showLoading: false);
        },
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
                    colors: [Color(0xFF0F2351), Color(0xFF7C2D12)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x267C2D12),
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
                            'Support Manager • ${user?.name ?? 'Team Lead'}',
                            style: const TextStyle(
                              color: AppColors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Team-only scope • ${overview?.employees.length ?? 0} team members',
                            style: TextStyle(
                              color: AppColors.white.withValues(alpha: 0.82),
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: [
                              _headerPill(
                                '${overview?.availableCount ?? 0} available',
                              ),
                              _headerPill(
                                '${overview?.leaveCount ?? 0} on leave',
                              ),
                              _headerPill('${manager.assignedTotal} customers'),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const PingoMascotWidget(
                      pose: PingoPoses.salute,
                      height: 52,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              const Text(
                'Team Snapshot',
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
                    title: 'Team Customers',
                    value:
                        '${support?.assignedCustomers ?? manager.assignedTotal}',
                    subtitle: 'Authorized team scope',
                    icon: Icons.groups_rounded,
                    color: AppColors.primary,
                    onTap: widget.onNavigateToCustomers,
                  ),
                  SupportKpiCard(
                    title: 'Open Issues',
                    value: '$openIssues',
                    subtitle: 'Pending Support problems',
                    icon: Icons.report_problem_outlined,
                    color: const Color(0xFFE11D48),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const SupportTicketsScreen(),
                      ),
                    ),
                  ),
                  SupportKpiCard(
                    title: 'Overdue Follow-ups',
                    value: '$overdue',
                    subtitle: 'Team monitoring',
                    icon: Icons.warning_amber_rounded,
                    color: const Color(0xFFDC2626),
                    onTap: widget.onNavigateToFollowups,
                  ),
                  SupportKpiCard(
                    title: 'Upcoming Follow-ups',
                    value: '$upcoming',
                    subtitle: 'Support interactions',
                    icon: Icons.alarm_rounded,
                    color: const Color(0xFFD97706),
                    onTap: widget.onNavigateToFollowups,
                  ),
                  SupportKpiCard(
                    title: 'Backup Assignments',
                    value: '${manager.backupCustomers.length}',
                    subtitle: 'Active coverage',
                    icon: Icons.swap_horiz_rounded,
                    color: const Color(0xFF2563EB),
                    onTap: _openBackup,
                  ),
                  SupportKpiCard(
                    title: 'Trial / Expiry Watch',
                    value: '${trials.length}',
                    subtitle: 'Trials needing attention',
                    icon: Icons.timelapse_rounded,
                    color: const Color(0xFF9333EA),
                    onTap: widget.onNavigateToCustomers,
                  ),
                ],
              ),
              const SizedBox(height: 20),
              SupportSectionHeader(
                title: 'Team Availability',
                actionLabel: 'Backup & Handover',
                onAction: _openBackup,
              ),
              const SizedBox(height: 8),
              if (manager.employees.isEmpty)
                const WacrmCard(
                  child: Text(
                    'No Support team members found in your authorized scope.',
                    style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                  ),
                )
              else
                ...manager.employees.map(
                  (employee) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: WacrmCard(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          CircleAvatar(
                            radius: 17,
                            backgroundColor: const Color(0xFFEFF6FF),
                            child: Text(
                              employee.employeeName.isNotEmpty
                                  ? employee.employeeName[0].toUpperCase()
                                  : 'S',
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: Color(0xFF2563EB),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  employee.employeeName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.textMain,
                                  ),
                                ),
                                Text(
                                  '${employee.assignedCustomerCount} customers'
                                  ' • ${employee.temporaryCoverageCount} backups'
                                  '${employee.onApprovedLeave ? ' • on leave' : ''}',
                                  style: const TextStyle(
                                    fontSize: 11,
                                    color: AppColors.textMuted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          _availabilityBadge(employee),
                        ],
                      ),
                    ),
                  ),
                ),
              const SizedBox(height: 16),
              const SupportSectionHeader(title: 'Team Performance'),
              const SizedBox(height: 8),
              if (manager.teamPerformance.isEmpty)
                const WacrmCard(
                  child: Text(
                    'Team performance appears once assignments are available.',
                    style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                  ),
                )
              else
                WacrmCard(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  child: Column(
                    children: [
                      const Row(
                        children: [
                          Expanded(
                            flex: 3,
                            child: Text(
                              'Employee',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: AppColors.textLight,
                              ),
                            ),
                          ),
                          _PerfHeader('Customers'),
                          _PerfHeader('Issues'),
                          _PerfHeader('Backups'),
                        ],
                      ),
                      const Divider(height: 12),
                      ...manager.teamPerformance.map(
                        (row) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: Row(
                            children: [
                              Expanded(
                                flex: 3,
                                child: Text(
                                  row.employee.employeeName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: AppColors.textMain,
                                  ),
                                ),
                              ),
                              _PerfCell('${row.assignedCustomers}'),
                              _PerfCell('${row.openIssues}'),
                              _PerfCell('${row.backupCustomers}'),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 16),
              SupportSectionHeader(
                title: 'Pending Customer Issues',
                actionLabel: 'Open queue',
                onAction: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const SupportTicketsScreen(),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              if ((overview?.pendingIssues ?? const []).isEmpty)
                const WacrmCard(
                  child: Text(
                    'No unresolved customer issues in your team scope.',
                    style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                  ),
                )
              else
                ...overview!.pendingIssues
                    .take(6)
                    .map(
                      (issue) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: WacrmCard(
                          padding: const EdgeInsets.all(12),
                          onTap: () => _openCustomer(
                            issue.leadId,
                            customerId: issue.customerId,
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      issue.customerName ?? 'Support Customer',
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.textMain,
                                      ),
                                    ),
                                  ),
                                  const WacrmBadge(
                                    label: 'PENDING',
                                    backgroundColor: Color(0xFFFEE2E2),
                                    textColor: Color(0xFFDC2626),
                                    fontSize: 9,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                issue.pendingIssues ?? 'No description saved.',
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: AppColors.textMuted,
                                ),
                              ),
                              const SizedBox(height: 3),
                              Text(
                                '${issue.handlingEmployeeName ?? 'Unassigned'}'
                                ' • ${supportFormatDateTime(issue.interactionAt)}',
                                style: const TextStyle(
                                  fontSize: 10,
                                  color: AppColors.textLight,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
              const SizedBox(height: 16),
              SupportSectionHeader(
                title: 'Follow-up Monitoring',
                actionLabel: 'My Follow-ups',
                onAction: widget.onNavigateToFollowups,
              ),
              const SizedBox(height: 8),
              if ((overview?.overdueFollowUps ?? const []).isEmpty &&
                  (overview?.upcomingFollowUps ?? const []).isEmpty)
                const WacrmCard(
                  child: Text(
                    'No monitored Support follow-ups in your team scope.',
                    style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                  ),
                )
              else ...[
                ...(overview?.overdueFollowUps ?? const [])
                    .take(5)
                    .map((item) => _followupTile(item, isOverdue: true)),
                ...(overview?.upcomingFollowUps ?? const [])
                    .take(5)
                    .map((item) => _followupTile(item, isOverdue: false)),
              ],
              const SizedBox(height: 16),
              const SupportSectionHeader(title: 'Trial / Expiry Reminders'),
              const SizedBox(height: 8),
              if (trials.isEmpty)
                const WacrmCard(
                  child: Text(
                    'No trials or expiring customers in your team scope.',
                    style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                  ),
                )
              else
                ...trials
                    .take(6)
                    .map(
                      (customer) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: WacrmCard(
                          padding: const EdgeInsets.all(12),
                          onTap: () => _openCustomer(
                            customer.leadId,
                            customerId: customer.customerId,
                          ),
                          child: Row(
                            children: [
                              const Icon(
                                Icons.timelapse_rounded,
                                size: 20,
                                color: Color(0xFF9333EA),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      customer.displayCompany,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.textMain,
                                      ),
                                    ),
                                    Text(
                                      '${customer.isTrialExpired ? 'Expired' : 'Expires'} '
                                      '${supportFormatDate(customer.trialEndDate)}'
                                      '${customer.trialDaysRemaining != null ? ' • ${customer.trialDaysRemaining} day(s)' : ''}',
                                      style: const TextStyle(
                                        fontSize: 11,
                                        color: AppColors.textMuted,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const Icon(
                                Icons.chevron_right_rounded,
                                size: 18,
                                color: AppColors.textLight,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
              if (manager.backupCustomers.isNotEmpty) ...[
                const SizedBox(height: 16),
                SupportSectionHeader(
                  title: 'Active Backup Assignments',
                  actionLabel: 'Manage',
                  onAction: _openBackup,
                ),
                const SizedBox(height: 8),
                ...manager.backupCustomers
                    .take(5)
                    .map(
                      (backup) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: WacrmCard(
                          padding: const EdgeInsets.all(12),
                          onTap: () => _openCustomer(
                            backup.history.leadId,
                            customerId: backup.history.customerId,
                          ),
                          child: Row(
                            children: [
                              const Icon(
                                Icons.swap_horiz_rounded,
                                size: 20,
                                color: Color(0xFF2563EB),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      backup.history.customerName,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.textMain,
                                      ),
                                    ),
                                    Text(
                                      '${backup.coverage?.originalEmployeeName ?? 'Original'} → '
                                      '${backup.coverage?.backupEmployeeName ?? 'Backup'}',
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
                              const Icon(
                                Icons.chevron_right_rounded,
                                size: 18,
                                color: AppColors.textLight,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _headerPill(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _availabilityBadge(SupportEmployee employee) {
    Color color = const Color(0xFF64748B);
    String label = 'Offline';
    if (employee.onApprovedLeave) {
      color = const Color(0xFFD97706);
      label = 'On leave';
    } else if (employee.online) {
      color = const Color(0xFF16A34A);
      label = 'Online';
    } else if (employee.available) {
      color = const Color(0xFF2563EB);
      label = 'Available';
    }
    return WacrmBadge(
      label: label,
      backgroundColor: color.withValues(alpha: 0.12),
      textColor: color,
      fontSize: 9,
    );
  }

  Widget _followupTile(
    SupportFollowupMonitorItem item, {
    required bool isOverdue,
  }) {
    final color = isOverdue ? const Color(0xFFDC2626) : const Color(0xFFD97706);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: WacrmCard(
        padding: const EdgeInsets.all(12),
        onTap: () => _openCustomer(item.leadId, customerId: item.customerId),
        child: Row(
          children: [
            Icon(
              isOverdue ? Icons.warning_amber_rounded : Icons.alarm_rounded,
              size: 20,
              color: color,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.customerName ?? 'Support Customer',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textMain,
                    ),
                  ),
                  Text(
                    '${supportFormatDateTime(item.followUpAt)}'
                    '${(item.handlingEmployeeName ?? '').trim().isNotEmpty ? ' • ${item.handlingEmployeeName}' : ''}',
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textMuted,
                    ),
                  ),
                  if ((item.nextAction ?? '').trim().isNotEmpty)
                    Text(
                      item.nextAction!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 10,
                        color: AppColors.textLight,
                      ),
                    ),
                ],
              ),
            ),
            WacrmBadge(
              label: isOverdue ? 'OVERDUE' : 'UPCOMING',
              backgroundColor: color.withValues(alpha: 0.12),
              textColor: color,
              fontSize: 8,
            ),
          ],
        ),
      ),
    );
  }
}

class _PerfHeader extends StatelessWidget {
  final String label;

  const _PerfHeader(this.label);

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 54,
      child: Text(
        label,
        textAlign: TextAlign.center,
        style: const TextStyle(
          fontSize: 9,
          fontWeight: FontWeight.w700,
          color: AppColors.textLight,
        ),
      ),
    );
  }
}

class _PerfCell extends StatelessWidget {
  final String value;

  const _PerfCell(this.value);

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 54,
      child: Text(
        value,
        textAlign: TextAlign.center,
        style: const TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: AppColors.textMain,
        ),
      ),
    );
  }
}
