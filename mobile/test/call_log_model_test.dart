import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/calls/models/call_log_model.dart';

void main() {
  group('CallLogModel.fromJson', () {
    test('reads customer_phone from the CRM call-log response', () {
      final call = CallLogModel.fromJson(<String, dynamic>{
        'id': 1,
        'customer_phone': '+91 98765 43210',
        'call_status': 'COMPLETED',
        'call_direction': 'OUTBOUND',
        'duration_seconds': 42,
        'provider': 'MOBILE_SIM',
        'sim_label': 'Airtel SIM 2',
        'recording_status': 'RECORDING_UNAVAILABLE',
      });

      expect(call.customerNumber, '+91 98765 43210');
      expect(call.callType, 'OUTBOUND');
      expect(call.isMobileSim, isTrue);
      expect(call.simLabel, 'Airtel SIM 2');
      expect(call.hasRecording, isFalse);
    });

    test('prefers customer_number and falls back to phone', () {
      final byCustomerNumber = CallLogModel.fromJson(<String, dynamic>{
        'id': 2,
        'customer_number': '9999999999',
        'phone': '1111111111',
      });
      final byPhone = CallLogModel.fromJson(<String, dynamic>{
        'id': 3,
        'phone': '2222222222',
      });

      expect(byCustomerNumber.customerNumber, '9999999999');
      expect(byPhone.customerNumber, '2222222222');
    });
  });
}
