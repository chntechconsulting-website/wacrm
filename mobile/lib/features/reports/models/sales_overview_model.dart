class SalesOverviewModel {
  final int totalLeads;
  final int totalCustomers;
  final double totalRevenue;
  final double conversionRate;
  final List<FunnelStageItem> funnelStages;
  final List<SourceBreakdownItem> sources;

  SalesOverviewModel({
    required this.totalLeads,
    required this.totalCustomers,
    required this.totalRevenue,
    required this.conversionRate,
    required this.funnelStages,
    required this.sources,
  });

  factory SalesOverviewModel.fromJson(Map<String, dynamic> json) {
    return SalesOverviewModel(
      totalLeads: json['total_leads'] ?? json['kpis']?['total_leads']?['value'] ?? 0,
      totalCustomers: json['total_customers'] ?? json['kpis']?['total_customers']?['value'] ?? 0,
      totalRevenue: (json['total_revenue'] ?? json['kpis']?['total_revenue']?['value'] as num?)?.toDouble() ?? 0.0,
      conversionRate: (json['conversion_rate'] ?? json['kpis']?['conversion_rate']?['value'] as num?)?.toDouble() ?? 0.0,
      funnelStages: (json['funnel'] as List? ?? json['sales_funnel'] as List? ?? [])
          .map((i) => FunnelStageItem.fromJson(i))
          .toList(),
      sources: (json['sources'] as List? ?? json['leads_by_source'] as List? ?? [])
          .map((i) => SourceBreakdownItem.fromJson(i))
          .toList(),
    );
  }
}

class FunnelStageItem {
  final String stage;
  final int count;
  final double percentage;

  FunnelStageItem({required this.stage, required this.count, required this.percentage});

  factory FunnelStageItem.fromJson(Map<String, dynamic> json) {
    return FunnelStageItem(
      stage: json['stage'] ?? json['name'] ?? '',
      count: json['count'] ?? json['value'] ?? 0,
      percentage: (json['percentage'] ?? json['rate'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class SourceBreakdownItem {
  final String source;
  final int count;

  SourceBreakdownItem({required this.source, required this.count});

  factory SourceBreakdownItem.fromJson(Map<String, dynamic> json) {
    return SourceBreakdownItem(
      source: json['source'] ?? 'Unknown',
      count: json['count'] ?? json['leads'] ?? 0,
    );
  }
}
