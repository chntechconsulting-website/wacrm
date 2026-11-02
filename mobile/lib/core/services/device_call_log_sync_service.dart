import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/calls/data/calls_repository.dart';
import '../../features/calls/providers/calls_provider.dart';
import 'mobile_call_recording_manager.dart';
import 'mobile_sim_call_service.dart';
import 'office_sim_service.dart';

/// One row from the Android device call log.
@immutable
class DeviceCallLogEntry {
  final String nativeReference;
  final String? deviceCallLogId;
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
  });

  bool get hasChanges => synced > 0 || recordingsUploaded > 0;

  bool get isOfficeSimBlocked =>
      officeSimState == OfficeSimState.requiresVerification ||
      officeSimState == OfficeSimState.unsupported;
}

/// Synchronizes the device's own call history with the CRM.
///
/// Only rows from Android's telephony call log are read (the native layer
/// excludes SIP/VoIP/WACRM connection-service rows). Each native row keeps its
/// stable reference so retries can never create duplicate CRM records. An
/// automatic recording upload only happens when the native matcher finds
/// exactly one plausible file for that exact call.
class DeviceCallLogSyncService {
  static const String _lastSyncKey = 'wacrm_device_call_sync_last';
  static const String _skippedKey = 'wacrm_device_call_sync_handled';
  static const String _directionRepairKey =
      'wacrm_device_call_direction_repair_v2';
  static const String _rescanKey = 'wacrm_device_call_sync_rescan_v2';
  static const int _maxSkipped = 800;
  static const int _overlapMinutes = 10;
  static const int _maxLookbackDays = 7;
  static const int _directionRepairLookbackDays = 30;

  static bool _running = false;

  static bool get isSupported => MobileSimCallService.isSupported;

  static Future<DeviceCallLogSyncResult> sync(
    CallsProvider callsProvider, {
    required String employeeKey,
    bool autoUploadRecordings = true,
  }) async {
    if (!isSupported) return const DeviceCallLogSyncResult();
    if (_running) return const DeviceCallLogSyncResult();
    _running = true;
    try {
      final permissions = await MobileSimCallService.permissionStatus();
      if (!permissions.readCallLog) {
        debugPrint(
          '[CallDirection] History sync blocked: READ_CALL_LOG is not granted. '
          'Incoming device calls cannot be read.',
        );
        return const DeviceCallLogSyncResult(
          permissionDenied: true,
          error:
              'Call-log permission is not granted, so incoming and outgoing '
              'device calls cannot be synchronized from the phone call log.',
        );
      }

      // A configured Office SIM is enforced strictly. When no mapping is
      // configured, legacy behaviour is preserved (the live dialer path already
      // does this), otherwise incoming history would never be imported.
      final officeSim = await OfficeSimService.evaluate();
      final mapping = officeSim.mapping;
      if (mapping != null && !officeSim.canSync) {
        return DeviceCallLogSyncResult(
          officeSimState: officeSim.state,
          officeSimMessage: officeSim.message,
        );
      }

      final prefs = await SharedPreferences.getInstance();
      final scope = employeeKey.trim().isEmpty ? 'default' : employeeKey.trim();
      final lastKey = '${_lastSyncKey}_$scope';
      final handledKey = '${_skippedKey}_$scope';
      final handled = (prefs.getStringList(handledKey) ?? const <String>[])
          .toSet();

      final now = DateTime.now().toUtc();
      final stored = prefs.getInt(lastKey);
      var since = stored == null
          ? now.subtract(const Duration(days: 2))
          : DateTime.fromMillisecondsSinceEpoch(
              stored,
              isUtc: true,
            ).subtract(const Duration(minutes: _overlapMinutes));
      final oldestAllowed = now.subtract(
        const Duration(days: _maxLookbackDays),
      );
      if (since.isBefore(oldestAllowed)) since = oldestAllowed;

      // A previous build could advance its watermark past inbound rows that it
      // then failed to import (missing permission, no Office SIM mapping, an
      // unknown direction or a rejected request). One full re-scan recovers
      // those rows; `handled` + backend idempotency prevent duplicates.
      final rescanKey = '${_rescanKey}_$scope';
      final needsRescan = prefs.getBool(rescanKey) != true;
      if (needsRescan) since = oldestAllowed;

      final rows = await MobileSimCallService.getRecentDeviceCalls(
        since: since,
        limit: 250,
      );

      final repository = CallsRepository();
      var synced = 0;
      var recordings = 0;
      var skippedPersonal = 0;
      var skippedMissingIdentity = 0;
      var skippedUnknownDirection = 0;
      var hadFailure = false;
      final consented = autoUploadRecordings
          ? await RecordingConsentService.hasConsent(scope)
          : false;

      for (final raw in rows) {
        final entry = DeviceCallLogEntry.fromMap(raw);
        if (!entry.isUsable) {
          // A row with a valid reference and phone but no supported Android
          // type is unresolved: never fall back to OUTBOUND, never sync it.
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
        if (handled.contains(entry.nativeReference)) continue;

        final entryIdentity = entry.simIdentity ?? entry.simAccountId;

        // With a configured Office SIM, only an exact identity match may reach
        // the CRM. Without a mapping, legacy devices keep synchronizing (the
        // live dialer path behaves the same way). Identity is never guessed.
        if (mapping != null) {
          if (!entry.hasSimIdentity) {
            skippedMissingIdentity += 1;
            debugPrint(
              '[OfficeSIM] Skipped device call: SIM identity missing.',
            );
            continue;
          }
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
        }

        debugPrint(
          '[CallDirection] Sync row nativeId=${entry.nativeReference} '
          'androidType=${entry.androidCallType} '
          'phoneAccount=${entry.simAccountId ?? "-"} '
          'subId=${entry.simSubscriptionId ?? "-"} '
          'nativeDirection=${entry.nativeDirection.isEmpty ? "-" : entry.nativeDirection} '
          'payloadDirection=${entry.direction}',
        );

        try {
          final response = await repository.logManualCall(
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
          );
          synced += 1;
          debugPrint(
            '[CallDirection] Saved row id=${_int(response?['id']) ?? "-"} '
            'direction=${(response?['call_direction'] ?? response?['direction'] ?? "-")}',
          );
          await markHandled(entry.nativeReference, employeeKey: scope);

          final callId = _int(response?['id']);
          final hasRecording = (response?['recording_url'] ?? '')
              .toString()
              .trim()
              .isNotEmpty;
          final started = entry.startedDateTime;
          if (consented &&
              callId != null &&
              !hasRecording &&
              entry.durationSeconds > 0 &&
              started != null) {
            try {
              final match =
                  await MobileCallRecordingManager.findRecordingForCall(
                    phone: entry.phone,
                    startedAt: started,
                    endedAt: entry.endedDateTime,
                    durationSeconds: entry.durationSeconds,
                  );
              if (match != null) {
                final outcome = await MobileCallRecordingManager.upload(
                  callId: callId,
                  recording: match,
                  consent: true,
                  callDurationSeconds: entry.durationSeconds,
                  simAccountId: entryIdentity,
                  simSubscriptionId: entry.simSubscriptionId,
                );
                if (outcome == RecordingUploadOutcome.uploaded ||
                    outcome == RecordingUploadOutcome.duplicate) {
                  recordings += 1;
                }
              }
            } catch (_) {
              // No accessible/unambiguous recording: keep "Unavailable".
            }
          }
        } catch (error) {
          // Keep this row unhandled so the next resume retries it. The
          // watermark must not advance past a failed row, or a rejected /
          // missed inbound call could be lost forever.
          hadFailure = true;
          debugPrint(
            '[CallDirection] Sync failed for nativeId=${entry.nativeReference} '
            'direction=${entry.direction}: $error',
          );
        }
      }

      if (synced > 0) {
        await callsProvider.fetchCalls(showLoading: false);
      }
      if (!hadFailure) {
        await prefs.setInt(lastKey, now.millisecondsSinceEpoch);
        if (needsRescan) await prefs.setBool(rescanKey, true);
      }
      return DeviceCallLogSyncResult(
        synced: synced,
        recordingsUploaded: recordings,
        officeSimState: officeSim.state,
        skippedPersonalSim: skippedPersonal,
        skippedMissingIdentity: skippedMissingIdentity,
        skippedUnknownDirection: skippedUnknownDirection,
        officeSimMessage: officeSim.message,
      );
    } catch (error) {
      return DeviceCallLogSyncResult(error: error.toString());
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

  /// Uploads the single device recording that matches a just-finished live
  /// tracked call. History sync skips that native row, so this closes the gap
  /// without ever guessing or attaching another call's audio.
  static Future<bool> attachRecordingForLiveResult({
    required MobileSimCallResult result,
    required int callId,
    required String employeeKey,
  }) async {
    if (!isSupported || result.hasRecording || result.durationSeconds <= 0) {
      return false;
    }
    final identity = (result.simIdentity ?? '').trim().isNotEmpty
        ? result.simIdentity!.trim()
        : (result.simSubscriptionId != null
              ? 'subId:${result.simSubscriptionId}'
              : (result.simAccountId ?? '').trim());
    final mapping = await OfficeSimService.fetch();
    if (mapping != null &&
        (!mapping.isVerified ||
            !OfficeSimService.callMatches(
              mapping,
              subscriptionId: result.simSubscriptionId,
              simAccountId: identity,
            ))) {
      return false;
    }
    final consented = await RecordingConsentService.hasConsent(employeeKey);
    if (!consented) return false;
    final startedRaw = result.startedAt;
    if (startedRaw == null || startedRaw.isEmpty) return false;
    final started = DateTime.tryParse(startedRaw)?.toUtc();
    if (started == null) return false;
    final ended = result.endedAt == null
        ? null
        : DateTime.tryParse(result.endedAt!)?.toUtc();
    try {
      final match = await MobileCallRecordingManager.findRecordingForCall(
        phone: result.customerPhone,
        startedAt: started,
        endedAt: ended,
        durationSeconds: result.durationSeconds,
      );
      if (match == null) return false;
      final outcome = await MobileCallRecordingManager.upload(
        callId: callId,
        recording: match,
        consent: true,
        callDurationSeconds: result.durationSeconds,
        simAccountId: identity.isEmpty ? null : identity,
        simSubscriptionId: result.simSubscriptionId,
      );
      return outcome == RecordingUploadOutcome.uploaded ||
          outcome == RecordingUploadOutcome.duplicate;
    } catch (_) {
      return false;
    }
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
