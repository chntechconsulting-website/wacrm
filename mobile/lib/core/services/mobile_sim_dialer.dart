import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../utils/phone_utils.dart';
import 'mobile_sim_call_service.dart';

/// Shared UI flow for placing a real cellular call from the device SIM.
///
/// Used by the lead details screen and the standalone dial pad so both entry
/// points behave identically: permission prompt, SIM selection on dual-SIM
/// devices, call start, and clear failure messages.
class MobileSimDialer {
  const MobileSimDialer._();

  /// Returns true when the device call was launched.
  static Future<bool> start(
    BuildContext context, {
    required String phone,
    int? leadId,
    String? contactName,
    String missingNumberMessage =
        'Enter a valid phone number with at least 3 digits.',
  }) async {
    var number = PhoneUtils.normalizeDialInput(phone);
    if (number.startsWith('00')) {
      number = '+${number.substring(2)}';
    }
    if (number.replaceAll('+', '').length < 3) {
      if (!context.mounted) return false;
      _showMessage(context, missingNumberMessage);
      return false;
    }

    if (!MobileSimCallService.isSupported) {
      if (!context.mounted) return false;
      _showMessage(
        context,
        'Mobile SIM calling is available on the Android app only.',
      );
      return false;
    }

    try {
      final permissions = await MobileSimCallService.requestPermissions();
      if (!context.mounted) return false;

      if (!permissions.hasRequired) {
        _showPermissionDialog(context, permissions);
        return false;
      }

      final sims = await MobileSimCallService.getSimAccounts();
      if (!context.mounted) return false;

      if (sims.isEmpty) {
        _showMessage(
          context,
          'No active SIM was found on this device. '
          'Check that a SIM is inserted and has signal.',
        );
        return false;
      }

      final SimAccount? selectedSim = sims.length == 1
          ? sims.first
          : await _showSimPicker(context, sims);
      if (selectedSim == null || !context.mounted) return false;

      await MobileSimCallService.startCall(
        phone: number,
        callId: MobileSimCallService.newCallId(),
        leadId: leadId,
        contactName: contactName,
        sim: selectedSim,
      );

      if (!context.mounted) return true;

      final durationNote = permissions.readCallLog
          ? ''
          : ' Call-log permission is off, so duration will be estimated.';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Calling $number from ${selectedSim.label}.$durationNote',
          ),
          backgroundColor: const Color(0xFF10B981),
          duration: const Duration(seconds: 4),
        ),
      );
      return true;
    } on PlatformException catch (error) {
      if (!context.mounted) return false;
      if (error.code == 'CALL_IN_PROGRESS') {
        _showMessage(
          context,
          'A device call is already being tracked. '
          'Finish it before starting another.',
        );
      } else if (error.code == 'PERMISSION_DENIED') {
        _showMessage(
          context,
          'Phone permission was denied. Allow it in Settings to call from your SIM.',
          openSettings: true,
        );
      } else if (error.code == 'INVALID_NUMBER') {
        _showMessage(
          context,
          'That phone number is not dialable. Check the number and try again.',
        );
      } else {
        _showMessage(
          context,
          error.message ?? 'Unable to start the mobile SIM call.',
        );
      }
      return false;
    } catch (error) {
      if (!context.mounted) return false;
      _showMessage(context, 'Unable to start the mobile SIM call: $error');
      return false;
    }
  }

  static Future<SimAccount?> _showSimPicker(
    BuildContext context,
    List<SimAccount> sims,
  ) {
    return showModalBottomSheet<SimAccount>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 18),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey.shade300,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Choose SIM for this call',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF0F172A),
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'The customer will see the selected SIM number as your caller ID.',
                style: TextStyle(fontSize: 12, color: Color(0xFF64748B)),
              ),
              const SizedBox(height: 12),
              ...sims.map(
                (sim) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Material(
                    color: const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(14),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(14),
                      onTap: () => Navigator.pop(ctx, sim),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 10,
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 38,
                              height: 38,
                              decoration: const BoxDecoration(
                                color: Color(0xFFECFDF5),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.sim_card_rounded,
                                size: 20,
                                color: Color(0xFF059669),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    sim.label,
                                    style: const TextStyle(
                                      fontSize: 13.5,
                                      fontWeight: FontWeight.w700,
                                      color: Color(0xFF0F172A),
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    [
                                      if (sim.carrierName.trim().isNotEmpty)
                                        sim.carrierName.trim(),
                                      'Slot ${sim.slotIndex + 1}',
                                      if ((sim.phoneNumber ?? '').isNotEmpty)
                                        sim.phoneNumber!,
                                    ].join(' • '),
                                    style: const TextStyle(
                                      fontSize: 11.5,
                                      color: Color(0xFF64748B),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            if (sim.isDefault)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 3,
                                ),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFE0F2FE),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: const Text(
                                  'Default',
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w700,
                                    color: Color(0xFF0369A1),
                                  ),
                                ),
                              ),
                            const SizedBox(width: 8),
                            const Icon(
                              Icons.chevron_right_rounded,
                              color: Color(0xFF94A3B8),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'SIM selection support varies by Android device and carrier. '
                'The call always uses the real cellular network, never the CRM PBX.',
                style: TextStyle(fontSize: 10.5, color: Color(0xFF94A3B8)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static void _showPermissionDialog(
    BuildContext context,
    MobileSimPermissionStatus permissions,
  ) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(
          'Phone permission required',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        content: Text(
          'To place calls from your mobile SIM, allow: '
          '${permissions.missingRequired.join(', ')}.\n\n'
          'Call-log access is optional. Without it, call duration is estimated.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              MobileSimCallService.openAppSettings();
            },
            child: const Text('Open Settings'),
          ),
        ],
      ),
    );
  }

  static void _showMessage(
    BuildContext context,
    String message, {
    bool openSettings = false,
  }) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(
          'Mobile SIM calling',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        content: Text(message),
        actions: [
          if (openSettings)
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                MobileSimCallService.openAppSettings();
              },
              child: const Text('Open Settings'),
            ),
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }
}
