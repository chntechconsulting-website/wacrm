import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../dashboard/providers/dashboard_provider.dart';
import '../../deals/providers/deals_provider.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';

class DealWonDialog extends StatefulWidget {
  final LeadModel lead;

  const DealWonDialog({super.key, required this.lead});

  static Future<bool?> show(BuildContext context, LeadModel lead) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => DealWonDialog(lead: lead),
    );
  }

  @override
  State<DealWonDialog> createState() => _DealWonDialogState();
}

class _DealWonDialogState extends State<DealWonDialog> {
  final _formKey = GlobalKey<FormState>();

  bool _loadingData = true;
  bool _submitting = false;
  String? _errorMessage;

  List<SupportManagerOption> _supportManagers = [];
  int? _selectedSupportManagerId;

  List<ProformaOption> _proformas = [];
  int? _selectedProformaId;

  final _dealAmountController = TextEditingController();
  final _userCountController = TextEditingController(text: '1');
  final _adjustmentReasonController = TextEditingController();
  final _paymentAmountController = TextEditingController(text: '0');
  final _requirementsController = TextEditingController();

  String _paymentStatus = 'PAYMENT_PENDING';
  double _originalProformaAmount = 0.0;

  @override
  void initState() {
    super.initState();
    _dealAmountController.text = (widget.lead.quotationAmount ?? 50000.0).toStringAsFixed(0);
    _requirementsController.text = widget.lead.requirement ?? '';
    _loadInitialData();
  }

  @override
  void dispose() {
    _dealAmountController.dispose();
    _userCountController.dispose();
    _adjustmentReasonController.dispose();
    _paymentAmountController.dispose();
    _requirementsController.dispose();
    super.dispose();
  }

  Future<void> _loadInitialData() async {
    setState(() => _loadingData = true);
    final provider = context.read<LeadsProvider>();

    try {
      final managers = await provider.getSupportManagers();
      final proformas = await provider.getLeadProformas(widget.lead.id);

      if (!mounted) return;

      int? defaultManagerId;
      if (managers.isNotEmpty) {
        final kumar = managers.firstWhere(
          (m) => m.name.toLowerCase().contains('kumar') || (m.username ?? '').toLowerCase().contains('kumar'),
          orElse: () => managers.first,
        );
        defaultManagerId = kumar.id;
      }

      int? defaultProformaId;
      if (proformas.isNotEmpty) {
        final firstPf = proformas.first;
        defaultProformaId = firstPf.id;
        _originalProformaAmount = firstPf.grandTotal;
        _dealAmountController.text = firstPf.grandTotal.toStringAsFixed(0);
        _userCountController.text = firstPf.licenceCount.toString();
        _paymentStatus = firstPf.paymentStatus;
        _paymentAmountController.text = firstPf.amountPaid.toStringAsFixed(0);
      }

      setState(() {
        _supportManagers = managers;
        _selectedSupportManagerId = defaultManagerId;
        _proformas = proformas;
        _selectedProformaId = defaultProformaId;
        _loadingData = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _loadingData = false;
          _errorMessage = 'Failed to load support managers or proformas.';
        });
      }
    }
  }

  void _onProformaSelected(int? proformaId) {
    setState(() {
      _selectedProformaId = proformaId;
      if (proformaId != null) {
        final pf = _proformas.firstWhere((p) => p.id == proformaId, orElse: () => _proformas.first);
        _originalProformaAmount = pf.grandTotal;
        _dealAmountController.text = pf.grandTotal.toStringAsFixed(0);
        _userCountController.text = pf.licenceCount.toString();
        _paymentStatus = pf.paymentStatus;
        _paymentAmountController.text = pf.amountPaid.toStringAsFixed(0);
      }
    });
  }

  bool get _isAmountAdjusted {
    if (_selectedProformaId == null || _proformas.isEmpty) return false;
    final currentAmt = double.tryParse(_dealAmountController.text) ?? 0.0;
    return (currentAmt - _originalProformaAmount).abs() > 0.01;
  }

  Future<void> _handleSubmit() async {
    if (_submitting) return;

    if (_selectedSupportManagerId == null || _selectedSupportManagerId! <= 0) {
      setState(() => _errorMessage = 'Please assign an active Support Manager before marking this deal as WON.');
      return;
    }

    final userCount = int.tryParse(_userCountController.text.trim()) ?? 0;
    if (userCount <= 0) {
      setState(() => _errorMessage = 'Please enter a valid user/employee licence count (minimum 1).');
      return;
    }

    final dealAmount = double.tryParse(_dealAmountController.text.trim()) ?? 0.0;
    if (dealAmount <= 0) {
      setState(() => _errorMessage = 'Please enter a valid total deal amount.');
      return;
    }

    if (_isAmountAdjusted && _adjustmentReasonController.text.trim().isEmpty) {
      setState(() => _errorMessage = 'Deal amount differs from the Proforma Total. Please provide a reason.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final provider = context.read<LeadsProvider>();

    ProformaOption? chosenPf;
    if (_selectedProformaId != null && _proformas.isNotEmpty) {
      chosenPf = _proformas.firstWhere((p) => p.id == _selectedProformaId, orElse: () => _proformas.first);
    }

    final payload = {
      'support_manager_id': _selectedSupportManagerId,
      'total_deal_amount': dealAmount,
      'customer_users_count': userCount,
      'payment_status': _paymentStatus,
      'payment_amount': double.tryParse(_paymentAmountController.text.trim()) ?? 0.0,
      if (chosenPf != null) ...{
        'proforma_id': chosenPf.id,
        'proforma_number': chosenPf.docNumber,
        'quotation_number': chosenPf.docNumber,
        'product_service': chosenPf.productSummary ?? 'WAHRMS Business Solution',
        'product_category': chosenPf.productCategory ?? 'WAHRMS',
        'selected_bundle': chosenPf.selectedBundle,
        'biometric_device_count': chosenPf.biometricDeviceCount,
      },
      if (_isAmountAdjusted) 'deal_adjustment_reason': _adjustmentReasonController.text.trim(),
      if (_requirementsController.text.trim().isNotEmpty)
        'customer_requirements': _requirementsController.text.trim(),
    };

    final success = await provider.markDealWon(widget.lead.id, payload);

    if (!mounted) return;

    setState(() => _submitting = false);

    if (success) {
      Navigator.pop(context, true);

      // Refresh cross-module data
      provider.fetchLeads(refresh: true);
      try {
        context.read<DealsProvider>().fetchFinanceHandoffs(showLoading: false);
        context.read<DashboardProvider>().fetchDashboardStats(showLoading: false);
      } catch (_) {}

      final managerName = _supportManagers.firstWhere(
        (m) => m.id == _selectedSupportManagerId,
        orElse: () => SupportManagerOption(id: 0, name: 'Support Manager'),
      ).name;

      PingoPopupDialog.showSuccessModal(
        context,
        title: 'Deal Closed (WON)!',
        subtitle: 'Deal closed for ${CurrencyFormatter.formatInr(dealAmount)}. Support handoff assigned to $managerName.',
        pose: PingoPoses.celebrate,
      );
    } else {
      setState(() {
        _errorMessage = provider.errorMessage ?? 'Failed to mark deal as WON. Please check required fields.';
      });
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
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: SafeArea(
          child: _loadingData
              ? const SizedBox(
                  height: 250,
                  child: Center(
                    child: CircularProgressIndicator(color: AppColors.primary),
                  ),
                )
              : SingleChildScrollView(
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Drag handle
                        Center(
                          child: Container(
                            width: 44,
                            height: 4,
                            decoration: BoxDecoration(
                              color: const Color(0xFFCBD5E1),
                              borderRadius: BorderRadius.circular(2),
                            ),
                          ),
                        ),
                        const SizedBox(height: 14),

                        // Header with Trophy
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFEF3C7),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(Icons.emoji_events_rounded, color: Color(0xFFD97706), size: 26),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Close Deal as WON',
                                    style: TextStyle(
                                      fontSize: 17,
                                      fontWeight: FontWeight.w800,
                                      color: Color(0xFF0F172A),
                                    ),
                                  ),
                                  Text(
                                    widget.lead.company ?? widget.lead.name,
                                    style: const TextStyle(fontSize: 13, color: Color(0xFF64748B)),
                                  ),
                                ],
                              ),
                            ),
                            const WacrmBadge(
                              label: 'WON HANDOFF',
                              backgroundColor: Color(0xFFECFDF5),
                              textColor: Color(0xFF059669),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // Error Banner if present
                        if (_errorMessage != null) ...[
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFFFF1F2),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFFECDD3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline_rounded, color: Color(0xFFE11D48), size: 20),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    _errorMessage!,
                                    style: const TextStyle(fontSize: 12.5, color: Color(0xFFBE123C), fontWeight: FontWeight.w600),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 14),
                        ],

                        // 1. Mandatory Support Manager Assignment
                        const Text(
                          'Assign Support Manager *',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF1E293B)),
                        ),
                        const SizedBox(height: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
                          decoration: BoxDecoration(
                            border: Border.all(color: const Color(0xFFE2E8F0)),
                            borderRadius: BorderRadius.circular(12),
                            color: const Color(0xFFF8FAFC),
                          ),
                          child: DropdownButtonHideUnderline(
                            child: DropdownButton<int>(
                              value: _selectedSupportManagerId,
                              isExpanded: true,
                              hint: const Text('Select active Support Manager'),
                              items: _supportManagers.map((mgr) {
                                return DropdownMenuItem<int>(
                                  value: mgr.id,
                                  child: Row(
                                    children: [
                                      const Icon(Icons.person_pin_rounded, size: 18, color: Color(0xFF0284C7)),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: Text(
                                          '${mgr.name} (${mgr.department ?? 'Support'})',
                                          style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                    ],
                                  ),
                                );
                              }).toList(),
                              onChanged: (val) {
                                setState(() => _selectedSupportManagerId = val);
                              },
                            ),
                          ),
                        ),
                        const SizedBox(height: 14),

                        // 2. Proforma Invoice Selection
                        const Text(
                          'Linked Proforma Invoice',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF1E293B)),
                        ),
                        const SizedBox(height: 6),
                        if (_proformas.isNotEmpty) ...[
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
                            decoration: BoxDecoration(
                              border: Border.all(color: const Color(0xFFE2E8F0)),
                              borderRadius: BorderRadius.circular(12),
                              color: const Color(0xFFF8FAFC),
                            ),
                            child: DropdownButtonHideUnderline(
                              child: DropdownButton<int>(
                                value: _selectedProformaId,
                                isExpanded: true,
                                items: _proformas.map((pf) {
                                  return DropdownMenuItem<int>(
                                    value: pf.id,
                                    child: Row(
                                      children: [
                                        const Icon(Icons.receipt_long_rounded, size: 18, color: Color(0xFF2563EB)),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: Text(
                                            '#${pf.docNumber} — ${CurrencyFormatter.formatInr(pf.grandTotal)}',
                                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ),
                                      ],
                                    ),
                                  );
                                }).toList(),
                                onChanged: _onProformaSelected,
                              ),
                            ),
                          ),
                        ] else ...[
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF1F5F9),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: const Row(
                              children: [
                                Icon(Icons.info_outline_rounded, color: Color(0xFF64748B), size: 18),
                                SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    'No existing Proforma Invoice found. A standard Proforma will be generated automatically.',
                                    style: TextStyle(fontSize: 12, color: Color(0xFF475569)),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                        const SizedBox(height: 14),

                        // 3. Deal Amount & User Licences
                        Row(
                          children: [
                            Expanded(
                              flex: 3,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Deal Amount (₹) *',
                                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF1E293B)),
                                  ),
                                  const SizedBox(height: 6),
                                  TextFormField(
                                    controller: _dealAmountController,
                                    keyboardType: TextInputType.number,
                                    decoration: InputDecoration(
                                      prefixText: '₹ ',
                                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                    ),
                                    onChanged: (_) => setState(() {}),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              flex: 2,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'User Licences *',
                                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF1E293B)),
                                  ),
                                  const SizedBox(height: 6),
                                  TextFormField(
                                    controller: _userCountController,
                                    keyboardType: TextInputType.number,
                                    decoration: InputDecoration(
                                      suffixText: 'users',
                                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),

                        // 4. Amount Adjustment Reason (if adjusted)
                        if (_isAmountAdjusted) ...[
                          const SizedBox(height: 14),
                          const Text(
                            'Reason for Deal Amount Adjustment *',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFFDC2626)),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _adjustmentReasonController,
                            decoration: InputDecoration(
                              hintText: 'e.g. Special promotional discount approved by Director',
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                            ),
                          ),
                        ],
                        const SizedBox(height: 14),

                        // 5. Payment Status
                        const Text(
                          'Payment Status',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF1E293B)),
                        ),
                        const SizedBox(height: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
                          decoration: BoxDecoration(
                            border: Border.all(color: const Color(0xFFE2E8F0)),
                            borderRadius: BorderRadius.circular(12),
                            color: const Color(0xFFF8FAFC),
                          ),
                          child: DropdownButtonHideUnderline(
                            child: DropdownButton<String>(
                              value: _paymentStatus,
                              isExpanded: true,
                              items: const [
                                DropdownMenuItem(value: 'PAYMENT_PENDING', child: Text('Payment Pending')),
                                DropdownMenuItem(value: 'PARTIALLY_PAID', child: Text('Partially Paid')),
                                DropdownMenuItem(value: 'PAID', child: Text('Full Payment Received (PAID)')),
                              ],
                              onChanged: (val) {
                                if (val != null) setState(() => _paymentStatus = val);
                              },
                            ),
                          ),
                        ),
                        const SizedBox(height: 14),

                        // 6. Customer Requirements
                        const Text(
                          'Customer Requirements / Onboarding Notes',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF1E293B)),
                        ),
                        const SizedBox(height: 6),
                        TextFormField(
                          controller: _requirementsController,
                          maxLines: 2,
                          decoration: InputDecoration(
                            hintText: 'Key notes for Support Manager & implementation team...',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                            contentPadding: const EdgeInsets.all(12),
                          ),
                        ),
                        const SizedBox(height: 20),

                        // Action Buttons
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton(
                                onPressed: _submitting ? null : () => Navigator.pop(context),
                                style: OutlinedButton.styleFrom(
                                  padding: const EdgeInsets.symmetric(vertical: 14),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                                ),
                                child: const Text('Cancel', style: TextStyle(fontWeight: FontWeight.w600)),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              flex: 2,
                              child: ElevatedButton(
                                onPressed: _submitting ? null : _handleSubmit,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFFE5252A),
                                  foregroundColor: Colors.white,
                                  elevation: 3,
                                  padding: const EdgeInsets.symmetric(vertical: 14),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                                ),
                                child: _submitting
                                    ? const SizedBox(
                                        height: 20,
                                        width: 20,
                                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                                      )
                                    : const Row(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: [
                                          Icon(Icons.check_circle_outline_rounded, size: 19),
                                          SizedBox(width: 8),
                                          Text(
                                            'Mark Deal WON',
                                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                                          ),
                                        ],
                                      ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
        ),
      ),
    );
  }
}
