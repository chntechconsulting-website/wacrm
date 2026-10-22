import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';

class LeadCreateEditScreen extends StatefulWidget {
  final LeadModel? leadToEdit;

  const LeadCreateEditScreen({super.key, this.leadToEdit});

  @override
  State<LeadCreateEditScreen> createState() => _LeadCreateEditScreenState();
}

class _LeadCreateEditScreenState extends State<LeadCreateEditScreen> {
  final _formKey = GlobalKey<FormState>();

  // 1. Contact Information Controllers
  late TextEditingController _firstNameController;
  late TextEditingController _lastNameController;
  late TextEditingController _phoneController;
  late TextEditingController _whatsappNumberController;
  late TextEditingController _emailController;
  late TextEditingController _designationController;

  // 2. Company Information Controllers
  late TextEditingController _companyController;
  late TextEditingController _industryController;
  late TextEditingController _websiteController;
  late TextEditingController _companySizeController;
  late TextEditingController _cityController;
  late TextEditingController _stateController;

  // 3. Lead Details & Assignment
  late TextEditingController _campaignNameController;
  String _source = 'MANUAL';
  String _status = 'NEW LEAD';
  String _rating = 'Warm';
  String _priority = 'Medium';
  int? _assignedTo;

  // 4. Requirement Notes
  late TextEditingController _requirementNotesController;

  // 5. Follow-up Schedule
  DateTime? _followupDate;
  String _followupTime = '10:00 AM';

  bool _isSaving = false;

  // Web-synchronized Option Lists
  static const List<String> _statusOptions = [
    'NEW LEAD',
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

  static const List<String> _sourceOptions = [
    'MANUAL',
    'META',
    'WEBSITE',
    'EXCEL',
    'REFERRAL',
  ];

  static const List<String> _ratingOptions = ['Hot', 'Warm', 'Cold'];
  static const List<String> _priorityOptions = ['High', 'Medium', 'Low'];

  static const List<String> _timePresets = [
    '10:00 AM',
    '11:30 AM',
    '02:00 PM',
    '04:30 PM',
    '06:00 PM',
  ];

  @override
  void initState() {
    super.initState();
    final lead = widget.leadToEdit;

    // Split name if first/last name not explicitly populated
    String initialFirst = lead?.firstName ?? '';
    String initialLast = lead?.lastName ?? '';
    if (initialFirst.isEmpty && lead != null && lead.name.isNotEmpty) {
      final parts = lead.name.trim().split(RegExp(r'\s+'));
      if (parts.isNotEmpty) initialFirst = parts[0];
      if (parts.length > 1) initialLast = parts.sublist(1).join(' ');
    }

    // 1. Contact Controllers
    _firstNameController = TextEditingController(text: initialFirst);
    _lastNameController = TextEditingController(text: initialLast);
    _phoneController = TextEditingController(text: lead?.phone ?? '');
    _whatsappNumberController = TextEditingController(text: lead?.whatsappNumber ?? '');
    _emailController = TextEditingController(text: lead?.email ?? '');
    _designationController = TextEditingController(text: lead?.designation ?? '');

    // 2. Company Controllers
    _companyController = TextEditingController(text: lead?.company ?? '');
    _industryController = TextEditingController(text: lead?.industry ?? '');
    _websiteController = TextEditingController(text: lead?.website ?? '');
    _companySizeController = TextEditingController(text: lead?.companySize ?? '');
    _cityController = TextEditingController(text: lead?.city ?? '');
    _stateController = TextEditingController(text: lead?.state ?? '');

    // 3. Lead Details
    _campaignNameController = TextEditingController(text: lead?.campaignName ?? '');

    if (lead != null) {
      // Normalize source
      final srcUpper = (lead.source ?? 'MANUAL').toUpperCase();
      if (_sourceOptions.contains(srcUpper)) {
        _source = srcUpper;
      } else {
        _source = _sourceOptions.first;
      }

      // Normalize status
      final stClean = lead.status.replaceAll('_', ' ').toUpperCase();
      if (_statusOptions.contains(stClean)) {
        _status = stClean;
      } else if (stClean == 'NEW') {
        _status = 'NEW LEAD';
      } else if (stClean == 'IN PROGRESS') {
        _status = 'CONTACTED';
      } else {
        _status = _statusOptions.first;
      }

      // Normalize rating
      final rClean = lead.rating != null && lead.rating!.isNotEmpty
          ? '${lead.rating![0].toUpperCase()}${lead.rating!.substring(1).toLowerCase()}'
          : 'Warm';
      _rating = _ratingOptions.contains(rClean) ? rClean : 'Warm';

      // Normalize priority
      final pClean = lead.priority != null && lead.priority!.isNotEmpty
          ? '${lead.priority![0].toUpperCase()}${lead.priority!.substring(1).toLowerCase()}'
          : 'Medium';
      _priority = _priorityOptions.contains(pClean) ? pClean : 'Medium';

      _assignedTo = lead.assignedTo;

      // Follow-up
      if (lead.followupDate != null && lead.followupDate!.isNotEmpty) {
        try {
          _followupDate = DateTime.parse(lead.followupDate!);
        } catch (_) {}
      }
      if (lead.followupTime != null && lead.followupTime!.isNotEmpty) {
        _followupTime = lead.followupTime!;
      }
    } else {
      // Default assignment to current user's employee ID if available
      final currentUser = context.read<AuthProvider>().currentUser;
      if (currentUser?.employeeId != null) {
        _assignedTo = currentUser!.employeeId;
      }
    }

    // 4. Requirement Notes
    _requirementNotesController = TextEditingController(
      text: lead?.requirementNotes ?? lead?.requirement ?? '',
    );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LeadsProvider>().fetchEmployees();
    });
  }

  @override
  void dispose() {
    _firstNameController.dispose();
    _lastNameController.dispose();
    _phoneController.dispose();
    _whatsappNumberController.dispose();
    _emailController.dispose();
    _designationController.dispose();

    _companyController.dispose();
    _industryController.dispose();
    _websiteController.dispose();
    _companySizeController.dispose();
    _cityController.dispose();
    _stateController.dispose();

    _campaignNameController.dispose();
    _requirementNotesController.dispose();
    super.dispose();
  }

  String _formatDateForApi(DateTime date) {
    return '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  String _formatDisplayDate(DateTime date) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${date.day} ${months[date.month - 1]} ${date.year}';
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _followupDate ?? now,
      firstDate: now.subtract(const Duration(days: 30)),
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() => _followupDate = picked);
    }
  }

  Future<void> _pickCustomTime() async {
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );
    if (time != null && mounted) {
      final hour = time.hourOfPeriod == 0 ? 12 : time.hourOfPeriod;
      final minute = time.minute.toString().padLeft(2, '0');
      final period = time.period == DayPeriod.am ? 'AM' : 'PM';
      setState(() {
        _followupTime = '$hour:$minute $period';
      });
    }
  }

  void _handleSave() async {
    if (!_formKey.currentState!.validate()) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please fill all required fields (First Name, Last Name, Phone Number).'),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    setState(() => _isSaving = true);
    final provider = context.read<LeadsProvider>();

    final firstName = _firstNameController.text.trim();
    final lastName = _lastNameController.text.trim();
    final fullName = lastName.isNotEmpty ? '$firstName $lastName' : firstName;

    final payload = <String, dynamic>{
      'first_name': firstName,
      'last_name': lastName,
      'name': fullName,
      'phone': _phoneController.text.trim(),
      if (_whatsappNumberController.text.trim().isNotEmpty)
        'whatsapp_number': _whatsappNumberController.text.trim(),
      if (_emailController.text.trim().isNotEmpty)
        'email': _emailController.text.trim(),
      if (_designationController.text.trim().isNotEmpty)
        'designation': _designationController.text.trim(),
      if (_companyController.text.trim().isNotEmpty)
        'company': _companyController.text.trim(),
      if (_industryController.text.trim().isNotEmpty)
        'industry': _industryController.text.trim(),
      if (_websiteController.text.trim().isNotEmpty)
        'website': _websiteController.text.trim(),
      if (_companySizeController.text.trim().isNotEmpty)
        'company_size': _companySizeController.text.trim(),
      if (_cityController.text.trim().isNotEmpty)
        'city': _cityController.text.trim(),
      if (_stateController.text.trim().isNotEmpty)
        'state': _stateController.text.trim(),
      'source': _source,
      'status': _status,
      if (_campaignNameController.text.trim().isNotEmpty)
        'campaign_name': _campaignNameController.text.trim(),
      'rating': _rating,
      'priority': _priority,
      'assigned_to': _assignedTo,
      if (_requirementNotesController.text.trim().isNotEmpty) ...{
        'requirement': _requirementNotesController.text.trim(),
        'requirement_notes': _requirementNotesController.text.trim(),
      },
      if (_followupDate != null)
        'followup_date': _formatDateForApi(_followupDate!),
      if (_followupDate != null)
        'followup_time': _followupTime,
    };

    bool success = false;
    if (widget.leadToEdit != null) {
      success = await provider.updateLead(widget.leadToEdit!.id, payload);
    } else {
      success = await provider.createLead(payload);
    }

    setState(() => _isSaving = false);

    if (mounted) {
      if (success) {
        Navigator.pop(context, true);
        PingoPopupDialog.show(
          context,
          title: widget.leadToEdit != null ? 'Lead Updated Successfully' : 'Lead Created Successfully',
          subtitle: '$fullName has been registered into your CRM pipeline.',
          badge: widget.leadToEdit != null ? 'LEAD UPDATED' : 'LEAD CREATED',
          pose: PingoPoses.celebrate,
        );
      } else {
        final err = provider.errorMessage ?? 'Failed to save lead. Please verify all inputs.';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(err), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEditing = widget.leadToEdit != null;
    final employees = context.watch<LeadsProvider>().employees;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF162A45)),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          isEditing ? 'Edit Lead Information' : 'Create New Lead',
          style: const TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w800,
            color: Color(0xFF0F172A),
          ),
        ),
        centerTitle: false,
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, -3),
            ),
          ],
        ),
        child: SafeArea(
          child: Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 48,
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      side: const BorderSide(color: Color(0xFFCBD5E1)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: _isSaving ? null : () => Navigator.pop(context),
                    child: const Text(
                      'Cancel',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF475569)),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: WacrmButton(
                  text: isEditing ? 'Save Changes' : 'Create Lead',
                  isLoading: _isSaving,
                  icon: isEditing ? Icons.save_rounded : Icons.person_add_alt_1_rounded,
                  height: 48,
                  onPressed: _handleSave,
                ),
              ),
            ],
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header Banner Card
              _buildHeaderBanner(isEditing),

              const SizedBox(height: 14),

              // SECTION 1: CONTACT INFORMATION
              _buildSectionCard(
                title: 'Contact Information',
                icon: Icons.person_outline_rounded,
                iconColor: const Color(0xFF2563EB),
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _buildTextField(
                          controller: _firstNameController,
                          label: 'First Name *',
                          hintText: 'e.g. John',
                          validator: (val) => val == null || val.trim().isEmpty ? 'Required' : null,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildTextField(
                          controller: _lastNameController,
                          label: 'Last Name *',
                          hintText: 'e.g. Doe',
                          validator: (val) => val == null || val.trim().isEmpty ? 'Required' : null,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildTextField(
                          controller: _phoneController,
                          label: 'Mobile Number *',
                          hintText: '+91 9876543210',
                          keyboardType: TextInputType.phone,
                          prefixIcon: Icons.phone_outlined,
                          validator: (val) {
                            if (val == null || val.trim().isEmpty) return 'Required';
                            if (val.trim().length < 8) return 'Min 8 digits';
                            return null;
                          },
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildTextField(
                          controller: _whatsappNumberController,
                          label: 'WhatsApp Number',
                          hintText: '+91 9876543210',
                          keyboardType: TextInputType.phone,
                          prefixIcon: Icons.chat_outlined,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildTextField(
                          controller: _emailController,
                          label: 'Email Address',
                          hintText: 'name@company.com',
                          keyboardType: TextInputType.emailAddress,
                          prefixIcon: Icons.email_outlined,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildTextField(
                          controller: _designationController,
                          label: 'Designation',
                          hintText: 'e.g. Sales Manager',
                          prefixIcon: Icons.badge_outlined,
                        ),
                      ),
                    ],
                  ),
                ],
              ),

              // SECTION 2: COMPANY INFORMATION
              _buildSectionCard(
                title: 'Company Information',
                icon: Icons.business_outlined,
                iconColor: const Color(0xFF6366F1),
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _buildTextField(
                          controller: _companyController,
                          label: 'Company Name',
                          hintText: 'e.g. Acme Tech Pvt Ltd',
                          prefixIcon: Icons.apartment_rounded,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildTextField(
                          controller: _industryController,
                          label: 'Industry',
                          hintText: 'e.g. Retail / IT',
                          prefixIcon: Icons.category_outlined,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildTextField(
                          controller: _websiteController,
                          label: 'Website',
                          hintText: 'https://example.com',
                          keyboardType: TextInputType.url,
                          prefixIcon: Icons.language_rounded,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildTextField(
                          controller: _companySizeController,
                          label: 'Company Size',
                          hintText: 'e.g. 10-50 employees',
                          prefixIcon: Icons.groups_outlined,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildTextField(
                          controller: _cityController,
                          label: 'City',
                          hintText: 'e.g. Mumbai',
                          prefixIcon: Icons.location_city_rounded,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildTextField(
                          controller: _stateController,
                          label: 'State',
                          hintText: 'e.g. Maharashtra',
                          prefixIcon: Icons.map_outlined,
                        ),
                      ),
                    ],
                  ),
                ],
              ),

              // SECTION 3: LEAD DETAILS & ASSIGNMENT
              _buildSectionCard(
                title: 'Lead Details & Assignment',
                icon: Icons.tune_rounded,
                iconColor: const Color(0xFFE5252A),
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdownField<String>(
                          label: 'Lead Source',
                          value: _source,
                          items: _sourceOptions.map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
                          onChanged: (val) {
                            if (val != null) setState(() => _source = val);
                          },
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildDropdownField<String>(
                          label: 'Initial Status',
                          value: _status,
                          items: _statusOptions.map((st) => DropdownMenuItem(value: st, child: Text(st))).toList(),
                          onChanged: (val) {
                            if (val != null) setState(() => _status = val);
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildTextField(
                          controller: _campaignNameController,
                          label: 'Campaign Name',
                          hintText: 'e.g. Summer Promo 2026',
                          prefixIcon: Icons.campaign_outlined,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildDropdownField<String>(
                          label: 'Rating',
                          value: _rating,
                          items: _ratingOptions.map((r) => DropdownMenuItem(value: r, child: Text(r))).toList(),
                          onChanged: (val) {
                            if (val != null) setState(() => _rating = val);
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdownField<int?>(
                          label: 'Assign To',
                          value: _assignedTo,
                          hintText: '-- Unassigned --',
                          items: [
                            const DropdownMenuItem<int?>(
                              value: null,
                              child: Text('-- Unassigned --', style: TextStyle(color: Color(0xFF94A3B8))),
                            ),
                            ...employees.map((emp) => DropdownMenuItem<int?>(
                                  value: emp.id,
                                  child: Text(
                                    '${emp.name} (${emp.designation ?? emp.role ?? 'Sales'})',
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                )),
                          ],
                          onChanged: (val) => setState(() => _assignedTo = val),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildDropdownField<String>(
                          label: 'Priority',
                          value: _priority,
                          items: _priorityOptions.map((p) => DropdownMenuItem(value: p, child: Text(p))).toList(),
                          onChanged: (val) {
                            if (val != null) setState(() => _priority = val);
                          },
                        ),
                      ),
                    ],
                  ),
                ],
              ),

              // SECTION 4: REQUIREMENT NOTES
              _buildSectionCard(
                title: 'Requirement & Discovery Notes',
                icon: Icons.notes_rounded,
                iconColor: const Color(0xFF0D9488),
                children: [
                  _buildTextField(
                    controller: _requirementNotesController,
                    label: 'Requirements / Customer Notes',
                    hintText: 'Describe client requirements, inquiries, product interest or call discussion notes...',
                    maxLines: 3,
                  ),
                ],
              ),

              // SECTION 5: FOLLOW-UP SCHEDULE
              _buildSectionCard(
                title: 'Follow-up Schedule',
                icon: Icons.calendar_month_rounded,
                iconColor: const Color(0xFF8B5CF6),
                children: [
                  Row(
                    children: [
                      // Date Picker Box
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Follow-up Date',
                              style: TextStyle(
                                fontSize: 12.5,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFF334155),
                              ),
                            ),
                            const SizedBox(height: 6),
                            InkWell(
                              onTap: _pickDate,
                              borderRadius: BorderRadius.circular(10),
                              child: Container(
                                height: 46,
                                padding: const EdgeInsets.symmetric(horizontal: 12),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFF8FAFC),
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(color: const Color(0xFFE2E8F0)),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.event_rounded, size: 18, color: Color(0xFF64748B)),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        _followupDate != null ? _formatDisplayDate(_followupDate!) : 'Select Date',
                                        style: TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w500,
                                          color: _followupDate != null ? const Color(0xFF0F172A) : const Color(0xFF94A3B8),
                                        ),
                                      ),
                                    ),
                                    if (_followupDate != null)
                                      GestureDetector(
                                        onTap: () => setState(() => _followupDate = null),
                                        child: const Icon(Icons.close_rounded, size: 16, color: Color(0xFF94A3B8)),
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 10),
                      // Time Picker Box
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Follow-up Time',
                              style: TextStyle(
                                fontSize: 12.5,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFF334155),
                              ),
                            ),
                            const SizedBox(height: 6),
                            InkWell(
                              onTap: _pickCustomTime,
                              borderRadius: BorderRadius.circular(10),
                              child: Container(
                                height: 46,
                                padding: const EdgeInsets.symmetric(horizontal: 12),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFF8FAFC),
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(color: const Color(0xFFE2E8F0)),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.access_time_rounded, size: 18, color: Color(0xFF64748B)),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        _followupTime,
                                        style: const TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w600,
                                          color: Color(0xFF0F172A),
                                        ),
                                      ),
                                    ),
                                    const Icon(Icons.arrow_drop_down_rounded, size: 20, color: Color(0xFF64748B)),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  // Quick Time Presets
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: _timePresets.map((time) {
                      final isSel = _followupTime == time;
                      return ChoiceChip(
                        label: Text(time),
                        selected: isSel,
                        selectedColor: const Color(0xFF8B5CF6),
                        backgroundColor: const Color(0xFFF1F5F9),
                        labelStyle: TextStyle(
                          fontSize: 11,
                          fontWeight: isSel ? FontWeight.w700 : FontWeight.w500,
                          color: isSel ? Colors.white : const Color(0xFF475569),
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                          side: BorderSide(
                            color: isSel ? const Color(0xFF8B5CF6) : const Color(0xFFE2E8F0),
                          ),
                        ),
                        onSelected: (_) {
                          setState(() => _followupTime = time);
                        },
                      );
                    }).toList(),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderBanner(bool isEditing) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(
          colors: [
            Color(0xFF1E3A5F),
            Color(0xFF162A45),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF162A45).withValues(alpha: 0.2),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isEditing ? 'Update Lead Details' : 'Manual Lead Registration',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  isEditing
                      ? 'Modify existing contact, company, pipeline status, or schedule.'
                      : 'Enter prospective client information across all CRM modules.',
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xFF94A3B8),
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          const PingoMascotWidget(
            pose: PingoPoses.salute,
            height: 64,
          ),
        ],
      ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required IconData icon,
    required Color iconColor,
    required List<Widget> children,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 16, color: iconColor),
              ),
              const SizedBox(width: 8),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF0F172A),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ...children,
        ],
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hintText,
    IconData? prefixIcon,
    TextInputType keyboardType = TextInputType.text,
    String? Function(String?)? validator,
    int maxLines = 1,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: Color(0xFF334155),
          ),
        ),
        const SizedBox(height: 6),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          validator: validator,
          maxLines: maxLines,
          style: const TextStyle(fontSize: 13, color: Color(0xFF0F172A), fontWeight: FontWeight.w500),
          decoration: InputDecoration(
            hintText: hintText,
            hintStyle: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
            prefixIcon: prefixIcon != null ? Icon(prefixIcon, size: 17, color: const Color(0xFF64748B)) : null,
            contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
            filled: true,
            fillColor: const Color(0xFFF8FAFC),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: Color(0xFF2563EB), width: 1.5),
            ),
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: Color(0xFFE5252A)),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDropdownField<T>({
    required String label,
    required T? value,
    required List<DropdownMenuItem<T>> items,
    required ValueChanged<T?> onChanged,
    String? hintText,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: Color(0xFF334155),
          ),
        ),
        const SizedBox(height: 6),
        Container(
          height: 44,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            color: const Color(0xFFF8FAFC),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<T>(
              value: value,
              isExpanded: true,
              hint: hintText != null ? Text(hintText, style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8))) : null,
              items: items,
              onChanged: onChanged,
              icon: const Icon(Icons.keyboard_arrow_down_rounded, size: 18, color: Color(0xFF64748B)),
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF0F172A), fontWeight: FontWeight.w600),
            ),
          ),
        ),
      ],
    );
  }
}
