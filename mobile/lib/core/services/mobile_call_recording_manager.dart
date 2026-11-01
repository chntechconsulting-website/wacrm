import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/calls/providers/calls_provider.dart';
import '../constants/api_endpoints.dart';
import '../network/api_client.dart';
import '../network/api_exceptions.dart';
import 'mobile_recording_service.dart';

/// Canonical recording lifecycle shared with the backend.
enum RecordingSyncStatus {
  available,
  pendingSync,
  recordingUnavailable,
  uploadFailed,
  verificationFailed;

  static RecordingSyncStatus fromApi(String? raw) {
    switch ((raw ?? '').trim().toUpperCase()) {
      case 'AVAILABLE':
      case 'RECORDING_AVAILABLE':
        return RecordingSyncStatus.available;
      case 'PENDING_SYNC':
      case 'RECORDING_PROCESSING':
      case 'PROCESSING':
      case 'PENDING':
        return RecordingSyncStatus.pendingSync;
      case 'UPLOAD_FAILED':
        return RecordingSyncStatus.uploadFailed;
      case 'VERIFICATION_FAILED':
        return RecordingSyncStatus.verificationFailed;
      default:
        return RecordingSyncStatus.recordingUnavailable;
    }
  }

  String get apiValue {
    switch (this) {
      case RecordingSyncStatus.available:
        return 'AVAILABLE';
      case RecordingSyncStatus.pendingSync:
        return 'PENDING_SYNC';
      case RecordingSyncStatus.uploadFailed:
        return 'UPLOAD_FAILED';
      case RecordingSyncStatus.verificationFailed:
        return 'VERIFICATION_FAILED';
      case RecordingSyncStatus.recordingUnavailable:
        return 'RECORDING_UNAVAILABLE';
    }
  }

  String get label {
    switch (this) {
      case RecordingSyncStatus.available:
        return 'Available';
      case RecordingSyncStatus.pendingSync:
        return 'Pending Sync';
      case RecordingSyncStatus.uploadFailed:
        return 'Upload Failed';
      case RecordingSyncStatus.verificationFailed:
        return 'Verification Failed';
      case RecordingSyncStatus.recordingUnavailable:
        return 'Recording Unavailable';
    }
  }

  bool get canRetry =>
      this == RecordingSyncStatus.uploadFailed ||
      this == RecordingSyncStatus.verificationFailed ||
      this == RecordingSyncStatus.pendingSync;
}

/// Runtime Android/OEM recording capability reported by the native module.
@immutable
class RecordingCapability {
  final String manufacturer;
  final String brand;
  final String model;
  final String androidVersion;
  final int androidSdk;
  final String oemFamily;
  final String? nativeDialerPackage;
  final List<String> oemRecorderPackages;
  final bool callLogPermission;
  final bool audioPermission;
  final bool safSupported;
  final bool mediaStoreAccessible;
  final bool oemRecordingMayExist;
  final String oemRecordingSupport;
  final String recordingCapability;
  final bool automaticSyncSupported;
  final bool manualImportSupported;
  final int mediaStoreRecordingCount;
  final List<String> recordingFolderHints;
  final List<Map<String, dynamic>> recentMediaStoreRecordings;
  final List<String> notes;

  const RecordingCapability({
    this.manufacturer = '',
    this.brand = '',
    this.model = '',
    this.androidVersion = '',
    this.androidSdk = 0,
    this.oemFamily = 'OTHER',
    this.nativeDialerPackage,
    this.oemRecorderPackages = const [],
    this.callLogPermission = false,
    this.audioPermission = false,
    this.safSupported = true,
    this.mediaStoreAccessible = false,
    this.oemRecordingMayExist = false,
    this.oemRecordingSupport = 'NO_KNOWN_OEM_RECORDING',
    this.recordingCapability = 'MANUAL_IMPORT_ONLY',
    this.automaticSyncSupported = false,
    this.manualImportSupported = true,
    this.mediaStoreRecordingCount = 0,
    this.recordingFolderHints = const [],
    this.recentMediaStoreRecordings = const [],
    this.notes = const [],
  });

  factory RecordingCapability.fromMap(Map<String, dynamic> map) {
    final recents = (map['recentMediaStoreRecordings'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
    return RecordingCapability(
      manufacturer: (map['manufacturer'] ?? '').toString(),
      brand: (map['brand'] ?? '').toString(),
      model: (map['model'] ?? '').toString(),
      androidVersion: (map['androidVersion'] ?? '').toString(),
      androidSdk: (map['androidSdk'] as num?)?.toInt() ?? 0,
      oemFamily: (map['oemFamily'] ?? 'OTHER').toString(),
      nativeDialerPackage: map['nativeDialerPackage']?.toString(),
      oemRecorderPackages: (map['oemRecorderPackages'] as List? ?? const [])
          .map((item) => item.toString())
          .toList(),
      callLogPermission: map['callLogPermission'] == true,
      audioPermission: map['audioPermission'] == true,
      safSupported: map['safSupported'] != false,
      mediaStoreAccessible: map['mediaStoreAccessible'] == true,
      oemRecordingMayExist: map['oemRecordingMayExist'] == true,
      oemRecordingSupport: (map['oemRecordingSupport'] ?? '').toString(),
      recordingCapability: (map['recordingCapability'] ?? 'MANUAL_IMPORT_ONLY')
          .toString(),
      automaticSyncSupported: map['automaticSyncSupported'] == true,
      manualImportSupported: map['manualImportSupported'] != false,
      mediaStoreRecordingCount:
          (map['mediaStoreRecordingCount'] as num?)?.toInt() ?? 0,
      recordingFolderHints:
          (map['recordingFolderHints'] as List? ?? const [])
              .map((item) => item.toString())
              .toList(),
      recentMediaStoreRecordings: recents,
      notes: (map['notes'] as List? ?? const [])
          .map((item) => item.toString())
          .toList(),
    );
  }

  bool get hasAutomaticDiscovery =>
      automaticSyncSupported && recordingCapability == 'AUTOMATIC_MEDIASTORE';
}

/// A recording that passed native metadata/integrity checks.
@immutable
class ImportedCallRecording {
  final String path;
  final String name;
  final int size;
  final String mimeType;
  final int durationMs;
  final String checksum;
  final String source;
  final bool verified;
  final String? matchedBy;

  const ImportedCallRecording({
    required this.path,
    required this.name,
    required this.size,
    required this.mimeType,
    required this.durationMs,
    required this.checksum,
    required this.source,
    required this.verified,
    this.matchedBy,
  });

  factory ImportedCallRecording.fromMap(Map<String, dynamic> map) {
    return ImportedCallRecording(
      path: (map['path'] ?? '').toString(),
      name: (map['name'] ?? 'call-recording').toString(),
      size: (map['size'] as num?)?.toInt() ?? 0,
      mimeType: (map['mimeType'] ?? 'audio/*').toString(),
      durationMs: (map['durationMs'] as num?)?.toInt() ?? 0,
      checksum: (map['checksum'] ?? '').toString(),
      source: (map['source'] ?? 'SAF_IMPORT').toString(),
      verified: map['verified'] == true,
      matchedBy: map['matchedBy']?.toString(),
    );
  }

  int get durationSeconds => (durationMs / 1000).round();

  PickedRecording toPickedRecording() => PickedRecording(
    path: path,
    name: name,
    size: size,
    mimeType: mimeType,
    durationSeconds: durationSeconds > 0 ? durationSeconds : null,
  );
}

enum RecordingUploadOutcome {
  uploaded,
  duplicate,
  consentRequired,
  verificationFailed,
  uploadFailed,
}

/// Result of an explicit SAF import attempt. Cancellation is deliberately
/// separate from “no match” so backing out of the picker is silent.
class RecordingPickResult {
  final ImportedCallRecording? recording;
  final bool cancelled;

  const RecordingPickResult({this.recording, this.cancelled = false});

  static const RecordingPickResult empty = RecordingPickResult();
}

/// Separate Flutter module for Mobile SIM call recording import and sync.
///
/// This module never records audio. It only asks Android for capability data,
/// opens the user-authorised document picker, performs a strict read-only
/// MediaStore lookup for an exact call, and uploads verified files to the
/// existing CRM recording endpoint.
class MobileCallRecordingManager {
  static const MethodChannel _channel = MethodChannel(
    'wacrm/mobile_call_recording',
  );
  static final ApiClient _client = ApiClient();

  static bool get isSupported => !kIsWeb && Platform.isAndroid;

  static Future<RecordingCapability> capability() async {
    if (!isSupported) return const RecordingCapability();
    try {
      final map = await _channel.invokeMethod<Map<dynamic, dynamic>>(
        'getCapability',
      );
      if (map == null) return const RecordingCapability();
      return RecordingCapability.fromMap(Map<String, dynamic>.from(map));
    } on PlatformException {
      return const RecordingCapability();
    } on MissingPluginException {
      return const RecordingCapability();
    }
  }

  /// Opens SAF. The employee explicitly chooses a file; persistent read access
  /// is requested but a verified cache copy is used for the upload.
  static Future<RecordingPickResult> pickRecordingFile() async {
    if (!isSupported) return RecordingPickResult.empty;
    final map = await _channel.invokeMethod<Map<dynamic, dynamic>>(
      'pickRecordingFile',
    );
    if (map == null) return RecordingPickResult.empty;
    final decoded = Map<String, dynamic>.from(map);
    if (decoded['cancelled'] == true) {
      return const RecordingPickResult(cancelled: true);
    }
    if (decoded['path'] == null) return RecordingPickResult.empty;
    return RecordingPickResult(recording: ImportedCallRecording.fromMap(decoded));
  }

  /// Strict automatic lookup. Returns null unless exactly one file matches the
  /// call by phone, direction-independent duration and time window.
  static Future<ImportedCallRecording?> findRecordingForCall({
    required String phone,
    required DateTime startedAt,
    DateTime? endedAt,
    required int durationSeconds,
  }) async {
    if (!isSupported || durationSeconds <= 0) return null;
    try {
      final map = await _channel.invokeMethod<Map<dynamic, dynamic>>(
        'findRecordingForCall',
        {
          'phone': phone,
          'startedAtMillis': startedAt.toUtc().millisecondsSinceEpoch,
          'endedAtMillis': endedAt?.toUtc().millisecondsSinceEpoch,
          'durationSeconds': durationSeconds,
        },
      );
      if (map == null || map.isEmpty) return null;
      return ImportedCallRecording.fromMap(Map<String, dynamic>.from(map));
    } on PlatformException {
      return null;
    } on MissingPluginException {
      return null;
    }
  }

  /// Uploads a verified file and mirrors the resulting status to the backend.
  static Future<RecordingUploadOutcome> upload({
    required int callId,
    required ImportedCallRecording recording,
    required bool consent,
    required int callDurationSeconds,
  }) async {
    if (!consent) {
      await reportStatus(
        callId: callId,
        status: RecordingSyncStatus.pendingSync,
        detail: 'Awaiting employee consent for device recording import.',
      );
      return RecordingUploadOutcome.consentRequired;
    }
    if (!recording.verified || recording.durationMs <= 0) {
      await reportStatus(
        callId: callId,
        status: RecordingSyncStatus.verificationFailed,
        detail: 'Recording metadata could not be verified on the device.',
      );
      return RecordingUploadOutcome.verificationFailed;
    }
    if (!File(recording.path).existsSync()) {
      await reportStatus(
        callId: callId,
        status: RecordingSyncStatus.uploadFailed,
        detail: 'The imported recording file is no longer available.',
      );
      return RecordingUploadOutcome.uploadFailed;
    }
    if (callDurationSeconds > 0) {
      final tolerance = callDurationSeconds < 20
          ? 20
          : (callDurationSeconds * 0.30).round();
      if ((recording.durationSeconds - callDurationSeconds).abs() > tolerance) {
        await reportStatus(
          callId: callId,
          status: RecordingSyncStatus.verificationFailed,
          detail:
              'Recording duration ${recording.durationSeconds}s does not match '
              'call duration ${callDurationSeconds}s.',
        );
        return RecordingUploadOutcome.verificationFailed;
      }
    }
    try {
      await _client.postMultipart(
        ApiEndpoints.ivrCallRecording(callId),
        file: File(recording.path),
        fields: {
          'source': 'DEVICE',
          'consent': 'true',
          'duration_seconds': '${recording.durationSeconds}',
          'checksum': recording.checksum,
        },
      );
      await reportStatus(
        callId: callId,
        status: RecordingSyncStatus.available,
        detail: 'Device recording verified and uploaded.',
      );
      return RecordingUploadOutcome.uploaded;
    } on ApiException catch (error) {
      final status = (error.statusCode ?? 0) == 422
          ? RecordingSyncStatus.verificationFailed
          : RecordingSyncStatus.uploadFailed;
      await reportStatus(
        callId: callId,
        status: status,
        detail: error.message,
      );
      return status == RecordingSyncStatus.verificationFailed
          ? RecordingUploadOutcome.verificationFailed
          : RecordingUploadOutcome.uploadFailed;
    } catch (error) {
      await reportStatus(
        callId: callId,
        status: RecordingSyncStatus.uploadFailed,
        detail: error.toString(),
      );
      return RecordingUploadOutcome.uploadFailed;
    }
  }

  static Future<void> reportStatus({
    required int callId,
    required RecordingSyncStatus status,
    String? detail,
  }) async {
    try {
      await _channel.invokeMethod<bool>('setUploadStatus', {
        'callId': '$callId',
        'status': status.apiValue,
        'detail': detail ?? '',
      });
    } catch (_) {
      // Local diagnostics are best-effort.
    }
    try {
      if (status != RecordingSyncStatus.available) {
        await _client.post(
          ApiEndpoints.ivrCallRecordingStatus(callId),
          body: {'status': status.apiValue, 'detail': detail},
        );
      }
    } catch (_) {
      // The call log still reflects the last known backend status.
    }
  }

  static Future<Map<String, dynamic>?> lastUploadStatus(int callId) async {
    if (!isSupported) return null;
    try {
      final map = await _channel.invokeMethod<Map<dynamic, dynamic>>(
        'getUploadStatus',
        {'callId': '$callId'},
      );
      return map == null ? null : Map<String, dynamic>.from(map);
    } catch (_) {
      return null;
    }
  }

  /// Applies the same consent check to every automatic history sync.
  static Future<bool> automaticSyncAllowed(String employeeKey) =>
      RecordingConsentService.hasConsent(employeeKey);

  /// Refreshes call logs after an upload changed recording availability.
  static Future<void> refresh(CallsProvider provider) =>
      provider.fetchCalls(showLoading: false);
}

/// Explicit, revocable recording-import disclosure. Stored per employee; no
/// device recording is read or uploaded until this is accepted.
class RecordingConsentService {
  static const String _consentKey = 'wacrm_recording_consent';
  static const String disclosureText =
      'WACRM does not record calls. It can import a recording that your '
      'phone\'s dialer or recorder has already created, and attach it to the '
      'matching CRM call log. By continuing you confirm that you are '
      'authorised to store and share this recording, and that all parties '
      'have been informed as required by your organisation and local law. '
      'You can revoke this permission at any time.';

  static Future<bool> hasConsent(String employeeKey) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_key(employeeKey)) ?? false;
  }

  static Future<DateTime?> consentAt(String employeeKey) async {
    final prefs = await SharedPreferences.getInstance();
    final ms = prefs.getInt('${_key(employeeKey)}_at');
    return ms == null
        ? null
        : DateTime.fromMillisecondsSinceEpoch(ms, isUtc: true);
  }

  static Future<void> grant(String employeeKey) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key(employeeKey), true);
    await prefs.setInt(
      '${_key(employeeKey)}_at',
      DateTime.now().toUtc().millisecondsSinceEpoch,
    );
  }

  static Future<void> revoke(String employeeKey) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key(employeeKey));
    await prefs.remove('${_key(employeeKey)}_at');
  }

  /// Shows the disclosure once. Returns true when consent is available.
  static Future<bool> ensureConsent(
    BuildContext context, {
    required String employeeKey,
  }) async {
    if (await hasConsent(employeeKey)) return true;
    if (!context.mounted) return false;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(
          'Recording import consent',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Please read before importing a Mobile SIM recording.',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 10),
              const Text(
                disclosureText,
                style: TextStyle(fontSize: 13, height: 1.45),
              ),
              const SizedBox(height: 12),
              const Text(
                'No Accessibility API, hidden microphone, root or security '
                'bypass is used. Files are read only through Android\'s system '
                'picker or media access that you authorise.',
                style: TextStyle(fontSize: 12, height: 1.4),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Not now'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('I agree'),
          ),
        ],
      ),
    );
    if (accepted == true) {
      await grant(employeeKey);
      return true;
    }
    return false;
  }

  static String _key(String employeeKey) {
    final scope = employeeKey.trim().isEmpty ? 'default' : employeeKey.trim();
    return '${_consentKey}_$scope';
  }
}

/// Diagnostics for the employee-facing capability sheet.
extension RecordingCapabilitySummary on RecordingCapability {
  String get platformLabel => [
    manufacturer.trim(),
    model.trim(),
  ].where((part) => part.isNotEmpty).join(' ');

  String get automaticSyncLabel => automaticSyncSupported
      ? 'Automatic MediaStore discovery available'
      : 'Manual import only (audio access not granted)';

  String get oemSupportLabel {
    switch (oemRecordingSupport) {
      case 'OEM_DIALER_RECORDING_MAY_EXIST_NO_PUBLIC_API':
        return 'OEM dialer may offer call recording (no public Android API)';
      case 'NO_KNOWN_OEM_RECORDING':
        return 'No known OEM recording capability detected';
      default:
        return 'Recording support not verified on this device';
    }
  }
}
