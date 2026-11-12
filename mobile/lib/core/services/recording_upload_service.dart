import 'dart:io';

import '../../features/calls/models/call_log_model.dart';
import '../../features/calls/providers/calls_provider.dart';
import 'mobile_call_recording_manager.dart';
import 'pending_recording_upload_queue.dart';

class RecordingQueueResult {
  final int uploaded;
  final int pending;
  final int retryablePending;
  final int failed;
  final String? lastError;

  const RecordingQueueResult({
    this.uploaded = 0,
    this.pending = 0,
    this.retryablePending = 0,
    this.failed = 0,
    this.lastError,
  });

  bool get hasPending => pending > 0;
}

/// Single upload/discovery pipeline used by live call sync, the WorkManager
/// call-log pass, the manual Sync Now button and manual recording import.
///
/// A task is persisted before the network call and is removed only after the
/// backend confirms the upload. Files copied into app storage are kept until
/// that confirmation, so a process death or offline period cannot lose audio.
class RecordingUploadService {
  static bool _running = false;

  /// Enqueues a completed call whose OEM/dialer recording still has to be
  /// discovered or uploaded. Safe to call repeatedly for the same call id.
  static Future<PendingRecordingUpload?> enqueueForCall({
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
    if (callId <= 0 || durationSeconds <= 0) return null;
    final queue = PendingRecordingUploadQueue(employeeKey);
    await queue.reload();
    return queue.enqueueForCall(
      callId: callId,
      employeeKey: employeeKey,
      phone: phone,
      startedAt: startedAt,
      endedAt: endedAt,
      durationSeconds: durationSeconds,
      direction: direction,
      nativeReference: nativeReference,
      simAccountId: simAccountId,
      simSubscriptionId: simSubscriptionId,
      source: source,
    );
  }

  /// Adds recent Mobile SIM calls that are still marked PENDING_SYNC (or whose
  /// upload failed) to the durable queue. This repairs rows that were synced
  /// by an older app version before recording retries existed.
  static Future<int> enqueueFromCalls(
    Iterable<CallLogModel> calls, {
    required String employeeKey,
    DateTime? now,
  }) async {
    final current = (now ?? DateTime.now()).toUtc();
    var queued = 0;
    for (final call in calls) {
      if (!call.isMobile || call.id <= 0 || call.hasRecording) continue;
      if (call.durationSeconds <= 0) continue;
      final status = call.recordingSyncStatus;
      final retryableStatus =
          status == RecordingSyncStatus.pendingSync ||
          status == RecordingSyncStatus.uploadFailed;
      if (!retryableStatus) continue;
      final rawStarted = call.startedAt ?? call.createdAt;
      final started = rawStarted == null
          ? null
          : DateTime.tryParse(rawStarted)?.toUtc();
      if (started == null) continue;
      final maxAge = status == RecordingSyncStatus.uploadFailed
          ? const Duration(days: 7)
          : const Duration(hours: 24);
      if (current.difference(started) > maxAge ||
          current.difference(started) < const Duration(days: -1)) {
        continue;
      }
      final entry = await enqueueForCall(
        callId: call.id,
        employeeKey: employeeKey,
        phone: call.customerNumber,
        startedAt: started,
        endedAt: call.endedAt == null
            ? null
            : DateTime.tryParse(call.endedAt!)?.toUtc(),
        durationSeconds: call.durationSeconds,
        direction: call.callType,
        nativeReference: call.nativeCallReference,
        simAccountId: call.simAccountId,
        simSubscriptionId: call.simSubscriptionId,
        source: 'REPAIR',
      );
      if (entry != null) queued += 1;
    }
    return queued;
  }

  /// Processes due discovery/upload tasks. Both automatic sync and manual
  /// "Sync Now" call this method (manual uses [forceRetry]).
  static Future<RecordingQueueResult> processQueue({
    required String employeeKey,
    CallsProvider? callsProvider,
    bool forceRetry = false,
    int maxEntries = 6,
  }) async {
    if (_running) {
      final pending = await PendingRecordingUploadQueue.pendingCount(
        employeeKey,
      );
      return RecordingQueueResult(
        pending: pending,
        retryablePending:
            await PendingRecordingUploadQueue.retryablePendingCount(
              employeeKey,
            ),
      );
    }
    _running = true;
    final queue = PendingRecordingUploadQueue(employeeKey);
    await queue.reload();
    var uploaded = 0;
    var failed = 0;
    String? lastError;
    try {
      if (queue.count == 0) {
        return const RecordingQueueResult();
      }
      final consented = await RecordingConsentService.hasConsent(employeeKey);
      if (!consented) {
        return RecordingQueueResult(
          pending: queue.count,
          retryablePending: queue.retryableCount,
        );
      }

      final capability = await MobileCallRecordingManager.capability();
      final canReadAudio = capability.audioPermission;
      final due = queue.dueEntries(forceRetry: forceRetry);
      var attempted = 0;
      for (final entry in due) {
        if (attempted >= maxEntries) break;
        attempted += 1;
        final callId = entry.callId;
        final started = entry.startedDateTime;
        if (callId == null || started == null) {
          await queue.remove(entry);
          continue;
        }

        if (!entry.hasFile) {
          if (!canReadAudio) {
            await _handleNoRecording(
              queue,
              entry,
              reason:
                  'Android audio media access is not granted, so the OEM/dialer '
                  'recording cannot be read. Allow Music and audio access for '
                  'WACRM, then refresh.',
            );
            lastError = 'Audio media permission is not granted.';
            continue;
          }
          final match = await MobileCallRecordingManager.findRecordingForCall(
            phone: entry.phone,
            startedAt: started,
            endedAt: entry.endedDateTime,
            durationSeconds: entry.durationSeconds,
          );
          if (match == null) {
            await _handleNoRecording(
              queue,
              entry,
              reason:
                  'No readable OEM/dialer recording was found for this call. '
                  'The phone may not have recorded it, the recording may be in '
                  'a private manufacturer folder, or the file may not be '
                  'indexed by Android yet.',
            );
            lastError = 'No device recording found yet.';
            continue;
          }
          final withFile = await queue.withRecording(
            entry,
            path: match.path,
            name: match.name,
            size: match.size,
            mimeType: match.mimeType,
            checksum: match.checksum,
            recordingDurationSeconds: match.durationSeconds,
          );
          final outcome = await _uploadEntry(queue, withFile);
          if (_isSuccess(outcome)) {
            uploaded += 1;
          } else {
            failed += 1;
            lastError = _failureReason(outcome);
          }
          continue;
        }

        final exists = await _fileExists(entry.filePath!);
        if (!exists) {
          final cleared = await queue.clearRecording(entry);
          await _handleNoRecording(
            queue,
            cleared,
            reason:
                'The app-owned recording copy was removed by Android storage '
                'cleanup. The next pass will look for the original file again.',
          );
          lastError = 'Cached recording copy is missing.';
          continue;
        }

        final outcome = await _uploadEntry(queue, entry);
        if (_isSuccess(outcome)) {
          uploaded += 1;
        } else {
          failed += 1;
          lastError = _failureReason(outcome);
        }
      }

      if (uploaded > 0 && callsProvider != null) {
        await callsProvider.fetchCalls(showLoading: false);
      }
      return RecordingQueueResult(
        uploaded: uploaded,
        pending: queue.count,
        retryablePending: queue.retryableCount,
        failed: failed,
        lastError: lastError,
      );
    } catch (error) {
      return RecordingQueueResult(
        uploaded: uploaded,
        pending: queue.count,
        retryablePending: queue.retryableCount,
        failed: failed,
        lastError: error.toString(),
      );
    } finally {
      _running = false;
    }
  }

  /// Manual import path: persist the chosen file first, then upload it through
  /// the same validation and duplicate-prevention logic as automatic sync.
  static Future<RecordingUploadOutcome> uploadRecordingForCall({
    required int callId,
    required String employeeKey,
    required String phone,
    required DateTime startedAt,
    DateTime? endedAt,
    required int durationSeconds,
    required ImportedCallRecording recording,
    String? direction,
    String? nativeReference,
    String? simAccountId,
    int? simSubscriptionId,
  }) async {
    if (callId <= 0) return RecordingUploadOutcome.uploadFailed;
    final queue = PendingRecordingUploadQueue(employeeKey);
    await queue.reload();
    var entry = await queue.enqueueForCall(
      callId: callId,
      employeeKey: employeeKey,
      phone: phone,
      startedAt: startedAt,
      endedAt: endedAt,
      durationSeconds: durationSeconds,
      direction: direction,
      nativeReference: nativeReference,
      simAccountId: simAccountId,
      simSubscriptionId: simSubscriptionId,
      source: 'MANUAL',
    );
    if (entry == null) return RecordingUploadOutcome.uploadFailed;
    entry = await queue.withRecording(
      entry,
      path: recording.path,
      name: recording.name,
      size: recording.size,
      mimeType: recording.mimeType,
      checksum: recording.checksum,
      recordingDurationSeconds: recording.durationSeconds,
    );
    return _uploadEntry(queue, entry);
  }

  /// Uploads a recording explicitly picked or shared by the employee.
  static Future<RecordingUploadOutcome> uploadPickedRecording({
    required int callId,
    required String employeeKey,
    required ImportedCallRecording recording,
    String? phone,
    DateTime? startedAt,
    DateTime? endedAt,
    int? durationSeconds,
    String? direction,
    String? nativeReference,
    String? simAccountId,
    int? simSubscriptionId,
    bool enforceSimIdentity = true,
  }) async {
    if (callId <= 0) return RecordingUploadOutcome.uploadFailed;
    final queue = PendingRecordingUploadQueue(employeeKey);
    await queue.reload();
    var entry = await queue.enqueueForCall(
      callId: callId,
      employeeKey: employeeKey,
      phone: phone ?? '',
      startedAt: startedAt ?? DateTime.now().toUtc(),
      endedAt: endedAt,
      durationSeconds: durationSeconds ?? recording.durationSeconds,
      direction: direction,
      nativeReference: nativeReference,
      simAccountId: simAccountId,
      simSubscriptionId: simSubscriptionId,
      source: 'MANUAL',
    );
    if (entry == null) return RecordingUploadOutcome.uploadFailed;
    entry = await queue.withRecording(
      entry,
      path: recording.path,
      name: recording.name,
      size: recording.size,
      mimeType: recording.mimeType,
      checksum: recording.checksum,
      recordingDurationSeconds: recording.durationSeconds,
    );
    return _uploadEntry(queue, entry, enforceSimIdentity: enforceSimIdentity);
  }

  static Future<RecordingUploadOutcome> _uploadEntry(
    PendingRecordingUploadQueue queue,
    PendingRecordingUpload entry, {
    bool enforceSimIdentity = true,
  }) async {
    final callId = entry.callId;
    if (callId == null) return RecordingUploadOutcome.uploadFailed;
    final recording = _recordingFromEntry(entry);
    if (recording == null) {
      await queue.markFailure(
        entry,
        'Recording metadata is incomplete.',
        retryable: false,
        status: 'VERIFICATION_FAILED',
        detail: 'Recording metadata is incomplete; the file was not uploaded.',
      );
      await MobileCallRecordingManager.reportStatus(
        callId: callId,
        status: RecordingSyncStatus.verificationFailed,
        detail: 'Recording metadata is incomplete; the file was not uploaded.',
      );
      return RecordingUploadOutcome.verificationFailed;
    }

    final outcome = await MobileCallRecordingManager.upload(
      callId: callId,
      recording: recording,
      consent: true,
      callDurationSeconds: entry.durationSeconds,
      simAccountId: entry.simAccountId,
      simSubscriptionId: entry.simSubscriptionId,
      enforceSimIdentity: enforceSimIdentity,
    );

    if (_isSuccess(outcome)) {
      await queue.remove(entry);
      await _deleteAppCopy(entry.filePath);
      return outcome;
    }

    final localStatus = await MobileCallRecordingManager.lastUploadStatus(
      callId,
    );
    final detail = (localStatus?['detail'] ?? '').toString().trim();
    final reason = detail.isEmpty ? _failureReason(outcome) : detail;
    final attempts = entry.attempts + 1;

    switch (outcome) {
      case RecordingUploadOutcome.consentRequired:
        await queue.markFailure(
          entry,
          reason,
          retryable: true,
          status: 'PENDING_SYNC',
          detail: reason,
          nextAttemptAt: DateTime.now().toUtc().add(
            RecordingRetryPolicy.backoffFor(attempts),
          ),
        );
        break;
      case RecordingUploadOutcome.verificationFailed:
        await queue.markFailure(
          entry,
          reason,
          retryable: false,
          status: 'VERIFICATION_FAILED',
          detail: reason,
        );
        break;
      case RecordingUploadOutcome.uploadFailed:
        final retryable = attempts < RecordingRetryPolicy.maxUploadAttempts;
        await queue.markFailure(
          entry,
          reason,
          retryable: retryable,
          status: 'UPLOAD_FAILED',
          detail: retryable
              ? reason
              : 'Upload failed after $attempts attempts: $reason',
          nextAttemptAt: retryable
              ? DateTime.now().toUtc().add(
                  RecordingRetryPolicy.backoffFor(attempts),
                )
              : null,
        );
        if (!retryable) {
          await MobileCallRecordingManager.reportStatus(
            callId: callId,
            status: RecordingSyncStatus.uploadFailed,
            detail: 'Upload failed after $attempts attempts: $reason',
          );
        }
        break;
      case RecordingUploadOutcome.uploaded:
      case RecordingUploadOutcome.duplicate:
        break;
    }
    return outcome;
  }

  static Future<void> _handleNoRecording(
    PendingRecordingUploadQueue queue,
    PendingRecordingUpload entry, {
    required String reason,
  }) async {
    final callId = entry.callId;
    final attempts = entry.attempts + 1;
    final started = entry.startedDateTime ?? entry.queuedAt;
    final age = DateTime.now().toUtc().difference(started);
    // A manual retry may re-attempt discovery after the automatic window even
    // though the task is terminal. It must not make the task retryable again
    // or downgrade RECORDING_UNAVAILABLE back to PENDING_SYNC: only the normal
    // automatic budget decides whether another pass is scheduled.
    final exhausted =
        age >= RecordingRetryPolicy.discoveryWindow ||
        attempts >= RecordingRetryPolicy.maxDiscoveryAttempts;
    final retryable = !exhausted;
    await queue.markFailure(
      entry,
      reason,
      retryable: retryable,
      status: exhausted ? 'RECORDING_UNAVAILABLE' : 'PENDING_SYNC',
      detail: exhausted
          ? '$reason Recording sync stopped after $attempts attempts.'
          : reason,
      nextAttemptAt: retryable
          ? DateTime.now().toUtc().add(
              RecordingRetryPolicy.backoffFor(attempts),
            )
          : null,
    );
    if (callId != null) {
      await MobileCallRecordingManager.reportStatus(
        callId: callId,
        status: exhausted
            ? RecordingSyncStatus.recordingUnavailable
            : RecordingSyncStatus.pendingSync,
        detail: exhausted
            ? '$reason Recording sync stopped after $attempts attempts.'
            : reason,
      );
    }
  }

  static ImportedCallRecording? _recordingFromEntry(
    PendingRecordingUpload entry,
  ) {
    final path = (entry.filePath ?? '').trim();
    if (path.isEmpty || entry.recordingDurationSeconds <= 0) return null;
    return ImportedCallRecording(
      path: path,
      name: (entry.fileName ?? '').trim().isEmpty
          ? 'call-recording'
          : entry.fileName!.trim(),
      size: entry.fileSize,
      mimeType: (entry.mimeType ?? '').trim().isEmpty
          ? 'audio/*'
          : entry.mimeType!.trim(),
      durationMs: entry.recordingDurationSeconds * 1000,
      checksum: (entry.checksum ?? '').trim(),
      source: entry.source,
      verified: true,
      matchedBy: 'pending_queue',
    );
  }

  static Future<bool> _fileExists(String path) async {
    try {
      final file = File(path);
      if (!await file.exists()) return false;
      return await file.length() > 0;
    } catch (_) {
      return false;
    }
  }

  static Future<void> _deleteAppCopy(String? path) async {
    final cleaned = (path ?? '').trim();
    if (cleaned.isEmpty) return;
    final lower = cleaned.replaceAll('\\', '/').toLowerCase();
    final isAppCopy =
        lower.contains('/files/call_recordings/') ||
        lower.contains('/files/recording_uploads/') ||
        lower.contains('/cache/call_recordings/') ||
        lower.contains('/cache/recording_uploads/');
    if (!isAppCopy) return;
    try {
      final file = File(cleaned);
      if (await file.exists()) await file.delete();
    } catch (_) {
      // Best effort: a future upload is still deduplicated by checksum.
    }
  }

  static bool _isSuccess(RecordingUploadOutcome outcome) =>
      outcome == RecordingUploadOutcome.uploaded ||
      outcome == RecordingUploadOutcome.duplicate;

  static String _failureReason(RecordingUploadOutcome outcome) {
    switch (outcome) {
      case RecordingUploadOutcome.consentRequired:
        return 'Recording consent is not granted on this device.';
      case RecordingUploadOutcome.verificationFailed:
        return 'The recording could not be verified against this call.';
      case RecordingUploadOutcome.uploadFailed:
        return 'The recording upload did not reach the CRM.';
      case RecordingUploadOutcome.uploaded:
      case RecordingUploadOutcome.duplicate:
        return '';
    }
  }
}
