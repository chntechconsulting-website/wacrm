import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/calls/data/calls_repository.dart';
import '../../features/calls/providers/calls_provider.dart';
import '../network/api_exceptions.dart';
import 'mobile_call_recording_manager.dart';
import 'mobile_sim_call_service.dart';
import 'office_sim_service.dart';
import 'pending_call_sync_queue.dart';
import 'recording_upload_service.dart';

/// One row from the Android device call log.
@immutable
class DeviceCallLogEntry {
  final String nativeReference;
  final String? deviceCallLogId;

  /// Android `CallLog.Calls.DATE` in epoch milliseconds.
  final int? dateMillis;
  final String phone;

  /// Raw Android `CallLog.Calls.TYPE`, kept for diagnostics and proof.
  final int? androidCallType;

  /// Direction string exactly as the native bridge supplied it, before mapping.
  final String nativeDirection;
  final String direction;
  final String status;
  final int durationSeconds;
  final String? startedAt;
  final String? endedAt;
  final String? simAccountId;
  final String? simAccountComponent;
  final int? simSubscriptionId;
  final int? simSlotIndex;
  final String? simCarrierName;
  final String? simIdentity;
  final String? simIdentityStatus;
  final String? contactName;

  const DeviceCallLogEntry({
    required this.nativeReference,
    this.deviceCallLogId,
    this.dateMillis,
    required this.phone,
    this.androidCallType,
    this.nativeDirection = '',
    required this.direction,
    required this.status,
    required this.durationSeconds,
    this.startedAt,
    this.endedAt,
    this.simAccountId,
    this.simAccountComponent,
    this.simSubscriptionId,
    this.simSlotIndex,
    this.simCarrierName,
    this.simIdentity,
    this.simIdentityStatus,
    this.contactName,
  });

  bool get isUsable =>
      nativeReference.trim().isNotEmpty &&
      phone.trim().isNotEmpty &&
      (direction == 'INBOUND' || direction == 'OUTBOUND');

  /// A call can only be attributed to a SIM when Android exposed an exact
  /// subscription or phone-account identity. Missing/ambiguous metadata fails
  /// closed instead of guessing from the slot.
  bool get hasSimIdentity =>
      (simIdentity ?? '').trim().isNotEmpty ||
      (simAccountId ?? '').trim().isNotEmpty ||
      simSubscriptionId != null;

  int? get nativeCallLogId => _int(deviceCallLogId);

  /// Android call-log rows are ordered by the composite (DATE, _ID). A row is
  /// eligible only when it is strictly newer than the activation baseline.
  bool isAfterBaseline({required int baselineDateMs, required int baselineId}) {
    final date = dateMillis;
    final id = nativeCallLogId;
    if (date == null || id == null) return false;
    return date > baselineDateMs || (date == baselineDateMs && id > baselineId);
  }

  DateTime? get startedDateTime {
    final raw = startedAt;
    if (raw == null || raw.isEmpty) return null;
    return DateTime.tryParse(raw)?.toUtc();
  }

  DateTime? get endedDateTime {
    final raw = endedAt;
    if (raw == null || raw.isEmpty) return null;
    return DateTime.tryParse(raw)?.toUtc();
  }

  factory DeviceCallLogEntry.fromMap(Map<String, dynamic> map) {
    final explicit = _direction(map['direction']);
    // Android's raw CallLog.Calls.TYPE is the ground truth. A direction string
    // from an older bridge may be stale, so the typed value wins when present.
    // If neither is available the entry is unusable (never assumed OUTBOUND).
    final direction = _directionForAndroidType(map['type']) ?? explicit ?? '';
    return DeviceCallLogEntry(
      nativeReference: (map['nativeCallReference'] ?? '').toString().trim(),
      deviceCallLogId: _text(map['deviceCallLogId']),
      dateMillis:
          _int(map['dateMillis']) ??
          DateTime.tryParse((map['startedAt'] ?? '').toString())
              ?.toUtc()
              .millisecondsSinceEpoch,
      phone: (map['phone'] ?? '').toString().trim(),
      androidCallType: _int(map['type']),
      nativeDirection: (map['direction'] ?? '').toString().trim().toUpperCase(),
      direction: direction,
      status: ((map['status'] ?? 'COMPLETED').toString()).toUpperCase(),
      durationSeconds: _int(map['durationSeconds']) ?? 0,
      startedAt: _text(map['startedAt']),
      endedAt: _text(map['endedAt']),
      simAccountId: _text(map['simAccountId']),
      simAccountComponent: _text(map['simAccountComponent']),
      simSubscriptionId: _int(map['simSubscriptionId']),
      simSlotIndex: _int(map['simSlotIndex']),
      simCarrierName: _text(map['simCarrierName']),
      simIdentity: _text(map['simIdentity']),
      simIdentityStatus: _text(map['simIdentityStatus']),
      contactName: _text(map['contactName']),
    );
  }

  static String? _direction(Object? raw) {
    final value = (raw ?? '').toString().trim().toUpperCase();
    if (value == 'INBOUND' || value == 'OUTBOUND') return value;
    return null;
  }

  /// Android `CallLog.Calls.TYPE` values. The CRM maps every non-outgoing
  /// telephony type to INBOUND; unknown types yield null instead of a guess.
  static String? _directionForAndroidType(Object? rawType) =>
      MobileSimCallService.directionForAndroidType(rawType);
}

class DeviceCallLogSyncResult {
  final int synced;
  final int recordingsUploaded;
  final bool permissionDenied;
  final String? error;

  /// Office SIM gate state for this pass. Only `verified` allows any call to
  /// reach the CRM.
  final OfficeSimState officeSimState;

  /// Rows skipped because they belonged to another (personal) SIM.
  final int skippedPersonalSim;

  /// Rows skipped because Android exposed no exact SIM identity.
  final int skippedMissingIdentity;

  /// Rows skipped because Android exposed no supported call type, so the
  /// direction is genuinely unknown. They are never guessed as OUTBOUND.
  final int skippedUnknownDirection;
  final String? officeSimMessage;
  final String syncStatus;
  final int syncedUpToDateMs;
  final int syncedUpToId;

  /// Calls still waiting for a confirmed backend response.
  final int pendingSyncCount;

  /// Pending calls that may succeed on a later automatic retry.
  final int retryablePending;

  /// Recordings still waiting for a device file or backend confirmation.
  final int recordingsPending;

  /// Recordings that may succeed on a later automatic retry.
  final int recordingRetryablePending;

  /// True when this pass failed for a transient reason (network, timeout,
  /// server or expired session) and should be retried.
  final bool retryableFailure;
  final DateTime? lastSuccessfulSyncAt;

  const DeviceCallLogSyncResult({
    this.synced = 0,
    this.recordingsUploaded = 0,
    this.permissionDenied = false,
    this.error,
    this.officeSimState = OfficeSimState.notConfigured,
    this.skippedPersonalSim = 0,
    this.skippedMissingIdentity = 0,
    this.skippedUnknownDirection = 0,
    this.officeSimMessage,
    this.syncStatus = 'NOT_CONFIGURED',
    this.syncedUpToDateMs = 0,
    this.syncedUpToId = 0,
    this.pendingSyncCount = 0,
    this.retryablePending = 0,
    this.recordingsPending = 0,
    this.recordingRetryablePending = 0,
    this.retryableFailure = false,
    this.lastSuccessfulSyncAt,
  });

  bool get hasChanges => synced > 0 || recordingsUploaded > 0;

  bool get isOfficeSimBlocked =>
      officeSimState == OfficeSimState.requiresVerification ||
      officeSimState == OfficeSimState.unsupported;

  bool get shouldRetry =>
      !permissionDenied &&
      !isOfficeSimBlocked &&
      (retryableFailure ||
          (syncStatus == 'ACTIVE' &&
              (retryablePending > 0 || recordingRetryablePending > 0)));
}

@immutable
class DeviceCallLogBaseline {
  final int dateMillis;
  final int callLogId;

  const DeviceCallLogBaseline({
    required this.dateMillis,
    required this.callLogId,
  });

  bool get isEmpty => dateMillis <= 0 && callLogId <= 0;
}

/// Synchronizes the device's own call history with the CRM.
///
/// Only rows from Android's telephony call log are read (the native layer
/// excludes SIP/VoIP/WACRM connection-service rows). Each native row keeps its
/// stable reference so retries can never create duplicate CRM records. An
/// automatic recording upload only happens when the native matcher finds
/// exactly one plausible file for that exact call.
class DeviceCallLogSyncService {
  static const String _skippedKey = 'wacrm_device_call_sync_handled';
  static const String _directionRepairKey =
      'wacrm_device_call_direction_repair_v2';
  static const int _maxSkipped = 800;
  static const int _pageSize = 250;
  // Android may append a finished call a few seconds after it ends. Re-read a
  // short window behind the composite watermark and dedupe by native reference.
  static const int _lateArrivalGraceMs = 120000;
  static const int _directionRepairLookbackDays = 30;

  static bool _running = false;

  static bool get isSupported => MobileSimCallService.isSupported;

  /// Captures the current Android call-log high-water mark. Used only when the
  /// employee enables or resumes sync, so existing history is never imported.
  static Future<DeviceCallLogBaseline?> captureBaseline() async {
    if (!isSupported) return null;
    final permissions = await MobileSimCallService.permissionStatus();
    if (!permissions.readCallLog) return null;
    final map = await MobileSimCallService.getDeviceCallLogBaseline();
    if (map == null) return null;
    return DeviceCallLogBaseline(
      dateMillis: _int(map['dateMillis']) ?? 0,
      callLogId: _int(map['callLogId']) ?? 0,
    );
  }

  static Future<DeviceCallLogSyncResult> sync(
    CallsProvider? callsProvider, {
    required String employeeKey,
    bool autoUploadRecordings = true,
    bool forceRetryPending = false,
    bool reportSimChanges = true,
  }) async {
    if (!isSupported) return const DeviceCallLogSyncResult();
    if (_running) return const DeviceCallLogSyncResult();
    _running = true;
    final scope = employeeKey.trim().isEmpty ? 'default' : employeeKey.trim();
    final queue = PendingCallSyncQueue(scope);
    await queue.reload();
    try {
      final permissions = await MobileSimCallService.permissionStatus();
      if (!permissions.readCallLog) {
        debugPrint(
          '[CallDirection] History sync blocked: READ_CALL_LOG is not granted. '
          'Incoming device calls cannot be read.',
        );
        return DeviceCallLogSyncResult(
          permissionDenied: true,
          error:
              'Call-log permission is not granted, so incoming and outgoing '
              'device calls cannot be synchronized from the phone call log.',
          pendingSyncCount: queue.count,
          retryablePending: queue.retryableCount,
        );
      }

      // The background worker never persists a SIM-verification change from a
      // transient telephony read failure (for example during boot or an OEM
      // restriction). It still fails closed for this pass; the next foreground
      // sync can report a genuinely replaced SIM.
      final officeSim = await OfficeSimService.evaluate(
        reportChange: reportSimChanges,
      );
      final mapping = officeSim.mapping;
      if (mapping == null) {
        return DeviceCallLogSyncResult(
          officeSimState: officeSim.state,
          officeSimMessage: officeSim.message,
          syncStatus: 'NOT_CONFIGURED',
          pendingSyncCount: queue.count,
          retryablePending: queue.retryableCount,
        );
      }
      if (!officeSim.canSync || !mapping.isVerified) {
        return DeviceCallLogSyncResult(
          officeSimState: officeSim.state,
          officeSimMessage: officeSim.message,
          syncStatus: mapping.syncStatus,
          pendingSyncCount: queue.count,
          retryablePending: queue.retryableCount,
          lastSuccessfulSyncAt: mapping.lastSuccessfulSyncAt,
        );
      }
      if (mapping.syncRequiresVerification) {
        return DeviceCallLogSyncResult(
          officeSimState: officeSim.state,
          officeSimMessage: 'The Office SIM must be re-verified before sync.',
          syncStatus: mapping.syncStatus,
          pendingSyncCount: queue.count,
          retryablePending: queue.retryableCount,
          lastSuccessfulSyncAt: mapping.lastSuccessfulSyncAt,
        );
      }
      if (!mapping.syncActive) {
        return DeviceCallLogSyncResult(
          officeSimState: officeSim.state,
          officeSimMessage: mapping.syncPaused
              ? 'Mobile call-log sync is paused on this device.'
              : 'Mobile call-log sync is not enabled on this device.',
          syncStatus: mapping.syncStatus,
          pendingSyncCount: queue.count,
          retryablePending: queue.retryableCount,
          lastSuccessfulSyncAt: mapping.lastSuccessfulSyncAt,
        );
      }

      final baselineDate = mapping.syncBaselineDateMs;
      final baselineId = mapping.syncBaselineId;
      if (baselineDate == null || baselineId == null) {
        return DeviceCallLogSyncResult(
          error:
              'The call-log sync baseline is missing. Pause and re-enable '
              'sync on this device.',
          syncStatus: mapping.syncStatus,
          pendingSyncCount: queue.count,
          retryablePending: queue.retryableCount,
          lastSuccessfulSyncAt: mapping.lastSuccessfulSyncAt,
        );
      }
      var watermarkDate = mapping.syncWatermarkDateMs ?? baselineDate;
      var watermarkId = mapping.syncWatermarkId ?? baselineId;
      if (!_cursorAfter(watermarkDate, watermarkId, baselineDate, baselineId)) {
        watermarkDate = baselineDate;
        watermarkId = baselineId;
      }

      final prefs = await SharedPreferences.getInstance();
      final handledKey = '${_skippedKey}_$scope';
      final handled = (prefs.getStringList(handledKey) ?? const <String>[])
          .toSet();

      final repository = CallsRepository();
      var synced = 0;
      var recordings = 0;
      var skippedPersonal = 0;
      var skippedMissingIdentity = 0;
      var skippedUnknownDirection = 0;
      var failureRetryable = false;
      String? failureMessage;
      DateTime? lastSuccessfulSyncAt = mapping.lastSuccessfulSyncAt;
      final consented = autoUploadRecordings
          ? await RecordingConsentService.hasConsent(scope)
          : false;

      Future<Map<String, dynamic>?> uploadEntry(DeviceCallLogEntry entry) {
        final entryIdentity = entry.simIdentity ?? entry.simAccountId;
        return repository.logManualCall(
          customerPhone: entry.phone,
          callStatus: entry.status,
          durationSeconds: entry.durationSeconds,
          notes:
              'Mobile SIM ${entry.direction.toLowerCase()} call synced from '
              'the device call history.',
          clientCallId: entry.nativeReference,
          callDirection: entry.direction,
          startedAt: entry.startedAt,
          endedAt: entry.endedAt,
          simAccountId: entryIdentity,
          simSubscriptionId: entry.simSubscriptionId,
          simSlot: entry.simSlotIndex,
          simLabel: entry.simCarrierName,
          callSource: 'MOBILE_SIM',
          nativeCallReference: entry.nativeReference,
          syncOrigin: 'HISTORY_SYNC',
          nativeCallDateMs: entry.dateMillis,
          nativeCallId: entry.nativeCallLogId,
        );
      }

      Future<void> confirmEntry(
        DeviceCallLogEntry entry,
        Map<String, dynamic>? response,
      ) async {
        synced += 1;
        debugPrint(
          '[CallDirection] Saved row id=${_int(response?['id']) ?? "-"} '
          'direction=${(response?['call_direction'] ?? response?['direction'] ?? "-")}',
        );
        // A row leaves the queue only after the backend has answered. The
        // handled set is written first so a crash between the two writes
        // cannot cause a duplicate scan; a retry is idempotent anyway.
        await markHandled(entry.nativeReference, employeeKey: scope);
        await queue.removeByReference(entry.nativeReference);

        final callId = _int(response?['id']);
        final hasRecording = (response?['recording_url'] ?? '')
            .toString()
            .trim()
            .isNotEmpty;
        final started = entry.startedDateTime;
        // Recording discovery is queued only for a row already proven to be
        // after the baseline and on the Office SIM, so a historical or
        // personal-SIM recording can never be uploaded. The durable queue,
        // rather than this call, owns the discovery/upload retry.
        if (consented &&
            callId != null &&
            !hasRecording &&
            entry.durationSeconds > 0 &&
            started != null) {
          try {
            await RecordingUploadService.enqueueForCall(
              callId: callId,
              employeeKey: scope,
              phone: entry.phone,
              startedAt: started,
              endedAt: entry.endedDateTime,
              durationSeconds: entry.durationSeconds,
              direction: entry.direction,
              nativeReference: entry.nativeReference,
              simAccountId: entry.simIdentity ?? entry.simAccountId,
              simSubscriptionId: entry.simSubscriptionId,
            );
          } catch (_) {
            // The call row is already durable; a later foreground pass can
            // enqueue the recording from the call-log list.
          }
        }
      }

      // Retry calls that were read in an earlier pass but never confirmed by
      // the backend. They are drained before new rows so a process death or
      // offline period cannot lose call metadata.
      var scanBlocked = false;
      for (final pending in queue.entries) {
        if (!forceRetryPending && !pending.retryable) continue;
        final entry = DeviceCallLogEntry.fromMap(pending.row);
        if (!entry.isAfterBaseline(
          baselineDateMs: baselineDate,
          baselineId: baselineId,
        )) {
          // A fresh verification baseline intentionally excludes older calls.
          await queue.remove(pending);
          continue;
        }
        if (handled.contains(entry.nativeReference)) {
          await queue.remove(pending);
          continue;
        }
        if (!entry.isUsable) {
          await queue.remove(pending);
          continue;
        }
        try {
          final response = await uploadEntry(entry);
          await confirmEntry(entry, response);
        } catch (error) {
          final retryable = isRetryableSyncError(error);
          failureMessage = error.toString();
          failureRetryable = failureRetryable || retryable;
          await queue.markFailure(pending, error, retryable: retryable);
          debugPrint(
            '[CallDirection] Pending sync retry failed for '
            'nativeId=${entry.nativeReference}: $error',
          );
          if (retryable) {
            scanBlocked = true;
            break;
          }
        }
      }

      var cursorDate = watermarkDate;
      var cursorId = watermarkId;
      var maxDate = watermarkDate;
      var maxId = watermarkId;
      var firstPage = true;
      var scanFailed = false;

      if (!scanBlocked) {
        while (true) {
          final page = await MobileSimCallService.getDeviceCallsIncremental(
            afterDateMillis: cursorDate,
            afterId: cursorId,
            graceMillis: firstPage ? _lateArrivalGraceMs : 0,
            limit: _pageSize,
          );
          if (page.rows.isEmpty) break;

          var pageFailed = false;
          for (final raw in page.rows) {
            final entry = DeviceCallLogEntry.fromMap(raw);
            final entryDate = entry.dateMillis;
            final entryId = entry.nativeCallLogId;
            if (entryDate != null &&
                entryId != null &&
                _cursorAfter(entryDate, entryId, maxDate, maxId)) {
              maxDate = entryDate;
              maxId = entryId;
            }

            // Only calls created after the activation baseline are eligible.
            // This is the guard that prevents a historical import on every
            // launch, enable, resume or app update.
            if (!entry.isAfterBaseline(
              baselineDateMs: baselineDate,
              baselineId: baselineId,
            )) {
              if (entry.nativeReference.trim().isNotEmpty) {
                debugPrint(
                  '[CallDirection] Skipped pre-baseline call: '
                  'nativeId=${entry.nativeReference}.',
                );
              }
              continue;
            }
            if (handled.contains(entry.nativeReference)) continue;
            if (queue.contains(entry.nativeReference)) continue;

            if (!entry.isUsable) {
              if (entry.nativeReference.trim().isNotEmpty &&
                  entry.phone.trim().isNotEmpty) {
                skippedUnknownDirection += 1;
                debugPrint(
                  '[CallDirection] Skipped device call: Android call type is '
                  'unknown, direction not inferred.',
                );
              }
              continue;
            }

            // A configured Office SIM is mandatory for history sync. Missing
            // or unknown SIM identity is excluded, never guessed.
            if (!entry.hasSimIdentity) {
              skippedMissingIdentity += 1;
              debugPrint(
                '[OfficeSIM] Skipped device call: SIM identity missing.',
              );
              continue;
            }
            final entryIdentity = entry.simIdentity ?? entry.simAccountId;
            final isOfficeCall = OfficeSimService.callMatches(
              mapping,
              subscriptionId: entry.simSubscriptionId,
              simAccountId: entryIdentity,
            );
            if (!isOfficeCall) {
              skippedPersonal += 1;
              debugPrint(
                '[OfficeSIM] Skipped device call: handled by a non-office SIM.',
              );
              continue;
            }

            debugPrint(
              '[CallDirection] Sync row nativeId=${entry.nativeReference} '
              'androidType=${entry.androidCallType} '
              'phoneAccount=${entry.simAccountId ?? "-"} '
              'subId=${entry.simSubscriptionId ?? "-"} '
              'nativeDirection=${entry.nativeDirection.isEmpty ? "-" : entry.nativeDirection} '
              'payloadDirection=${entry.direction}',
            );

            // Persist the native row before the network call. If the process
            // dies during upload the next engine pass retries this exact id.
            final queued = await queue.enqueue(raw);
            try {
              final response = await uploadEntry(entry);
              await confirmEntry(entry, response);
            } catch (error) {
              final retryable = isRetryableSyncError(error);
              failureMessage = error.toString();
              failureRetryable = failureRetryable || retryable;
              if (queued != null) {
                await queue.markFailure(queued, error, retryable: retryable);
              }
              debugPrint(
                '[CallDirection] Sync failed for '
                'nativeId=${entry.nativeReference} '
                'direction=${entry.direction}: $error',
              );
              scanFailed = true;
              pageFailed = true;
              break;
            }
          }

          if (pageFailed) break;

          final last = page.rows.last;
          final lastDate = _int(last['dateMillis']);
          final lastId = _int(last['deviceCallLogId']);
          if (lastDate == null || lastId == null) break;
          // The grace window may return a first page whose last row is older
          // than the watermark; follow it once so no late-arriving row is
          // skipped. After that the cursor must strictly advance.
          if (!firstPage &&
              !_cursorAfter(lastDate, lastId, cursorDate, cursorId)) {
            break;
          }
          cursorDate = lastDate;
          cursorId = lastId;
          if (!page.hasMore) break;
          firstPage = false;
        }
      }

      // The watermark may only move once every eligible row it covers was
      // confirmed. A pending retry therefore blocks advancement, so a later
      // pass can never skip an older unsynced call.
      if (!scanFailed && !scanBlocked && queue.count == 0) {
        try {
          final updated = await OfficeSimService.reportSyncProgress(
            watermarkDateMs: maxDate,
            watermarkId: maxId,
          );
          lastSuccessfulSyncAt = updated.lastSuccessfulSyncAt;
        } catch (error) {
          debugPrint(
            '[CallDirection] Could not persist sync watermark yet: $error',
          );
        }
      }

      var recordingResult = const RecordingQueueResult();
      if (autoUploadRecordings) {
        // Discovery and upload use the same durable queue for live calls,
        // history rows, the WorkManager pass and manual Sync Now. It runs after
        // call metadata is confirmed so a failed recording upload can never
        // roll back or duplicate the call row.
        recordingResult = await RecordingUploadService.processQueue(
          employeeKey: scope,
          callsProvider: callsProvider,
          forceRetry: forceRetryPending,
        );
        recordings = recordingResult.uploaded;
      }

      if ((synced > 0 || recordings > 0) && callsProvider != null) {
        await callsProvider.fetchCalls(showLoading: false);
      }
      return DeviceCallLogSyncResult(
        synced: synced,
        recordingsUploaded: recordings,
        error: failureMessage,
        officeSimState: officeSim.state,
        skippedPersonalSim: skippedPersonal,
        skippedMissingIdentity: skippedMissingIdentity,
        skippedUnknownDirection: skippedUnknownDirection,
        officeSimMessage: officeSim.message,
        syncStatus: mapping.syncStatus,
        syncedUpToDateMs: maxDate,
        syncedUpToId: maxId,
        pendingSyncCount: queue.count,
        retryablePending: queue.retryableCount,
        recordingsPending: recordingResult.pending,
        recordingRetryablePending: recordingResult.retryablePending,
        retryableFailure: failureRetryable,
        lastSuccessfulSyncAt: lastSuccessfulSyncAt,
      );
    } catch (error) {
      return DeviceCallLogSyncResult(
        error: error.toString(),
        retryableFailure: isRetryableSyncError(error),
        pendingSyncCount: queue.count,
        retryablePending: queue.retryableCount,
      );
    } finally {
      _running = false;
    }
  }

  /// Re-posts previously synced inbound device-history rows so the backend can
  /// correct a stored direction using the current Android `CallLog.Calls.TYPE`.
  ///
  /// This runs once per employee. Only inbound rows whose native reference was
  /// already synced from this device are eligible, so a repair never creates a
  /// new CRM record and never resurrects a personal-SIM call. The native call
  /// type is the only evidence used: phone number, duration and status are
  /// ignored.
  static Future<int> repairHistoricalDirections(
    CallsProvider callsProvider, {
    required String employeeKey,
  }) async {
    if (!isSupported || _running) return 0;
    final permissions = await MobileSimCallService.permissionStatus();
    if (!permissions.readCallLog) return 0;

    final officeSim = await OfficeSimService.evaluate();
    final mapping = officeSim.mapping;
    // With a mapping configured, an unverified SIM blocks the repair exactly as
    // it blocks sync. Without a mapping (legacy devices) previously synced
    // references may still be corrected; no new row can be created.
    if (mapping != null && !officeSim.canSync) return 0;

    final prefs = await SharedPreferences.getInstance();
    final scope = employeeKey.trim().isEmpty ? 'default' : employeeKey.trim();
    final repairKey = '${_directionRepairKey}_$scope';
    if (prefs.getBool(repairKey) == true) return 0;

    final handled =
        (prefs.getStringList('${_skippedKey}_$scope') ?? const <String>[])
            .toSet();
    if (handled.isEmpty) {
      // Nothing was ever synced from this device, so there is no historical
      // row whose direction could be proven. Never repair by guessing.
      await prefs.setBool(repairKey, true);
      return 0;
    }

    final now = DateTime.now().toUtc();
    final rows = await MobileSimCallService.getRecentDeviceCalls(
      since: now.subtract(const Duration(days: _directionRepairLookbackDays)),
      limit: 500,
    );
    final repository = CallsRepository();
    var repaired = 0;

    for (final raw in rows) {
      final entry = DeviceCallLogEntry.fromMap(raw);
      if (!entry.isUsable) continue;
      if (!handled.contains(entry.nativeReference)) continue;
      // Only inbound rows are re-asserted. Outbound behaviour is untouched;
      // the reported defect is an inbound call stored as OUTBOUND.
      if (entry.direction != 'INBOUND') continue;
      final entryIdentity = entry.simIdentity ?? entry.simAccountId;
      if (mapping != null) {
        if (!entry.hasSimIdentity) continue;
        if (!OfficeSimService.callMatches(
          mapping,
          subscriptionId: entry.simSubscriptionId,
          simAccountId: entryIdentity,
        )) {
          continue;
        }
      }

      try {
        await repository.logManualCall(
          customerPhone: entry.phone,
          callStatus: entry.status,
          durationSeconds: entry.durationSeconds,
          notes:
              'Mobile SIM ${entry.direction.toLowerCase()} call direction '
              'verified from the device call history.',
          clientCallId: entry.nativeReference,
          callDirection: entry.direction,
          startedAt: entry.startedAt,
          endedAt: entry.endedAt,
          simAccountId: entryIdentity,
          simSubscriptionId: entry.simSubscriptionId,
          simSlot: entry.simSlotIndex,
          simLabel: entry.simCarrierName,
          callSource: 'MOBILE_SIM',
          nativeCallReference: entry.nativeReference,
        );
        repaired += 1;
      } catch (_) {
        // Leave the repair pass undecided; it retries on the next launch.
        return repaired;
      }
    }

    await prefs.setBool(repairKey, true);
    if (repaired > 0) {
      await callsProvider.fetchCalls(showLoading: false);
    }
    return repaired;
  }

  /// Remembers a native row already handled by the live in-app tracker, so the
  /// history pass cannot log the same call twice.
  static Future<void> markHandled(
    String? nativeReference, {
    String employeeKey = 'default',
  }) async {
    final reference = (nativeReference ?? '').trim();
    if (reference.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final scope = employeeKey.trim().isEmpty ? 'default' : employeeKey.trim();
      final key = '${_skippedKey}_$scope';
      final handled = (prefs.getStringList(key) ?? const <String>[]).toList();
      if (handled.contains(reference)) return;
      handled.add(reference);
      if (handled.length > _maxSkipped) {
        handled.removeRange(0, handled.length - _maxSkipped);
      }
      await prefs.setStringList(key, handled);
    } catch (_) {
      // Best-effort: backend idempotency/adoption still prevents duplicates.
    }
  }
}

String? _text(dynamic value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

int? _int(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  return int.tryParse(value.toString());
}

bool _cursorAfter(int date, int id, int otherDate, int otherId) =>
    date > otherDate || (date == otherDate && id > otherId);

/// Network, timeout, expired-session, throttling and server failures are worth
/// retrying automatically. Validation/forbidden business errors are kept in the
/// queue but are not retried every 15 minutes; a manual sync can retry them
/// after the employee corrects the underlying issue.
bool isRetryableSyncError(Object error) {
  if (error is NetworkException || error is TimeoutException) return true;
  if (error is ApiException) {
    final code = error.statusCode;
    if (code == null) return true;
    if (code == 401 || code == 403 || code == 408 || code == 425) return true;
    if (code == 429 || code >= 500) return true;
    return false;
  }
  return true;
}
