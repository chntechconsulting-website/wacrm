import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/services.dart';

import '../../features/calls/data/calls_repository.dart';
import '../../features/calls/providers/calls_provider.dart';

/// A SIM subscription reported by Android's SubscriptionManager.
class SimAccount {
  final int subscriptionId;
  final int slotIndex;
  final String carrierName;
  final String displayName;
  final String? phoneNumber;
  final bool isDefault;

  const SimAccount({
    required this.subscriptionId,
    required this.slotIndex,
    required this.carrierName,
    required this.displayName,
    this.phoneNumber,
    this.isDefault = false,
  });

  String get label {
    if (displayName.trim().isNotEmpty) return displayName.trim();
    if (carrierName.trim().isNotEmpty) return carrierName.trim();
    return 'SIM ${slotIndex + 1}';
  }

  factory SimAccount.fromMap(Map<dynamic, dynamic> map) {
    return SimAccount(
      subscriptionId: _asInt(map['subscriptionId']) ?? -1,
      slotIndex: _asInt(map['slotIndex']) ?? 0,
      carrierName: _asString(map['carrierName']) ?? '',
      displayName: _asString(map['displayName']) ?? '',
      phoneNumber: _asString(map['phoneNumber']),
      isDefault: map['isDefault'] == true,
    );
  }
}

class MobileSimPermissionStatus {
  final bool callPhone;
  final bool readPhoneState;
  final bool readCallLog;
  final bool readPhoneNumbers;

  const MobileSimPermissionStatus({
    required this.callPhone,
    required this.readPhoneState,
    required this.readCallLog,
    required this.readPhoneNumbers,
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
    );
  }
}

/// Result produced by the native Android layer when a device call ends.
class MobileSimCallResult {
  final String callId;
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
  final String? simLabel;
  final int? simSlot;
  final String? simPhoneNumber;
  final String? recordingUrl;
  final String recordingStatus;

  const MobileSimCallResult({
    required this.callId,
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
    this.simLabel,
    this.simSlot,
    this.simPhoneNumber,
    this.recordingUrl,
    this.recordingStatus = 'RECORDING_UNAVAILABLE',
  });

  bool get hasRecording =>
      recordingUrl != null && recordingUrl!.trim().isNotEmpty;

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
      leadId: _asInt(map['leadId']),
      customerPhone: _asString(map['customerPhone']) ?? '',
      contactName: _asString(map['contactName']),
      callDirection: (_asString(map['callDirection']) ?? 'OUTBOUND')
          .toUpperCase(),
      callStatus: (_asString(map['callStatus']) ?? 'COMPLETED').toUpperCase(),
      durationSeconds: _asInt(map['durationSeconds']) ?? 0,
      durationAccuracy: _asString(map['durationAccuracy']) ?? 'estimated',
      startedAt: _asString(map['startedAt']),
      answeredAt: _asString(map['answeredAt']),
      endedAt: _asString(map['endedAt']),
      simAccountId: _asString(map['simAccountId']),
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
  static bool _handlerAttached = false;

  static final Set<String> _syncedCallIds = <String>{};
  static final Map<String, Future<bool>> _syncFutures =
      <String, Future<bool>>{};

  static bool get isSupported => Platform.isAndroid;

  /// Registers the native -> Flutter callback. Call once from the app shell.
  static void attach({
    required Future<void> Function(MobileSimCallResult result) onCallEnded,
  }) {
    _onCallEnded = onCallEnded;
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
      }
    });
  }

  static Future<MobileSimPermissionStatus> requestPermissions() async {
    final response = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'requestCallPermissions',
    );
    return MobileSimPermissionStatus.fromMap(response ?? const {});
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
    if (_syncedCallIds.contains(result.callId)) return Future<bool>.value(true);

    final inFlight = _syncFutures[result.callId];
    if (inFlight != null) return inFlight;

    final future = _syncResultInternal(result, callsProvider);
    _syncFutures[result.callId] = future;
    future.whenComplete(() => _syncFutures.remove(result.callId));
    return future;
  }

  static Future<bool> _syncResultInternal(
    MobileSimCallResult result,
    CallsProvider callsProvider,
  ) async {
    final repository = CallsRepository();
    try {
      await repository.logManualCall(
        customerNumber: result.customerPhone,
        callStatus: result.callStatus,
        durationSeconds: result.durationSeconds,
        leadId: result.leadId,
        notes: result.syncNotes,
        clientCallId: result.callId,
        callDirection: result.callDirection,
        startedAt: result.startedAt,
        answeredAt: result.answeredAt,
        endedAt: result.endedAt,
        recordingUrl: result.hasRecording ? result.recordingUrl : null,
        simAccountId: result.simAccountId,
        simLabel: result.simLabel,
        simSlot: result.simSlot,
        simPhoneNumber: result.simPhoneNumber,
        callSource: 'MOBILE_SIM',
      );
      _syncedCallIds.add(result.callId);
      await clearPendingResult(result.callId);
      await callsProvider.fetchCalls(showLoading: false);
      return true;
    } catch (_) {
      return false;
    }
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
