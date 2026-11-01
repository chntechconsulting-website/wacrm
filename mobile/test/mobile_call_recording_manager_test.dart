import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mobile/core/services/mobile_call_recording_manager.dart';
import 'package:mobile/features/calls/models/call_log_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Recording status mapping', () {
    test('maps legacy and canonical backend values', () {
      expect(
        RecordingSyncStatus.fromApi('RECORDING_AVAILABLE'),
        RecordingSyncStatus.available,
      );
      expect(
        RecordingSyncStatus.fromApi('RECORDING_PROCESSING'),
        RecordingSyncStatus.pendingSync,
      );
      expect(
        RecordingSyncStatus.fromApi('PENDING_SYNC'),
        RecordingSyncStatus.pendingSync,
      );
      expect(
        RecordingSyncStatus.fromApi('UPLOAD_FAILED'),
        RecordingSyncStatus.uploadFailed,
      );
      expect(
        RecordingSyncStatus.fromApi('VERIFICATION_FAILED'),
        RecordingSyncStatus.verificationFailed,
      );
      expect(
        RecordingSyncStatus.fromApi('WHATEVER'),
        RecordingSyncStatus.recordingUnavailable,
      );
    });

    test('exposes API values and retry flags', () {
      expect(RecordingSyncStatus.available.apiValue, 'AVAILABLE');
      expect(RecordingSyncStatus.pendingSync.label, 'Pending Sync');
      expect(RecordingSyncStatus.uploadFailed.canRetry, isTrue);
      expect(RecordingSyncStatus.recordingUnavailable.canRetry, isFalse);
    });

    test('call log model prefers a real URL over a stale status', () {
      final call = CallLogModel.fromJson(<String, dynamic>{
        'id': 5,
        'customer_phone': '9999999999',
        'call_status': 'COMPLETED',
        'provider': 'MOBILE_SIM',
        'recording_status': 'UPLOAD_FAILED',
        'recording_url': 'https://cdn.example/call.mp3',
      });

      expect(call.recordingSyncStatus, RecordingSyncStatus.available);
      expect(call.isRecordingAvailable, isTrue);
    });
  });

  group('Recording capability parsing', () {
    test('parses native capability and diagnostics', () {
      final capability = RecordingCapability.fromMap(<String, dynamic>{
        'manufacturer': 'vivo',
        'model': 'V2310',
        'androidVersion': '14',
        'androidSdk': 34,
        'oemFamily': 'VIVO',
        'nativeDialerPackage': 'com.vivo.dialer',
        'callLogPermission': true,
        'audioPermission': true,
        'safSupported': true,
        'mediaStoreAccessible': true,
        'oemRecordingMayExist': true,
        'recordingCapability': 'AUTOMATIC_MEDIASTORE',
        'automaticSyncSupported': true,
        'manualImportSupported': true,
        'mediaStoreRecordingCount': 12,
        'recordingFolderHints': ['Recordings/Call/'],
        'recentMediaStoreRecordings': [
          {'name': 'CallRecord_9999999999.m4a', 'durationMs': 30000},
        ],
        'notes': ['Recording files are provided by the OEM dialer.'],
      });

      expect(capability.hasAutomaticDiscovery, isTrue);
      expect(capability.platformLabel, 'vivo V2310');
      expect(capability.mediaStoreRecordingCount, 12);
      expect(capability.recordingFolderHints, ['Recordings/Call/']);
      expect(capability.recentMediaStoreRecordings, hasLength(1));
      expect(capability.notes.single, contains('OEM'));
    });

    test('treats unverified devices as manual-import only', () {
      final capability = RecordingCapability.fromMap(<String, dynamic>{
        'manufacturer': 'Unknown',
        'androidSdk': 29,
        'recordingCapability': 'MANUAL_IMPORT_ONLY',
        'automaticSyncSupported': false,
        'manualImportSupported': true,
      });

      expect(capability.hasAutomaticDiscovery, isFalse);
      expect(capability.manualImportSupported, isTrue);
    });
  });

  group('Recording consent', () {
    test('is per employee and can be revoked', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});

      expect(await RecordingConsentService.hasConsent('7'), isFalse);
      await RecordingConsentService.grant('7');
      expect(await RecordingConsentService.hasConsent('7'), isTrue);
      expect(await RecordingConsentService.hasConsent('8'), isFalse);
      expect(await RecordingConsentService.consentAt('7'), isNotNull);

      await RecordingConsentService.revoke('7');
      expect(await RecordingConsentService.hasConsent('7'), isFalse);
    });
  });
}
