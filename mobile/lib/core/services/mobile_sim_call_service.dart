import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../../features/calls/data/calls_repository.dart';
import '../../features/calls/providers/calls_provider.dart';
import 'office_sim_service.dart';

/// A SIM subscription reported by Android's SubscriptionManager.
class SimAccount {
  final int subscriptionId;
  final int slotIndex;
  final String carrierName;
  final String displayName;
  final String? phoneNumber;
  final bool isDefault;
  final String? phoneAccountId;
  final String? phoneAccountComponent;
  final String? simFingerprint;
  final bool isEmbedded;
  final bool isRemovable;

  const SimAccount({
    required this.subscriptionId,
    required this.slotIndex,
    required this.carrierName,
    required this.displayName,
    this.phoneNumber,
    this.isDefault = false,
    this.phoneAccountId,
    this.phoneAccountComponent,
    this.simFingerprint,
    this.isEmbedded = false,
    this.isRemovable = false,
  });

  String get label {
    if (displayName.trim().isNotEmpty) return displayName.trim();
    if (carrierName.trim().isNotEmpty) return carrierName.trim();
    return 'SIM ${slotIndex + 1}';
  }

  /// Exact identity token stored on CRM call rows.
  String? get identityToken {
    if (subscriptionId >= 0) return 'subId:$subscriptionId';
    final account = (phoneAccountId ?? '').trim();
    if (account.isEmpty) return null;
    final component = (phoneAccountComponent ?? '').trim();
    return component.isEmpty
        ? 'phoneAccount:$account'
        : 'phoneAccount:$component#$account';
  }

  factory SimAccount.fromMap(Map<dynamic, dynamic> map) {
    return SimAccount(
      subscriptionId: _asInt(map['subscriptionId']) ?? -1,
      slotIndex: _asInt(map['slotIndex']) ?? 0,
      carrierName: _asString(map['carrierName']) ?? '',
      displayName: _asString(map['displayName']) ?? '',
      phoneNumber: _asString(map['phoneNumber']),
      isDefault: map['isDefault'] == true,
      phoneAccountId: _asString(map['phoneAccountId']),
      phoneAccountComponent: _asString(map['phoneAccountComponent']),
      simFingerprint: _asString(map['simFingerprint']),
      isEmbedded: map['isEmbedded'] == true,
      isRemovable: map['isRemovable'] == true,
    );
  }
}

class MobileSimPermissionStatus {
  final bool callPhone;
  final bool readPhoneState;
  final bool readCallLog;
  final bool readPhoneNumbers;
  final bool readMediaAudio;

  const MobileSimPermissionStatus({
    required this.callPhone,
    required this.readPhoneState,
    required this.readCallLog,
    required this.readPhoneNumbers,
    required this.readMediaAudio,
  });

  bool get hasRequired => callPhone && readPhoneState;

  List<String> get missingRequired {
    final missing = <String>[];
    if (!callPhone) missing.add('Phone calling');
    if (!readPhoneState) missing.add('Phone state / SIM info');
    return missing;
  }

  factory MobileSimPermissionStatus.fromMap(Map<dynamic, dynamic> map) {
    return MobileSimPermissionStatus(
      callPhone: map['callPhone'] == true,
      readPhoneState: map['readPhoneState'] == true,
      readCallLog: map['readCallLog'] == true,
      readPhoneNumbers: map['readPhoneNumbers'] == true,
      readMediaAudio: map['readMediaAudio'] == true,
    );
  }
}

/// Result produced by the native Android layer when a device call ends.
class MobileSimCallResult {
  final String callId;
  final String? callReference;
  final String? deviceCallLogId;
  final String? nativeCallReference;
  final int? androidCallType;
  final int? leadId;
  final String customerPhone;
  final String? contactName;
  final String callDirection;
  final String callStatus;
  final int durationSeconds;
  final String durationAccuracy; // exact | estimated
  final String? startedAt;
  final String? answeredAt;
  final String? endedAt;
  final String? simAccountId;
  final int? simSubscriptionId;
  final String? simAccountComponent;
  final String? simIdentity;
  final String? simIdentityStatus;
  final String? simLabel;
  final int? simSlot;
  final String? simPhoneNumber;
  final String? recordingUrl;
  final String recordingStatus;

  const MobileSimCallResult({
    required this.callId,
    this.callReference,
    this.deviceCallLogId,
    this.nativeCallReference,
    this.androidCallType,
    this.leadId,
    required this.customerPhone,
    this.contactName,
    required this.callDirection,
    required this.callStatus,
    required this.durationSeconds,
    required this.durationAccuracy,
    this.startedAt,
    this.answeredAt,
    this.endedAt,
    this.simAccountId,
    this.simSubscriptionId,
    this.simAccountComponent,
    this.simIdentity,
    this.simIdentityStatus,
    this.simLabel,
    this.simSlot,
    this.simPhoneNumber,
    this.recordingUrl,
    this.recordingStatus = 'RECORDING_UNAVAILABLE',
  });

  bool get hasRecording =>
      recordingUrl != null && recordingUrl!.trim().isNotEmpty;

  /// A result may only be written to the CRM when the native layer proved the
  /// direction. An empty/UNKNOWN value is unresolved, never outbound.
  bool get hasKnownDirection =>
      callDirection == 'INBOUND' || callDirection == 'OUTBOUND';

  String get syncNotes {
    final parts = <String>['Mobile SIM call'];
    if (simLabel != null && simLabel!.trim().isNotEmpty) {
      parts.add('via $simLabel');
    }
    parts.add(
      '(${durationAccuracy == 'exact' ? 'duration from device call log' : 'estimated duration'})',
    );
    parts.add(hasRecording ? 'Recording supplied' : 'Recording unavailable');
    return parts.join(' ');
  }

  factory MobileSimCallResult.fromMap(Map<dynamic, dynamic> map) {
    return MobileSimCallResult(
      callId: _asString(map['callId']) ?? '',
      callReference: _asString(map['callReference']),
      deviceCallLogId: _asString(map['deviceCallLogId']),
      nativeCallReference: _asString(map['nativeCallReference']),
      androidCallType: _asInt(map['callType']),
      leadId: _asInt(map['leadId']),
      customerPhone: _asString(map['customerPhone']) ?? '',
      contactName: _asString(map['contactName']),
      callDirection:
          MobileSimCallService.directionForAndroidType(map['callType']) ??
          MobileSimCallService.normalizeDirection(map['callDirection']) ??
          '',
      callStatus: (_asString(map['callStatus']) ?? 'COMPLETED').toUpperCase(),
      durationSeconds: _asInt(map['durationSeconds']) ?? 0,
      durationAccuracy: _asString(map['durationAccuracy']) ?? 'estimated',
      startedAt: _asString(map['startedAt']),
      answeredAt: _asString(map['answeredAt']),
      endedAt: _asString(map['endedAt']),
      simAccountId: _asString(map['simAccountId']),
      simSubscriptionId: _asInt(map['simSubscriptionId']),
      simAccountComponent: _asString(map['simAccountComponent']),
      simIdentity: _asString(map['simIdentity']),
      simIdentityStatus: _asString(map['simIdentityStatus']),
      simLabel: _asString(map['simLabel']),
      simSlot: _asInt(map['simSlot']),
      simPhoneNumber: _asString(map['simPhoneNumber']),
      recordingUrl: _asString(map['recordingUrl']),
      recordingStatus:
          _asString(map['recordingStatus']) ?? 'RECORDING_UNAVAILABLE',
    );
  }
}

/// Bridges Flutter to the native Android SIM dialer and persists the resulting
/// call metadata through the existing CRM call-log API.
class MobileSimCallService {
  static const MethodChannel _channel = MethodChannel(
    'com.wacrm.mobile/sim_call',
  );

  static Future<void> Function(MobileSimCallResult result)? _onCallEnded;
  static void Function(Map<String, dynamic> recording)? _onSharedRecording;
  static bool _handlerAttached = false;

  static final Set<String> _syncedCallIds = <String>{};
  static final Map<String, int> _callRowIds = <String, int>{};
  static final Map<String, Future<bool>> _syncFutures =
      <String, Future<bool>>{};

  static bool get isSupported => Platform.isAndroid;

  /// Normalizes a direction that a native/bridge layer explicitly supplied.
  static String? normalizeDirection(Object? raw) {
    final value = (raw ?? '').toString().trim().toUpperCase();
    if (value == 'INBOUND' || value == 'OUTBOUND') return value;
    return null;
  }

  /// Mirrors Android `CallLog.Calls.TYPE`. Unknown types return null so no
  /// caller can accidentally default an inbound call to OUTBOUND.
  static String? directionForAndroidType(Object? rawType) {
    final type = rawType is num
        ? rawType.toInt()
        : int.tryParse((rawType ?? '').toString().trim());
    switch (type) {
      case 1: // INCOMING_TYPE
      case 3: // MISSED_TYPE
      case 5: // REJECTED_TYPE
      case 6: // BLOCKED_TYPE
      case 7: // ANSWERED_EXTERNALLY_TYPE
        return 'INBOUND';
      case 2: // OUTGOING_TYPE
        return 'OUTBOUND';
      default:
        return null;
    }
  }

  /// Installs one channel handler that dispatches both call results and
  /// shared-recording events. Installing a second handler (for example from
  /// the Call Logs tab) must never disconnect call-end synchronisation.
  static void _ensureChannelHandler() {
    if (_handlerAttached) return;
    _handlerAttached = true;

    _channel.setMethodCallHandler((call) async {
      if (call.method == 'onCallEnded' && call.arguments is Map) {
        final result = MobileSimCallResult.fromMap(
          Map<dynamic, dynamic>.from(call.arguments as Map),
        );
        final handler = _onCallEnded;
        if (handler != null) {
          await handler(result);
        }
      } else if (call.method == 'recordingShared' && call.arguments is Map) {
        _onSharedRecording?.call(
          Map<String, dynamic>.from(call.arguments as Map),
        );
      }
      return null;
    });
  }

  /// Registers the native -> Flutter callback. Call once from the app shell.
  static void attach({
    required Future<void> Function(MobileSimCallResult result) onCallEnded,
  }) {
    _onCallEnded = onCallEnded;
    _ensureChannelHandler();
  }

  /// Returns the current permission state without opening a system prompt.
  static Future<MobileSimPermissionStatus> permissionStatus() async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'getCallPermissionStatus',
    );
    return MobileSimPermissionStatus.fromMap(response ?? const {});
  }

  static Future<MobileSimPermissionStatus> requestPermissions() async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'requestCallPermissions',
    );
    return MobileSimPermissionStatus.fromMap(response ?? const {});
  }

  /// Creates the pending CRM call record *before* the Android dialer starts.
  ///
  /// The returned call id is the single reference used by the native tracker
  /// and every later sync, so the completed result updates this row instead of
  /// inserting a duplicate. A network failure never blocks the call: the same
  /// id is reused when the final result is delivered.
  static Future<String> beginAttempt({
    required String phone,
    int? leadId,
    String? contactName,
    SimAccount? sim,
  }) async {
    final callId = newCallId();
    final startedAt = DateTime.now().toUtc().toIso8601String();
    final identity = sim?.identityToken;
    // When an Office SIM is registered, an attempt from any other SIM must not
    // create a CRM row. The dialer already restricts selection, so this is a
    // second line of defence.
    final mapping = await OfficeSimService.fetch();
    if (mapping != null &&
        (sim == null ||
            !mapping.isVerified ||
            !OfficeSimService.callMatches(
              mapping,
              subscriptionId: sim.subscriptionId >= 0
                  ? sim.subscriptionId
                  : null,
              simAccountId: identity,
            ))) {
      return callId;
    }
    try {
      await CallsRepository()
          .logManualCall(
            customerPhone: phone,
            callStatus: 'INITIATED',
            durationSeconds: 0,
            leadId: leadId,
            notes: 'Mobile SIM call attempt from device dialer.',
            clientCallId: callId,
            callDirection: 'OUTBOUND',
            startedAt: startedAt,
            simAccountId: identity,
            simSubscriptionId: (sim?.subscriptionId ?? -1) >= 0
                ? sim!.subscriptionId
                : null,
            simLabel: sim?.label,
            simSlot: sim?.slotIndex,
            simPhoneNumber: sim?.phoneNumber,
            callSource: 'MOBILE_SIM',
          )
          .timeout(const Duration(seconds: 6));
    } catch (_) {
      // Offline / slow CRM: the native result still carries this same call id
      // and will create (or update) the row when connectivity returns.
    }
    return callId;
  }

  /// Closes a pending attempt that never reached the Android dialer.
  static Future<void> failAttempt({
    required String callId,
    required String phone,
    int? leadId,
    String? contactName,
    String? reason,
    SimAccount? sim,
  }) async {
    final identity = sim?.identityToken;
    final mapping = await OfficeSimService.fetch();
    if (mapping != null &&
        (sim == null ||
            !mapping.isVerified ||
            !OfficeSimService.callMatches(
              mapping,
              subscriptionId: sim.subscriptionId >= 0
                  ? sim.subscriptionId
                  : null,
              simAccountId: identity,
            ))) {
      return;
    }
    try {
      await CallsRepository()
          .logManualCall(
            customerPhone: phone,
            callStatus: 'FAILED',
            durationSeconds: 0,
            leadId: leadId,
            notes: reason == null || reason.trim().isEmpty
                ? 'Mobile SIM call could not be started.'
                : 'Mobile SIM call could not be started: $reason',
            clientCallId: callId,
            callDirection: 'OUTBOUND',
            startedAt: DateTime.now().toUtc().toIso8601String(),
            endedAt: DateTime.now().toUtc().toIso8601String(),
            simAccountId: identity,
            simSubscriptionId: (sim?.subscriptionId ?? -1) >= 0
                ? sim!.subscriptionId
                : null,
            simSlot: sim?.slotIndex,
            callSource: 'MOBILE_SIM',
          )
          .timeout(const Duration(seconds: 8));
    } catch (_) {
      // The pending row can be reconciled later; never block the UI.
    }
  }

  static Future<List<SimAccount>> getSimAccounts() async {
    final response = await _channel.invokeMethod<List<dynamic>>(
      'getSimAccounts',
    );
    if (response == null) return <SimAccount>[];
    return response
        .whereType<Map>()
        .map((item) => SimAccount.fromMap(Map<dynamic, dynamic>.from(item)))
        .toList();
  }

  static Future<void> openAppSettings() async {
    await _channel.invokeMethod<bool>('openAppSettings');
  }

  /// True when Android already allows this app to run background work without
  /// battery-optimization restrictions. Returns true when the OS cannot report
  /// the state, so the UI does not nag unnecessarily.
  static Future<bool> isIgnoringBatteryOptimizations() async {
    try {
      final response = await _channel.invokeMethod<bool>(
        'isIgnoringBatteryOptimizations',
      );
      return response ?? true;
    } catch (_) {
      return true;
    }
  }

  /// Opens the system battery-optimization list. WACRM never requests a
  /// broad exemption silently; the employee chooses it in Android settings.
  static Future<bool> openBatteryOptimizationSettings() async {
    try {
      final response = await _channel.invokeMethod<bool>(
        'openBatteryOptimizationSettings',
      );
      return response ?? false;
    } catch (_) {
      return false;
    }
  }

  /// Re-arms the native periodic worker and requests one immediate pass.
  static Future<void> scheduleAutomaticSync() async {
    await _channel.invokeMethod<bool>('scheduleAutomaticSync');
  }

  static Future<Map<String, dynamic>> startCall({
    required String phone,
    required String callId,
    int? leadId,
    String? contactName,
    SimAccount? sim,
  }) async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'startCall',
      {
        'phone': phone,
        'callId': callId,
        'leadId': leadId,
        'contactName': contactName,
        'subscriptionId': sim?.subscriptionId,
        'slotIndex': sim?.slotIndex,
        'simLabel': sim?.label,
        'simPhoneNumber': sim?.phoneNumber,
      },
    );
    return response == null
        ? <String, dynamic>{}
        : Map<String, dynamic>.from(response);
  }

  /// Returns a native result saved while the app was backgrounded or killed.
  /// It is not cleared until the backend sync succeeds.
  static Future<MobileSimCallResult?> consumePendingResult() async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'consumePendingResult',
    );
    if (response == null || response.isEmpty) return null;
    return MobileSimCallResult.fromMap(response);
  }

  static Future<void> clearPendingResult(String callId) async {
    try {
      await _channel.invokeMethod<bool>('clearPendingResult', {
        'callId': callId,
      });
    } on PlatformException {
      // A stale pending result is harmless because sync is idempotent.
    }
  }

  /// POSTs the device call metadata to the existing CRM manual-call API and
  /// refreshes the Call Logs provider. Safe to call more than once per call.
  static Future<bool> syncResult(
    MobileSimCallResult result,
    CallsProvider callsProvider,
  ) {
    if (result.callId.isEmpty) return Future<bool>.value(false);
    // Never send an unresolved direction. The backend also rejects device rows
    // without a direction, but failing here avoids a guaranteed rejected write
    // and keeps the native result pending until the type is understood.
    if (!result.hasKnownDirection) {
      debugPrint(
        '[MobileSIM] Skipped call ${result.callId}: direction is UNKNOWN.',
      );
      return Future<bool>.value(false);
    }
    if (_syncedCallIds.contains(result.callId)) return Future<bool>.value(true);

    final inFlight = _syncFutures[result.callId];
    if (inFlight != null) return inFlight;

    final future = _syncResultInternal(result, callsProvider);
    _syncFutures[result.callId] = future;
    future.whenComplete(() => _syncFutures.remove(result.callId));
    return future;
  }

  /// CRM row id created/updated for a live call result.
  static int? callRowId(String callId) => _callRowIds[callId];

  static Future<bool> _syncResultInternal(
    MobileSimCallResult result,
    CallsProvider callsProvider,
  ) async {
    if (!result.hasKnownDirection) return false;
    final identity = (result.simIdentity ?? '').trim().isNotEmpty
        ? result.simIdentity!.trim()
        : (result.simSubscriptionId != null
              ? 'subId:${result.simSubscriptionId}'
              : (result.simAccountId ?? '').trim());
    // Fail closed: once an Office SIM is registered, a live result from any
    // other SIM (or with no exact SIM identity) never reaches the CRM.
    final mapping = await OfficeSimService.fetch();
    if (mapping != null) {
      if (!mapping.isVerified ||
          !OfficeSimService.callMatches(
            mapping,
            subscriptionId: result.simSubscriptionId,
            simAccountId: identity,
          )) {
        return false;
      }
    }

    final repository = CallsRepository();
    debugPrint(
      '[CallDirection] Live result callId=${result.callId} '
      'nativeType=${result.androidCallType ?? "-"} '
      'phoneAccount=${result.simAccountId ?? "-"} '
      'subId=${result.simSubscriptionId ?? "-"} '
      'payloadDirection=${result.callDirection.isEmpty ? "-" : result.callDirection}',
    );
    try {
      final response = await repository.logManualCall(
        customerNumber: result.customerPhone,
        callStatus: result.callStatus,
        durationSeconds: result.durationSeconds,
        leadId: result.leadId,
        notes: result.syncNotes,
        clientCallId: result.callId,
        callDirection: result.callDirection.isEmpty
            ? null
            : result.callDirection,
        startedAt: result.startedAt,
        answeredAt: result.answeredAt,
        endedAt: result.endedAt,
        recordingUrl: result.hasRecording ? result.recordingUrl : null,
        simAccountId: identity.isEmpty ? null : identity,
        simSubscriptionId: result.simSubscriptionId,
        simLabel: result.simLabel,
        simSlot: result.simSlot,
        simPhoneNumber: result.simPhoneNumber,
        callSource: 'MOBILE_SIM',
        nativeCallReference: result.nativeCallReference,
      );
      _syncedCallIds.add(result.callId);
      final rowId = _asInt(response?['id']);
      if (rowId != null) _callRowIds[result.callId] = rowId;
      await clearPendingResult(result.callId);
      await callsProvider.fetchCalls(showLoading: false);
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Opens the Android document picker for an audio file. Returns null when
  /// the employee cancels.
  static Future<Map<String, dynamic>?> pickRecordingFile() async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'pickRecordingFile',
    );
    if (response == null || response.isEmpty) return null;
    return Map<String, dynamic>.from(response);
  }

  /// Returns an audio file shared into WACRM from the OEM recorder or file
  /// manager, then clears it so the same file is not offered twice.
  static Future<Map<String, dynamic>?> consumeSharedRecordingFile() async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'consumeSharedRecordingFile',
    );
    if (response == null || response.isEmpty) return null;
    return Map<String, dynamic>.from(response);
  }

  /// Called when Android delivers a shared recording while the app is open.
  /// This keeps the call-end handler installed on the same channel.
  static void setSharedRecordingHandler(
    void Function(Map<String, dynamic> recording)? handler,
  ) {
    _onSharedRecording = handler;
    _ensureChannelHandler();
  }

  /// Plays an authenticated recording through the device's media player.
  static Future<void> playRecording({
    required String url,
    required String token,
  }) async {
    await _channel.invokeMethod<bool>('playRecording', {
      'url': url,
      'token': token,
    });
  }

  static Future<void> stopRecordingPlayback() async {
    await _channel.invokeMethod<bool>('stopRecordingPlayback');
  }

  /// Returns recent native call-log rows. Requires READ_CALL_LOG; the native
  /// layer reports PERMISSION_DENIED when it is missing.
  /// Returns recent native call-log rows. Requires READ_CALL_LOG; the native
  /// layer reports PERMISSION_DENIED when it is missing.
  static Future<List<Map<String, dynamic>>> getRecentDeviceCalls({
    required DateTime since,
    int limit = 200,
  }) async {
    final response = await _channel.invokeMethod<List<dynamic>>(
      'getRecentDeviceCalls',
      {'sinceMillis': since.toUtc().millisecondsSinceEpoch, 'limit': limit},
    );
    if (response == null) return <Map<String, dynamic>>[];
    return response.whereType<Map>().map((item) {
      return Map<String, dynamic>.from(item);
    }).toList();
  }

  static Future<Map<String, dynamic>?> getDeviceCallLogBaseline() async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'getDeviceCallLogBaseline',
    );
    if (response == null) return null;
    return Map<String, dynamic>.from(response);
  }

  static Future<({List<Map<String, dynamic>> rows, bool hasMore})>
  getDeviceCallsIncremental({
    required int afterDateMillis,
    required int afterId,
    int graceMillis = 0,
    int limit = 250,
  }) async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'getDeviceCallsIncremental',
      {
        'afterDateMillis': afterDateMillis,
        'afterId': afterId,
        'graceMillis': graceMillis,
        'limit': limit,
      },
    );
    if (response == null) {
      return (rows: <Map<String, dynamic>>[], hasMore: false);
    }
    final rawRows = response['rows'];
    final rows = rawRows is List
        ? rawRows
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList()
        : <Map<String, dynamic>>[];
    return (rows: rows, hasMore: response['hasMore'] == true);
  }

  /// Looks for exactly one device audio file that matches this native call.
  /// Returns null when no unambiguous recording exists.
  static Future<Map<String, dynamic>?> findDeviceRecording({
    required String phone,
    required DateTime startedAt,
    DateTime? endedAt,
    required int durationSeconds,
  }) async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'findDeviceRecording',
      {
        'phone': phone,
        'startedAtMillis': startedAt.toUtc().millisecondsSinceEpoch,
        'endedAtMillis': endedAt?.toUtc().millisecondsSinceEpoch,
        'durationSeconds': durationSeconds,
      },
    );
    if (response == null || response.isEmpty) return null;
    return Map<String, dynamic>.from(response);
  }

  static String newCallId() {
    final random = Random.secure();
    final suffix = random.nextInt(1 << 32).toRadixString(16).padLeft(8, '0');
    return 'SIM_${DateTime.now().toUtc().millisecondsSinceEpoch}_$suffix';
  }
}

int? _asInt(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  return int.tryParse(value.toString());
}

String? _asString(dynamic value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}
