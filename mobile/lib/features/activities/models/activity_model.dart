class ActivityModel {
  final int id;
  final int? leadId;
  final String? leadName;
  final int? employeeId;
  final String? employeeName;
  final String activityType;
  final String description;
  final String? createdAt;

  ActivityModel({
    required this.id,
    this.leadId,
    this.leadName,
    this.employeeId,
    this.employeeName,
    required this.activityType,
    required this.description,
    this.createdAt,
  });

  factory ActivityModel.fromJson(Map<String, dynamic> json) {
    return ActivityModel(
      id: json['id'] ?? 0,
      leadId: json['lead_id'],
      leadName: json['lead_name'],
      employeeId: json['employee_id'],
      employeeName: json['employee_name'],
      activityType: json['activity_type'] ?? 'NOTE',
      description: json['description'] ?? '',
      createdAt: json['created_at'],
    );
  }
}
