import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Retry timing shared by the foreground and WorkManager upload passes.
///
/// The OEM dialer may need several minutes to finish writing and indexing a
/// recording. Discovery is retried with exponential backoff for up to
/// [discoveryWindow]; upload failures are retried for [maxUploadAttempts]
/// attempts before the task is surfaced as `UPLOAD_FAILED`.
class RecordingRetryPolicy {
  static const Duration discoveryWindow = Duration(hours: 24);
  static const int maxDiscoveryAttempts = 10;
  static const int maxUploadAttempts = 8;

  static Duration backoffFor(int attempts) {
    switch (attempts) {
      case 0:
      case 1:
        return const Duration(minutes: 1);
      case 2:
        return const Duration(minutes: 5);
      case 3:
        return const Duration(minutes: 15);
      case 4:
        return const Duration(minutes: 30);
      case 5:
        return const Duration(hours: 1);
      case 6:
        return const Duration(hours: 2);
      case 7:
        return const Duration(hours: 4);
      default:
        return const Duration(hours: 8);
    }
  }
}

/// One recording that still has to be discovered, uploaded and confirmed by the
/// backend.
///
/// [key] is the CRM call-log id, so the same call can never be queued twice.
/// The stable identifiers needed for a safe retry are kept with the task:
/// native call reference, employee scope, phone, direction, start/end time,
/// duration and SIM identity. Phone number alone is never used as identity.
class PendingRecordingUpload {
  final String key;
  final int? callId;
  final String employeeKey;
  final String nativeReference;
  final String phone;
  final String direction;
  final String? startedAt;
  final String? endedAt;
  final int durationSeconds;
  final String? simAccountId;
  final int? simSubscriptionId;
  final String source;

  final String? filePath;
  final String? fileName;
  final int fileSize;
  final String? mimeType;
  final String? checksum;
  final int recordingDurationSeconds;

  final DateTime queuedAt;
  final DateTime? discoveredAt;
  final DateTime? lastAttemptAt;
  final DateTime? nextAttemptAt;
  final int attempts;
  final String? lastError;
  final String? lastStatus;
  final String? lastStatusDetail;
  final bool retryable;

  const PendingRecordingUpload({
    required this.key,
    required this.callId,
    required this.employeeKey,
    required this.nativeReference,
    required this.phone,
    required this.direction,
    required this.startedAt,
    required this.endedAt,
    required this.durationSeconds,
    required this.simAccountId,
    required this.simSubscriptionId,
    required this.source,
    this.filePath,
    this.fileName,
    this.fileSize = 0,
    this.mimeType,
    this.checksum,
    this.recordingDurationSeconds = 0,
    required this.queuedAt,
    this.discoveredAt,
    this.lastAttemptAt,
    this.nextAttemptAt,
    this.attempts = 0,
    this.lastError,
    this.lastStatus,
    this.lastStatusDetail,
    this.retryable = true,
  });

  bool get hasFile =>
      (filePath ?? '').trim().isNotEmpty && recordingDurationSeconds > 0;

  DateTime? get startedDateTime =>
      startedAt == null ? null : DateTime.tryParse(startedAt!)?.toUtc();

  DateTime? get endedDateTime =>
      endedAt == null ? null : DateTime.tryParse(endedAt!)?.toUtc();

  PendingRecordingUpload copyWith({
    String? filePath,
    String? fileName,
    int? fileSize,
    String? mimeType,
    String? checksum,
    int? recordingDurationSeconds,
    DateTime? discoveredAt,
    DateTime? lastAttemptAt,
    DateTime? nextAttemptAt,
    bool clearNextAttemptAt = false,
    int? attempts,
    String? lastError,
    String? lastStatus,
    String? lastStatusDetail,
    bool? retryable,
  }) {
    return PendingRecordingUpload(
      key: key,
      callId: callId,
      employeeKey: employeeKey,
      nativeReference: nativeReference,
      phone: phone,
      direction: direction,
      startedAt: startedAt,
      endedAt: endedAt,
      durationSeconds: durationSeconds,
      simAccountId: simAccountId,
      simSubscriptionId: simSubscriptionId,
      source: source,
      filePath: filePath ?? this.filePath,
      fileName: fileName ?? this.fileName,
      fileSize: fileSize ?? this.fileSize,
      mimeType: mimeType ?? this.mimeType,
      checksum: checksum ?? this.checksum,
      recordingDurationSeconds:
          recordingDurationSeconds ?? this.recordingDurationSeconds,
      queuedAt: queuedAt,
      discoveredAt: discoveredAt ?? this.discoveredAt,
      lastAttemptAt: lastAttemptAt ?? this.lastAttemptAt,
      nextAttemptAt: clearNextAttemptAt
          ? null
          : (nextAttemptAt ?? this.nextAttemptAt),
      attempts: attempts ?? this.attempts,
      lastError: lastError ?? this.lastError,
      lastStatus: lastStatus ?? this.lastStatus,
      lastStatusDetail: lastStatusDetail ?? this.lastStatusDetail,
      retryable: retryable ?? this.retryable,
    );
  }

  factory PendingRecordingUpload.fromJson(Map<String, dynamic> json) {
    return PendingRecordingUpload(
      key: (json['key'] ?? '').toString().trim(),
      callId: _int(json['callId']),
      employeeKey: (json['employeeKey'] ?? '').toString().trim(),
      nativeReference: (json['nativeReference'] ?? '').toString().trim(),
      phone: (json['phone'] ?? '').toString().trim(),
      direction: (json['direction'] ?? '').toString().trim().toUpperCase(),
      startedAt: _text(json['startedAt']),
      endedAt: _text(json['endedAt']),
      durationSeconds: _int(json['durationSeconds']) ?? 0,
      simAccountId: _text(json['simAccountId']),
      simSubscriptionId: _int(json['simSubscriptionId']),
      source: (json['source'] ?? 'AUTO').toString(),
      filePath: _text(json['filePath']),
      fileName: _text(json['fileName']),
      fileSize: _int(json['fileSize']) ?? 0,
      mimeType: _text(json['mimeType']),
      checksum: _text(json['checksum']),
      recordingDurationSeconds: _int(json['recordingDurationSeconds']) ?? 0,
      queuedAt:
          DateTime.tryParse((json['queuedAt'] ?? '').toString())?.toUtc() ??
          DateTime.now().toUtc(),
      discoveredAt: DateTime.tryParse((json['discoveredAt'] ?? '').toString())
          ?.toUtc(),
      lastAttemptAt: DateTime.tryParse((json['lastAttemptAt'] ?? '').toString())
          ?.toUtc(),
      nextAttemptAt: DateTime.tryParse((json['nextAttemptAt'] ?? '').toString())
          ?.toUtc(),
      attempts: _int(json['attempts']) ?? 0,
      lastError: _text(json['lastError']),
      lastStatus: _text(json['lastStatus']),
      lastStatusDetail: _text(json['lastStatusDetail']),
      retryable: json['retryable'] != false,
    );
  }

  Map<String, dynamic> toJson() => {
    'key': key,
    'callId': callId,
    'employeeKey': employeeKey,
    'nativeReference': nativeReference,
    'phone': phone,
    'direction': direction,
    'startedAt': startedAt,
    'endedAt': endedAt,
    'durationSeconds': durationSeconds,
    'simAccountId': simAccountId,
    'simSubscriptionId': simSubscriptionId,
    'source': source,
    'filePath': filePath,
    'fileName': fileName,
    'fileSize': fileSize,
    'mimeType': mimeType,
    'checksum': checksum,
    'recordingDurationSeconds': recordingDurationSeconds,
    'queuedAt': queuedAt.toIso8601String(),
    'discoveredAt': discoveredAt?.toIso8601String(),
    'lastAttemptAt': lastAttemptAt?.toIso8601String(),
    'nextAttemptAt': nextAttemptAt?.toIso8601String(),
    'attempts': attempts,
    'lastError': lastError,
    'lastStatus': lastStatus,
    'lastStatusDetail': lastStatusDetail,
    'retryable': retryable,
  };
}

/// Persistent, per-employee queue of recordings awaiting backend confirmation.
///
/// One SharedPreferences key is used per call id so the UI isolate and the
/// headless WorkManager engine cannot overwrite each other's queue state.
class PendingRecordingUploadQueue {
  static const String _prefixBase = 'wacrm_pending_recording_upload_v1';

  final String _scope;
  final List<PendingRecordingUpload> _entries = <PendingRecordingUpload>[];
  bool _loaded = false;

  PendingRecordingUploadQueue(String employeeKey)
    : _scope = employeeKey.trim().isEmpty ? 'default' : employeeKey.trim();

  String get _prefix => '${_prefixBase}_${_scope}_';

  List<PendingRecordingUpload> get entries {
    final copy = List<PendingRecordingUpload>.of(_entries);
    copy.sort((a, b) {
      final aDate = a.startedDateTime ?? a.queuedAt;
      final bDate = b.startedDateTime ?? b.queuedAt;
      return aDate.compareTo(bDate);
    });
    return List<PendingRecordingUpload>.unmodifiable(copy);
  }

  int get count => _entries.length;
  int get retryableCount => _entries.where((entry) => entry.retryable).length;

  bool containsCall(int callId) =>
      _entries.any((entry) => entry.callId == callId);

  Future<void> reload() async {
    _entries.clear();
    try {
      final prefs = await SharedPreferences.getInstance();
      for (final key in prefs.getKeys()) {
        if (!key.startsWith(_prefix)) continue;
        final raw = prefs.getString(key);
        if (raw == null || raw.isEmpty) continue;
        try {
          final decoded = jsonDecode(raw);
          if (decoded is! Map) continue;
          final entry = PendingRecordingUpload.fromJson(
            Map<String, dynamic>.from(decoded),
          );
          if (entry.key.isEmpty || entry.callId == null) continue;
          _entries.add(entry);
        } catch (_) {
          // A single corrupted task must not stop the remaining queue.
        }
      }
    } catch (_) {
      // A storage failure must not break call scanning.
    }
    _loaded = true;
  }

  Future<PendingRecordingUpload?> enqueueForCall({
    required int callId,
    required String employeeKey,
    required String phone,
    required DateTime startedAt,
    DateTime? endedAt,
    required int durationSeconds,
    String? direction,
    String? nativeReference,
    String? simAccountId,
    int? simSubscriptionId,
    String source = 'AUTO',
  }) async {
    if (callId <= 0) return null;
    if (!_loaded) await reload();
    final key = '$callId';
    for (final existing in _entries) {
      if (existing.key == key) return existing;
    }
    final entry = PendingRecordingUpload(
      key: key,
      callId: callId,
      employeeKey: _scope,
      nativeReference: (nativeReference ?? '').trim(),
      phone: phone.trim(),
      direction: (direction ?? '').trim().toUpperCase(),
      startedAt: startedAt.toUtc().toIso8601String(),
      endedAt: endedAt?.toUtc().toIso8601String(),
      durationSeconds: durationSeconds,
      simAccountId: (simAccountId ?? '').trim().isEmpty
          ? null
          : simAccountId!.trim(),
      simSubscriptionId: simSubscriptionId,
      source: source,
      queuedAt: DateTime.now().toUtc(),
    );
    await _persist(entry);
    _entries.add(entry);
    return entry;
  }

  Future<PendingRecordingUpload> withRecording(
    PendingRecordingUpload entry, {
    required String path,
    required String name,
    required int size,
    required String mimeType,
    required String checksum,
    required int recordingDurationSeconds,
  }) async {
    final updated = entry
        .copyWith(
          filePath: path,
          fileName: name,
          fileSize: size,
          mimeType: mimeType,
          checksum: checksum,
          recordingDurationSeconds: recordingDurationSeconds,
          discoveredAt: DateTime.now().toUtc(),
          lastError: '',
          lastStatus: 'PENDING_SYNC',
          lastStatusDetail:
              'Recording found on the device and awaiting upload.',
          retryable: true,
        )
        .copyWith(clearNextAttemptAt: true);
    await _persist(updated);
    _replace(updated);
    return updated;
  }

  /// Drops the cached copy reference when the app-owned file disappeared. The
  /// task stays queued so the next pass can discover the recording again from
  /// Android MediaStore.
  Future<PendingRecordingUpload> clearRecording(
    PendingRecordingUpload entry,
  ) async {
    final updated = PendingRecordingUpload(
      key: entry.key,
      callId: entry.callId,
      employeeKey: entry.employeeKey,
      nativeReference: entry.nativeReference,
      phone: entry.phone,
      direction: entry.direction,
      startedAt: entry.startedAt,
      endedAt: entry.endedAt,
      durationSeconds: entry.durationSeconds,
      simAccountId: entry.simAccountId,
      simSubscriptionId: entry.simSubscriptionId,
      source: entry.source,
      queuedAt: entry.queuedAt,
      discoveredAt: entry.discoveredAt,
      lastAttemptAt: entry.lastAttemptAt,
      nextAttemptAt: entry.nextAttemptAt,
      attempts: entry.attempts,
      lastError: entry.lastError,
      lastStatus: entry.lastStatus,
      lastStatusDetail: entry.lastStatusDetail,
      retryable: entry.retryable,
    );
    await _persist(updated);
    _replace(updated);
    return updated;
  }

  Future<void> markFailure(
    PendingRecordingUpload entry,
    Object error, {
    required bool retryable,
    String? status,
    String? detail,
    DateTime? nextAttemptAt,
  }) async {
    final updated = PendingRecordingUpload(
      key: entry.key,
      callId: entry.callId,
      employeeKey: entry.employeeKey,
      nativeReference: entry.nativeReference,
      phone: entry.phone,
      direction: entry.direction,
      startedAt: entry.startedAt,
      endedAt: entry.endedAt,
      durationSeconds: entry.durationSeconds,
      simAccountId: entry.simAccountId,
      simSubscriptionId: entry.simSubscriptionId,
      source: entry.source,
      filePath: entry.filePath,
      fileName: entry.fileName,
      fileSize: entry.fileSize,
      mimeType: entry.mimeType,
      checksum: entry.checksum,
      recordingDurationSeconds: entry.recordingDurationSeconds,
      queuedAt: entry.queuedAt,
      discoveredAt: entry.discoveredAt,
      lastAttemptAt: DateTime.now().toUtc(),
      nextAttemptAt: nextAttemptAt,
      attempts: entry.attempts + 1,
      lastError: error.toString(),
      lastStatus: status ?? entry.lastStatus,
      lastStatusDetail: detail ?? entry.lastStatusDetail,
      retryable: retryable,
    );
    await _persist(updated);
    _replace(updated);
  }

  Future<void> markAttempt(PendingRecordingUpload entry) async {
    final updated = entry.copyWith(
      attempts: entry.attempts + 1,
      lastAttemptAt: DateTime.now().toUtc(),
    );
    await _persist(updated);
    _replace(updated);
  }

  Future<void> remove(PendingRecordingUpload entry) => removeByKey(entry.key);

  Future<void> removeByKey(String key) async {
    final cleaned = key.trim();
    if (cleaned.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('$_prefix$cleaned');
    } catch (_) {
      // Best effort: the backend checksum still prevents duplicate uploads.
    }
    _entries.removeWhere((entry) => entry.key == cleaned);
  }

  /// Tasks the current pass should attempt. A retryable task whose backoff has
  /// not elapsed is left for the periodic WorkManager pass instead of burning
  /// a discovery attempt on every app resume.
  List<PendingRecordingUpload> dueEntries({
    bool forceRetry = false,
    DateTime? now,
  }) {
    final current = (now ?? DateTime.now()).toUtc();
    return entries
        .where((entry) {
          if (!entry.retryable && !forceRetry) return false;
          if (forceRetry) return true;
          final next = entry.nextAttemptAt;
          return next == null || !next.isAfter(current);
        })
        .toList(growable: false);
  }

  Future<void> _persist(PendingRecordingUpload entry) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('$_prefix${entry.key}', jsonEncode(entry.toJson()));
    } catch (_) {
      // Keep the in-memory copy so the current pass can still report status.
    }
  }

  void _replace(PendingRecordingUpload updated) {
    final index = _entries.indexWhere((entry) => entry.key == updated.key);
    if (index >= 0) {
      _entries[index] = updated;
    } else {
      _entries.add(updated);
    }
  }

  /// Number of recordings waiting for backend confirmation for this employee.
  static Future<int> pendingCount(String employeeKey) async {
    final queue = PendingRecordingUploadQueue(employeeKey);
    await queue.reload();
    return queue.count;
  }

  static Future<int> retryablePendingCount(String employeeKey) async {
    final queue = PendingRecordingUploadQueue(employeeKey);
    await queue.reload();
    return queue.retryableCount;
  }
}

int? _int(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  return int.tryParse(value.toString());
}

String? _text(dynamic value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}
