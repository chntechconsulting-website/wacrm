import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/services/device_call_log_sync_service.dart';
import 'package:mobile/core/services/mobile_sim_call_service.dart';
import 'package:mobile/features/calls/models/call_log_model.dart';

void main() {
  group('Mobile SIM call result parsing', () {
    test('parses the native call-result map', () {
      final result = MobileSimCallResult.fromMap(<dynamic, dynamic>{
        'callId': 'SIM_123_abcd',
        'callReference': 'SIM_123_abcd',
        'deviceCallLogId': '9977',
        'nativeCallReference': 'MOBILE_device_9977',
        'leadId': 42,
        'customerPhone': '+91 98765 43210',
        'contactName': 'Test Customer',
        'callDirection': 'outbound',
        'callStatus': 'completed',
        'durationSeconds': 137,
        'durationAccuracy': 'exact',
        'startedAt': '2026-10-31T05:26:56.000Z',
        'answeredAt': '2026-10-31T05:28:02.000Z',
        'endedAt': '2026-10-31T05:31:19.000Z',
        'simAccountId': 'subId:2',
        'simLabel': 'Airtel SIM 2',
        'simSlot': 1,
        'simPhoneNumber': '+919111122233',
        'recordingUrl': null,
        'recordingStatus': 'RECORDING_UNAVAILABLE',
      });

      expect(result.callId, 'SIM_123_abcd');
      expect(result.callReference, 'SIM_123_abcd');
      expect(result.deviceCallLogId, '9977');
      expect(result.nativeCallReference, 'MOBILE_device_9977');
      expect(result.leadId, 42);
      expect(result.customerPhone, '+91 98765 43210');
      expect(result.callStatus, 'COMPLETED');
      expect(result.callDirection, 'OUTBOUND');
      expect(result.durationSeconds, 137);
      expect(result.durationAccuracy, 'exact');
      expect(result.answeredAt, '2026-10-31T05:28:02.000Z');
      expect(result.simAccountId, 'subId:2');
      expect(result.simLabel, 'Airtel SIM 2');
      expect(result.simSlot, 1);
      expect(result.hasRecording, isFalse);
      expect(result.syncNotes, contains('Recording unavailable'));
    });

    test('treats a supplied recording URL as available', () {
      final result = MobileSimCallResult.fromMap(<dynamic, dynamic>{
        'callId': 'SIM_1',
        'customerPhone': '9999999999',
        'callDirection': 'OUTBOUND',
        'callStatus': 'COMPLETED',
        'durationSeconds': 12,
        'recordingUrl': 'https://example.com/recording.mp3',
      });

      expect(result.hasRecording, isTrue);
      expect(result.syncNotes, contains('Recording supplied'));
    });
  });

  group('SIM account parsing', () {
    test('uses carrier or slot as a fallback label', () {
      final carrierOnly = SimAccount.fromMap(<dynamic, dynamic>{
        'subscriptionId': 3,
        'slotIndex': 1,
        'carrierName': 'Jio',
        'displayName': '',
      });
      final slotOnly = SimAccount.fromMap(<dynamic, dynamic>{
        'subscriptionId': 4,
        'slotIndex': 0,
        'carrierName': '',
        'displayName': '',
      });

      expect(carrierOnly.label, 'Jio');
      expect(slotOnly.label, 'SIM 1');
      expect(carrierOnly.slotIndex, 1);
    });
  });

  group('SIM permission status', () {
    test('requires call phone and phone state, but not call log', () {
      final status = MobileSimPermissionStatus.fromMap(<dynamic, dynamic>{
        'callPhone': true,
        'readPhoneState': true,
        'readCallLog': false,
        'readPhoneNumbers': false,
      });

      expect(status.hasRequired, isTrue);
      expect(status.missingRequired, isEmpty);
      expect(status.readCallLog, isFalse);
    });

    test('reports missing required permissions', () {
      final status = MobileSimPermissionStatus.fromMap(<dynamic, dynamic>{
        'callPhone': false,
        'readPhoneState': false,
      });

      expect(status.hasRequired, isFalse);
      expect(status.missingRequired, contains('Phone calling'));
      expect(status.missingRequired, contains('Phone state / SIM info'));
    });
  });

  group('Call reference', () {
    test('generates a unique reference for every attempt', () {
      final ids = List.generate(50, (_) => MobileSimCallService.newCallId());

      expect(ids.toSet().length, ids.length);
      for (final id in ids) {
        expect(id, startsWith('SIM_'));
        expect(id.length, greaterThan(10));
      }
    });
  });

  group('Call source', () {
    test('maps mobile providers to MOBILE and others to DOOCTI', () {
      final mobile = CallLogModel.fromJson(<String, dynamic>{
        'id': 1,
        'customer_phone': '9999999999',
        'call_status': 'COMPLETED',
        'provider': 'MOBILE_SIM',
      });
      final doocti = CallLogModel.fromJson(<String, dynamic>{
        'id': 2,
        'customer_phone': '9999999999',
        'call_status': 'COMPLETED',
        'provider': 'DOOCTI',
        'call_source': 'DOOCTI',
      });

      expect(mobile.source, 'MOBILE');
      expect(mobile.isMobile, isTrue);
      expect(doocti.source, 'DOOCTI');
      expect(doocti.isDoocti, isTrue);
    });

    test('prefers the backend call_source over the storage provider', () {
      final call = CallLogModel.fromJson(<String, dynamic>{
        'id': 3,
        'customer_phone': '9999999999',
        'call_status': 'MISSED',
        'provider': 'MOBILE_SIM',
        'call_source': 'DOOCTI',
      });

      expect(call.source, 'DOOCTI');
    });
  });

  group('Device call-log entry', () {
    test('parses direction, status and native reference', () {
      final entry = DeviceCallLogEntry.fromMap(<String, dynamic>{
        'nativeCallReference': 'MOBILE_device_123',
        'deviceCallLogId': 123,
        'phone': '+91 98765 43210',
        'direction': 'inbound',
        'status': 'missed',
        'durationSeconds': 0,
        'startedAt': '2026-10-31T05:26:56.000Z',
      });

      expect(entry.isUsable, isTrue);
      expect(entry.nativeReference, 'MOBILE_device_123');
      expect(entry.direction, 'INBOUND');
      expect(entry.status, 'MISSED');
      expect(entry.startedDateTime, isNotNull);
    });

    test('keeps zero-duration missed and rejected inbound rows', () {
      for (final type in [1, 3, 5, 6, 7]) {
        final entry = DeviceCallLogEntry.fromMap(<String, dynamic>{
          'nativeCallReference': 'MOBILE_device_$type',
          'deviceCallLogId': type,
          'phone': '+919876543210',
          'type': type,
          'status': type == 1 ? 'MISSED' : 'REJECTED',
          'durationSeconds': 0,
          'startedAt': '2026-10-31T05:26:56.000Z',
        });
        expect(entry.isUsable, isTrue, reason: 'Android type $type');
        expect(entry.direction, 'INBOUND', reason: 'Android type $type');
        expect(entry.androidCallType, type);
        expect(entry.durationSeconds, 0);
      }
    });

    test('preserves the raw native direction beside the mapped direction', () {
      final entry = DeviceCallLogEntry.fromMap(<String, dynamic>{
        'nativeCallReference': 'MOBILE_device_777',
        'phone': '+919876543210',
        'type': 2,
        'direction': 'inbound',
        'status': 'COMPLETED',
        'durationSeconds': 9,
      });

      expect(entry.nativeDirection, 'INBOUND');
      expect(entry.androidCallType, 2);
      expect(entry.direction, 'OUTBOUND');
    });

    test('rejects rows without a phone or native reference', () {
      final entry = DeviceCallLogEntry.fromMap(<String, dynamic>{
        'phone': '',
        'direction': 'OUTBOUND',
      });

      expect(entry.isUsable, isFalse);
    });

    group('maps every Android CallLog.Calls.TYPE explicitly', () {
      DeviceCallLogEntry parseType(int? type, {String? direction}) {
        final map = <String, dynamic>{
          'nativeCallReference': 'MOBILE_device_500',
          'deviceCallLogId': 500,
          'phone': '+919876543210',
          'status': 'COMPLETED',
          'durationSeconds': 12,
        };
        if (type != null) map['type'] = type;
        if (direction != null) map['direction'] = direction;
        return DeviceCallLogEntry.fromMap(map);
      }

      test('INCOMING_TYPE (1) is INBOUND', () {
        expect(parseType(1).direction, 'INBOUND');
      });

      test('OUTGOING_TYPE (2) is OUTBOUND', () {
        expect(parseType(2).direction, 'OUTBOUND');
      });

      test('MISSED_TYPE (3) is INBOUND', () {
        expect(parseType(3).direction, 'INBOUND');
      });

      test('REJECTED_TYPE (5) is INBOUND', () {
        expect(parseType(5).direction, 'INBOUND');
      });

      test('BLOCKED_TYPE (6) is INBOUND', () {
        expect(parseType(6).direction, 'INBOUND');
      });

      test('ANSWERED_EXTERNALLY_TYPE (7) is INBOUND', () {
        expect(parseType(7).direction, 'INBOUND');
      });

      test('unknown type without direction is rejected, never OUTBOUND', () {
        final entry = parseType(99);
        expect(entry.direction, isEmpty);
        expect(entry.isUsable, isFalse);
      });

      test('the raw Android type wins over a conflicting direction string', () {
        expect(parseType(1, direction: 'OUTBOUND').direction, 'INBOUND');
      });
    });

    test('native result falls back to the raw Android type', () {
      final result = MobileSimCallResult.fromMap(<dynamic, dynamic>{
        'callId': 'SIM_INCOMING_1',
        'customerPhone': '+919876543210',
        'callType': 1,
        'callStatus': 'COMPLETED',
        'durationSeconds': 8,
      });

      expect(result.callDirection, 'INBOUND');
    });

    test('native result without any direction is not assumed OUTBOUND', () {
      final result = MobileSimCallResult.fromMap(<dynamic, dynamic>{
        'callId': 'SIM_UNKNOWN_1',
        'customerPhone': '+919876543210',
        'callStatus': 'COMPLETED',
        'durationSeconds': 8,
      });

      expect(result.callDirection, isEmpty);
      expect(result.hasKnownDirection, isFalse);
    });

    test('native result with an UNKNOWN direction is not synchronizable', () {
      final result = MobileSimCallResult.fromMap(<dynamic, dynamic>{
        'callId': 'SIM_UNKNOWN_2',
        'customerPhone': '+919876543210',
        'callDirection': 'UNKNOWN',
        'callType': 99,
        'callStatus': 'COMPLETED',
        'durationSeconds': 8,
      });

      expect(result.callDirection, isEmpty);
      expect(result.hasKnownDirection, isFalse);
    });

    test('native result trusts callType over a conflicting direction', () {
      final result = MobileSimCallResult.fromMap(<dynamic, dynamic>{
        'callId': 'SIM_INCOMING_3',
        'customerPhone': '+919876543210',
        'callDirection': 'OUTBOUND',
        'callType': 1,
        'callStatus': 'COMPLETED',
        'durationSeconds': 8,
      });

      expect(result.callDirection, 'INBOUND');
    });

    test('native result with a proven direction is synchronizable', () {
      final result = MobileSimCallResult.fromMap(<dynamic, dynamic>{
        'callId': 'SIM_INBOUND_2',
        'customerPhone': '+919876543210',
        'callDirection': 'INBOUND',
        'callStatus': 'MISSED',
        'durationSeconds': 0,
      });

      expect(result.hasKnownDirection, isTrue);
    });
  });
}
