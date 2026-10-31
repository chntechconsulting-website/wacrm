class CallLogModel {
  final int id;
  final int? leadId;
  final String? leadName;
  final String customerNumber;
  final String callType; // INBOUND, OUTBOUND, MANUAL
  final String callStatus; // ANSWERED, MISSED, BUSY, FAILED, COMPLETED
  final int durationSeconds;
  final String? recordingUrl;
  final String? recordingStatus;
  final String? notes;
  final String? employeeName;
  final String? provider;
  final String? simLabel;
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
    this.recordingStatus,
    this.notes,
    this.employeeName,
    this.provider,
    this.simLabel,
    this.createdAt,
  });

  bool get isMobileSim => (provider ?? '').toUpperCase().contains('MOBILE_SIM');

  bool get hasRecording =>
      recordingUrl != null && recordingUrl!.trim().isNotEmpty;

  factory CallLogModel.fromJson(Map<String, dynamic> json) {
    return CallLogModel(
      id: json['id'] ?? 0,
      leadId: json['lead_id'],
      leadName: json['lead_name'] ?? json['customer_name'],
      customerNumber:
          json['customer_number'] ??
          json['customer_phone'] ??
          json['phone'] ??
          '',
      callType: (json['call_direction'] ?? json['call_type'] ?? 'OUTBOUND')
          .toString()
          .toUpperCase(),
      callStatus: (json['call_status'] ?? json['status'] ?? 'COMPLETED')
          .toString()
          .toUpperCase(),
      durationSeconds: json['duration_seconds'] ?? json['duration'] ?? 0,
      recordingUrl: json['recording_url'],
      recordingStatus: json['recording_status'],
      notes: json['notes'],
      employeeName: json['employee_name'],
      provider: json['provider'],
      simLabel: json['sim_label'],
      createdAt: json['created_at'] ?? json['started_at'],
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
