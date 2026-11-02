import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/services/device_call_log_sync_service.dart';
import 'package:mobile/core/services/mobile_sim_call_service.dart';
import 'package:mobile/core/services/office_sim_service.dart';

const _component =
    'com.android.phone/com.android.services.telephony.TelephonyConnectionService';

OfficeSimMapping _mapping({
  int? subscriptionId = 2,
  String? accountId = 'account-2',
  String? component = _component,
  int? slot = 1,
  String number = '+919876543210',
}) {
  return OfficeSimMapping(
    subscriptionId: subscriptionId,
    simSlot: slot,
    carrierName: 'Airtel',
    displayName: 'Office',
    phoneNumber: number,
    phoneAccountId: accountId,
    phoneAccountComponent: component,
    simFingerprint: 'f' * 64,
    status: 'VERIFIED',
  );
}

void main() {
  group('Office SIM identity matching', () {
    test('matches the exact subscription token', () {
      final mapping = _mapping();
      expect(
        OfficeSimService.callMatches(mapping, simAccountId: 'subId:2'),
        isTrue,
      );
      expect(
        OfficeSimService.callMatches(mapping, subscriptionId: 2),
        isTrue,
      );
      expect(
        OfficeSimService.callMatches(mapping, simAccountId: 'subId:1'),
        isFalse,
      );
    });

    test('matches phone account identity when no subscription exists', () {
      final mapping = _mapping(subscriptionId: null);
      expect(
        OfficeSimService.callMatches(
          mapping,
          simAccountId: 'phoneAccount:$_component#account-2',
        ),
        isTrue,
      );
      expect(
        OfficeSimService.callMatches(
          mapping,
          simAccountId: 'phoneAccount:account-2',
        ),
        isTrue,
      );
      expect(
        OfficeSimService.callMatches(
          mapping,
          simAccountId: 'phoneAccount:$_component#account-9',
        ),
        isFalse,
      );
    });

    test('never falls back to slot or phone number', () {
      final mapping = _mapping();
      expect(OfficeSimService.callMatches(mapping, simAccountId: null), isFalse);
      expect(OfficeSimService.callMatches(mapping, simAccountId: ''), isFalse);
      expect(
        OfficeSimService.callMatches(mapping, simAccountId: '+919876543210'),
        isFalse,
      );
      expect(
        OfficeSimService.callMatches(mapping, simAccountId: 'SLOT:1'),
        isFalse,
      );
    });

    test('finds the installed SIM by subscription before account', () {
      final mapping = _mapping();
      final sims = [
        const SimAccount(
          subscriptionId: 1,
          slotIndex: 0,
          carrierName: 'Jio',
          displayName: 'Personal',
          phoneAccountId: 'account-1',
          phoneAccountComponent: _component,
          simFingerprint: 'a',
        ),
        const SimAccount(
          subscriptionId: 2,
          slotIndex: 1,
          carrierName: 'Airtel',
          displayName: 'Office',
          phoneAccountId: 'account-2',
          phoneAccountComponent: _component,
          simFingerprint: 'b',
        ),
      ];
      expect(OfficeSimService.matchSim(mapping, sims)?.subscriptionId, 2);
    });

    test('missing registered SIM produces no match (fail closed)', () {
      final mapping = _mapping();
      final sims = [
        const SimAccount(
          subscriptionId: 1,
          slotIndex: 0,
          carrierName: 'Jio',
          displayName: 'Personal',
        ),
      ];
      expect(OfficeSimService.matchSim(mapping, sims), isNull);
    });

    test('SIM without subscription uses phone account identity', () {
      final mapping = _mapping(subscriptionId: null);
      const sim = SimAccount(
        subscriptionId: -1,
        slotIndex: 0,
        carrierName: 'Airtel',
        displayName: 'Office',
        phoneAccountId: 'account-2',
        phoneAccountComponent: _component,
        simFingerprint: 'c',
      );
      expect(OfficeSimService.matchSim(mapping, [sim])?.phoneAccountId,
          'account-2');
      expect(OfficeSimService.callMatches(mapping, simAccountId: sim.identityToken),
          isTrue);
    });
  });

  group('SimAccount identity', () {
    test('parses phone account and fingerprint metadata', () {
      final sim = SimAccount.fromMap({
        'subscriptionId': 3,
        'slotIndex': 1,
        'carrierName': 'Vi',
        'displayName': 'Office',
        'phoneNumber': '+919111122233',
        'isDefault': true,
        'phoneAccountId': 'account-3',
        'phoneAccountComponent': _component,
        'simFingerprint': 'abc123',
        'isEmbedded': false,
        'isRemovable': true,
      });
      expect(sim.identityToken, 'subId:3');
      expect(sim.phoneAccountId, 'account-3');
      expect(sim.simFingerprint, 'abc123');
      expect(sim.isRemovable, isTrue);
    });

    test('falls back to phone account token when subscription is absent', () {
      const sim = SimAccount(
        subscriptionId: -1,
        slotIndex: 0,
        carrierName: 'Airtel',
        displayName: 'Office',
        phoneAccountId: 'account-9',
        phoneAccountComponent: _component,
      );
      expect(
        sim.identityToken,
        'phoneAccount:$_component#account-9',
      );
    });
  });

  group('Device call log SIM identity', () {
    test('reads canonical identity and subscription from native row', () {
      final entry = DeviceCallLogEntry.fromMap({
        'nativeCallReference': 'native-1',
        'phone': '+919876543210',
        'direction': 'INBOUND',
        'status': 'MISSED',
        'durationSeconds': 0,
        'simAccountId': 'subId:2',
        'simIdentity': 'subId:2',
        'simSubscriptionId': 2,
        'simSlotIndex': 1,
        'simIdentityStatus': 'RESOLVED',
      });
      expect(entry.direction, 'INBOUND');
      expect(entry.hasSimIdentity, isTrue);
      expect(entry.simSubscriptionId, 2);
      expect(entry.simSlotIndex, 1);
    });

    test('a row without SIM identity fails closed', () {
      final entry = DeviceCallLogEntry.fromMap({
        'nativeCallReference': 'native-2',
        'phone': '+919876543210',
        'direction': 'OUTBOUND',
        'status': 'COMPLETED',
        'durationSeconds': 10,
        'simIdentityStatus': 'MISSING',
      });
      expect(entry.hasSimIdentity, isFalse);
    });
  });

  group('Office SIM mapping JSON', () {
    test('round-trips configuration including verification state', () {
      final mapping = OfficeSimMapping.fromJson({
        'id': 4,
        'employee_id': 9,
        'subscription_id': 2,
        'sim_slot': 1,
        'carrier_name': 'Airtel',
        'display_name': 'Office',
        'phone_number': '+919876543210',
        'phone_account_id': 'account-2',
        'phone_account_component': _component,
        'sim_fingerprint': 'f' * 64,
        'status': 'REQUIRES_VERIFICATION',
        'verification_reason': 'SIM replaced',
      });
      expect(mapping.isVerified, isFalse);
      expect(mapping.verificationReason, 'SIM replaced');
      expect(OfficeSimMapping.fromJson(mapping.toJson()).subscriptionId, 2);
    });
  });
}
