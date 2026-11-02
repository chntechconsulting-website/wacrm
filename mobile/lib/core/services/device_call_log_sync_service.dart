import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/calls/data/calls_repository.dart';
import '../../features/calls/providers/calls_provider.dart';
import 'mobile_call_recording_manager.dart';
import 'mobile_sim_call_service.dart';

/// One row from the Android device call log.
@immutable
class DeviceCallLogEntry {
  final String nativeReference;
  final String? deviceCallLogId;
  final String phone;
  final String direction;
  final String status;
  final int durationSeconds;
  final String? startedAt;
  final String? endedAt;
  final String? simAccountId;
  final String? contactName;

  const DeviceCallLogEntry({
    required this.nativeReference,
    this.deviceCallLogId,
    required this.phone,
    required this.direction,
    required this.status,
    required this.durationSeconds,
    this.startedAt,
    this.endedAt,
    this.simAccountId,
    this.contactName,
  });

  bool get isUsable =>
      nativeReference.trim().isNotEmpty &&
      phone.trim().isNotEmpty &&
      (direction == 'INBOUND' || direction == 'OUTBOUND');

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
    // The native history map always carries `direction`, but fall back to the
    // raw Android CallLog.Calls.TYPE so an older bridge cannot silently produce
    // an OUTBOUND row. If neither is available the entry is unusable.
    final direction = explicit ?? _directionForAndroidType(map['type']) ?? '';
    return DeviceCallLogEntry(
      nativeReference: (map['nativeCallReference'] ?? '').toString().trim(),
      deviceCallLogId: _text(map['deviceCallLogId']),
      phone: (map['phone'] ?? '').toString().trim(),
      direction: direction,
      status: ((map['status'] ?? 'COMPLETED').toString()).toUpperCase(),
      durationSeconds: _int(map['durationSeconds']) ?? 0,
      startedAt: _text(map['startedAt']),
      endedAt: _text(map['endedAt']),
      simAccountId: _text(map['simAccountId']),
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

  const DeviceCallLogSyncResult({
    this.synced = 0,
    this.recordingsUploaded = 0,
    this.permissionDenied = false,
    this.error,
  });

  bool get hasChanges => synced > 0 || recordingsUploaded > 0;
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
  static const int _maxSkipped = 800;
  static const int _overlapMinutes = 10;
  static const int _maxLookbackDays = 7;

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
        return const DeviceCallLogSyncResult(permissionDenied: true);
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
          : DateTime.fromMillisecondsSinceEpoch(stored, isUtc: true).subtract(
              const Duration(minutes: _overlapMinutes),
            );
      final oldestAllowed = now.subtract(const Duration(days: _maxLookbackDays));
      if (since.isBefore(oldestAllowed)) since = oldestAllowed;

      final rows = await MobileSimCallService.getRecentDeviceCalls(
        since: since,
        limit: 250,
      );

      final repository = CallsRepository();
      var synced = 0;
      var recordings = 0;
      final consented = autoUploadRecordings
          ? await RecordingConsentService.hasConsent(scope)
          : false;

      for (final raw in rows) {
        final entry = DeviceCallLogEntry.fromMap(raw);
        if (!entry.isUsable) continue;
        if (handled.contains(entry.nativeReference)) continue;

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
            simAccountId: entry.simAccountId,
            callSource: 'MOBILE_SIM',
            nativeCallReference: entry.nativeReference,
          );
          synced += 1;
          await markHandled(entry.nativeReference, employeeKey: scope);

          final callId = _int(response?['id']);
          final hasRecording =
              (response?['recording_url'] ?? '').toString().trim().isNotEmpty;
          final started = entry.startedDateTime;
          if (consented &&
              callId != null &&
              !hasRecording &&
              entry.durationSeconds > 0 &&
              started != null) {
            try {
              final match = await MobileCallRecordingManager.findRecordingForCall(
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
        } catch (_) {
          // Keep this row unhandled so the next resume retries it.
        }
      }

      if (synced > 0) {
        await callsProvider.fetchCalls(showLoading: false);
      }
      await prefs.setInt(lastKey, now.millisecondsSinceEpoch);
      return DeviceCallLogSyncResult(
        synced: synced,
        recordingsUploaded: recordings,
      );
    } catch (error) {
      return DeviceCallLogSyncResult(error: error.toString());
    } finally {
      _running = false;
    }
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
