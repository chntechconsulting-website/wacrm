int _asInt(dynamic value, [int fallback = 0]) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? fallback;
}

int? _asNullableInt(dynamic value) {
  if (value == null || value.toString().trim().isEmpty) return null;
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value.toString());
}

double? _asNullableDouble(dynamic value) {
  if (value == null || value.toString().trim().isEmpty) return null;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString());
}

String _asString(dynamic value, [String fallback = '']) {
  if (value == null) return fallback;
  return value.toString();
}

String? _asNullableString(dynamic value) {
  final text = value?.toString().trim();
  if (text == null || text.isEmpty) return null;
  return text;
}

bool _asBool(dynamic value, [bool fallback = false]) {
  if (value is bool) return value;
  if (value is num) return value != 0;
  final text = value?.toString().trim().toLowerCase();
  if (text == 'true' || text == '1' || text == 'yes') return true;
  if (text == 'false' || text == '0' || text == 'no') return false;
  return fallback;
}

class SupportPoc {
  final int id;
  final int leadId;
  final int? customerId;
  final String name;
  final String mobile;
  final String? alternateMobile;
  final String? whatsappNumber;
  final String? email;
  final String? designation;
  final String? department;
  final String preferredContactMethod;
  final String? notes;
  final bool isPrimary;

  const SupportPoc({
    required this.id,
    required this.leadId,
    this.customerId,
    required this.name,
    required this.mobile,
    this.alternateMobile,
    this.whatsappNumber,
    this.email,
    this.designation,
    this.department,
    this.preferredContactMethod = 'CALL',
    this.notes,
    this.isPrimary = false,
  });

  factory SupportPoc.fromJson(Map<String, dynamic> json) {
    return SupportPoc(
      id: _asInt(json['id']),
      leadId: _asInt(json['lead_id']),
      customerId: _asNullableInt(json['customer_id']),
      name: _asString(json['name'], 'Point of Contact'),
      mobile: _asString(json['mobile']),
      alternateMobile: _asNullableString(json['alternate_mobile']),
      whatsappNumber: _asNullableString(json['whatsapp_number']),
      email: _asNullableString(json['email']),
      designation: _asNullableString(json['designation']),
      department: _asNullableString(json['department']),
      preferredContactMethod:
          _asString(json['preferred_contact_method'], 'CALL'),
      notes: _asNullableString(json['notes']),
      isPrimary: _asBool(json['is_primary']),
    );
  }

  String get subtitle {
    final pieces = <String>[];
    if ((designation ?? '').trim().isNotEmpty) pieces.add(designation!.trim());
    if ((department ?? '').trim().isNotEmpty) pieces.add(department!.trim());
    if (pieces.isEmpty) return preferredContactMethod;
    return pieces.join(' • ');
  }
}

class SupportCustomer {
  final int id;
  final int leadId;
  final int? supportHandoffId;
  final int? customerId;
  final String name;
  final String contactPerson;
  final String? companyName;
  final String? phone;
  final String? email;
  final String? location;
  final String? city;
  final String? state;
  final String? source;
  final String? salesStatus;
  final String supportStatus;
  final String onboardingStatus;
  final String priority;
  final String? productService;
  final String? supportRequirements;
  final String? notes;
  final int? assignedSupportExecutiveId;
  final String? assignedSupportExecutiveName;
  final int? assignedSupportManagerId;
  final String? assignedSupportManagerName;
  final String? assignmentDate;
  final String? salesEmployeeName;
  final String? trialStartDate;
  final String? trialEndDate;
  final int? trialDaysRemaining;
  final bool isTrialExpired;
  final String? trialStatus;
  final String? nextFollowupDate;
  final String? nextFollowupTime;
  final List<SupportPoc> pocs;
  final SupportPoc? primaryPoc;
  final SupportPurchaseDetails? purchaseDetails;
  final int activitiesCount;

  const SupportCustomer({
    required this.id,
    required this.leadId,
    this.supportHandoffId,
    this.customerId,
    required this.name,
    required this.contactPerson,
    this.companyName,
    this.phone,
    this.email,
    this.location,
    this.city,
    this.state,
    this.source,
    this.salesStatus,
    required this.supportStatus,
    required this.onboardingStatus,
    required this.priority,
    this.productService,
    this.supportRequirements,
    this.notes,
    this.assignedSupportExecutiveId,
    this.assignedSupportExecutiveName,
    this.assignedSupportManagerId,
    this.assignedSupportManagerName,
    this.assignmentDate,
    this.salesEmployeeName,
    this.trialStartDate,
    this.trialEndDate,
    this.trialDaysRemaining,
    this.isTrialExpired = false,
    this.trialStatus,
    this.nextFollowupDate,
    this.nextFollowupTime,
    this.pocs = const [],
    this.primaryPoc,
    this.purchaseDetails,
    this.activitiesCount = 0,
  });

  factory SupportCustomer.fromJson(Map<String, dynamic> json) {
    final rawPocs = json['pocs'];
    final pocs = rawPocs is List
        ? rawPocs
            .whereType<Map>()
            .map((item) => SupportPoc.fromJson(Map<String, dynamic>.from(item)))
            .toList()
        : <SupportPoc>[];
    final primaryJson = json['primary_poc'];
    final primary = primaryJson is Map
        ? SupportPoc.fromJson(Map<String, dynamic>.from(primaryJson))
        : (pocs.where((poc) => poc.isPrimary).isNotEmpty
            ? pocs.firstWhere((poc) => poc.isPrimary)
            : (pocs.isNotEmpty ? pocs.first : null));
    final purchaseJson = json['purchase_details'];
    return SupportCustomer(
      id: _asInt(json['id']),
      leadId: _asInt(json['lead_id'], _asInt(json['id'])),
      supportHandoffId: _asNullableInt(json['support_handoff_id']),
      customerId: _asNullableInt(json['customer_id']),
      name: _asString(json['name'], 'Support Customer'),
      contactPerson:
          _asString(json['contact_person'], _asString(json['name'], 'Customer')),
      companyName: _asNullableString(json['company_name'] ?? json['company']),
      phone: _asNullableString(json['phone']),
      email: _asNullableString(json['email']),
      location: _asNullableString(json['location']),
      city: _asNullableString(json['city']),
      state: _asNullableString(json['state']),
      source: _asNullableString(json['source']),
      salesStatus: _asNullableString(json['sales_status'] ?? json['status']),
      supportStatus: _asString(json['support_status'], 'NEW'),
      onboardingStatus: _asString(json['onboarding_status'], 'PENDING_ONBOARDING'),
      priority: _asString(json['priority'], 'MEDIUM'),
      productService: _asNullableString(json['product_service']),
      supportRequirements: _asNullableString(json['support_requirements']),
      notes: _asNullableString(json['notes']),
      assignedSupportExecutiveId:
          _asNullableInt(json['assigned_support_executive_id']),
      assignedSupportExecutiveName:
          _asNullableString(json['assigned_support_executive_name']),
      assignedSupportManagerId:
          _asNullableInt(json['assigned_support_manager_id']),
      assignedSupportManagerName:
          _asNullableString(json['assigned_support_manager_name']),
      assignmentDate: _asNullableString(json['assignment_date']),
      salesEmployeeName: _asNullableString(json['sales_employee_name']),
      trialStartDate: _asNullableString(json['trial_start_date']),
      trialEndDate: _asNullableString(json['trial_end_date']),
      trialDaysRemaining: _asNullableInt(json['trial_days_remaining']),
      isTrialExpired: _asBool(json['is_trial_expired']),
      trialStatus: _asNullableString(json['trial_status']),
      nextFollowupDate: _asNullableString(json['next_followup_date']),
      nextFollowupTime: _asNullableString(json['next_followup_time']),
      pocs: pocs,
      primaryPoc: primary,
      purchaseDetails: purchaseJson is Map
          ? SupportPurchaseDetails.fromJson(
              Map<String, dynamic>.from(purchaseJson))
          : null,
      activitiesCount: _asInt(json['activities_count']),
    );
  }

  String get displayCompany =>
      (companyName ?? '').trim().isNotEmpty ? companyName!.trim() : name;

  bool get isTrial => (trialStatus ?? '').trim().isNotEmpty &&
      (trialStatus ?? '').toUpperCase() != 'NONE';

  bool get isTrialExpiringSoon {
    if (isTrialExpired) return true;
    final days = trialDaysRemaining;
    return days != null && days >= 0 && days <= 7;
  }
}

class SupportPurchaseAddon {
  final String name;
  final int? quantity;
  final double? unitPrice;
  final String? classification;
  final double? lineTotal;

  const SupportPurchaseAddon({
    required this.name,
    this.quantity,
    this.unitPrice,
    this.classification,
    this.lineTotal,
  });

  factory SupportPurchaseAddon.fromJson(Map<String, dynamic> json) {
    return SupportPurchaseAddon(
      name: _asString(json['name'], 'Add-on'),
      quantity: _asNullableInt(json['quantity']),
      unitPrice: _asNullableDouble(json['unit_price']),
      classification: _asNullableString(json['classification']),
      lineTotal: _asNullableDouble(json['line_total']),
    );
  }
}

class SupportPurchaseDetails {
  final String? packageName;
  final String? planName;
  final int? employeeQuantity;
  final int? biometricDeviceCount;
  final int? durationMonths;
  final String? startDate;
  final String? endDate;
  final List<SupportPurchaseAddon> addons;
  final double? purchaseAmount;
  final String? source;

  const SupportPurchaseDetails({
    this.packageName,
    this.planName,
    this.employeeQuantity,
    this.biometricDeviceCount,
    this.durationMonths,
    this.startDate,
    this.endDate,
    this.addons = const [],
    this.purchaseAmount,
    this.source,
  });

  factory SupportPurchaseDetails.fromJson(Map<String, dynamic> json) {
    final package = json['package'];
    final plan = json['plan'];
    final subscription = json['subscription'];
    final addons = json['addons'];
    return SupportPurchaseDetails(
      packageName: package is Map
          ? _asNullableString(package['name'] ?? package['code'])
          : _asNullableString(json['package_name']),
      planName: plan is Map
          ? _asNullableString(plan['name'] ?? plan['code'])
          : _asNullableString(json['plan_name']),
      employeeQuantity:
          _asNullableInt(json['employee_quantity'] ?? json['employee_count']),
      biometricDeviceCount: _asNullableInt(json['biometric_device_count']),
      durationMonths: subscription is Map
          ? _asNullableInt(subscription['duration_months'])
          : _asNullableInt(json['duration_months']),
      startDate: subscription is Map
          ? _asNullableString(subscription['start_date'])
          : _asNullableString(json['start_date']),
      endDate: subscription is Map
          ? _asNullableString(subscription['end_date'])
          : _asNullableString(json['end_date']),
      addons: addons is List
          ? addons
              .whereType<Map>()
              .map((item) => SupportPurchaseAddon.fromJson(
                  Map<String, dynamic>.from(item)))
              .toList()
          : const [],
      purchaseAmount: _asNullableDouble(json['purchase_amount']),
      source: _asNullableString(json['source']),
    );
  }

  bool get hasAnyValue =>
      (packageName ?? '').trim().isNotEmpty ||
      (planName ?? '').trim().isNotEmpty ||
      employeeQuantity != null ||
      addons.isNotEmpty ||
      purchaseAmount != null;
}

class SupportFollowupSummary {
  final int id;
  final int leadId;
  final String leadName;
  final String leadPhone;
  final String followupDate;
  final String followupTime;
  final String priority;
  final String? notes;
  final bool isOverdue;

  const SupportFollowupSummary({
    required this.id,
    required this.leadId,
    required this.leadName,
    required this.leadPhone,
    required this.followupDate,
    required this.followupTime,
    required this.priority,
    this.notes,
    this.isOverdue = false,
  });

  factory SupportFollowupSummary.fromJson(Map<String, dynamic> json) {
    return SupportFollowupSummary(
      id: _asInt(json['id']),
      leadId: _asInt(json['lead_id']),
      leadName: _asString(json['lead_name'], 'Customer'),
      leadPhone: _asString(json['lead_phone']),
      followupDate: _asString(json['followup_date']),
      followupTime: _asString(json['followup_time'], '10:00 AM'),
      priority: _asString(json['priority'], 'MEDIUM'),
      notes: _asNullableString(json['notes']),
      isOverdue: _asBool(json['is_overdue']),
    );
  }
}

class SupportRecentTicket {
  final int id;
  final int? leadId;
  final int? customerId;
  final String customerName;
  final String? companyName;
  final String? phone;
  final String? email;
  final String? productService;
  final String supportStatus;
  final String statusLabel;
  final String? statusColor;
  final bool isTrialExpired;
  final int? trialDaysRemaining;
  final String? assignedAgentName;
  final String? supportManagerName;
  final String? createdAt;
  final String? completedAt;

  const SupportRecentTicket({
    required this.id,
    this.leadId,
    this.customerId,
    required this.customerName,
    this.companyName,
    this.phone,
    this.email,
    this.productService,
    required this.supportStatus,
    required this.statusLabel,
    this.statusColor,
    this.isTrialExpired = false,
    this.trialDaysRemaining,
    this.assignedAgentName,
    this.supportManagerName,
    this.createdAt,
    this.completedAt,
  });

  factory SupportRecentTicket.fromJson(Map<String, dynamic> json) {
    return SupportRecentTicket(
      id: _asInt(json['id']),
      leadId: _asNullableInt(json['lead_id']),
      customerId: _asNullableInt(json['customer_id']),
      customerName: _asString(json['customer_name'], 'Support Customer'),
      companyName: _asNullableString(json['company_name']),
      phone: _asNullableString(json['phone']),
      email: _asNullableString(json['email']),
      productService: _asNullableString(json['product_service']),
      supportStatus: _asString(json['support_status'], 'NEW'),
      statusLabel: _asString(json['status_label'], 'New'),
      statusColor: _asNullableString(json['status_color']),
      isTrialExpired: _asBool(json['is_trial_expired']),
      trialDaysRemaining: _asNullableInt(json['trial_days_remaining']),
      assignedAgentName: _asNullableString(json['assigned_agent_name']),
      supportManagerName: _asNullableString(json['support_manager_name']),
      createdAt: _asNullableString(json['created_at']),
      completedAt: _asNullableString(json['completed_at']),
    );
  }
}

class SupportStatusBreakdownItem {
  final String status;
  final String label;
  final int count;
  final double percentage;
  final String? color;
  final String? bucket;

  const SupportStatusBreakdownItem({
    required this.status,
    required this.label,
    required this.count,
    required this.percentage,
    this.color,
    this.bucket,
  });

  factory SupportStatusBreakdownItem.fromJson(Map<String, dynamic> json) {
    return SupportStatusBreakdownItem(
      status: _asString(json['status']),
      label: _asString(json['label'], _asString(json['status'], 'Status')),
      count: _asInt(json['count']),
      percentage: _asNullableDouble(json['percentage']) ?? 0,
      color: _asNullableString(json['color']),
      bucket: _asNullableString(json['bucket']),
    );
  }
}

class SupportAgentWorkload {
  final String name;
  final int count;
  final double percentage;

  const SupportAgentWorkload({
    required this.name,
    required this.count,
    required this.percentage,
  });

  factory SupportAgentWorkload.fromJson(Map<String, dynamic> json) {
    return SupportAgentWorkload(
      name: _asString(json['name'], 'Unassigned'),
      count: _asInt(json['count']),
      percentage: _asNullableDouble(json['percentage']) ?? 0,
    );
  }
}

class SupportDashboardStats {
  final int totalTickets;
  final int openTickets;
  final int resolvedTickets;
  final int pendingTickets;
  final int customerFollowups;
  final int assignedCustomers;
  final int activeCustomers;
  final int overdueFollowUps;
  final int completedSupportActivities;
  final int todaySupportCalls;
  final double? averageResolutionHours;
  final String? averageResolutionDisplay;
  final List<SupportStatusBreakdownItem> statusBreakdown;
  final List<SupportAgentWorkload> agentWorkload;
  final List<SupportRecentTicket> recentTickets;
  final List<SupportFollowupSummary> upcomingFollowups;

  const SupportDashboardStats({
    required this.totalTickets,
    required this.openTickets,
    required this.resolvedTickets,
    required this.pendingTickets,
    required this.customerFollowups,
    required this.assignedCustomers,
    required this.activeCustomers,
    required this.overdueFollowUps,
    required this.completedSupportActivities,
    required this.todaySupportCalls,
    this.averageResolutionHours,
    this.averageResolutionDisplay,
    this.statusBreakdown = const [],
    this.agentWorkload = const [],
    this.recentTickets = const [],
    this.upcomingFollowups = const [],
  });

  factory SupportDashboardStats.fromJson(Map<String, dynamic> json) {
    final totalTickets = _asInt(json['total_tickets']);
    final openTickets = _asInt(json['open_tickets']);
    final resolvedTickets = _asInt(json['resolved_tickets']);
    final pendingTickets = _asInt(json['pending_tickets']);
    final followups = _asInt(json['customer_followups']);
    final recent = json['recent_tickets'];
    final statusBreakdown = json['status_breakdown'];
    final agentWorkload = json['agent_workload'];
    final upcoming = json['upcoming_followups'];
    return SupportDashboardStats(
      totalTickets: totalTickets,
      openTickets: openTickets,
      resolvedTickets: resolvedTickets,
      pendingTickets: pendingTickets,
      customerFollowups: followups,
      assignedCustomers: _asInt(json['assigned_customers'], totalTickets),
      activeCustomers:
          _asInt(json['active_customers'], totalTickets - resolvedTickets),
      overdueFollowUps: _asInt(json['overdue_follow_ups']),
      completedSupportActivities:
          _asInt(json['completed_support_activities'], resolvedTickets),
      todaySupportCalls: _asInt(json['today_support_calls']),
      averageResolutionHours: _asNullableDouble(json['average_resolution_hours']),
      averageResolutionDisplay:
          _asNullableString(json['average_resolution_display']),
      statusBreakdown: statusBreakdown is List
          ? statusBreakdown
              .whereType<Map>()
              .map((item) => SupportStatusBreakdownItem.fromJson(
                  Map<String, dynamic>.from(item)))
              .toList()
          : const [],
      agentWorkload: agentWorkload is List
          ? agentWorkload
              .whereType<Map>()
              .map((item) => SupportAgentWorkload.fromJson(
                  Map<String, dynamic>.from(item)))
              .toList()
          : const [],
      recentTickets: recent is List
          ? recent
              .whereType<Map>()
              .map((item) => SupportRecentTicket.fromJson(
                  Map<String, dynamic>.from(item)))
              .toList()
          : const [],
      upcomingFollowups: upcoming is List
          ? upcoming
              .whereType<Map>()
              .map((item) => SupportFollowupSummary.fromJson(
                  Map<String, dynamic>.from(item)))
              .toList()
          : const [],
    );
  }
}

class SupportCustomerPage {
  final int total;
  final int page;
  final int limit;
  final List<SupportCustomer> items;

  const SupportCustomerPage({
    required this.total,
    required this.page,
    required this.limit,
    required this.items,
  });

  factory SupportCustomerPage.fromJson(Map<String, dynamic> json) {
    final raw = json['items'];
    return SupportCustomerPage(
      total: _asInt(json['total']),
      page: _asInt(json['page'], 1),
      limit: _asInt(json['limit'], 50),
      items: raw is List
          ? raw
              .whereType<Map>()
              .map((item) =>
                  SupportCustomer.fromJson(Map<String, dynamic>.from(item)))
              .toList()
          : const [],
    );
  }
}

class SupportBackupCustomer {
  final SupportHistory history;
  final SupportCoverage? coverage;
  final SupportLeave? leave;

  const SupportBackupCustomer({
    required this.history,
    this.coverage,
    this.leave,
  });

  factory SupportBackupCustomer.fromJson(Map<String, dynamic> json) {
    final coverageJson = json['coverage'];
    final leaveJson = json['leave'];
    return SupportBackupCustomer(
      history: SupportHistory.fromJson(json),
      coverage: coverageJson is Map
          ? SupportCoverage.fromJson(Map<String, dynamic>.from(coverageJson))
          : null,
      leave: leaveJson is Map
          ? SupportLeave.fromJson(Map<String, dynamic>.from(leaveJson))
          : null,
    );
  }
}

class SupportInteraction {
  final int id;
  final int? customerId;
  final int? leadId;
  final int? customerPocId;
  final String? pocName;
  final String? pocPhone;
  final String interactionType;
  final String? interactionAt;
  final String? discussion;
  final String? problemReported;
  final String? troubleshooting;
  final String? solutionProvided;
  final String? pendingIssues;
  final String? customerCommitments;
  final String? nextAction;
  final String? followUpAt;
  final String? notes;
  final String? handlingEmployeeName;
  final String? originalEmployeeName;

  const SupportInteraction({
    required this.id,
    this.customerId,
    this.leadId,
    this.customerPocId,
    this.pocName,
    this.pocPhone,
    required this.interactionType,
    this.interactionAt,
    this.discussion,
    this.problemReported,
    this.troubleshooting,
    this.solutionProvided,
    this.pendingIssues,
    this.customerCommitments,
    this.nextAction,
    this.followUpAt,
    this.notes,
    this.handlingEmployeeName,
    this.originalEmployeeName,
  });

  factory SupportInteraction.fromJson(Map<String, dynamic> json) {
    return SupportInteraction(
      id: _asInt(json['id']),
      customerId: _asNullableInt(json['customer_id']),
      leadId: _asNullableInt(json['lead_id']),
      customerPocId: _asNullableInt(json['customer_poc_id']),
      pocName: _asNullableString(json['poc_name']),
      pocPhone: _asNullableString(json['poc_phone']),
      interactionType: _asString(json['interaction_type'], 'MANUAL'),
      interactionAt: _asNullableString(json['interaction_at']),
      discussion: _asNullableString(json['discussion']),
      problemReported: _asNullableString(json['problem_reported']),
      troubleshooting: _asNullableString(json['troubleshooting']),
      solutionProvided: _asNullableString(json['solution_provided']),
      pendingIssues: _asNullableString(json['pending_issues']),
      customerCommitments: _asNullableString(json['customer_commitments']),
      nextAction: _asNullableString(json['next_action']),
      followUpAt: _asNullableString(json['follow_up_at']),
      notes: _asNullableString(json['notes']),
      handlingEmployeeName: _asNullableString(json['handling_employee_name']),
      originalEmployeeName: _asNullableString(json['original_employee_name']),
    );
  }

  bool get hasPendingIssue => (pendingIssues ?? '').trim().isNotEmpty;
}

class SupportHistorySummary {
  final String? lastConversationSummary;
  final String? lastReportedProblem;
  final String? currentUnresolvedIssue;
  final String? unresolvedSince;
  final String? nextRecommendedAction;
  final int interactionCount;
  final List<String> solutionsAttempted;
  final SupportFollowupSummary? pendingFollowUp;

  const SupportHistorySummary({
    this.lastConversationSummary,
    this.lastReportedProblem,
    this.currentUnresolvedIssue,
    this.unresolvedSince,
    this.nextRecommendedAction,
    this.interactionCount = 0,
    this.solutionsAttempted = const [],
    this.pendingFollowUp,
  });

  factory SupportHistorySummary.fromJson(Map<String, dynamic> json) {
    final solutions = json['solutions_attempted'];
    final pending = json['pending_follow_up'];
    return SupportHistorySummary(
      lastConversationSummary:
          _asNullableString(json['last_conversation_summary']),
      lastReportedProblem: _asNullableString(json['last_reported_problem']),
      currentUnresolvedIssue:
          _asNullableString(json['current_unresolved_issue']),
      unresolvedSince: _asNullableString(json['unresolved_since']),
      nextRecommendedAction:
          _asNullableString(json['next_recommended_action']),
      interactionCount: _asInt(json['interaction_count']),
      solutionsAttempted: solutions is List
          ? solutions
              .whereType<Map>()
              .map((item) => _asString(item['solution']))
              .where((item) => item.trim().isNotEmpty)
              .toList()
          : const [],
      pendingFollowUp: pending is Map
          ? SupportFollowupSummary.fromJson({
              'id': pending['interaction_id'],
              'followup_date': pending['follow_up_at'],
              'followup_time': '',
              'priority': 'MEDIUM',
              'notes': pending['next_action'],
              'is_overdue': pending['is_overdue'],
            })
          : null,
    );
  }
}

class SupportScheduledFollowup {
  final int id;
  final String? followupDate;
  final String? followupTime;
  final String? notes;
  final String priority;
  final String status;
  final int? assignedTo;

  const SupportScheduledFollowup({
    required this.id,
    this.followupDate,
    this.followupTime,
    this.notes,
    this.priority = 'MEDIUM',
    this.status = 'Pending',
    this.assignedTo,
  });

  factory SupportScheduledFollowup.fromJson(Map<String, dynamic> json) {
    return SupportScheduledFollowup(
      id: _asInt(json['id']),
      followupDate: _asNullableString(json['followup_date']),
      followupTime: _asNullableString(json['followup_time']),
      notes: _asNullableString(json['notes']),
      priority: _asString(json['priority'], 'MEDIUM'),
      status: _asString(json['status'], 'Pending'),
      assignedTo: _asNullableInt(json['assigned_to']),
    );
  }
}

class SupportCoverage {
  final int id;
  final int leadId;
  final int? customerId;
  final int? originalEmployeeId;
  final String? originalEmployeeName;
  final int? backupEmployeeId;
  final String? backupEmployeeName;
  final String? startDate;
  final String? endDate;
  final String status;

  const SupportCoverage({
    required this.id,
    required this.leadId,
    this.customerId,
    this.originalEmployeeId,
    this.originalEmployeeName,
    this.backupEmployeeId,
    this.backupEmployeeName,
    this.startDate,
    this.endDate,
    this.status = 'ACTIVE',
  });

  factory SupportCoverage.fromJson(Map<String, dynamic> json) {
    return SupportCoverage(
      id: _asInt(json['id']),
      leadId: _asInt(json['lead_id']),
      customerId: _asNullableInt(json['customer_id']),
      originalEmployeeId: _asNullableInt(json['original_employee_id']),
      originalEmployeeName: _asNullableString(json['original_employee_name']),
      backupEmployeeId: _asNullableInt(json['backup_employee_id']),
      backupEmployeeName: _asNullableString(json['backup_employee_name']),
      startDate: _asNullableString(json['start_date']),
      endDate: _asNullableString(json['end_date']),
      status: _asString(json['status'], 'ACTIVE'),
    );
  }
}

class SupportHistory {
  final int leadId;
  final int? customerId;
  final int? supportHandoffId;
  final String customerName;
  final String? companyName;
  final String? phone;
  final String? email;
  final String? location;
  final String? productService;
  final String? customerRequirements;
  final String? supportStatus;
  final int? originalSupportEmployeeId;
  final String? originalSupportEmployeeName;
  final int? currentHandlingEmployeeId;
  final String? currentHandlingEmployeeName;
  final int? backupEmployeeId;
  final String? backupEmployeeName;
  final SupportCoverage? coverage;
  final List<SupportCoverage> coverageHistory;
  final List<SupportPoc> pocs;
  final SupportPoc? primaryPoc;
  final List<SupportInteraction> interactions;
  final SupportHistorySummary summary;
  final List<SupportScheduledFollowup> scheduledFollowups;
  final SupportPurchaseDetails? purchaseDetails;

  const SupportHistory({
    required this.leadId,
    this.customerId,
    this.supportHandoffId,
    required this.customerName,
    this.companyName,
    this.phone,
    this.email,
    this.location,
    this.productService,
    this.customerRequirements,
    this.supportStatus,
    this.originalSupportEmployeeId,
    this.originalSupportEmployeeName,
    this.currentHandlingEmployeeId,
    this.currentHandlingEmployeeName,
    this.backupEmployeeId,
    this.backupEmployeeName,
    this.coverage,
    this.coverageHistory = const [],
    this.pocs = const [],
    this.primaryPoc,
    this.interactions = const [],
    required this.summary,
    this.scheduledFollowups = const [],
    this.purchaseDetails,
  });

  factory SupportHistory.fromJson(Map<String, dynamic> json) {
    final pocsJson = json['pocs'];
    final pocs = pocsJson is List
        ? pocsJson
            .whereType<Map>()
            .map((item) => SupportPoc.fromJson(Map<String, dynamic>.from(item)))
            .toList()
        : <SupportPoc>[];
    final primaryJson = json['primary_poc'];
    final interactionsJson = json['interactions'];
    final scheduledJson = json['scheduled_followups'];
    final coverageJson = json['coverage'];
    final coverageHistoryJson = json['coverage_history'];
    final purchaseJson = json['purchase_details'];
    final summaryJson = json['summary'];
    return SupportHistory(
      leadId: _asInt(json['lead_id']),
      customerId: _asNullableInt(json['customer_id']),
      supportHandoffId: _asNullableInt(json['support_handoff_id']),
      customerName: _asString(json['customer_name'], 'Support Customer'),
      companyName: _asNullableString(json['company_name']),
      phone: _asNullableString(json['phone']),
      email: _asNullableString(json['email']),
      location: _asNullableString(json['location']),
      productService: _asNullableString(json['product_service']),
      customerRequirements: _asNullableString(json['customer_requirements']),
      supportStatus: _asNullableString(json['support_status']),
      originalSupportEmployeeId:
          _asNullableInt(json['original_support_employee_id']),
      originalSupportEmployeeName:
          _asNullableString(json['original_support_employee_name']),
      currentHandlingEmployeeId:
          _asNullableInt(json['current_handling_employee_id']),
      currentHandlingEmployeeName:
          _asNullableString(json['current_handling_employee_name']),
      backupEmployeeId: _asNullableInt(json['backup_employee_id']),
      backupEmployeeName: _asNullableString(json['backup_employee_name']),
      coverage: coverageJson is Map
          ? SupportCoverage.fromJson(Map<String, dynamic>.from(coverageJson))
          : null,
      coverageHistory: coverageHistoryJson is List
          ? coverageHistoryJson
              .whereType<Map>()
              .map((item) =>
                  SupportCoverage.fromJson(Map<String, dynamic>.from(item)))
              .toList()
          : const [],
      pocs: pocs,
      primaryPoc: primaryJson is Map
          ? SupportPoc.fromJson(Map<String, dynamic>.from(primaryJson))
          : (pocs.where((poc) => poc.isPrimary).isNotEmpty
              ? pocs.firstWhere((poc) => poc.isPrimary)
              : (pocs.isNotEmpty ? pocs.first : null)),
      interactions: interactionsJson is List
          ? interactionsJson
              .whereType<Map>()
              .map((item) =>
                  SupportInteraction.fromJson(Map<String, dynamic>.from(item)))
              .toList()
          : const [],
      summary: summaryJson is Map
          ? SupportHistorySummary.fromJson(
              Map<String, dynamic>.from(summaryJson))
          : const SupportHistorySummary(),
      scheduledFollowups: scheduledJson is List
          ? scheduledJson
              .whereType<Map>()
              .map((item) => SupportScheduledFollowup.fromJson(
                  Map<String, dynamic>.from(item)))
              .toList()
          : const [],
      purchaseDetails: purchaseJson is Map
          ? SupportPurchaseDetails.fromJson(
              Map<String, dynamic>.from(purchaseJson))
          : null,
    );
  }
}

class SupportEmployee {
  final int employeeId;
  final String employeeName;
  final String? role;
  final String? department;
  final String? employmentStatus;
  final String presenceStatus;
  final bool online;
  final bool onApprovedLeave;
  final bool available;
  final SupportLeave? leave;
  final int assignedCustomerCount;
  final int temporaryCoverageCount;

  const SupportEmployee({
    required this.employeeId,
    required this.employeeName,
    this.role,
    this.department,
    this.employmentStatus,
    this.presenceStatus = 'OFFLINE',
    this.online = false,
    this.onApprovedLeave = false,
    this.available = false,
    this.leave,
    this.assignedCustomerCount = 0,
    this.temporaryCoverageCount = 0,
  });

  factory SupportEmployee.fromJson(Map<String, dynamic> json) {
    final leaveJson = json['leave'];
    return SupportEmployee(
      employeeId: _asInt(json['employee_id']),
      employeeName: _asString(json['employee_name'], 'Support Employee'),
      role: _asNullableString(json['role']),
      department: _asNullableString(json['department']),
      employmentStatus: _asNullableString(json['employment_status']),
      presenceStatus: _asString(json['presence_status'], 'OFFLINE'),
      online: _asBool(json['online']),
      onApprovedLeave: _asBool(json['on_approved_leave']),
      available: _asBool(json['available']),
      leave: leaveJson is Map
          ? SupportLeave.fromJson(Map<String, dynamic>.from(leaveJson))
          : null,
      assignedCustomerCount: _asInt(json['assigned_customer_count']),
      temporaryCoverageCount: _asInt(json['temporary_coverage_count']),
    );
  }

  String get availabilityLabel {
    if (onApprovedLeave) return 'On leave';
    if (online) return 'Online';
    if (available) return 'Available';
    return 'Offline';
  }
}

class SupportLeave {
  final int id;
  final int employeeId;
  final String? employeeName;
  final String leaveType;
  final String? startDate;
  final String? endDate;
  final String status;
  final String? reason;

  const SupportLeave({
    required this.id,
    required this.employeeId,
    this.employeeName,
    required this.leaveType,
    this.startDate,
    this.endDate,
    required this.status,
    this.reason,
  });

  factory SupportLeave.fromJson(Map<String, dynamic> json) {
    return SupportLeave(
      id: _asInt(json['id']),
      employeeId: _asInt(json['employee_id']),
      employeeName: _asNullableString(json['employee_name']),
      leaveType: _asString(json['leave_type'], 'LEAVE'),
      startDate: _asNullableString(json['start_date']),
      endDate: _asNullableString(json['end_date']),
      status: _asString(json['status'], 'PENDING'),
      reason: _asNullableString(json['reason']),
    );
  }
}

class SupportPendingIssue {
  final int interactionId;
  final int? leadId;
  final int? customerId;
  final String? customerName;
  final String? pendingIssues;
  final int? handlingEmployeeId;
  final String? handlingEmployeeName;
  final String? interactionAt;

  const SupportPendingIssue({
    required this.interactionId,
    this.leadId,
    this.customerId,
    this.customerName,
    this.pendingIssues,
    this.handlingEmployeeId,
    this.handlingEmployeeName,
    this.interactionAt,
  });

  factory SupportPendingIssue.fromJson(Map<String, dynamic> json) {
    return SupportPendingIssue(
      interactionId: _asInt(json['interaction_id']),
      leadId: _asNullableInt(json['lead_id']),
      customerId: _asNullableInt(json['customer_id']),
      customerName: _asNullableString(json['customer_name']),
      pendingIssues: _asNullableString(json['pending_issues']),
      handlingEmployeeId: _asNullableInt(json['handling_employee_id']),
      handlingEmployeeName: _asNullableString(json['handling_employee_name']),
      interactionAt: _asNullableString(json['interaction_at']),
    );
  }
}

class SupportFollowupMonitorItem {
  final int interactionId;
  final int? leadId;
  final int? customerId;
  final String? customerName;
  final String? followUpAt;
  final String? nextAction;
  final String? handlingEmployeeName;

  const SupportFollowupMonitorItem({
    required this.interactionId,
    this.leadId,
    this.customerId,
    this.customerName,
    this.followUpAt,
    this.nextAction,
    this.handlingEmployeeName,
  });

  factory SupportFollowupMonitorItem.fromJson(Map<String, dynamic> json) {
    return SupportFollowupMonitorItem(
      interactionId: _asInt(json['interaction_id']),
      leadId: _asNullableInt(json['lead_id']),
      customerId: _asNullableInt(json['customer_id']),
      customerName: _asNullableString(json['customer_name']),
      followUpAt: _asNullableString(json['follow_up_at']),
      nextAction: _asNullableString(json['next_action']),
      handlingEmployeeName: _asNullableString(json['handling_employee_name']),
    );
  }
}

class SupportManagerOverview {
  final List<SupportEmployee> employees;
  final List<SupportLeave> approvedLeaves;
  final List<SupportCoverage> activeCoverage;
  final List<SupportCoverage> handoverHistory;
  final List<SupportPendingIssue> pendingIssues;
  final List<SupportFollowupMonitorItem> overdueFollowUps;
  final List<SupportFollowupMonitorItem> upcomingFollowUps;

  const SupportManagerOverview({
    this.employees = const [],
    this.approvedLeaves = const [],
    this.activeCoverage = const [],
    this.handoverHistory = const [],
    this.pendingIssues = const [],
    this.overdueFollowUps = const [],
    this.upcomingFollowUps = const [],
  });

  factory SupportManagerOverview.fromJson(Map<String, dynamic> json) {
    List<T> parseList<T>(dynamic raw, T Function(Map<String, dynamic>) parser) {
      if (raw is! List) return <T>[];
      return raw
          .whereType<Map>()
          .map((item) => parser(Map<String, dynamic>.from(item)))
          .toList();
    }

    return SupportManagerOverview(
      employees: parseList(json['employees'], SupportEmployee.fromJson),
      approvedLeaves: parseList(json['approved_leaves'], SupportLeave.fromJson),
      activeCoverage:
          parseList(json['active_coverage'], SupportCoverage.fromJson),
      handoverHistory:
          parseList(json['handover_history'], SupportCoverage.fromJson),
      pendingIssues:
          parseList(json['pending_issues'], SupportPendingIssue.fromJson),
      overdueFollowUps: parseList(
          json['overdue_follow_ups'], SupportFollowupMonitorItem.fromJson),
      upcomingFollowUps: parseList(
          json['upcoming_follow_ups'], SupportFollowupMonitorItem.fromJson),
    );
  }

  int get availableCount =>
      employees.where((employee) => employee.available).length;
  int get leaveCount =>
      employees.where((employee) => employee.onApprovedLeave).length;
}

/// One Support ownership row. Active rows are the current owner; ended rows
/// form the permanent reassignment history.
class SupportAssignmentRecord {
  final int? id;
  final int leadId;
  final int? customerId;
  final int? supportHandoffId;
  final int employeeId;
  final String? employeeName;
  final int? previousEmployeeId;
  final String? previousEmployeeName;
  final int? assignedByEmployeeId;
  final String? assignedByEmployeeName;
  final int? assignedByUserId;
  final String? assignedByUsername;
  final String? reason;
  final String source;
  final String status;
  final String? assignedAt;
  final String? endedAt;
  final String? endReason;
  final bool synthetic;

  const SupportAssignmentRecord({
    this.id,
    required this.leadId,
    this.customerId,
    this.supportHandoffId,
    required this.employeeId,
    this.employeeName,
    this.previousEmployeeId,
    this.previousEmployeeName,
    this.assignedByEmployeeId,
    this.assignedByEmployeeName,
    this.assignedByUserId,
    this.assignedByUsername,
    this.reason,
    this.source = 'MANUAL_ASSIGN',
    this.status = 'ACTIVE',
    this.assignedAt,
    this.endedAt,
    this.endReason,
    this.synthetic = false,
  });

  factory SupportAssignmentRecord.fromJson(Map<String, dynamic> json) {
    return SupportAssignmentRecord(
      id: _asNullableInt(json['id']),
      leadId: _asInt(json['lead_id']),
      customerId: _asNullableInt(json['customer_id']),
      supportHandoffId: _asNullableInt(json['support_handoff_id']),
      employeeId: _asInt(json['employee_id']),
      employeeName: _asNullableString(json['employee_name']),
      previousEmployeeId: _asNullableInt(json['previous_employee_id']),
      previousEmployeeName:
          _asNullableString(json['previous_employee_name']),
      assignedByEmployeeId:
          _asNullableInt(json['assigned_by_employee_id']),
      assignedByEmployeeName:
          _asNullableString(json['assigned_by_employee_name']),
      assignedByUserId: _asNullableInt(json['assigned_by_user_id']),
      assignedByUsername: _asNullableString(json['assigned_by_username']),
      reason: _asNullableString(json['reason']),
      source: _asString(json['source'], 'MANUAL_ASSIGN'),
      status: _asString(json['status'], 'ACTIVE'),
      assignedAt: _asNullableString(json['assigned_at']),
      endedAt: _asNullableString(json['ended_at']),
      endReason: _asNullableString(json['end_reason']),
      synthetic: _asBool(json['synthetic']),
    );
  }

  bool get isActive => status.toUpperCase() == 'ACTIVE';

  String get assignedByName =>
      assignedByEmployeeName ?? assignedByUsername ?? 'System';
}

/// Current Support owner plus the complete reassignment history.
class SupportAssignmentState {
  final int leadId;
  final int? customerId;
  final int? supportHandoffId;
  final String? salesStatus;
  final int? supportEmployeeId;
  final String? supportEmployeeName;
  final int? supportManagerId;
  final String? supportManagerName;
  final SupportAssignmentRecord? current;
  final List<SupportAssignmentRecord> history;
  final int historyCount;
  final bool reasonRequired;
  final bool canReassign;
  final String? reassignBlockedReason;
  final bool isConvertedToSupport;
  final bool assignmentEnabled;

  const SupportAssignmentState({
    required this.leadId,
    this.customerId,
    this.supportHandoffId,
    this.salesStatus,
    this.supportEmployeeId,
    this.supportEmployeeName,
    this.supportManagerId,
    this.supportManagerName,
    this.current,
    this.history = const [],
    this.historyCount = 0,
    this.reasonRequired = false,
    this.canReassign = false,
    this.reassignBlockedReason,
    this.isConvertedToSupport = false,
    this.assignmentEnabled = false,
  });

  factory SupportAssignmentState.fromJson(Map<String, dynamic> json) {
    final currentJson = json['current'];
    final historyJson = json['history'];
    final history = historyJson is List
        ? historyJson
            .whereType<Map>()
            .map((item) => SupportAssignmentRecord.fromJson(
                  Map<String, dynamic>.from(item),
                ))
            .toList()
        : <SupportAssignmentRecord>[];
    return SupportAssignmentState(
      leadId: _asInt(json['lead_id']),
      customerId: _asNullableInt(json['customer_id']),
      supportHandoffId: _asNullableInt(json['support_handoff_id']),
      salesStatus: _asNullableString(json['sales_status']),
      supportEmployeeId: _asNullableInt(json['support_employee_id']),
      supportEmployeeName: _asNullableString(json['support_employee_name']),
      supportManagerId: _asNullableInt(json['support_manager_id']),
      supportManagerName: _asNullableString(json['support_manager_name']),
      current: currentJson is Map
          ? SupportAssignmentRecord.fromJson(
              Map<String, dynamic>.from(currentJson),
            )
          : null,
      history: history,
      historyCount: _asInt(json['history_count'], history.length),
      reasonRequired: _asBool(json['reason_required']),
      canReassign: _asBool(json['can_reassign']),
      reassignBlockedReason:
          _asNullableString(json['reassign_blocked_reason']),
      isConvertedToSupport: _asBool(json['is_converted_to_support']),
      assignmentEnabled: _asBool(
        json['assignment_enabled'],
        _asBool(json['is_converted_to_support']),
      ),
    );
  }
}

/// Assignable Support Executive returned by /leads/support/team-members.
class SupportAssignTeamMember {
  final int id;
  final String name;
  final String? role;
  final String? department;
  final int? managerId;
  final String? managerName;

  const SupportAssignTeamMember({
    required this.id,
    required this.name,
    this.role,
    this.department,
    this.managerId,
    this.managerName,
  });

  factory SupportAssignTeamMember.fromJson(Map<String, dynamic> json) {
    return SupportAssignTeamMember(
      id: _asInt(json['id']),
      name: _asString(json['name'], 'Support Employee'),
      role: _asNullableString(json['role']),
      department: _asNullableString(json['department']),
      managerId: _asNullableInt(json['manager_id']),
      managerName: _asNullableString(json['manager_name']),
    );
  }
}
