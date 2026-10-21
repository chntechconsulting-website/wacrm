import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_text_field.dart';
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
  late TextEditingController _nameController;
  late TextEditingController _phoneController;
  late TextEditingController _emailController;
  late TextEditingController _companyController;
  late TextEditingController _requirementController;

  String _priority = 'MEDIUM';
  String _source = 'Manual';
  int? _assignedTo;
  bool _isSaving = false;

  final List<String> _priorities = ['LOW', 'MEDIUM', 'HIGH'];
  final List<String> _sources = ['Manual', 'Website', 'Meta Ads', 'Referral', 'Cold Call', 'Walk-in'];

  @override
  void initState() {
    super.initState();
    final lead = widget.leadToEdit;
    _nameController = TextEditingController(text: lead?.name ?? '');
    _phoneController = TextEditingController(text: lead?.phone ?? '');
    _emailController = TextEditingController(text: lead?.email ?? '');
    _companyController = TextEditingController(text: lead?.company ?? '');
    _requirementController = TextEditingController(text: lead?.requirement ?? '');

    if (lead != null) {
      _priority = lead.priority ?? 'MEDIUM';
      _source = lead.source ?? 'Manual';
      _assignedTo = lead.assignedTo;
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LeadsProvider>().fetchEmployees();
    });
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _companyController.dispose();
    _requirementController.dispose();
    super.dispose();
  }

  void _handleSave() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSaving = true);
    final provider = context.read<LeadsProvider>();

    final payload = {
      'name': _nameController.text.trim(),
      'phone': _phoneController.text.trim(),
      if (_emailController.text.trim().isNotEmpty) 'email': _emailController.text.trim(),
      if (_companyController.text.trim().isNotEmpty) 'company': _companyController.text.trim(),
      if (_requirementController.text.trim().isNotEmpty) 'requirement': _requirementController.text.trim(),
      'priority': _priority,
      'source': _source,
      if (_assignedTo != null) 'assigned_to': _assignedTo,
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
          title: widget.leadToEdit != null ? 'Lead Updated' : 'New Lead Created',
          subtitle: '${_nameController.text.trim()} saved to CRM.',
          badge: widget.leadToEdit != null ? 'UPDATED' : 'NEW',
          pose: PingoPoses.salute,
        );
      } else {
        final err = provider.errorMessage ?? 'Failed to save lead';
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
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(isEditing ? 'Edit Lead' : 'Create New Lead'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              WacrmTextField(
                controller: _nameController,
                label: 'Lead Name *',
                hintText: 'e.g. John Doe',
                prefixIcon: Icons.person_outline_rounded,
                validator: (val) => val == null || val.trim().isEmpty ? 'Please enter lead name' : null,
              ),
              const SizedBox(height: 14),
              WacrmTextField(
                controller: _phoneController,
                label: 'Phone Number *',
                hintText: 'e.g. 9876543210',
                keyboardType: TextInputType.phone,
                prefixIcon: Icons.phone_outlined,
                validator: (val) {
                  if (val == null || val.trim().isEmpty) return 'Please enter phone number';
                  if (val.trim().length < 8) return 'Enter a valid phone number';
                  return null;
                },
              ),
              const SizedBox(height: 14),
              WacrmTextField(
                controller: _emailController,
                label: 'Email Address',
                hintText: 'e.g. contact@client.com',
                keyboardType: TextInputType.emailAddress,
                prefixIcon: Icons.email_outlined,
              ),
              const SizedBox(height: 14),
              WacrmTextField(
                controller: _companyController,
                label: 'Company Name',
                hintText: 'e.g. Acme Technologies',
                prefixIcon: Icons.business_outlined,
              ),
              const SizedBox(height: 14),

              // Priority and Source Row
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
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Lead Source',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                        ),
                        const SizedBox(height: 6),
                        DropdownButtonFormField<String>(
                          value: _sources.contains(_source) ? _source : _sources.first,
                          items: _sources.map((s) {
                            return DropdownMenuItem(value: s, child: Text(s));
                          }).toList(),
                          onChanged: (val) {
                            if (val != null) setState(() => _source = val);
                          },
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Assigned To Dropdown
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Assign Sales Representative',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                  ),
                  const SizedBox(height: 6),
                  DropdownButtonFormField<int>(
                    value: _assignedTo,
                    hint: const Text('Unassigned'),
                    items: [
                      const DropdownMenuItem<int>(
                        value: null,
                        child: Text('Unassigned'),
                      ),
                      ...employees.map((e) {
                        return DropdownMenuItem<int>(
                          value: e.id,
                          child: Text('${e.name} (${e.role ?? 'Sales'})'),
                        );
                      }),
                    ],
                    onChanged: (val) {
                      setState(() => _assignedTo = val);
                    },
                  ),
                ],
              ),
              const SizedBox(height: 14),

              WacrmTextField(
                controller: _requirementController,
                label: 'Requirement & Customer Notes',
                hintText: 'Describe client requirements, product interest...',
                maxLines: 3,
              ),
              const SizedBox(height: 24),

              WacrmButton(
                text: isEditing ? 'Save Changes' : 'Create Lead',
                isLoading: _isSaving,
                icon: Icons.check_circle_outline_rounded,
                onPressed: _handleSave,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
