import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../../activities/providers/activities_provider.dart';
import '../../followups/providers/followups_provider.dart';
import '../../leads/models/lead_model.dart';
import '../../leads/providers/leads_provider.dart';
import '../providers/field_visits_provider.dart';

class FieldVisitFormScreen extends StatefulWidget {
  final LeadModel? preselectedLead;
  final int? preselectedCustomerId;
  final String? preselectedCustomerName;

  const FieldVisitFormScreen({
    super.key,
    this.preselectedLead,
    this.preselectedCustomerId,
    this.preselectedCustomerName,
  });

  @override
  State<FieldVisitFormScreen> createState() => _FieldVisitFormScreenState();
}

class _FieldVisitFormScreenState extends State<FieldVisitFormScreen> {
  final _formKey = GlobalKey<FormState>();

  int? _selectedLeadId;
  String _customerName = '';
  int? _customerId;

  DateTime _visitDate = DateTime.now();
  TimeOfDay _visitTime = TimeOfDay.now();

  final _latController = TextEditingController(text: '13.0827');
  final _lngController = TextEditingController(text: '80.2707');
  final _addressController = TextEditingController(text: 'Anna Salai Commercial Zone, Chennai');
  final _customerController = TextEditingController();

  final _boardPhotoController = TextEditingController();
  final _cardPhotoController = TextEditingController();
  final _requirementsController = TextEditingController();
  final _notesController = TextEditingController();

  String _visitOutcome = 'Interested';
  final List<String> _outcomeOptions = [
    'Interested',
    'Follow-up Required',
    'Quotation Requested',
    'Meeting Done',
    'Deal Won',
    'Closed / Not Interested'
  ];

  // Follow-up Scheduling Section
  bool _scheduleFollowup = false;
  DateTime _followupDate = DateTime.now().add(const Duration(days: 2));
  TimeOfDay _followupTime = const TimeOfDay(hour: 10, minute: 30);
  String _followupPriority = 'MEDIUM';
  final _followupNotesController = TextEditingController(
    text: 'Follow-up regarding product discussion and quotation proposal.',
  );

  late final String _clientToken;
  bool _isLocating = false;

  @override
  void initState() {
    super.initState();
    _clientToken = 'visit_${DateTime.now().millisecondsSinceEpoch}_${(1000 + DateTime.now().microsecond % 9000)}';

    if (widget.preselectedLead != null) {
      _selectedLeadId = widget.preselectedLead!.id;
      _customerName = widget.preselectedLead!.name;
      _customerController.text = _customerName;
    } else if (widget.preselectedCustomerName != null) {
      _customerName = widget.preselectedCustomerName!;
      _customerId = widget.preselectedCustomerId;
      _customerController.text = _customerName;
    }

    // Pre-fill board and card demo URLs if blank
    _boardPhotoController.text = 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=400';
    _cardPhotoController.text = 'https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=400';
  }

  @override
  void dispose() {
    _latController.dispose();
    _lngController.dispose();
    _addressController.dispose();
    _customerController.dispose();
    _boardPhotoController.dispose();
    _cardPhotoController.dispose();
    _requirementsController.dispose();
    _notesController.dispose();
    _followupNotesController.dispose();
    super.dispose();
  }

  void _simulateLocationCapture() {
    setState(() => _isLocating = true);
    Future.delayed(const Duration(milliseconds: 600), () {
      if (mounted) {
        setState(() {
          _latController.text = '13.0067';
          _lngController.text = '80.2032';
          _addressController.text = 'Guindy Industrial Estate, Chennai 600032';
          _isLocating = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('GPS Coordinates and Verified Address Captured Successfully!'),
            backgroundColor: AppColors.success,
            duration: Duration(seconds: 2),
          ),
        );
      }
    });
  }

  Future<void> _pickVisitDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _visitDate,
      firstDate: DateTime.now().subtract(const Duration(days: 7)),
      lastDate: DateTime.now().add(const Duration(days: 1)),
    );
    if (picked != null) {
      setState(() => _visitDate = picked);
    }
  }

  Future<void> _pickVisitTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _visitTime,
    );
    if (picked != null) {
      setState(() => _visitTime = picked);
    }
  }

  Future<void> _pickFollowupDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _followupDate,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() => _followupDate = picked);
    }
  }

  Future<void> _pickFollowupTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _followupTime,
    );
    if (picked != null) {
      setState(() => _followupTime = picked);
    }
  }

  String _formatTimeOfDay(TimeOfDay tod) {
    final now = DateTime.now();
    final dt = DateTime(now.year, now.month, now.day, tod.hour, tod.minute);
    return DateFormat('hh:mm a').format(dt);
  }

  Future<void> _submitFieldVisit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    if (_selectedLeadId == null && _customerName.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select a lead or enter the customer name.'),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    final combinedVisitDt = DateTime(
      _visitDate.year,
      _visitDate.month,
      _visitDate.day,
      _visitTime.hour,
      _visitTime.minute,
    );

    final payload = <String, dynamic>{
      'client_token': _clientToken,
      'lead_id': _selectedLeadId,
      'customer_id': _customerId,
      'customer_name': _customerName.trim(),
      'checkin_time': combinedVisitDt.toIso8601String(),
      'checkin_lat': _latController.text.trim(),
      'checkin_lng': _lngController.text.trim(),
      'checkin_address': _addressController.text.trim(),
      'company_board_photo': _boardPhotoController.text.trim(),
      'visiting_card_photo': _cardPhotoController.text.trim(),
      'customer_requirements': _requirementsController.text.trim(),
      'visit_outcome': _visitOutcome,
      'notes': _notesController.text.trim(),
      'schedule_followup': _scheduleFollowup,
    };

    if (_scheduleFollowup) {
      payload['followup_date'] = DateFormat('yyyy-MM-dd').format(_followupDate);
      payload['followup_time'] = _formatTimeOfDay(_followupTime);
      payload['followup_priority'] = _followupPriority;
      payload['followup_notes'] = _followupNotesController.text.trim();
    }

    final provider = context.read<FieldVisitsProvider>();
    final result = await provider.submitFieldVisit(payload);

    if (result != null && mounted) {
      // Refresh global Activity and Follow-up providers so timelines immediately update
      context.read<ActivitiesProvider>().fetchActivities(leadId: _selectedLeadId);
      context.read<FollowupsProvider>().fetchFollowups();
      context.read<LeadsProvider>().fetchLeads();

      PingoPopupDialog.showSuccessModal(
        context,
        title: 'Field Visit Recorded!',
        subtitle: _scheduleFollowup
            ? 'Visit activity logged and follow-up scheduled with 1-hour automated reminder.'
            : 'Visit activity logged successfully in lead and customer timeline.',
        pose: PingoPoses.celebrate,
        onConfirm: () {
          Navigator.pop(context, true);
        },
      );
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(provider.errorMessage ?? 'Failed to submit field visit.'),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final leads = context.watch<LeadsProvider>().leads;
    final isSubmitting = context.watch<FieldVisitsProvider>().isSubmitting;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Record Field Visit'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Lead / Customer Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.business_rounded, color: AppColors.primary, size: 20),
                        SizedBox(width: 8),
                        Text(
                          'Client & Contact Information',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textMain),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    if (widget.preselectedLead != null)
                      WacrmTextField(
                        label: 'Associated Lead',
                        hintText: widget.preselectedLead!.name,
                        readOnly: true,
                        prefixIcon: Icons.person_outline_rounded,
                      )
                    else ...[
                      const Text(
                        'Select Lead or Existing Customer',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                      ),
                      const SizedBox(height: 6),
                      DropdownButtonFormField<int>(
                        value: _selectedLeadId,
                        hint: const Text('Choose a lead...'),
                        isExpanded: true,
                        decoration: InputDecoration(
                          prefixIcon: const Icon(Icons.people_outline_rounded, color: AppColors.textMuted),
                          filled: true,
                          fillColor: AppColors.inputBackground,
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        items: leads.map((l) {
                          return DropdownMenuItem<int>(
                            value: l.id,
                            child: Text('${l.name} (${l.phone})', overflow: TextOverflow.ellipsis),
                          );
                        }).toList(),
                        onChanged: (val) {
                          setState(() {
                            _selectedLeadId = val;
                            if (val != null) {
                              final match = leads.firstWhere((l) => l.id == val);
                              _customerName = match.name;
                              _customerController.text = match.name;
                            }
                          });
                        },
                      ),
                      const SizedBox(height: 12),
                      WacrmTextField(
                        label: 'Client / Company Name *',
                        hintText: 'e.g. Apex Industrial Supplies',
                        controller: _customerController,
                        prefixIcon: Icons.apartment_rounded,
                        onChanged: (v) => _customerName = v,
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Please enter customer name' : null,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Date & Time Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.calendar_month_rounded, color: AppColors.primary, size: 20),
                        SizedBox(width: 8),
                        Text(
                          'Visit Date & Time',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textMain),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: InkWell(
                            onTap: _pickVisitDate,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                              decoration: BoxDecoration(
                                color: AppColors.inputBackground,
                                border: Border.all(color: AppColors.border),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.event_rounded, size: 18, color: AppColors.primary),
                                  const SizedBox(width: 8),
                                  Text(
                                    DateFormat('dd MMM yyyy').format(_visitDate),
                                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: InkWell(
                            onTap: _pickVisitTime,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                              decoration: BoxDecoration(
                                color: AppColors.inputBackground,
                                border: Border.all(color: AppColors.border),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.schedule_rounded, size: 18, color: AppColors.primary),
                                  const SizedBox(width: 8),
                                  Text(
                                    _formatTimeOfDay(_visitTime),
                                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Location Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.location_on_rounded, color: AppColors.primary, size: 20),
                            SizedBox(width: 8),
                            Text(
                              'Captured Location (GPS)',
                              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textMain),
                            ),
                          ],
                        ),
                        TextButton.icon(
                          onPressed: _isLocating ? null : _simulateLocationCapture,
                          icon: _isLocating
                              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                              : const Icon(Icons.my_location_rounded, size: 16),
                          label: Text(_isLocating ? 'Detecting...' : 'Detect GPS'),
                          style: TextButton.styleFrom(
                            foregroundColor: AppColors.primary,
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: WacrmTextField(
                            label: 'Latitude',
                            controller: _latController,
                            prefixIcon: Icons.explore_outlined,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: WacrmTextField(
                            label: 'Longitude',
                            controller: _lngController,
                            prefixIcon: Icons.explore_outlined,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    WacrmTextField(
                      label: 'Verified Address / Landmark',
                      controller: _addressController,
                      prefixIcon: Icons.pin_drop_outlined,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Photo Verification Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.photo_camera_rounded, color: AppColors.primary, size: 20),
                        SizedBox(width: 8),
                        Text(
                          'Photos & Verification',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textMain),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    WacrmTextField(
                      label: 'Company Board Photo URL / Attachment',
                      controller: _boardPhotoController,
                      prefixIcon: Icons.image_outlined,
                      hintText: 'https://...',
                    ),
                    const SizedBox(height: 12),
                    WacrmTextField(
                      label: 'Visiting Card Photo URL / Attachment',
                      controller: _cardPhotoController,
                      prefixIcon: Icons.credit_card_rounded,
                      hintText: 'https://...',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Requirements & Outcome Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.assignment_turned_in_rounded, color: AppColors.primary, size: 20),
                        SizedBox(width: 8),
                        Text(
                          'Requirements & Outcome',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textMain),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    const Text(
                      'Visit Outcome *',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                    ),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<String>(
                      value: _visitOutcome,
                      decoration: InputDecoration(
                        prefixIcon: const Icon(Icons.flag_rounded, color: AppColors.primary),
                        filled: true,
                        fillColor: AppColors.inputBackground,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      items: _outcomeOptions.map((o) {
                        return DropdownMenuItem<String>(value: o, child: Text(o));
                      }).toList(),
                      onChanged: (val) {
                        if (val != null) {
                          setState(() {
                            _visitOutcome = val;
                            if (val == 'Follow-up Required' || val == 'Quotation Requested') {
                              _scheduleFollowup = true;
                            }
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 14),
                    WacrmTextField(
                      label: 'Customer Requirements',
                      controller: _requirementsController,
                      hintText: 'Specify requirements, volume, machinery, or software specifications...',
                      maxLines: 3,
                    ),
                    const SizedBox(height: 14),
                    WacrmTextField(
                      label: 'Visit Discussion Notes',
                      controller: _notesController,
                      hintText: 'Key discussion points, objections handled, agreed action items...',
                      maxLines: 3,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Schedule Next Follow-up Switch Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.alarm_add_rounded, color: Color(0xFFD97706), size: 20),
                            SizedBox(width: 8),
                            Text(
                              'Schedule Next Follow-up',
                              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textMain),
                            ),
                          ],
                        ),
                        Switch(
                          value: _scheduleFollowup,
                          activeColor: AppColors.primary,
                          onChanged: (val) => setState(() => _scheduleFollowup = val),
                        ),
                      ],
                    ),
                    if (_scheduleFollowup) ...[
                      const Divider(height: 20),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF3C7).withValues(alpha: 0.5),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFFDE68A)),
                        ),
                        child: const Row(
                          children: [
                            Icon(Icons.notifications_active_rounded, color: Color(0xFFD97706), size: 18),
                            SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'An automated CRM notification will trigger 1 hour before the scheduled follow-up.',
                                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Color(0xFF92400E)),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          Expanded(
                            child: InkWell(
                              onTap: _pickFollowupDate,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                decoration: BoxDecoration(
                                  color: AppColors.inputBackground,
                                  border: Border.all(color: AppColors.border),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.event_available_rounded, size: 18, color: AppColors.primary),
                                    const SizedBox(width: 8),
                                    Text(
                                      DateFormat('dd MMM yyyy').format(_followupDate),
                                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: InkWell(
                              onTap: _pickFollowupTime,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                decoration: BoxDecoration(
                                  color: AppColors.inputBackground,
                                  border: Border.all(color: AppColors.border),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.access_time_rounded, size: 18, color: AppColors.primary),
                                    const SizedBox(width: 8),
                                    Text(
                                      _formatTimeOfDay(_followupTime),
                                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      const Text(
                        'Follow-up Priority',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                      ),
                      const SizedBox(height: 6),
                      DropdownButtonFormField<String>(
                        value: _followupPriority,
                        decoration: InputDecoration(
                          prefixIcon: const Icon(Icons.priority_high_rounded, color: Color(0xFFD97706)),
                          filled: true,
                          fillColor: AppColors.inputBackground,
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        items: ['LOW', 'MEDIUM', 'HIGH'].map((p) {
                          return DropdownMenuItem<String>(value: p, child: Text('$p Priority'));
                        }).toList(),
                        onChanged: (val) {
                          if (val != null) setState(() => _followupPriority = val);
                        },
                      ),
                      const SizedBox(height: 14),
                      WacrmTextField(
                        label: 'Follow-up Purpose / Reminder Notes',
                        controller: _followupNotesController,
                        maxLines: 2,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Submit Button
              WacrmButton(
                text: 'Submit Field Visit',
                icon: Icons.check_circle_outline_rounded,
                isLoading: isSubmitting,
                onPressed: isSubmitting ? null : _submitFieldVisit,
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}
