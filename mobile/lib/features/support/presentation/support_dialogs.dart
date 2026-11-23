import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../../followups/models/followup_model.dart';
import '../../followups/providers/followups_provider.dart';
import '../models/support_models.dart';
import '../providers/support_customers_provider.dart';

TimeOfDay _parseFollowupTime(String? raw) {
  final value = (raw ?? '').trim();
  if (value.isEmpty) return const TimeOfDay(hour: 10, minute: 0);
  for (final pattern in const ['h:mm a', 'hh:mm a', 'H:mm', 'HH:mm']) {
    try {
      final parsed = DateFormat(pattern).parseStrict(value);
      return TimeOfDay(hour: parsed.hour, minute: parsed.minute);
    } catch (_) {
      // Try the next supported format.
    }
  }
  return const TimeOfDay(hour: 10, minute: 0);
}

DateTime _parseFollowupDate(String? raw) {
  final value = (raw ?? '').trim();
  if (value.isEmpty) return DateTime.now().add(const Duration(days: 1));
  try {
    return DateTime.parse(value);
  } catch (_) {
    return DateTime.now().add(const Duration(days: 1));
  }
}

/// Shared Support follow-up scheduler. It uses the existing Follow-ups API and
/// never writes the Sales-owned lead follow-up fields on the backend.
class SupportFollowupSheet extends StatefulWidget {
  final int? preselectedLeadId;
  final String? preselectedLeadName;
  final FollowupModel? followupToEdit;
  final List<SupportCustomer> customers;

  const SupportFollowupSheet({
    super.key,
    this.preselectedLeadId,
    this.preselectedLeadName,
    this.followupToEdit,
    this.customers = const [],
  });

  static Future<bool?> show(
    BuildContext context, {
    int? preselectedLeadId,
    String? preselectedLeadName,
    FollowupModel? followupToEdit,
    List<SupportCustomer> customers = const [],
  }) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => SupportFollowupSheet(
        preselectedLeadId: preselectedLeadId,
        preselectedLeadName: preselectedLeadName,
        followupToEdit: followupToEdit,
        customers: customers,
      ),
    );
  }

  @override
  State<SupportFollowupSheet> createState() => _SupportFollowupSheetState();
}

class _SupportFollowupSheetState extends State<SupportFollowupSheet> {
  int? _leadId;
  DateTime _date = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _time = const TimeOfDay(hour: 10, minute: 0);
  String _priority = 'MEDIUM';
  String _status = 'Pending';
  bool _isSaving = false;
  final TextEditingController _notesController = TextEditingController();

  @override
  void initState() {
    super.initState();
    final existing = widget.followupToEdit;
    _leadId = existing?.leadId ?? widget.preselectedLeadId;
    if (existing != null) {
      _date = _parseFollowupDate(existing.followupDate);
      _time = _parseFollowupTime(existing.followupTime);
      _priority = existing.priority;
      _status = existing.status;
      _notesController.text = existing.notes ?? '';
    }
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime.now().subtract(const Duration(days: 60)),
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(context: context, initialTime: _time);
    if (picked != null) setState(() => _time = picked);
  }

  Future<void> _save() async {
    if (_isSaving) return;
    if (_leadId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Select a Support customer first.')),
      );
      return;
    }
    setState(() => _isSaving = true);
    final payload = <String, dynamic>{
      'lead_id': _leadId,
      'followup_date': DateFormat('yyyy-MM-dd').format(_date),
      'followup_time': _time.format(context),
      'priority': _priority,
      'status': _status,
      'notes': _notesController.text.trim(),
    };
    final provider = context.read<FollowupsProvider>();
    final success = widget.followupToEdit != null
        ? await provider.updateFollowup(widget.followupToEdit!.id, payload)
        : await provider.createFollowup(payload);
    if (!mounted) return;
    setState(() => _isSaving = false);
    if (success) Navigator.pop(context, true);
    if (!success) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            provider.errorMessage ?? 'Unable to save this follow-up.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final editing = widget.followupToEdit != null;
    final showCustomerPicker =
        _leadId == null &&
        (widget.preselectedLeadName ?? '').trim().isEmpty &&
        widget.customers.isNotEmpty;

    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: SafeArea(
          child: SingleChildScrollView(
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
                    const Icon(
                      Icons.event_available_rounded,
                      color: AppColors.primary,
                      size: 22,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      editing
                          ? 'Edit Support Follow-up'
                          : 'Schedule Support Follow-up',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                if (showCustomerPicker)
                  DropdownButtonFormField<int>(
                    value: _leadId,
                    decoration: const InputDecoration(
                      labelText: 'Support Customer',
                    ),
                    items: widget.customers
                        .map(
                          (customer) => DropdownMenuItem<int>(
                            value: customer.leadId,
                            child: Text(
                              customer.displayCompany,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) => setState(() => _leadId = value),
                  )
                else
                  WacrmTextField(
                    label: 'Support Customer',
                    hintText: editing
                        ? widget.followupToEdit!.leadName
                        : (widget.preselectedLeadName ?? 'Support customer'),
                    readOnly: true,
                    prefixIcon: Icons.business_rounded,
                  ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: _PickerTile(
                        label: 'Follow-up Date',
                        icon: Icons.calendar_today_rounded,
                        value: DateFormat('dd MMM yyyy').format(_date),
                        onTap: _pickDate,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _PickerTile(
                        label: 'Time',
                        icon: Icons.access_time_rounded,
                        value: _time.format(context),
                        onTap: _pickTime,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: DropdownButtonFormField<String>(
                        value: _priority,
                        decoration: const InputDecoration(
                          labelText: 'Priority',
                        ),
                        items: const ['LOW', 'MEDIUM', 'HIGH']
                            .map(
                              (value) => DropdownMenuItem(
                                value: value,
                                child: Text(value),
                              ),
                            )
                            .toList(),
                        onChanged: (value) {
                          if (value != null) setState(() => _priority = value);
                        },
                      ),
                    ),
                    if (editing) ...[
                      const SizedBox(width: 12),
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          value: _status,
                          decoration: const InputDecoration(
                            labelText: 'Status',
                          ),
                          items: const ['Pending', 'Completed', 'Cancelled']
                              .map(
                                (value) => DropdownMenuItem(
                                  value: value,
                                  child: Text(value),
                                ),
                              )
                              .toList(),
                          onChanged: (value) {
                            if (value != null) setState(() => _status = value);
                          },
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 14),
                WacrmTextField(
                  controller: _notesController,
                  label: 'Agenda / Notes',
                  hintText: 'What should Support cover on this follow-up?',
                  maxLines: 3,
                ),
                const SizedBox(height: 18),
                WacrmButton(
                  text: editing ? 'Save Follow-up' : 'Schedule Follow-up',
                  icon: Icons.check_rounded,
                  isLoading: _isSaving,
                  onPressed: _save,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _PickerTile extends StatelessWidget {
  final String label;
  final IconData icon;
  final String value;
  final VoidCallback onTap;

  const _PickerTile({
    required this.label,
    required this.icon,
    required this.value,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppColors.textMain,
          ),
        ),
        const SizedBox(height: 6),
        InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 13),
            decoration: BoxDecoration(
              border: Border.all(color: AppColors.border),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Icon(icon, size: 18, color: AppColors.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    value,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textMain,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// Records a Support interaction against the selected customer and POC.
class SupportInteractionSheet extends StatefulWidget {
  final SupportHistory history;

  const SupportInteractionSheet({super.key, required this.history});

  static Future<bool?> show(
    BuildContext context, {
    required SupportHistory history,
  }) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => SupportInteractionSheet(history: history),
    );
  }

  @override
  State<SupportInteractionSheet> createState() =>
      _SupportInteractionSheetState();
}

class _SupportInteractionSheetState extends State<SupportInteractionSheet> {
  final _discussion = TextEditingController();
  final _problem = TextEditingController();
  final _troubleshooting = TextEditingController();
  final _solution = TextEditingController();
  final _pending = TextEditingController();
  final _nextAction = TextEditingController();
  final _notes = TextEditingController();
  String _type = 'MANUAL';
  int? _pocId;
  bool _scheduleFollowup = false;
  DateTime _followupDate = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _followupTime = const TimeOfDay(hour: 10, minute: 0);
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _pocId = widget.history.primaryPoc?.id;
  }

  @override
  void dispose() {
    _discussion.dispose();
    _problem.dispose();
    _troubleshooting.dispose();
    _solution.dispose();
    _pending.dispose();
    _nextAction.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_isSaving) return;
    final hasContent = [
      _discussion,
      _problem,
      _troubleshooting,
      _solution,
      _pending,
      _nextAction,
      _notes,
    ].any((controller) => controller.text.trim().isNotEmpty);
    if (!hasContent) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Add at least one discussion, problem or action.'),
        ),
      );
      return;
    }
    setState(() => _isSaving = true);
    final payload = <String, dynamic>{
      'customer_id': widget.history.customerId,
      'customer_poc_id': _pocId,
      'interaction_type': _type,
      'discussion': _discussion.text.trim(),
      'problem_reported': _problem.text.trim(),
      'troubleshooting': _troubleshooting.text.trim(),
      'solution_provided': _solution.text.trim(),
      'pending_issues': _pending.text.trim(),
      'next_action': _nextAction.text.trim(),
      'notes': _notes.text.trim(),
      if (_scheduleFollowup)
        'follow_up_at': DateTime(
          _followupDate.year,
          _followupDate.month,
          _followupDate.day,
          _followupTime.hour,
          _followupTime.minute,
        ).toIso8601String(),
    };
    final done = await context.read<SupportCustomersProvider>().addInteraction(
      widget.history.leadId,
      payload,
    );
    if (!mounted) return;
    setState(() => _isSaving = false);
    if (done) Navigator.pop(context, true);
    if (!done) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            context.read<SupportCustomersProvider>().detailError ??
                'Unable to save this interaction.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: SafeArea(
          child: SingleChildScrollView(
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
                    const Icon(
                      Icons.support_agent_rounded,
                      color: AppColors.primary,
                      size: 22,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Add Interaction - ${widget.history.customerName}',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textMain,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: DropdownButtonFormField<String>(
                        value: _type,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Interaction Type',
                        ),
                        items: const ['MANUAL', 'OUTBOUND', 'INBOUND']
                            .map(
                              (value) => DropdownMenuItem(
                                value: value,
                                child: Text(value),
                              ),
                            )
                            .toList(),
                        onChanged: (value) {
                          if (value != null) setState(() => _type = value);
                        },
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: DropdownButtonFormField<int?>(
                        value: _pocId,
                        isExpanded: true,
                        decoration: const InputDecoration(labelText: 'POC'),
                        items: [
                          const DropdownMenuItem<int?>(
                            value: null,
                            child: Text('No specific POC'),
                          ),
                          ...widget.history.pocs.map(
                            (poc) => DropdownMenuItem<int?>(
                              value: poc.id,
                              child: Text(
                                '${poc.name}${poc.isPrimary ? ' (Primary)' : ''}',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ),
                        ],
                        onChanged: (value) => setState(() => _pocId = value),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                WacrmTextField(
                  controller: _discussion,
                  label: 'Discussion / Conversation',
                  hintText: 'What did the customer say?',
                  maxLines: 2,
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _problem,
                  label: 'Problem Reported',
                  hintText: 'Reported issue or symptom',
                  maxLines: 2,
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _troubleshooting,
                  label: 'Troubleshooting Performed',
                  hintText: 'Steps already taken',
                  maxLines: 2,
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _solution,
                  label: 'Solution Provided',
                  hintText: 'Resolution given to the customer',
                  maxLines: 2,
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _pending,
                  label: 'Pending Issue',
                  hintText: 'Leave blank when fully resolved',
                  maxLines: 2,
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _nextAction,
                  label: 'Next Action',
                  hintText: 'Recommended next step',
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _notes,
                  label: 'Internal Notes',
                  hintText: 'Optional internal context',
                  maxLines: 2,
                ),
                const SizedBox(height: 10),
                Material(
                  color: AppColors.card,
                  child: SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text(
                      'Schedule a Support follow-up',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    value: _scheduleFollowup,
                    activeThumbColor: AppColors.primary,
                    onChanged: (value) =>
                        setState(() => _scheduleFollowup = value),
                  ),
                ),
                if (_scheduleFollowup) ...[
                  Row(
                    children: [
                      Expanded(
                        child: _PickerTile(
                          label: 'Follow-up Date',
                          icon: Icons.calendar_today_rounded,
                          value: DateFormat('dd MMM yyyy')
                              .format(_followupDate),
                          onTap: () async {
                            final picked = await showDatePicker(
                              context: context,
                              initialDate: _followupDate,
                              firstDate: DateTime.now(),
                              lastDate: DateTime.now().add(
                                const Duration(days: 730),
                              ),
                            );
                            if (picked != null) {
                              setState(() => _followupDate = picked);
                            }
                          },
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _PickerTile(
                          label: 'Time',
                          icon: Icons.access_time_rounded,
                          value: _followupTime.format(context),
                          onTap: () async {
                            final picked = await showTimePicker(
                              context: context,
                              initialTime: _followupTime,
                            );
                            if (picked != null) {
                              setState(() => _followupTime = picked);
                            }
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'This follow-up is stored inside the Support interaction history.',
                    style: TextStyle(fontSize: 11, color: AppColors.textLight),
                  ),
                ],
                const SizedBox(height: 18),
                WacrmButton(
                  text: 'Save Interaction',
                  icon: Icons.save_rounded,
                  isLoading: _isSaving,
                  onPressed: _save,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Create or edit a customer Point of Contact.
class SupportPocSheet extends StatefulWidget {
  final int leadId;
  final int? customerId;
  final SupportPoc? poc;

  const SupportPocSheet({
    super.key,
    required this.leadId,
    this.customerId,
    this.poc,
  });

  static Future<bool?> show(
    BuildContext context, {
    required int leadId,
    int? customerId,
    SupportPoc? poc,
  }) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) =>
          SupportPocSheet(leadId: leadId, customerId: customerId, poc: poc),
    );
  }

  @override
  State<SupportPocSheet> createState() => _SupportPocSheetState();
}

class _SupportPocSheetState extends State<SupportPocSheet> {
  final _name = TextEditingController();
  final _mobile = TextEditingController();
  final _alternate = TextEditingController();
  final _whatsapp = TextEditingController();
  final _email = TextEditingController();
  final _designation = TextEditingController();
  final _department = TextEditingController();
  final _notes = TextEditingController();
  String _preferred = 'CALL';
  bool _isPrimary = false;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    final poc = widget.poc;
    if (poc != null) {
      _name.text = poc.name;
      _mobile.text = poc.mobile;
      _alternate.text = poc.alternateMobile ?? '';
      _whatsapp.text = poc.whatsappNumber ?? '';
      _email.text = poc.email ?? '';
      _designation.text = poc.designation ?? '';
      _department.text = poc.department ?? '';
      _notes.text = poc.notes ?? '';
      _preferred = poc.preferredContactMethod;
      _isPrimary = poc.isPrimary;
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _mobile.dispose();
    _alternate.dispose();
    _whatsapp.dispose();
    _email.dispose();
    _designation.dispose();
    _department.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_isSaving) return;
    if (_name.text.trim().isEmpty || _mobile.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('POC name and mobile number are required.'),
        ),
      );
      return;
    }
    setState(() => _isSaving = true);
    final payload = <String, dynamic>{
      'name': _name.text.trim(),
      'mobile': _mobile.text.trim(),
      'alternate_mobile': _alternate.text.trim(),
      'whatsapp_number': _whatsapp.text.trim(),
      'email': _email.text.trim(),
      'designation': _designation.text.trim(),
      'department': _department.text.trim(),
      'preferred_contact_method': _preferred,
      'notes': _notes.text.trim(),
      'is_primary': _isPrimary,
    };
    final provider = context.read<SupportCustomersProvider>();
    final done = widget.poc == null
        ? await provider.addPoc(
            widget.leadId,
            payload,
            customerId: widget.customerId,
          )
        : await provider.updatePoc(widget.poc!.id, payload);
    if (!mounted) return;
    setState(() => _isSaving = false);
    if (done) Navigator.pop(context, true);
    if (!done) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(provider.detailError ?? 'Unable to save this POC.'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final editing = widget.poc != null;
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: SafeArea(
          child: SingleChildScrollView(
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
                    const Icon(
                      Icons.contact_phone_rounded,
                      color: AppColors.primary,
                      size: 22,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      editing
                          ? 'Edit Point of Contact'
                          : 'Add Point of Contact',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                WacrmTextField(
                  controller: _name,
                  label: 'POC Name *',
                  hintText: 'Contact person name',
                  prefixIcon: Icons.person_outline_rounded,
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _mobile,
                  label: 'Mobile Number *',
                  hintText: '+91 98765 43210',
                  keyboardType: TextInputType.phone,
                  prefixIcon: Icons.phone_outlined,
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: WacrmTextField(
                        controller: _alternate,
                        label: 'Alternate Mobile',
                        keyboardType: TextInputType.phone,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: WacrmTextField(
                        controller: _whatsapp,
                        label: 'WhatsApp',
                        keyboardType: TextInputType.phone,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _email,
                  label: 'Email',
                  keyboardType: TextInputType.emailAddress,
                  prefixIcon: Icons.mail_outline_rounded,
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: WacrmTextField(
                        controller: _designation,
                        label: 'Designation',
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: WacrmTextField(
                        controller: _department,
                        label: 'Department',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: _preferred,
                  decoration: const InputDecoration(
                    labelText: 'Preferred Contact Method',
                  ),
                  items: const ['CALL', 'WHATSAPP', 'EMAIL', 'SMS']
                      .map(
                        (value) =>
                            DropdownMenuItem(value: value, child: Text(value)),
                      )
                      .toList(),
                  onChanged: (value) {
                    if (value != null) setState(() => _preferred = value);
                  },
                ),
                const SizedBox(height: 12),
                WacrmTextField(
                  controller: _notes,
                  label: 'POC Notes',
                  hintText: 'Best time to call, language, escalation notes...',
                  maxLines: 2,
                ),
                const SizedBox(height: 4),
                Material(
                  color: AppColors.card,
                  child: SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text(
                      'Primary Point of Contact',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    subtitle: const Text(
                      'Only one primary POC is kept per customer.',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppColors.textMuted,
                      ),
                    ),
                    value: _isPrimary,
                    activeThumbColor: AppColors.primary,
                    onChanged: (value) => setState(() => _isPrimary = value),
                  ),
                ),
                const SizedBox(height: 12),
                WacrmButton(
                  text: editing ? 'Save POC' : 'Add POC',
                  icon: Icons.check_rounded,
                  isLoading: _isSaving,
                  onPressed: _save,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Small reusable completion confirmation used by Support follow-up screens.
Future<bool> confirmSupportFollowupCompletion(
  BuildContext context,
  String customerName,
) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Row(
        children: [
          const PingoMascotWidget(pose: PingoPoses.celebrate, height: 34),
          const SizedBox(width: 8),
          const Expanded(
            child: Text(
              'Complete Follow-up',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
      content: Text(
        'Mark the follow-up with $customerName as completed?',
        style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: Colors.white,
            elevation: 0,
          ),
          onPressed: () => Navigator.pop(ctx, true),
          child: const Text('Complete'),
        ),
      ],
    ),
  );
  return result == true;
}
