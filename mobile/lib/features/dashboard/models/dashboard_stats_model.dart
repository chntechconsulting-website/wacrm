import '../../support/models/support_models.dart';

class DashboardStatsModel {
  final String dashboardType;
  final String? role;
  final String? department;
  final SupportDashboardStats? support;
  final FinanceDashboardSummary? finance;
  final int totalLeads;
  final int newLeads;
  final int assignedLeads;
  final int contactedLeads;
  final int followupLeads;
  final int qualifiedLeads;
  final int convertedLeads;
  final int lostLeads;
  final int connectedCalls;
  final int totalCustomers;
  final List<UpcomingFollowupItem> upcomingFollowups;
  final List<TeamPerformanceItem> teamPerformance;
  final List<SourceCountItem> sourceCounts;
  final List<TodayActivityItem> todayActivities;

  DashboardStatsModel({
    this.dashboardType = 'sales',
    this.role,
    this.department,
    this.support,
    this.finance,
    required this.totalLeads,
    required this.newLeads,
    required this.assignedLeads,
    required this.contactedLeads,
    required this.followupLeads,
    required this.qualifiedLeads,
    required this.convertedLeads,
    required this.lostLeads,
    required this.connectedCalls,
    required this.totalCustomers,
    required this.upcomingFollowups,
    required this.teamPerformance,
    required this.sourceCounts,
    required this.todayActivities,
  });

  factory DashboardStatsModel.fromJson(Map<String, dynamic> json) {
    final supportJson = json['support'];
    final financeJson = json['finance'];
    return DashboardStatsModel(
      dashboardType: json['dashboard_type']?.toString() ?? 'sales',
      role: json['role']?.toString(),
      department: json['department']?.toString(),
      support: supportJson is Map
          ? SupportDashboardStats.fromJson(Map<String, dynamic>.from(supportJson))
          : null,
      finance: financeJson is Map
          ? FinanceDashboardSummary.fromJson(
              Map<String, dynamic>.from(financeJson),
            )
          : null,
      totalLeads: json['total_leads'] ?? 0,
      newLeads: json['new_leads'] ?? 0,
      assignedLeads: json['assigned_leads'] ?? 0,
      contactedLeads: json['contacted_leads'] ?? 0,
      followupLeads: json['followup_leads'] ?? 0,
      qualifiedLeads: json['qualified_leads'] ?? 0,
      convertedLeads: json['converted_leads'] ?? 0,
      lostLeads: json['lost_leads'] ?? 0,
      connectedCalls: json['connected_calls'] ?? 0,
      totalCustomers: json['total_customers'] ?? 0,
      upcomingFollowups: (json['upcoming_followups'] as List? ?? [])
          .map((i) => UpcomingFollowupItem.fromJson(i))
          .toList(),
      teamPerformance: (json['team_performance'] as List? ?? [])
          .map((i) => TeamPerformanceItem.fromJson(i))
          .toList(),
      sourceCounts: (json['source_lead_counts'] as List? ?? [])
          .map((i) => SourceCountItem.fromJson(i))
          .toList(),
      todayActivities: (json['today_activities'] as List? ?? [])
          .map((i) => TodayActivityItem.fromJson(i))
          .toList(),
    );
  }
}

/// Finance KPIs returned inside the Admin dashboard payload. These are the
/// same values the web Finance dashboard consumes; the mobile app only
/// presents them, it never recalculates revenue.
class FinanceDashboardSummary {
  final double totalRevenue;
  final double netRevenue;
  final double currentMonthRevenue;
  final double prevMonthRevenue;
  final double revenueGrowthPct;
  final int pendingPaymentsCount;
  final double pendingPaymentsAmount;
  final int pendingHandoffsCount;
  final double pendingHandoffsAmount;
  final int paidInvoicesCount;
  final double paidInvoicesAmount;
  final int totalInvoicesCount;
  final int overduePaymentsCount;
  final double overduePaymentsAmount;
  final int totalRefundsCount;
  final double totalRefundsAmount;
  final int pendingRefundsCount;
  final int activeSubscriptionsCount;
  final int upcomingRenewalsCount;
  final int expiredSubscriptionsCount;

  const FinanceDashboardSummary({
    required this.totalRevenue,
    required this.netRevenue,
    required this.currentMonthRevenue,
    required this.prevMonthRevenue,
    required this.revenueGrowthPct,
    required this.pendingPaymentsCount,
    required this.pendingPaymentsAmount,
    required this.pendingHandoffsCount,
    required this.pendingHandoffsAmount,
    required this.paidInvoicesCount,
    required this.paidInvoicesAmount,
    required this.totalInvoicesCount,
    required this.overduePaymentsCount,
    required this.overduePaymentsAmount,
    required this.totalRefundsCount,
    required this.totalRefundsAmount,
    required this.pendingRefundsCount,
    required this.activeSubscriptionsCount,
    required this.upcomingRenewalsCount,
    required this.expiredSubscriptionsCount,
  });

  factory FinanceDashboardSummary.fromJson(Map<String, dynamic> json) {
    double amount(String key) =>
        (json[key] as num?)?.toDouble() ?? 0.0;
    int count(String key) => (json[key] as num?)?.toInt() ?? 0;
    return FinanceDashboardSummary(
      totalRevenue: amount('total_revenue'),
      netRevenue: amount('net_revenue'),
      currentMonthRevenue: amount('current_month_revenue'),
      prevMonthRevenue: amount('prev_month_revenue'),
      revenueGrowthPct: amount('revenue_growth_pct'),
      pendingPaymentsCount: count('pending_payments_count'),
      pendingPaymentsAmount: amount('pending_payments_amount'),
      pendingHandoffsCount: count('pending_handoffs_count'),
      pendingHandoffsAmount: amount('pending_handoffs_amount'),
      paidInvoicesCount: count('paid_invoices_count'),
      paidInvoicesAmount: amount('paid_invoices_amount'),
      totalInvoicesCount: count('total_invoices_count'),
      overduePaymentsCount: count('overdue_payments_count'),
      overduePaymentsAmount: amount('overdue_payments_amount'),
      totalRefundsCount: count('total_refunds_count'),
      totalRefundsAmount: amount('total_refunds_amount'),
      pendingRefundsCount: count('pending_refunds_count'),
      activeSubscriptionsCount: count('active_subscriptions_count'),
      upcomingRenewalsCount: count('upcoming_renewals_count'),
      expiredSubscriptionsCount: count('expired_subscriptions_count'),
    );
  }
}

class UpcomingFollowupItem {
  final int id;
  final String leadName;
  final String leadPhone;
  final String followupDate;
  final String followupTime;
  final String priority;
  final String? notes;

  UpcomingFollowupItem({
    required this.id,
    required this.leadName,
    required this.leadPhone,
    required this.followupDate,
    required this.followupTime,
    required this.priority,
    this.notes,
  });

  factory UpcomingFollowupItem.fromJson(Map<String, dynamic> json) {
    return UpcomingFollowupItem(
      id: json['id'] ?? 0,
      leadName: json['lead_name'] ?? 'Lead',
      leadPhone: json['lead_phone'] ?? '',
      followupDate: json['followup_date'] ?? '',
      followupTime: json['followup_time'] ?? '10:00 AM',
      priority: json['priority'] ?? 'MEDIUM',
      notes: json['notes'],
    );
  }
}

class TeamPerformanceItem {
  final String name;
  final int totalLeads;
  final int converted;
  final int calls;
  final int followups;
  final double conversionRate;

  TeamPerformanceItem({
    required this.name,
    required this.totalLeads,
    required this.converted,
    required this.calls,
    required this.followups,
    required this.conversionRate,
  });

  factory TeamPerformanceItem.fromJson(Map<String, dynamic> json) {
    return TeamPerformanceItem(
      name: json['name'] ?? 'Sales Rep',
      totalLeads: json['total_leads'] ?? 0,
      converted: json['converted'] ?? 0,
      calls: json['calls'] ?? 0,
      followups: json['followups'] ?? 0,
      conversionRate: (json['conversion_rate'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class SourceCountItem {
  final String source;
  final int count;

  SourceCountItem({required this.source, required this.count});

  factory SourceCountItem.fromJson(Map<String, dynamic> json) {
    return SourceCountItem(
      source: json['source'] ?? 'Unknown',
      count: json['count'] ?? 0,
    );
  }
}

class TodayActivityItem {
  final int id;
  final String title;
  final String createdAt;
  final String status;
  final String icon;

  TodayActivityItem({
    required this.id,
    required this.title,
    required this.createdAt,
    required this.status,
    required this.icon,
  });

  factory TodayActivityItem.fromJson(Map<String, dynamic> json) {
    return TodayActivityItem(
      id: json['id'] ?? 0,
      title: json['title'] ?? 'Activity',
      createdAt: json['created_at'] ?? '',
      status: json['status'] ?? 'UPDATED',
      icon: json['icon'] ?? 'note',
    );
  }
}
