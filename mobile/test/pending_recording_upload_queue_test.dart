import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/calls/models/call_log_model.dart';
import 'package:mobile/core/services/mobile_call_recording_manager.dart';
import 'package:mobile/core/services/pending_recording_upload_queue.dart';
import 'package:mobile/core/services/recording_upload_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<PendingRecordingUpload> _enqueue(
  PendingRecordingUploadQueue queue, {
  required String employeeKey,
  int callId = 1,
  DateTime? startedAt,
  int durationSeconds = 30,
}) {
  final start = startedAt ?? DateTime.utc(2026, 1, 1, 10);
  return queue
      .enqueueForCall(
        callId: callId,
        employeeKey: employeeKey,
        phone: '+919999999999',
        startedAt: start,
        endedAt: start.add(Duration(seconds: durationSeconds)),
        durationSeconds: durationSeconds,
        direction: 'OUTBOUND',
        nativeReference: 'MOBILE_device_$callId',
        simAccountId: 'subId:1',
        simSubscriptionId: 1,
      )
      .then((entry) => entry!);
}

CallLogModel _call({
  required int id,
  required String source,
  required String recordingStatus,
  required DateTime startedAt,
  int durationSeconds = 30,
  String? recordingUrl,
}) {
  return CallLogModel(
    id: id,
    customerNumber: '+919999999999',
    callType: 'OUTBOUND',
    callStatus: 'COMPLETED',
    durationSeconds: durationSeconds,
    recordingStatus: recordingStatus,
    recordingUrl: recordingUrl,
    callSource: source,
    nativeCallReference: 'MOBILE_device_$id',
    simAccountId: 'subId:1',
    simSubscriptionId: 1,
    startedAt: startedAt.toIso8601String(),
    endedAt: startedAt
        .add(Duration(seconds: durationSeconds))
        .toIso8601String(),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  group('PendingRecordingUploadQueue', () {
    test('persists a recording task until the backend confirms it', () async {
      final queue = PendingRecordingUploadQueue('42');
      await queue.reload();
      final entry = await _enqueue(queue, employeeKey: '42');
      expect(queue.count, 1);
      expect(queue.containsCall(1), isTrue);
      expect(entry.phone, '+919999999999');
      expect(entry.simAccountId, 'subId:1');
      expect(entry.nativeReference, 'MOBILE_device_1');

      final reloaded = PendingRecordingUploadQueue('42');
      await reloaded.reload();
      expect(reloaded.count, 1);
      expect(reloaded.entries.single.callId, 1);
      expect(reloaded.entries.single.direction, 'OUTBOUND');

      final withFile = await reloaded.withRecording(
        reloaded.entries.single,
        path: '/data/user/0/com.wacrm.mobile/files/call_recordings/a.m4a',
        name: 'call.m4a',
        size: 2048,
        mimeType: 'audio/mp4',
        checksum: 'abc123',
        recordingDurationSeconds: 30,
      );
      expect(withFile.hasFile, isTrue);
      expect(withFile.lastStatus, 'PENDING_SYNC');

      final afterFile = PendingRecordingUploadQueue('42');
      await afterFile.reload();
      expect(afterFile.entries.single.fileName, 'call.m4a');
      expect(afterFile.entries.single.checksum, 'abc123');
      expect(afterFile.entries.single.recordingDurationSeconds, 30);

      await afterFile.remove(afterFile.entries.single);
      final afterRemoval = PendingRecordingUploadQueue('42');
      await afterRemoval.reload();
      expect(afterRemoval.count, 0);
    });

    test('does not duplicate a call and scopes tasks per employee', () async {
      final first = PendingRecordingUploadQueue('42');
      await first.reload();
      await _enqueue(first, employeeKey: '42');
      await _enqueue(first, employeeKey: '42');
      expect(first.count, 1);

      final second = PendingRecordingUploadQueue('43');
      await second.reload();
      expect(second.count, 0);

      expect(await PendingRecordingUploadQueue.pendingCount('42'), 1);
      expect(await PendingRecordingUploadQueue.pendingCount('43'), 0);
    });

    test('honours retry backoff until the task is forced', () async {
      final queue = PendingRecordingUploadQueue('42');
      await queue.reload();
      final entry = await _enqueue(queue, employeeKey: '42');
      await queue.markFailure(
        entry,
        'Network unavailable',
        retryable: true,
        status: 'UPLOAD_FAILED',
        detail: 'Network unavailable',
        nextAttemptAt: DateTime.now().toUtc().add(const Duration(hours: 1)),
      );

      expect(queue.dueEntries(), isEmpty);
      expect(queue.dueEntries(forceRetry: true), hasLength(1));
      expect(queue.entries.single.attempts, 1);
      expect(queue.entries.single.lastStatus, 'UPLOAD_FAILED');
      expect(queue.retryableCount, 1);
    });

    test('clearRecording keeps the task but drops the missing file', () async {
      final queue = PendingRecordingUploadQueue('42');
      await queue.reload();
      var entry = await _enqueue(queue, employeeKey: '42');
      entry = await queue.withRecording(
        entry,
        path: '/tmp/gone.m4a',
        name: 'gone.m4a',
        size: 2048,
        mimeType: 'audio/mp4',
        checksum: 'abc123',
        recordingDurationSeconds: 30,
      );
      await queue.markAttempt(entry);

      final cleared = await queue.clearRecording(queue.entries.single);
      expect(cleared.hasFile, isFalse);
      expect(cleared.filePath, isNull);
      expect(cleared.attempts, 1);

      final reloaded = PendingRecordingUploadQueue('42');
      await reloaded.reload();
      expect(reloaded.count, 1);
      expect(reloaded.entries.single.hasFile, isFalse);
    });
  });

  group('RecordingRetryPolicy', () {
    test('backoff grows monotonically with attempts', () {
      Duration? previous;
      for (var attempt = 0; attempt <= 10; attempt++) {
        final current = RecordingRetryPolicy.backoffFor(attempt);
        if (previous != null) {
          expect(current >= previous, isTrue);
        }
        previous = current;
      }
      expect(RecordingRetryPolicy.discoveryWindow, const Duration(hours: 24));
      expect(RecordingRetryPolicy.backoffFor(0), const Duration(minutes: 1));
    });
  });

  group('RecordingUploadService.enqueueFromCalls', () {
    test('queues only recent retryable Mobile SIM calls', () async {
      final now = DateTime.utc(2026, 6, 1, 12);
      final calls = <CallLogModel>[
        _call(
          id: 1,
          source: 'MOBILE',
          recordingStatus: 'PENDING_SYNC',
          startedAt: now.subtract(const Duration(hours: 1)),
        ),
        _call(
          id: 2,
          source: 'MOBILE',
          recordingStatus: 'UPLOAD_FAILED',
          startedAt: now.subtract(const Duration(days: 2)),
        ),
        _call(
          id: 3,
          source: 'MOBILE',
          recordingStatus: 'PENDING_SYNC',
          startedAt: now.subtract(const Duration(days: 2)),
        ),
        _call(
          id: 4,
          source: 'DOOCTI',
          recordingStatus: 'PENDING_SYNC',
          startedAt: now.subtract(const Duration(hours: 1)),
        ),
        _call(
          id: 5,
          source: 'MOBILE',
          recordingStatus: 'AVAILABLE',
          startedAt: now.subtract(const Duration(hours: 1)),
          recordingUrl: 'https://example.test/rec.m4a',
        ),
        _call(
          id: 6,
          source: 'MOBILE',
          recordingStatus: 'PENDING_SYNC',
          startedAt: now.subtract(const Duration(hours: 1)),
          durationSeconds: 0,
        ),
      ];

      final queued = await RecordingUploadService.enqueueFromCalls(
        calls,
        employeeKey: '42',
        now: now,
      );
      expect(queued, 2);
      final queue = PendingRecordingUploadQueue('42');
      await queue.reload();
      expect(queue.entries.map((entry) => entry.callId).toSet(), <int>{1, 2});
    });

    test('skips a call already linked to a recording', () async {
      final now = DateTime.utc(2026, 6, 1, 12);
      final linked = _call(
        id: 7,
        source: 'MOBILE',
        recordingStatus: 'PENDING_SYNC',
        startedAt: now.subtract(const Duration(hours: 1)),
        recordingUrl: 'https://example.test/rec.m4a',
      );
      expect(linked.hasRecording, isTrue);

      final queued = await RecordingUploadService.enqueueFromCalls(
        [linked],
        employeeKey: '42',
        now: now,
      );
      expect(queued, 0);
    });
  });

  group('CallLogModel recording status detail', () {
    test('parses the backend detail and legacy SYNCED alias', () {
      final call = CallLogModel.fromJson(<String, dynamic>{
        'id': 10,
        'customer_number': '+919999999999',
        'call_direction': 'OUTBOUND',
        'call_status': 'COMPLETED',
        'duration_seconds': 30,
        'call_source': 'MOBILE',
        'recording_status': 'SYNCED',
        'recording_status_detail': 'Uploaded after the OEM file was indexed.',
      });
      expect(call.recordingStatus, 'SYNCED');
      expect(call.recordingSyncStatus, RecordingSyncStatus.available);
      expect(
        call.recordingStatusDetailLabel,
        'Uploaded after the OEM file was indexed.',
      );

      final pending = CallLogModel.fromJson(<String, dynamic>{
        'id': 11,
        'customer_number': '+919999999999',
        'call_direction': 'OUTBOUND',
        'call_status': 'COMPLETED',
        'duration_seconds': 30,
        'call_source': 'MOBILE',
        'recording_status': 'PENDING_SYNC',
      });
      expect(
        pending.recordingStatusDetailLabel,
        'Waiting for the device recording to be found and uploaded.',
      );
    });
  });
}
