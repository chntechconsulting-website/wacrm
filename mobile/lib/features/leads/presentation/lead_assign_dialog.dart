import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';

class LeadAssignDialog extends StatefulWidget {
  final LeadModel lead;

  const LeadAssignDialog({super.key, required this.lead});

  static Future<void> show(BuildContext context, LeadModel lead) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => LeadAssignDialog(lead: lead),
    );
  }

  @override
  State<LeadAssignDialog> createState() => _LeadAssignDialogState();
}

class _LeadAssignDialogState extends State<LeadAssignDialog> {
  int? _selectedEmployeeId;
  final _notesController = TextEditingController();
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _selectedEmployeeId = widget.lead.assignedTo;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LeadsProvider>().fetchEmployees();
    });
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  void _handleAssign() async {
    if (_selectedEmployeeId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select an employee')),
      );
      return;
    }

    setState(() => _isSaving = true);
    final provider = context.read<LeadsProvider>();
    final success = await provider.assignLead(
      widget.lead.id,
      _selectedEmployeeId!,
      notes: _notesController.text.trim().isNotEmpty ? _notesController.text.trim() : null,
    );
    setState(() => _isSaving = false);

    if (mounted) {
      Navigator.pop(context);
      if (success) {
        final assignedEmp = provider.employees.firstWhere(
          (e) => e.id == _selectedEmployeeId,
          orElse: () => EmployeeOption(id: 0, name: 'Employee'),
        );

        PingoPopupDialog.show(
          context,
          title: 'Lead Reassigned',
          subtitle: '${widget.lead.name} assigned to ${assignedEmp.name}.',
          badge: 'ASSIGNED',
          pose: PingoPoses.pointRight,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final employees = context.watch<LeadsProvider>().employees;

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: SafeArea(
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
                  const Icon(Icons.person_add_alt_1_rounded, color: AppColors.primary, size: 22),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Assign Lead',
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
                ],
              ),
              const SizedBox(height: 18),
              const Text(
                'Select Sales Representative',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
              ),
              const SizedBox(height: 6),
              DropdownButtonFormField<int>(
                value: _selectedEmployeeId,
                hint: const Text('Choose an employee'),
                items: employees.map((emp) {
                  return DropdownMenuItem<int>(
                    value: emp.id,
                    child: Text('${emp.name} (${emp.role ?? 'Sales'})'),
                  );
                }).toList(),
                onChanged: (val) {
                  setState(() => _selectedEmployeeId = val);
                },
              ),
              const SizedBox(height: 16),
              WacrmTextField(
                controller: _notesController,
                label: 'Assignment Note (Optional)',
                hintText: 'e.g. Follow up on product demo quotation...',
                maxLines: 2,
              ),
              const SizedBox(height: 22),
              WacrmButton(
                text: 'Confirm Assignment',
                isLoading: _isSaving,
                icon: Icons.check_rounded,
                onPressed: _handleAssign,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
