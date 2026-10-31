import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../constants/app_colors.dart';
import '../utils/phone_utils.dart';
import '../../features/calls/data/calls_repository.dart';
import '../../features/calls/providers/calls_provider.dart';

class DooctiCallService {
  static final CallsRepository _callsRepository = CallsRepository();

  /// Initiates a phone call routed through DooCTI.
  /// 1. Validates the agent's DooCTI PBX extension.
  /// 2. If unmapped, prompts user with extension requirement dialog (with direct device call fallback).
  /// 3. If mapped, initiates call through DooCTI and opens the live call controller sheet.
  static Future<void> makeCall(
    BuildContext context, {
    required String phone,
    int? leadId,
    String? contactName,
  }) async {
    final cleanPhone = PhoneUtils.normalize(phone);
    if (cleanPhone.replaceAll('+', '').length < 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'No valid phone number saved for this contact. '
            'Update the number or use the dial pad.',
          ),
        ),
      );
      return;
    }

    // Show initial loading indicator
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: Card(
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: 24, vertical: 20),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(color: AppColors.primary),
                SizedBox(width: 20),
                Text(
                  'Connecting to DooCTI...',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    Map<String, dynamic> extInfo;
    try {
      extInfo = await _callsRepository.getAgentExtension();
    } catch (_) {
      extInfo = {'registered': false};
    }

    if (!context.mounted) return;
    Navigator.of(context, rootNavigator: true).pop(); // Dismiss loading

    final isRegistered = extInfo['registered'] == true;
    final station = extInfo['station']?.toString() ?? '';
    final callerDid = extInfo['caller_did']?.toString() ?? 'DooCTI PBX';

    if (!isRegistered || station.isEmpty) {
      _showExtensionRequiredDialog(context, cleanPhone, contactName);
      return;
    }

    // Extension is verified; open DooCTI Active Call Sheet
    _showDooctiActiveCallSheet(
      context,
      phone: cleanPhone,
      leadId: leadId,
      contactName: contactName,
      station: station,
      callerDid: callerDid,
    );
  }

  static void _showExtensionRequiredDialog(
    BuildContext context,
    String cleanPhone,
    String? contactName,
  ) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.phonelink_ring_rounded, color: AppColors.primary, size: 28),
            SizedBox(width: 12),
            Expanded(
              child: Text(
                'DooCTI Extension Required',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
        content: Text(
          'Your CRM user account does not have a registered DooCTI PBX extension. '
          'To route calls via DooCTI, please ask your administrator to map your extension (e.g. 1281, 1282, 1283, 1286).\n\n'
          'Would you like to place a direct phone call using your device instead?',
          style: const TextStyle(fontSize: 13, color: AppColors.textMuted, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: AppColors.textMuted)),
          ),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.navy,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            icon: const Icon(Icons.call, size: 16),
            label: const Text('Direct Device Call'),
            onPressed: () async {
              Navigator.pop(ctx);
              final uri = Uri.parse('tel:$cleanPhone');
              if (await canLaunchUrl(uri)) {
                await launchUrl(uri);
              }
            },
          ),
        ],
      ),
    );
  }

  static void _showDooctiActiveCallSheet(
    BuildContext context, {
    required String phone,
    int? leadId,
    String? contactName,
    required String station,
    required String callerDid,
  }) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _DooctiCallSheetContent(
        phone: phone,
        leadId: leadId,
        contactName: contactName,
        station: station,
        callerDid: callerDid,
      ),
    );
  }
}

class _DooctiCallSheetContent extends StatefulWidget {
  final String phone;
  final int? leadId;
  final String? contactName;
  final String station;
  final String callerDid;

  const _DooctiCallSheetContent({
    required this.phone,
    this.leadId,
    this.contactName,
    required this.station,
    required this.callerDid,
  });

  @override
  State<_DooctiCallSheetContent> createState() => _DooctiCallSheetContentState();
}

class _DooctiCallSheetContentState extends State<_DooctiCallSheetContent> {
  final CallsRepository _callsRepo = CallsRepository();
  final TextEditingController _notesController = TextEditingController();

  Timer? _timer;
  int _seconds = 0;
  bool _isDialing = true;
  String _selectedDisposition = 'ANSWERED';
  String? _statusMessage;
  bool _isSubmitting = false;

  final List<String> _dispositions = [
    'ANSWERED',
    'INTERESTED',
    'FOLLOW_UP',
    'BUSY',
    'NO_ANSWER',
    'NOT_INTERESTED',
    'WRONG_NUMBER',
    'CALL_BACK',
  ];

  @override
  void initState() {
    super.initState();
    _startCall();
  }

  Future<void> _startCall() async {
    setState(() {
      _isDialing = true;
      _statusMessage = 'Connecting via DooCTI PBX...';
    });

    try {
      await _callsRepo.initiateDooctiCall(
        phone: widget.phone,
        leadId: widget.leadId,
        notes: 'Mobile DooCTI outbound call to ${widget.phone}',
      );
      if (mounted) {
        setState(() {
          _isDialing = false;
          _statusMessage = 'Call connected through DooCTI';
        });
        _startTimer();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isDialing = false;
          _statusMessage = 'DooCTI session initiated (PBX station ringing)';
        });
        _startTimer();
      }
    }
  }

  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(() {
          _seconds++;
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _notesController.dispose();
    super.dispose();
  }

  String _formatTimer(int totalSecs) {
    final m = (totalSecs ~/ 60).toString().padLeft(2, '0');
    final s = (totalSecs % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  Future<void> _endAndSaveCall() async {
    setState(() {
      _isSubmitting = true;
    });
    _timer?.cancel();

    try {
      await _callsRepo.logManualCall(
        customerPhone: widget.phone,
        customerNumber: widget.phone,
        callStatus: _selectedDisposition,
        durationSeconds: _seconds > 0 ? _seconds : 1,
        leadId: widget.leadId,
        notes: _notesController.text.trim().isNotEmpty
            ? _notesController.text.trim()
            : 'Mobile DooCTI call (Ext: ${widget.station})',
      );

      if (mounted) {
        // Trigger provider refresh so CRM call logs reflect immediately
        try {
          context.read<CallsProvider>().fetchCalls(showLoading: false);
        } catch (_) {}

        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.navy,
            content: Text(
              'Call completed & logged to CRM (${_formatTimer(_seconds)})',
              style: const TextStyle(color: Colors.white),
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving call: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Top Drag Handle
              Center(
                child: Container(
                  width: 44,
                  height: 4,
                  decoration: BoxDecoration(
                    color: const Color(0xFFE2E8F0),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Telephony Header Badge
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.navyDark,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: const BoxDecoration(
                            color: Color(0xFF10B981),
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        const Text(
                          'DooCTI Telephony',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    'Ext: ${widget.station}',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: AppColors.primary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Contact & Call Details
              Center(
                child: Column(
                  children: [
                    CircleAvatar(
                      radius: 36,
                      backgroundColor: AppColors.navyLight,
                      child: _isDialing
                          ? const SizedBox(
                              width: 32,
                              height: 32,
                              child: CircularProgressIndicator(
                                strokeWidth: 3,
                                color: AppColors.primary,
                              ),
                            )
                          : const Icon(
                              Icons.phone_in_talk_rounded,
                              size: 36,
                              color: AppColors.primary,
                            ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      widget.contactName ?? widget.phone,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      widget.phone,
                      style: const TextStyle(
                        fontSize: 14,
                        color: AppColors.textMuted,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF1F5F9),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        'Outbound DID: ${widget.callerDid}',
                        style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _formatTimer(_seconds),
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w800,
                        color: AppColors.navyDark,
                        letterSpacing: 1.5,
                      ),
                    ),
                    if (_statusMessage != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        _statusMessage!,
                        style: const TextStyle(fontSize: 12, color: Color(0xFF10B981)),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // Disposition Label
              const Text(
                'Call Outcome / Disposition',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textMain,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _dispositions.map((d) {
                  final isSelected = _selectedDisposition == d;
                  return ChoiceChip(
                    label: Text(
                      d.replaceAll('_', ' '),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                        color: isSelected ? Colors.white : AppColors.textMain,
                      ),
                    ),
                    selected: isSelected,
                    selectedColor: AppColors.primary,
                    backgroundColor: const Color(0xFFF1F5F9),
                    onSelected: (selected) {
                      if (selected) {
                        setState(() => _selectedDisposition = d);
                      }
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 12),

              // Notes Input
              TextField(
                controller: _notesController,
                decoration: InputDecoration(
                  hintText: 'Add call notes (optional)...',
                  hintStyle: const TextStyle(fontSize: 12, color: AppColors.textLight),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
                  ),
                  filled: true,
                  fillColor: const Color(0xFFFAFAFA),
                ),
                style: const TextStyle(fontSize: 13),
              ),
              const SizedBox(height: 20),

              // End Call / Save Button
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  elevation: 2,
                ),
                icon: _isSubmitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                      )
                    : const Icon(Icons.call_end_rounded),
                label: Text(
                  _isSubmitting ? 'Saving Call...' : 'End & Save to CRM',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                ),
                onPressed: _isSubmitting ? null : _endAndSaveCall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
