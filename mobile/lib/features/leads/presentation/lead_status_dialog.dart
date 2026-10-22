import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../followups/presentation/followup_create_edit_dialog.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';
import 'deal_won_dialog.dart';

class LeadStatusDialog extends StatefulWidget {
  final LeadModel lead;

  const LeadStatusDialog({super.key, required this.lead});

  static Future<void> show(BuildContext context, LeadModel lead) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => LeadStatusDialog(lead: lead),
    );
  }

  @override
  State<LeadStatusDialog> createState() => _LeadStatusDialogState();
}

class _LeadStatusDialogState extends State<LeadStatusDialog> {
  bool _isUpdating = false;

  final List<String> _statuses = [
    'NEW LEAD',
    'RE-INQUIRY',
    'CONTACTED',
    'INTERESTED',
    'QUALIFIED',
    'DEMO / MEETING',
    'PROPOSAL SENT',
    'NEGOTIATION',
    'FOLLOW-UP',
    'WON',
    'LOST',
  ];

  void _selectStatus(String newStatus) async {
    if (_isUpdating) return;

    if (newStatus == widget.lead.status) {
      Navigator.pop(context);
      return;
    }

    // 1. If status is WON (or legacy CONVERTED), trigger Deal WON Workflow
    if (newStatus == 'WON' || newStatus == 'CONVERTED') {
      Navigator.pop(context);
      DealWonDialog.show(context, widget.lead);
      return;
    }

    // 2. If status is FOLLOW-UP, trigger Follow-up Scheduling Dialog
    if (newStatus == 'FOLLOW-UP' || newStatus == 'FOLLOW_UP') {
      Navigator.pop(context);
      FollowupCreateEditDialog.show(
        context,
        preselectedLeadId: widget.lead.id,
        preselectedLeadName: widget.lead.name,
      );
      return;
    }

    setState(() => _isUpdating = true);
    final provider = context.read<LeadsProvider>();
    final updated = await provider.updateLeadStatus(widget.lead.id, newStatus);
    setState(() => _isUpdating = false);

    if (mounted) {
      Navigator.pop(context);
      if (updated != null) {
        // Trigger matching Pingo mascot celebration modal
        final pose = PingoPoses.mapStatusToPose(newStatus);
        PingoPopupDialog.showSuccessModal(
          context,
          title: 'Status Updated!',
          subtitle: 'Lead status has been changed to ${newStatus.replaceAll('_', ' ')} successfully.',
          pose: pose,
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(provider.errorMessage ?? 'Failed to update status'),
            backgroundColor: AppColors.danger,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Update Lead Status',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textMain,
                        ),
                      ),
                      Text(
                        widget.lead.name,
                        style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
                      ),
                    ],
                  ),
                ),
                WacrmBadge.status(widget.lead.status),
              ],
            ),
            const SizedBox(height: 16),
            if (_isUpdating)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(24.0),
                  child: CircularProgressIndicator(color: AppColors.primary),
                ),
              )
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _statuses.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final s = _statuses[index];
                  final isCurrent = s == widget.lead.status;
                  final pose = PingoPoses.mapStatusToPose(s);

                  return ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    leading: PingoMascotWidget(
                      pose: pose,
                      height: 36,
                    ),
                    title: Text(
                      s.replaceAll('_', ' '),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: isCurrent ? FontWeight.w700 : FontWeight.w500,
                        color: isCurrent ? AppColors.primary : AppColors.textMain,
                      ),
                    ),
                    trailing: isCurrent
                        ? const Icon(Icons.check_circle_rounded, color: AppColors.primary, size: 20)
                        : const Icon(Icons.chevron_right_rounded, color: AppColors.textLight, size: 20),
                    onTap: () => _selectStatus(s),
                  );
                },
              ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }
}
