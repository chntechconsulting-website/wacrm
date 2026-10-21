import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../../leads/providers/leads_provider.dart';
import '../providers/followups_provider.dart';

class FollowupCreateEditDialog extends StatefulWidget {
  final int? preselectedLeadId;
  final String? preselectedLeadName;

  const FollowupCreateEditDialog({
    super.key,
    this.preselectedLeadId,
    this.preselectedLeadName,
  });

  static Future<void> show(
    BuildContext context, {
    int? preselectedLeadId,
    String? preselectedLeadName,
  }) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => FollowupCreateEditDialog(
        preselectedLeadId: preselectedLeadId,
        preselectedLeadName: preselectedLeadName,
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
  final _notesController = TextEditingController();
  bool _isSaving = false;

  final List<String> _priorities = ['LOW', 'MEDIUM', 'HIGH'];

  @override
  void initState() {
    super.initState();
    _leadId = widget.preselectedLeadId;
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
      firstDate: DateTime.now(),
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

    final payload = {
      'lead_id': _leadId,
      'followup_date': dateStr,
      'followup_time': timeStr,
      'priority': _priority,
      'status': 'Pending',
      if (_notesController.text.trim().isNotEmpty) 'notes': _notesController.text.trim(),
    };

    final success = await followupsProvider.createFollowup(payload);
    setState(() => _isSaving = false);

    if (mounted) {
      Navigator.pop(context);
      if (success) {
        PingoPopupDialog.show(
          context,
          title: 'Follow-up Scheduled',
          subtitle: 'Scheduled for $dateStr at $timeStr.',
          badge: 'SCHEDULED',
          pose: PingoPoses.pointRight,
        );
      }
    }
  }

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
                const Row(
                  children: [
                    Icon(Icons.calendar_month_rounded, color: AppColors.primary, size: 22),
                    SizedBox(width: 8),
                    Text(
                      'Schedule Follow-up',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Lead Selection
                if (widget.preselectedLeadName != null)
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

                // Priority Selection
                Column(
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
                const SizedBox(height: 14),

                WacrmTextField(
                  controller: _notesController,
                  label: 'Follow-up Agenda / Notes',
                  hintText: 'e.g. Call client to discuss commercial quotation...',
                  maxLines: 2,
                ),
                const SizedBox(height: 22),

                WacrmButton(
                  text: 'Confirm Schedule',
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
