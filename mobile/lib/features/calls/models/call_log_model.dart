import '../../../core/services/mobile_call_recording_manager.dart';

class CallLogModel {
  final int id;
  final int? leadId;
  final String? leadName;
  final String customerNumber;
  final String callType; // INBOUND, OUTBOUND, MANUAL
  final String callStatus; // ANSWERED, MISSED, BUSY, FAILED, COMPLETED
  final int durationSeconds;
  final String? recordingUrl;
  final String? recordingId;
  final int? recordingDurationSeconds;
  final String? recordingStatus;
  final String? notes;
  final String? employeeName;
  final String? provider;
  final String? callSource;
  final String? nativeCallReference;
  final String? simLabel;
  final String? createdAt;
  final String? startedAt;
  final String? endedAt;

  CallLogModel({
    required this.id,
    this.leadId,
    this.leadName,
    required this.customerNumber,
    required this.callType,
    required this.callStatus,
    required this.durationSeconds,
    this.recordingUrl,
    this.recordingId,
    this.recordingDurationSeconds,
    this.recordingStatus,
    this.notes,
    this.employeeName,
    this.provider,
    this.callSource,
    this.nativeCallReference,
    this.simLabel,
    this.createdAt,
    this.startedAt,
    this.endedAt,
  });

  bool get isMobileSim => (provider ?? '').toUpperCase().contains('MOBILE_SIM');

  /// Display-level source. The backend sends `call_source`; older responses
  /// fall back to the provider so a SIM call can never appear as DooCTI.
  String get source {
    final explicit = (callSource ?? '').trim().toUpperCase();
    if (explicit == 'MOBILE' || explicit == 'DOOCTI') return explicit;
    return isMobileSim || (provider ?? '').toUpperCase().contains('DIRECT_DIAL')
        ? 'MOBILE'
        : 'DOOCTI';
  }

  bool get isMobile => source == 'MOBILE';
  bool get isDoocti => source == 'DOOCTI';

  /// Canonical recording lifecycle, including legacy backend values.
  RecordingSyncStatus get recordingSyncStatus {
    if (hasRecording) return RecordingSyncStatus.available;
    return RecordingSyncStatus.fromApi(recordingStatus);
  }

  String get recordingStatusLabel => recordingSyncStatus.label;

  bool get isRecordingAvailable =>
      recordingSyncStatus == RecordingSyncStatus.available;

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
      // Backend always supplies call_direction. If an older response omits it,
      // fall back to INBOUND (matching the API response default) rather than
      // labelling a call OUTBOUND without evidence.
      callType: (json['call_direction'] ?? json['call_type'] ?? 'INBOUND')
          .toString()
          .toUpperCase(),
      callStatus: (json['call_status'] ?? json['status'] ?? 'COMPLETED')
          .toString()
          .toUpperCase(),
      durationSeconds: json['duration_seconds'] ?? json['duration'] ?? 0,
      recordingUrl: json['recording_url'],
      recordingId: json['recording_id'],
      recordingDurationSeconds: (json['recording_duration_seconds'] as num?)
          ?.toInt(),
      recordingStatus: json['recording_status'],
      notes: json['notes'],
      employeeName: json['employee_name'],
      provider: json['provider'],
      callSource: json['call_source'],
      nativeCallReference: json['native_call_reference'],
      simLabel: json['sim_label'],
      createdAt: json['created_at'] ?? json['started_at'],
      startedAt: json['started_at'],
      endedAt: json['ended_at'],
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
