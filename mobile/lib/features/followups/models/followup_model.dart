class FollowupModel {
  final int id;
  final int leadId;
  final String leadName;
  final String leadPhone;
  final int? assignedTo;
  final String? assignedToName;
  final String followupDate;
  final String followupTime;
  final String priority;
  final String status; // Pending, Completed, Cancelled
  final String? notes;
  final String? createdAt;

  FollowupModel({
    required this.id,
    required this.leadId,
    required this.leadName,
    required this.leadPhone,
    this.assignedTo,
    this.assignedToName,
    required this.followupDate,
    required this.followupTime,
    required this.priority,
    required this.status,
    this.notes,
    this.createdAt,
  });

  factory FollowupModel.fromJson(Map<String, dynamic> json) {
    return FollowupModel(
      id: json['id'] ?? 0,
      leadId: json['lead_id'] ?? 0,
      leadName: json['lead_name'] ?? (json['lead'] != null ? json['lead']['name'] : 'Lead'),
      leadPhone: json['lead_phone'] ?? (json['lead'] != null ? json['lead']['phone'] : ''),
      assignedTo: json['assigned_to'],
      assignedToName: json['assigned_to_name'],
      followupDate: json['followup_date'] ?? '',
      followupTime: json['followup_time'] ?? '10:00 AM',
      priority: json['priority'] ?? 'MEDIUM',
      status: json['status'] ?? 'Pending',
      notes: json['notes'],
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'lead_id': leadId,
      'followup_date': followupDate,
      'followup_time': followupTime,
      'priority': priority,
      'status': status,
      if (notes != null) 'notes': notes,
    };
  }
}

class FollowupReminderModel {
  final int id;
  final int leadId;
  final String leadName;
  final String leadPhone;
  final String followupDate;
  final String followupTime;
  final String priority;
  final String? notes;
  final bool isOverdue;

  FollowupReminderModel({
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

  factory FollowupReminderModel.fromJson(Map<String, dynamic> json) {
    return FollowupReminderModel(
      id: json['id'] ?? 0,
      leadId: json['lead_id'] ?? 0,
      leadName: json['lead_name'] ?? 'Lead',
      leadPhone: json['lead_phone'] ?? '',
      followupDate: json['followup_date'] ?? '',
      followupTime: json['followup_time'] ?? '',
      priority: json['priority'] ?? 'MEDIUM',
      notes: json['notes'],
      isOverdue: json['is_overdue'] ?? false,
    );
  }
}
