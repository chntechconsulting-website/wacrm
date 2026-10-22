import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../../leads/providers/leads_provider.dart';
import '../models/followup_model.dart';
import '../providers/followups_provider.dart';

class FollowupCreateEditDialog extends StatefulWidget {
  final int? preselectedLeadId;
  final String? preselectedLeadName;
  final FollowupModel? followupToEdit;

  const FollowupCreateEditDialog({
    super.key,
    this.preselectedLeadId,
    this.preselectedLeadName,
    this.followupToEdit,
  });

  static Future<bool?> show(
    BuildContext context, {
    int? preselectedLeadId,
    String? preselectedLeadName,
    FollowupModel? followupToEdit,
  }) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => FollowupCreateEditDialog(
        preselectedLeadId: preselectedLeadId,
        preselectedLeadName: preselectedLeadName,
        followupToEdit: followupToEdit,
      ),
    );
  }

  @override
  State<FollowupCreateEditDialog> createState() => _FollowupCreateEditDialogState();
}

class _FollowupCreateEditDialogState extends State<FollowupCreateEditDialog> {
  final _formKey = GlobalKey<FormState>();
  int? _leadId;
  DateTime _selectedDate = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _selectedTime = const TimeOfDay(hour: 10, minute: 0);
  String _priority = 'MEDIUM';
  String _status = 'Pending';
  final _notesController = TextEditingController();
  bool _isSaving = false;

  final List<String> _priorities = ['LOW', 'MEDIUM', 'HIGH'];
  final List<String> _statuses = ['Pending', 'Completed', 'Cancelled'];

  @override
  void initState() {
    super.initState();
    if (widget.followupToEdit != null) {
      final f = widget.followupToEdit!;
      _leadId = f.leadId;
      try {
        _selectedDate = DateTime.parse(f.followupDate);
      } catch (_) {}
      _priority = f.priority;
      _status = f.status;
      _notesController.text = f.notes ?? '';
    } else {
      _leadId = widget.preselectedLeadId;
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LeadsProvider>().fetchLeads();
    });
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  void _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime.now().subtract(const Duration(days: 30)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() => _selectedDate = picked);
    }
  }

  void _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _selectedTime,
    );
    if (picked != null) {
      setState(() => _selectedTime = picked);
    }
  }

  void _handleSave() async {
    if (_isSaving) return;

    if (_leadId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a lead to schedule a follow-up for.')),
      );
      return;
    }

    setState(() => _isSaving = true);
    final followupsProvider = context.read<FollowupsProvider>();

    final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
    final timeStr = _selectedTime.format(context);

    final isEdit = widget.followupToEdit != null;

    final payload = {
      'lead_id': _leadId,
      'followup_date': dateStr,
      'followup_time': timeStr,
      'priority': _priority,
      'status': _status,
      'notes': _notesController.text.trim(),
    };

    final bool success;
    if (isEdit) {
      success = await followupsProvider.updateFollowup(widget.followupToEdit!.id, payload);
    } else {
      success = await followupsProvider.createFollowup(payload);
    }

    setState(() => _isSaving = false);

    if (mounted) {
      Navigator.pop(context, success);
      if (success) {
        // Also refresh LeadsProvider so lead details reflect the updated schedule
        try {
          context.read<LeadsProvider>().fetchLeads(refresh: true);
        } catch (_) {}

        PingoPopupDialog.show(
          context,
          title: isEdit ? 'Follow-up Updated' : 'Follow-up Scheduled',
          subtitle: '$statusText for $dateStr at $timeStr.',
          badge: isEdit ? 'UPDATED' : 'SCHEDULED',
          pose: PingoPoses.pointRight,
        );
      }
    }
  }

  String get statusText => _status == 'Completed' ? 'Completed interaction' : 'Scheduled';

  @override
  Widget build(BuildContext context) {
    final leads = context.watch<LeadsProvider>().leads;

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: SafeArea(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
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
                    const Icon(Icons.calendar_month_rounded, color: AppColors.primary, size: 22),
                    const SizedBox(width: 8),
                    Text(
                      widget.followupToEdit != null ? 'Edit / Reschedule Follow-up' : 'Schedule Follow-up',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Lead Selection
                if (widget.followupToEdit != null)
                  WacrmTextField(
                    label: 'Target Lead',
                    hintText: widget.followupToEdit!.leadName,
                    readOnly: true,
                    prefixIcon: Icons.person_outline_rounded,
                  )
                else if (widget.preselectedLeadName != null)
                  WacrmTextField(
                    label: 'Target Lead',
                    hintText: widget.preselectedLeadName,
                    readOnly: true,
                    prefixIcon: Icons.person_outline_rounded,
                  )
                else
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Select Lead *',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                      ),
                      const SizedBox(height: 6),
                      DropdownButtonFormField<int>(
                        value: _leadId,
                        hint: const Text('Choose lead...'),
                        items: leads.map((l) {
                          return DropdownMenuItem<int>(
                            value: l.id,
                            child: Text('${l.name} (${l.company ?? l.phone})'),
                          );
                        }).toList(),
                        onChanged: (val) => setState(() => _leadId = val),
                      ),
                    ],
                  ),
                const SizedBox(height: 14),

                // Date & Time pickers
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Follow-up Date',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                          ),
                          const SizedBox(height: 6),
                          InkWell(
                            onTap: _pickDate,
                            borderRadius: BorderRadius.circular(10),
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                              decoration: BoxDecoration(
                                border: Border.all(color: AppColors.border),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.event_outlined, size: 18, color: AppColors.primary),
                                  const SizedBox(width: 8),
                                  Text(
                                    DateFormat('dd MMM yyyy').format(_selectedDate),
                                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Time',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                          ),
                          const SizedBox(height: 6),
                          InkWell(
                            onTap: _pickTime,
                            borderRadius: BorderRadius.circular(10),
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                              decoration: BoxDecoration(
                                border: Border.all(color: AppColors.border),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.access_time_outlined, size: 18, color: AppColors.primary),
                                  const SizedBox(width: 8),
                                  Text(
                                    _selectedTime.format(context),
                                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),

                // Priority & Status (if edit)
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Priority',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                          ),
                          const SizedBox(height: 6),
                          DropdownButtonFormField<String>(
                            value: _priority,
                            items: _priorities.map((p) {
                              return DropdownMenuItem(value: p, child: Text(p));
                            }).toList(),
                            onChanged: (val) {
                              if (val != null) setState(() => _priority = val);
                            },
                          ),
                        ],
                      ),
                    ),
                    if (widget.followupToEdit != null) ...[
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Status',
                              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                            ),
                            const SizedBox(height: 6),
                            DropdownButtonFormField<String>(
                              value: _status,
                              items: _statuses.map((s) {
                                return DropdownMenuItem(value: s, child: Text(s));
                              }).toList(),
                              onChanged: (val) {
                                if (val != null) setState(() => _status = val);
                              },
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 14),

                WacrmTextField(
                  controller: _notesController,
                  label: 'Follow-up Agenda / Notes',
                  hintText: 'e.g. Call client to discuss commercial quotation...',
                  maxLines: 2,
                ),
                const SizedBox(height: 22),

                WacrmButton(
                  text: widget.followupToEdit != null ? 'Save Changes' : 'Confirm Schedule',
                  isLoading: _isSaving,
                  icon: Icons.check_rounded,
                  onPressed: _handleSave,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
