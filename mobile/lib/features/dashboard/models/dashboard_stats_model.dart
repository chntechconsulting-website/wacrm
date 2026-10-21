class DashboardStatsModel {
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
    return DashboardStatsModel(
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
