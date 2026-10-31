import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/services/mobile_sim_call_service.dart';

void main() {
  group('Mobile SIM call result parsing', () {
    test('parses the native call-result map', () {
      final result = MobileSimCallResult.fromMap(<dynamic, dynamic>{
        'callId': 'SIM_123_abcd',
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
}
