class CallLogModel {
  final int id;
  final int? leadId;
  final String? leadName;
  final String customerNumber;
  final String callType; // INBOUND, OUTBOUND, MANUAL
  final String callStatus; // ANSWERED, MISSED, BUSY, FAILED, COMPLETED
  final int durationSeconds;
  final String? recordingUrl;
  final String? notes;
  final String? employeeName;
  final String? createdAt;

  CallLogModel({
    required this.id,
    this.leadId,
    this.leadName,
    required this.customerNumber,
    required this.callType,
    required this.callStatus,
    required this.durationSeconds,
    this.recordingUrl,
    this.notes,
    this.employeeName,
    this.createdAt,
  });

  factory CallLogModel.fromJson(Map<String, dynamic> json) {
    return CallLogModel(
      id: json['id'] ?? 0,
      leadId: json['lead_id'],
      leadName: json['lead_name'] ?? json['customer_name'],
      customerNumber: json['customer_number'] ?? json['phone'] ?? '',
      callType: json['call_type'] ?? 'OUTBOUND',
      callStatus: (json['call_status'] ?? json['status'] ?? 'COMPLETED').toString().toUpperCase(),
      durationSeconds: json['duration_seconds'] ?? json['duration'] ?? 0,
      recordingUrl: json['recording_url'],
      notes: json['notes'],
      employeeName: json['employee_name'],
      createdAt: json['created_at'],
    );
  }

  String get formattedDuration {
    final m = durationSeconds ~/ 60;
    final s = durationSeconds % 60;
    if (m > 0) {
      return '${m}m ${s}s';
    }
    return '${s}s';
  }
}
