import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mobile/core/network/api_exceptions.dart';
import 'package:mobile/core/services/device_call_log_sync_service.dart';
import 'package:mobile/core/services/pending_call_sync_queue.dart';

Map<String, dynamic> _row(String reference, {int date = 1000, int id = 1}) {
  return <String, dynamic>{
    'nativeCallReference': reference,
    'deviceCallLogId': id,
    'phone': '+919999999999',
    'direction': 'INBOUND',
    'type': 1,
    'status': 'COMPLETED',
    'dateMillis': date,
    'durationSeconds': 12,
    'startedAt': '2026-01-01T10:00:00.000Z',
    'endedAt': '2026-01-01T10:00:12.000Z',
    'simIdentity': 'subId:1',
    'simIdentityStatus': 'RESOLVED',
    'simSubscriptionId': 1,
    'simSlotIndex': 0,
  };
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  group('PendingCallSyncQueue', () {
    test('persists a row until the backend confirms it', () async {
      final queue = PendingCallSyncQueue('42');
      await queue.reload();
      final entry = await queue.enqueue(_row('MOBILE_device_1'));
      expect(entry, isNotNull);
      expect(queue.count, 1);
      expect(queue.contains('MOBILE_device_1'), isTrue);

      final reloaded = PendingCallSyncQueue('42');
      await reloaded.reload();
      expect(reloaded.count, 1);
      expect(reloaded.entries.single.nativeReference, 'MOBILE_device_1');
      expect(reloaded.entries.single.dateMillis, 1000);
      expect(reloaded.entries.single.callLogId, 1);

      await reloaded.removeByReference('MOBILE_device_1');
      expect(reloaded.count, 0);

      final afterRemoval = PendingCallSyncQueue('42');
      await afterRemoval.reload();
      expect(afterRemoval.count, 0);
    });

    test('does not duplicate the same native reference', () async {
      final queue = PendingCallSyncQueue('42');
      await queue.reload();
      final first = await queue.enqueue(_row('MOBILE_device_1'));
      final second = await queue.enqueue(_row('MOBILE_device_1'));
      expect(second?.nativeReference, first?.nativeReference);
      expect(queue.count, 1);
    });

    test(
      'keeps permanently failed rows but reports them non-retryable',
      () async {
        final queue = PendingCallSyncQueue('42');
        await queue.reload();
        final entry = await queue.enqueue(_row('MOBILE_device_1'));
        expect(entry, isNotNull);

        await queue.markFailure(
          entry!,
          ApiException('validation failed', statusCode: 422),
          retryable: false,
        );
        expect(queue.count, 1);
        expect(queue.retryableCount, 0);

        final reloaded = PendingCallSyncQueue('42');
        await reloaded.reload();
        expect(reloaded.count, 1);
        expect(reloaded.retryableCount, 0);
        expect(reloaded.entries.single.attempts, 1);
        expect(
          reloaded.entries.single.lastError,
          contains('validation failed'),
        );
      },
    );

    test('scopes queues per employee', () async {
      final first = PendingCallSyncQueue('42');
      await first.reload();
      await first.enqueue(_row('MOBILE_device_1'));

      final second = PendingCallSyncQueue('43');
      await second.reload();
      expect(second.count, 0);

      expect(await PendingCallSyncQueue.pendingCount('42'), 1);
      expect(await PendingCallSyncQueue.pendingCount('43'), 0);
    });

    test('sorts entries by call date and id', () async {
      final queue = PendingCallSyncQueue('42');
      await queue.reload();
      await queue.enqueue(_row('MOBILE_device_3', date: 3000, id: 3));
      await queue.enqueue(_row('MOBILE_device_1', date: 1000, id: 1));
      await queue.enqueue(_row('MOBILE_device_2', date: 2000, id: 2));

      expect(queue.entries.map((entry) => entry.nativeReference), <String>[
        'MOBILE_device_1',
        'MOBILE_device_2',
        'MOBILE_device_3',
      ]);
    });
  });

  group('isRetryableSyncError', () {
    test(
      'retries network, timeout, auth-expiry, throttling and server errors',
      () {
        expect(isRetryableSyncError(NetworkException()), isTrue);
        expect(isRetryableSyncError(TimeoutException()), isTrue);
        expect(
          isRetryableSyncError(ApiException('expired', statusCode: 401)),
          isTrue,
        );
        expect(
          isRetryableSyncError(ApiException('forbidden', statusCode: 403)),
          isTrue,
        );
        expect(
          isRetryableSyncError(ApiException('timeout', statusCode: 408)),
          isTrue,
        );
        expect(
          isRetryableSyncError(ApiException('too many', statusCode: 429)),
          isTrue,
        );
        expect(
          isRetryableSyncError(ApiException('server error', statusCode: 503)),
          isTrue,
        );
      },
    );

    test('does not loop on business validation errors', () {
      expect(
        isRetryableSyncError(ApiException('invalid call', statusCode: 422)),
        isFalse,
      );
      expect(
        isRetryableSyncError(ApiException('not found', statusCode: 404)),
        isFalse,
      );
    });
  });
}
