import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../utils/phone_utils.dart';
import 'mobile_sim_call_service.dart';
import 'office_sim_service.dart';

/// Shared UI flow for placing a real cellular call from the device SIM.
///
/// Used by the lead details screen and the standalone dial pad so both entry
/// points behave identically: permission prompt, SIM selection on dual-SIM
/// devices, call start, and clear failure messages.
class MobileSimDialer {
  const MobileSimDialer._();

  /// The optional call-log prompt is offered once per app run. Repeatedly
  /// asking after a denial is poor UX and Android may not show the system
  /// prompt at all, so the CRM keeps logging with an estimated duration.
  static bool _optionalCallLogPrompted = false;

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

    String? attemptCallId;
    try {
      final permissions = await _ensurePermissions(context);
      if (permissions == null || !context.mounted) return false;

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

      // A registered Office SIM restricts in-app mobile calling to that exact
      // SIM. Personal-SIM calls must never create a CRM record, and an
      // unverified/replaced SIM pauses calling until it is re-verified.
      final officeSim = await OfficeSimService.evaluate();
      if (!context.mounted) return false;
      var availableSims = sims;
      if (officeSim.state == OfficeSimState.requiresVerification) {
        _showMessage(
          context,
          officeSim.message.trim().isEmpty
              ? 'Your Office SIM must be re-verified before calling.'
              : officeSim.message,
        );
        return false;
      }
      if (officeSim.state == OfficeSimState.verified &&
          officeSim.mapping != null) {
        final office = OfficeSimService.matchSim(
          officeSim.mapping!,
          sims,
        );
        if (office == null) {
          _showMessage(
            context,
            'The registered Office SIM is not available on this device. '
            'Re-verify it in Settings before calling.',
          );
          return false;
        }
        availableSims = [office];
      }

      final SimAccount? selectedSim = availableSims.length == 1
          ? availableSims.first
          : await _showSimPicker(context, availableSims);
      if (selectedSim == null || !context.mounted) return false;

      // Persist the attempt before ACTION_CALL. The native tracker and the
      // final sync both use this exact call id, so the later result updates
      // this row instead of creating a duplicate.
      attemptCallId = await MobileSimCallService.beginAttempt(
        phone: number,
        leadId: leadId,
        contactName: contactName,
        sim: selectedSim,
      );

      await MobileSimCallService.startCall(
        phone: number,
        callId: attemptCallId,
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
            'Calling $number from ${selectedSim.label}. '
            'This call is being logged to CRM.$durationNote',
          ),
          backgroundColor: const Color(0xFF10B981),
          duration: const Duration(seconds: 4),
        ),
      );
      return true;
    } on PlatformException catch (error) {
      if (attemptCallId != null) {
        await MobileSimCallService.failAttempt(
          callId: attemptCallId,
          phone: number,
          leadId: leadId,
          contactName: contactName,
          reason: error.message ?? error.code,
        );
      }
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
      if (attemptCallId != null) {
        await MobileSimCallService.failAttempt(
          callId: attemptCallId,
          phone: number,
          leadId: leadId,
          contactName: contactName,
          reason: error.toString(),
        );
      }
      if (!context.mounted) return false;
      _showMessage(context, 'Unable to start the mobile SIM call: $error');
      return false;
    }
  }

  /// Explains why Android asks for phone access before the system prompt is
  /// shown. Call-log access remains optional; without it the CRM estimates the
  /// duration and keeps the call as unverified until the device result arrives.
  static Future<MobileSimPermissionStatus?> _ensurePermissions(
    BuildContext context,
  ) async {
    var status = await MobileSimCallService.permissionStatus();
    if (!context.mounted) return null;

    if (!status.hasRequired) {
      final proceed = await _showPermissionRationale(
        context,
        status,
        required: true,
      );
      if (!proceed || !context.mounted) return null;
      // The native request includes the optional call-log permission, so do not
      // show a second rationale prompt for it in the same flow.
      _optionalCallLogPrompted = true;
      status = await MobileSimCallService.requestPermissions();
      if (!context.mounted) return null;
      if (!status.hasRequired) {
        _showPermissionDialog(context, status);
        return null;
      }
    }

    if (!status.readCallLog && !_optionalCallLogPrompted) {
      _optionalCallLogPrompted = true;
      final allowCallLog = await _showPermissionRationale(
        context,
        status,
        required: false,
      );
      if (allowCallLog && context.mounted) {
        status = await MobileSimCallService.requestPermissions();
        if (!context.mounted) return null;
      }
    }
    return status;
  }

  static Future<bool> _showPermissionRationale(
    BuildContext context,
    MobileSimPermissionStatus permissions, {
    required bool required,
  }) async {
    final missing = required
        ? permissions.missingRequired.join(', ')
        : 'Call log access';
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          required ? 'Phone access required' : 'Improve call accuracy',
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        content: Text(
          required
              ? 'WACRM needs $missing to place this call from your SIM and '
                    'track when it ends.\n\n'
                    'The CRM stores the call attempt, direction, timestamp and '
                    'final result. It never records audio.'
              : 'Allow $missing so WACRM can read the exact talk duration and '
                    'final status from this device.\n\n'
                    'Android may restrict call-log access. Without it, the call '
                    'is still logged with an estimated duration and is never '
                    'marked completed unless the device confirms it.',
          style: const TextStyle(fontSize: 13, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(required ? 'Cancel' : 'Not now'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(required ? 'Continue' : 'Allow'),
          ),
        ],
      ),
    );
    return result == true;
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
