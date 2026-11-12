import 'package:flutter/services.dart';

import '../constants/api_endpoints.dart';
import '../network/token_storage.dart';
import 'device_call_log_sync_service.dart';
import 'mobile_sim_call_service.dart';

/// Runs the existing device call-log pipeline from a headless Flutter engine.
///
/// The Android WorkManager worker starts a background engine and invokes
/// [backgroundCallSyncMain] from `main.dart`. This class restores the employee
/// session exactly as the UI would, then reports the outcome so WorkManager can
/// retry transient failures with backoff.
class AutomaticCallSyncService {
  static const MethodChannel _completionChannel = MethodChannel(
    'com.wacrm.mobile/background_call_sync',
  );

  static Future<void> runBackgroundSync() async {
    try {
      final serverUrl = (await TokenStorage.getServerUrl())?.trim();
      if (serverUrl != null && serverUrl.isNotEmpty) {
        ApiEndpoints.baseUrl = serverUrl;
      }

      final token = (await TokenStorage.getToken())?.trim();
      final user = await TokenStorage.getUserData();
      if (token == null || token.isEmpty || user == null) {
        await _finish(
          success: false,
          retry: false,
          reason: 'NOT_AUTHENTICATED',
        );
        return;
      }

      final employeeKey =
          (user['id'] ?? user['employee_id'] ?? user['user_id'] ?? '')
              .toString()
              .trim();
      if (employeeKey.isEmpty) {
        await _finish(success: false, retry: false, reason: 'EMPLOYEE_UNKNOWN');
        return;
      }

      final result = await DeviceCallLogSyncService.sync(
        null,
        employeeKey: employeeKey,
        // The worker registers the same read-only recording bridge as the UI,
        // so WorkManager can discover and upload OEM/dialer recordings while
        // the app is closed.
        autoUploadRecordings: true,
        // Never persist a SIM verification failure from a background pass;
        // SIM reads can be temporarily unavailable at boot or under OEM
        // battery restrictions. The pass still fails closed.
        reportSimChanges: false,
      );

      await _finish(
        success: result.error == null || result.synced > 0,
        retry: result.shouldRetry,
        synced: result.synced,
        pending: result.pendingSyncCount,
        retryablePending: result.retryablePending,
        recordingsPending: result.recordingsPending,
        recordingRetryablePending: result.recordingRetryablePending,
        permissionDenied: result.permissionDenied,
        error: result.error,
      );
    } catch (error) {
      await _finish(
        success: false,
        retry: error is! MissingPluginException,
        error: error.toString(),
        reason: 'UNEXPECTED',
      );
    }
  }

  /// Asks the native scheduler for an immediate background pass. Used after
  /// enabling sync so the first call does not wait for the 15-minute period.
  static Future<void> scheduleOneOffSync() async {
    try {
      await MobileSimCallService.scheduleAutomaticSync();
    } catch (_) {
      // The periodic worker remains the fallback.
    }
  }

  static Future<void> _finish({
    required bool success,
    required bool retry,
    int? synced,
    int? pending,
    int? retryablePending,
    int? recordingsPending,
    int? recordingRetryablePending,
    bool permissionDenied = false,
    String? error,
    String? reason,
  }) async {
    try {
      await _completionChannel.invokeMethod<void>('syncFinished', {
        'success': success,
        'retry': retry,
        'synced': synced ?? 0,
        'pending': pending ?? 0,
        'retryablePending': retryablePending ?? 0,
        'recordingsPending': recordingsPending ?? 0,
        'recordingRetryablePending': recordingRetryablePending ?? 0,
        'permissionDenied': permissionDenied,
        'error': error,
        'reason': reason,
      });
    } catch (_) {
      // The engine may already be shutting down; the queue remains durable.
    }
  }
}
