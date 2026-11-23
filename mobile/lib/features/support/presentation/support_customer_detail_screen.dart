import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/services/doocti_call_service.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../auth/providers/auth_provider.dart';
import '../../calls/models/call_log_model.dart';
import '../../followups/models/followup_model.dart';
import '../../followups/providers/followups_provider.dart';
import '../models/support_models.dart';
import '../providers/support_customers_provider.dart';
import 'support_dialogs.dart';
import 'support_widgets.dart';

class SupportCustomerDetailScreen extends StatefulWidget {
  final int leadId;
  final int? customerId;
  final SupportCustomer? initialCustomer;

  const SupportCustomerDetailScreen({
    super.key,
    required this.leadId,
    this.customerId,
    this.initialCustomer,
  });

  @override
  State<SupportCustomerDetailScreen> createState() =>
      _SupportCustomerDetailScreenState();
}

class _SupportCustomerDetailScreenState
    extends State<SupportCustomerDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SupportCustomersProvider>().loadCustomerDetail(
        widget.leadId,
        customerId: widget.customerId,
      );
    });
  }

  SupportCustomersProvider get _provider =>
      context.read<SupportCustomersProvider>();

  Future<void> _refresh() async {
    await _provider.loadCustomerDetail(
      widget.leadId,
      customerId: widget.customerId ?? _provider.selectedHistory?.customerId,
    );
  }

  /// Support Manager / Admin reassignment. The backend enforces team scope and
  /// requires a reason whenever an existing owner is being replaced.
  Future<void> _openReassignDialog(SupportHistory history) async {
    final provider = _provider;
    await provider.loadAssignTeamMembers();
    if (!mounted) return;

    final assignment = provider.supportAssignment;
    final currentOwnerId = assignment?.supportEmployeeId;
    final currentOwnerName =
        assignment?.supportEmployeeName ?? history.currentHandlingEmployeeName;
    final isReassignment =
        currentOwnerId != null && (currentOwnerName ?? '').trim().isNotEmpty;
    final members = provider.assignTeamMembers
        .where((member) => member.id != currentOwnerId)
        .toList();

    if (members.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'No other active Support Executive is available in your team.',
          ),
        ),
      );
      return;
    }

    int? selectedId = members.first.id;
    final reasonController = TextEditingController();
    String? dialogError;

    final submitted = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) {
          return AlertDialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
            title: Text(
              isReassignment
                  ? 'Reassign Client'
                  : 'Assign Client',
              style: const TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF8FAFC),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: const Color(0xFFE2E8F0)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'CURRENT ASSIGNEE',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.4,
                            color: AppColors.textMuted,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          isReassignment
                              ? currentOwnerName!
                              : 'Unassigned',
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF0F172A),
                          ),
                        ),
                        if (assignment?.supportManagerName != null &&
                            assignment!.supportManagerName!.trim().isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            'Support Manager: ${assignment.supportManagerName}',
                            style: const TextStyle(
                              fontSize: 11,
                              color: AppColors.textMuted,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<int>(
                    initialValue: selectedId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Support Employee *',
                    ),
                    items: members
                        .map(
                          (member) => DropdownMenuItem<int>(
                            value: member.id,
                            child: Text(
                              member.name,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) =>
                        setDialogState(() => selectedId = value),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: reasonController,
                    maxLines: 3,
                    maxLength: 2000,
                    decoration: InputDecoration(
                      labelText: isReassignment
                          ? 'Reassignment Reason *'
                          : 'Remarks (optional)',
                      hintText: isReassignment
                          ? 'Explain why this client is being moved (required)...'
                          : 'Optional handover notes...',
                    ),
                    onChanged: (_) {
                      if (dialogError != null) {
                        setDialogState(() => dialogError = null);
                      }
                    },
                  ),
                  if (dialogError != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      dialogError!,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFFB91C1C),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: provider.isSavingAssignment
                    ? null
                    : () => Navigator.pop(ctx, false),
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  elevation: 0,
                ),
                onPressed: provider.isSavingAssignment
                    ? null
                    : () async {
                        final targetId = selectedId;
                        if (targetId == null) {
                          setDialogState(
                            () => dialogError = 'Select a Support employee.',
                          );
                          return;
                        }
                        if (isReassignment &&
                            reasonController.text.trim().isEmpty) {
                          setDialogState(
                            () => dialogError =
                                'A reassignment reason is required.',
                          );
                          return;
                        }
                        setDialogState(() => dialogError = null);
                        final error = await provider.assignSupportOwner(
                          leadId: history.leadId,
                          employeeId: targetId,
                          reason: reasonController.text,
                        );
                        if (!ctx.mounted) return;
                        if (error == null) {
                          Navigator.pop(ctx, true);
                        } else {
                          setDialogState(() => dialogError = error);
                        }
                      },
                child: Text(
                  provider.isSavingAssignment
                      ? 'Saving...'
                      : (isReassignment ? 'Reassign' : 'Assign'),
                ),
              ),
            ],
          );
        },
      ),
    );

    reasonController.dispose();
    if (submitted == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.success,
          content: Text('Support ownership updated.'),
        ),
      );
    }
  }

  void _call({required String phone, int? pocId, String? pocName}) {
    if (phone.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No phone number saved for this contact.'),
        ),
      );
      return;
    }
    DooctiCallService.makeCall(
      context,
      phone: phone,
      leadId: widget.leadId,
      contactName:
          _provider.selectedHistory?.customerName ??
          widget.initialCustomer?.displayCompany,
      customerPocId: pocId,
      pocName: pocName,
    );
  }

  Future<void> _addInteraction(SupportHistory history) async {
    final saved = await SupportInteractionSheet.show(context, history: history);
    if (saved == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.success,
          content: Text('Support interaction saved.'),
        ),
      );
    }
  }

  Future<void> _scheduleFollowup(SupportHistory history) async {
    final saved = await SupportFollowupSheet.show(
      context,
      preselectedLeadId: history.leadId,
      preselectedLeadName: history.customerName,
    );
    if (saved == true && mounted) {
      context.read<FollowupsProvider>().fetchFollowups(showLoading: false);
      await _refresh();
    }
  }

  Future<void> _addPoc(SupportHistory history) async {
    final saved = await SupportPocSheet.show(
      context,
      leadId: history.leadId,
      customerId: history.customerId,
    );
    if (saved == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.success,
          content: Text('Point of contact saved.'),
        ),
      );
    }
  }

  Future<void> _editPoc(SupportPoc poc, SupportHistory history) async {
    final saved = await SupportPocSheet.show(
      context,
      leadId: history.leadId,
      customerId: history.customerId,
      poc: poc,
    );
    if (saved == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.success,
          content: Text('Point of contact updated.'),
        ),
      );
    }
  }

  Future<void> _makePrimaryPoc(SupportPoc poc) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Set Primary POC'),
        content: Text(
          'Make ${poc.name} the primary point of contact for this customer?',
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
            child: const Text('Set Primary'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final success = await _provider.setPrimaryPoc(poc.id);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: success ? AppColors.success : AppColors.danger,
        content: Text(
          success
              ? '${poc.name} is now the primary POC.'
              : (_provider.detailError ?? 'Unable to update the primary POC.'),
        ),
      ),
    );
  }

  Future<void> _editScheduledFollowup(
    SupportHistory history,
    SupportScheduledFollowup followup,
  ) async {
    final model = FollowupModel(
      id: followup.id,
      leadId: history.leadId,
      leadName: history.customerName,
      leadPhone: history.phone ?? '',
      assignedTo: followup.assignedTo,
      followupDate: followup.followupDate ?? '',
      followupTime: followup.followupTime ?? '',
      priority: followup.priority,
      status: followup.status,
      notes: followup.notes,
    );
    final saved = await SupportFollowupSheet.show(
      context,
      preselectedLeadId: history.leadId,
      preselectedLeadName: history.customerName,
      followupToEdit: model,
    );
    if (saved == true && mounted) {
      context.read<FollowupsProvider>().fetchFollowups(showLoading: false);
      await _refresh();
    }
  }

  Future<void> _completeScheduledFollowup(
    SupportHistory history,
    SupportScheduledFollowup followup,
  ) async {
    final confirmed = await confirmSupportFollowupCompletion(
      context,
      history.customerName,
    );
    if (!confirmed || !mounted) return;
    final success = await context.read<FollowupsProvider>().updateStatus(
      followup.id,
      'Completed',
    );
    if (!mounted) return;
    if (success) {
      await _refresh();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.success,
          content: Text('Follow-up completed.'),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            context.read<FollowupsProvider>().errorMessage ??
                'Unable to complete this follow-up.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SupportCustomersProvider>();
    final history = provider.selectedHistory;
    final initial = widget.initialCustomer;
    final user = context.watch<AuthProvider>().currentUser;
    final canCall = user?.canCallSupportCustomer ?? false;
    final canAddInteraction = user?.canAddSupportInteraction ?? false;
    final canCreateFollowup = user?.canCreateSupportFollowup ?? false;
    final canEditFollowup = user?.canEditSupportFollowup ?? false;
    final canManagePoc = user?.canManageSupportPoc ?? false;
    final canReassignAssignment =
        user != null && (user.isAdmin || user.isSupportManagerWorkspace);
    final title =
        history?.customerName ?? initial?.displayCompany ?? 'Support Customer';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            const Text(
              'Support Customer',
              style: TextStyle(fontSize: 10, color: AppColors.textMuted),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: _refresh,
          ),
        ],
      ),
      body: provider.isDetailLoading && history == null
          ? const LoadingIndicator(
              message: 'Loading customer support history...',
            )
          : history == null
          ? _buildUnavailableBody(provider, initial)
          : RefreshIndicator(
              color: AppColors.primary,
              onRefresh: _refresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 30),
                children: [
                  _buildProfileCard(history),
                  const SizedBox(height: 12),
                  if (canCall || canAddInteraction || canCreateFollowup) ...[
                    _buildQuickActions(
                      history,
                      canCall: canCall,
                      canAddInteraction: canAddInteraction,
                      canCreateFollowup: canCreateFollowup,
                    ),
                    const SizedBox(height: 14),
                  ],
                  _buildAssignmentCard(
                    history,
                    canReassign: canReassignAssignment,
                  ),
                  const SizedBox(height: 14),                  _buildPurchaseCard(history),
                  const SizedBox(height: 14),
                  _buildPocSection(
                    history,
                    canCall: canCall,
                    canManagePoc: canManagePoc,
                  ),
                  const SizedBox(height: 14),
                  _buildSummaryCard(history),
                  const SizedBox(height: 14),
                  _buildScheduledFollowups(
                    history,
                    canCreateFollowup: canCreateFollowup,
                    canEditFollowup: canEditFollowup,
                  ),
                  const SizedBox(height: 14),
                  _buildInteractionHistory(
                    history,
                    canAddInteraction: canAddInteraction,
                  ),
                  const SizedBox(height: 14),
                  _buildCallHistory(provider.selectedCalls),
                ],
              ),
            ),
    );
  }

  Widget _buildUnavailableBody(
    SupportCustomersProvider provider,
    SupportCustomer? initial,
  ) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (initial != null) _buildInitialProfileCard(initial),
        if (initial != null) const SizedBox(height: 12),
        ErrorView(
          message:
              provider.detailError ??
              'Support history is not available for this customer yet.',
          onRetry: _refresh,
        ),
      ],
    );
  }

  Widget _buildInitialProfileCard(SupportCustomer customer) {
    return WacrmCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  customer.displayCompany,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textMain,
                  ),
                ),
              ),
              SupportStatusBadge(status: customer.supportStatus),
            ],
          ),
          const SizedBox(height: 6),
          if (customer.phone != null) ...[
            SupportInfoRow(
              icon: Icons.phone_outlined,
              label: 'Phone',
              value: customer.phone!,
            ),
          ],
          if (customer.email != null)
            SupportInfoRow(
              icon: Icons.mail_outline_rounded,
              label: 'Email',
              value: customer.email!,
            ),
        ],
      ),
    );
  }

  Widget _buildProfileCard(SupportHistory history) {
    final status = history.supportStatus ?? 'NEW';
    return WacrmCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      (history.companyName ?? '').trim().isNotEmpty
                          ? history.companyName!
                          : history.customerName,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textMain,
                      ),
                    ),
                    if ((history.companyName ?? '').trim().isNotEmpty)
                      Text(
                        history.customerName,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textMuted,
                        ),
                      ),
                  ],
                ),
              ),
              SupportStatusBadge(status: status),
            ],
          ),
          const SizedBox(height: 10),
          if ((history.phone ?? '').trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.phone_outlined,
              label: 'Phone',
              value: history.phone!,
            ),
          if ((history.email ?? '').trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.mail_outline_rounded,
              label: 'Email',
              value: history.email!,
            ),
          if ((history.location ?? '').trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.location_on_outlined,
              label: 'Location',
              value: history.location!,
            ),
          if ((history.productService ?? '').trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.inventory_2_outlined,
              label: 'Product / Service',
              value: history.productService!,
            ),
          if ((history.customerRequirements ?? '').trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.assignment_outlined,
              label: 'Requirements',
              value: history.customerRequirements!,
            ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              if (history.primaryPoc != null)
                WacrmBadge(
                  label: 'POC: ${history.primaryPoc!.name}',
                  backgroundColor: const Color(0xFFF0FDFA),
                  textColor: const Color(0xFF0F766E),
                  icon: Icons.contact_phone_rounded,
                  fontSize: 9,
                ),
              if (history.coverage != null)
                const WacrmBadge(
                  label: 'BACKUP COVERAGE ACTIVE',
                  backgroundColor: Color(0xFFEFF6FF),
                  textColor: Color(0xFF2563EB),
                  icon: Icons.swap_horiz_rounded,
                  fontSize: 9,
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildQuickActions(
    SupportHistory history, {
    required bool canCall,
    required bool canAddInteraction,
    required bool canCreateFollowup,
  }) {
    final primary = history.primaryPoc;
    final phone = (primary?.mobile ?? '').trim().isNotEmpty
        ? primary!.mobile
        : (history.phone ?? '');
    final actions = <Widget>[
      if (canCall)
        Expanded(
          child: WacrmButton(
            text: 'Call',
            icon: Icons.phone_rounded,
            height: 38,
            onPressed: () => _call(
              phone: phone,
              pocId: primary?.id,
              pocName: primary?.name,
            ),
          ),
        ),
      if (canAddInteraction)
        Expanded(
          child: WacrmButton(
            text: 'Interaction',
            icon: Icons.support_agent_rounded,
            type: WacrmButtonType.outline,
            height: 38,
            onPressed: () => _addInteraction(history),
          ),
        ),
      if (canCreateFollowup)
        Expanded(
          child: WacrmButton(
            text: 'Follow-up',
            icon: Icons.add_alarm_rounded,
            type: WacrmButtonType.outline,
            height: 38,
            onPressed: () => _scheduleFollowup(history),
          ),
        ),
    ];
    return WacrmCard(
      padding: const EdgeInsets.all(10),
      child: Row(
        children: [
          for (var i = 0; i < actions.length; i++) ...[
            if (i > 0) const SizedBox(width: 6),
            actions[i],
          ],
        ],
      ),
    );
  }

  Widget _buildAssignmentCard(
    SupportHistory history, {
    bool canReassign = false,
  }) {
    final assignment = _provider.supportAssignment;
    final current = assignment?.current;
    final currentOwnerName = (assignment?.supportEmployeeName ??
            history.currentHandlingEmployeeName ??
            'Unassigned')
        .trim();
    final historyRows = assignment?.history.reversed.toList() ??
        const <SupportAssignmentRecord>[];
    final showReassign = canReassign &&
        (assignment?.canReassign ?? false) &&
        (assignment?.assignmentEnabled ?? false);

    return WacrmCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Expanded(
                child: SupportSectionHeader(title: 'Support Ownership'),
              ),
              if (showReassign)
                TextButton.icon(
                  onPressed: () => _openReassignDialog(history),
                  icon: const Icon(Icons.swap_horiz_rounded, size: 15),
                  label: const Text(
                    'Reassign Client',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  style: TextButton.styleFrom(
                    foregroundColor: AppColors.primary,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          SupportInfoRow(
            icon: Icons.person_pin_circle_outlined,
            label: 'Current Assignee',
            value: currentOwnerName.isEmpty ? 'Unassigned' : currentOwnerName,
            valueColor: const Color(0xFF2563EB),
          ),
          SupportInfoRow(
            icon: Icons.person_outline_rounded,
            label: 'Original Employee',
            value: history.originalSupportEmployeeName ?? 'Not recorded',
          ),
          if (assignment?.supportManagerName != null &&
              assignment!.supportManagerName!.trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.supervisor_account_rounded,
              label: 'Support Manager',
              value: assignment.supportManagerName!,
            ),
          if (current?.previousEmployeeName != null &&
              current!.previousEmployeeName!.trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.swap_horiz_rounded,
              label: 'Previous Assignee',
              value: current.previousEmployeeName!,
              valueColor: const Color(0xFFD97706),
            ),
          if (current?.assignedAt != null &&
              current!.assignedAt!.trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.event_available_rounded,
              label: 'Assigned On',
              value: supportFormatDateTime(current.assignedAt),
            ),
          if (current?.assignedByName != null &&
              current!.assignedByName.trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.badge_outlined,
              label: 'Reassigned By',
              value: current.assignedByName,
            ),
          if (current?.reason != null && current!.reason!.trim().isNotEmpty)
            SupportInfoRow(
              icon: Icons.notes_rounded,
              label: 'Reason',
              value: current.reason!,
            ),
          if (history.backupEmployeeName != null)
            SupportInfoRow(
              icon: Icons.swap_horiz_rounded,
              label: 'Backup Employee',
              value: history.backupEmployeeName!,
              valueColor: const Color(0xFFD97706),
            ),
          if (history.coverage != null)
            SupportInfoRow(
              icon: Icons.date_range_rounded,
              label: 'Coverage Period',
              value:
                  '${supportFormatDate(history.coverage!.startDate)} → ${supportFormatDate(history.coverage!.endDate)}',
            ),
          if (history.coverageHistory.length > 1)
            SupportInfoRow(
              icon: Icons.history_rounded,
              label: 'Handover History',
              value: '${history.coverageHistory.length} coverage records',
            ),
          if (historyRows.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text(
              'ASSIGNMENT HISTORY',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.5,
                color: AppColors.textMuted,
              ),
            ),
            const SizedBox(height: 6),
            ...historyRows.map(
              (row) => Container(
                width: double.infinity,
                margin: const EdgeInsets.only(bottom: 6),
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(9),
                  border: Border.all(color: const Color(0xFFE2E8F0)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            row.employeeName ?? 'Employee #${row.employeeId}',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF0F172A),
                            ),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 7,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: row.isActive
                                ? const Color(0xFFDCFCE7)
                                : const Color(0xFFF1F5F9),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            row.status.toUpperCase(),
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                              color: row.isActive
                                  ? const Color(0xFF166534)
                                  : const Color(0xFF475569),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${row.assignedAt != null ? supportFormatDateTime(row.assignedAt) : 'N/A'}'
                      '${row.previousEmployeeName != null ? ' · from ${row.previousEmployeeName}' : ''}',
                      style: const TextStyle(
                        fontSize: 10.5,
                        color: AppColors.textMuted,
                      ),
                    ),
                    Text(
                      'Assigned by: ${row.assignedByName}',
                      style: const TextStyle(
                        fontSize: 10.5,
                        color: Color(0xFF475569),
                      ),
                    ),
                    if (row.reason != null && row.reason!.trim().isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(
                          'Reason: ${row.reason}',
                          style: const TextStyle(
                            fontSize: 10.5,
                            color: Color(0xFF334155),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPurchaseCard(SupportHistory history) {
    final purchase = providerPurchase(history);
    return WacrmCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SupportSectionHeader(title: 'Package & Plan'),
          const SizedBox(height: 4),
          if (purchase == null || !purchase.hasAnyValue)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text(
                'No package or purchase details recorded for this customer.',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted),
              ),
            )
          else ...[
            SupportInfoRow(
              icon: Icons.inventory_2_outlined,
              label: 'Package',
              value: purchase.packageName ?? 'Not set',
            ),
            SupportInfoRow(
              icon: Icons.workspace_premium_outlined,
              label: 'Plan',
              value: purchase.planName ?? 'Not set',
            ),
            SupportInfoRow(
              icon: Icons.groups_outlined,
              label: 'Employee Qty',
              value: purchase.employeeQuantity?.toString() ?? 'Not set',
            ),
            if (purchase.biometricDeviceCount != null)
              SupportInfoRow(
                icon: Icons.fingerprint_rounded,
                label: 'Biometric Devices',
                value: '${purchase.biometricDeviceCount}',
              ),
            if (purchase.durationMonths != null)
              SupportInfoRow(
                icon: Icons.timelapse_rounded,
                label: 'Duration',
                value: '${purchase.durationMonths} month(s)',
              ),
            if ((purchase.startDate ?? '').trim().isNotEmpty ||
                (purchase.endDate ?? '').trim().isNotEmpty)
              SupportInfoRow(
                icon: Icons.date_range_rounded,
                label: 'Subscription',
                value:
                    '${supportFormatDate(purchase.startDate)} → ${supportFormatDate(purchase.endDate)}',
              ),
            if (purchase.purchaseAmount != null)
              SupportInfoRow(
                icon: Icons.currency_rupee_rounded,
                label: 'Purchase Amount',
                value: purchase.purchaseAmount!.toStringAsFixed(2),
              ),
            if (purchase.addons.isNotEmpty) ...[
              const SizedBox(height: 6),
              const Text(
                'Add-ons',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textMuted,
                ),
              ),
              const SizedBox(height: 4),
              ...purchase.addons.map(
                (addon) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.add_circle_outline_rounded,
                        size: 14,
                        color: AppColors.accent,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          addon.quantity != null
                              ? '${addon.name} × ${addon.quantity}'
                              : addon.name,
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.textMain,
                          ),
                        ),
                      ),
                      if (addon.lineTotal != null)
                        Text(
                          addon.lineTotal!.toStringAsFixed(2),
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textMuted,
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }

  SupportPurchaseDetails? providerPurchase(SupportHistory history) {
    return _provider.selectedPurchaseDetails ?? history.purchaseDetails;
  }

  Widget _buildPocSection(
    SupportHistory history, {
    required bool canCall,
    required bool canManagePoc,
  }) {
    return WacrmCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SupportSectionHeader(
            title: 'Points of Contact (${history.pocs.length})',
            actionLabel: canManagePoc ? 'Add POC' : null,
            onAction: canManagePoc ? () => _addPoc(history) : null,
          ),
          const SizedBox(height: 4),
          if (history.pocs.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text(
                'No points of contact saved. Add the customer contact who should receive Support calls.',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted),
              ),
            )
          else
            ...history.pocs.map(
              (poc) => Container(
                margin: const EdgeInsets.only(top: 8),
                padding: const EdgeInsets.all(11),
                decoration: BoxDecoration(
                  color: pobPocBackground(poc),
                  borderRadius: BorderRadius.circular(11),
                  border: Border.all(
                    color: poc.isPrimary
                        ? const Color(0xFF99F6E4)
                        : AppColors.border,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            poc.name,
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppColors.textMain,
                            ),
                          ),
                        ),
                        if (poc.isPrimary)
                          const WacrmBadge(
                            label: 'PRIMARY',
                            backgroundColor: Color(0xFFCCFBF1),
                            textColor: Color(0xFF0F766E),
                            icon: Icons.star_rounded,
                            fontSize: 8,
                          ),
                        if (canManagePoc)
                          IconButton(
                            visualDensity: VisualDensity.compact,
                            icon: const Icon(Icons.edit_outlined, size: 17),
                            tooltip: 'Edit POC',
                            onPressed: () => _editPoc(poc, history),
                          ),
                      ],
                    ),
                    if ((poc.designation ?? '').trim().isNotEmpty ||
                        (poc.department ?? '').trim().isNotEmpty)
                      Text(
                        poc.subtitle,
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppColors.textMuted,
                        ),
                      ),
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 10,
                      runSpacing: 4,
                      children: [
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.phone_outlined,
                              size: 14,
                              color: AppColors.textMuted,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              poc.mobile,
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: AppColors.textMain,
                              ),
                            ),
                          ],
                        ),
                        if ((poc.email ?? '').trim().isNotEmpty)
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(
                                Icons.mail_outline_rounded,
                                size: 14,
                                color: AppColors.textMuted,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                poc.email!,
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: AppColors.textMain,
                                ),
                              ),
                            ],
                          ),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.chat_outlined,
                              size: 14,
                              color: AppColors.textMuted,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              poc.preferredContactMethod,
                              style: const TextStyle(
                                fontSize: 11,
                                color: AppColors.textMuted,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    if ((poc.notes ?? '').trim().isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        poc.notes!,
                        style: const TextStyle(
                          fontSize: 10,
                          color: AppColors.textLight,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ],
                    if (canCall || (canManagePoc && !poc.isPrimary)) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          if (canCall)
                            Expanded(
                              child: SizedBox(
                                height: 32,
                                child: OutlinedButton.icon(
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: AppColors.success,
                                    side: const BorderSide(
                                      color: Color(0xFFBBF7D0),
                                    ),
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                    ),
                                  ),
                                  onPressed: () => _call(
                                    phone: poc.mobile,
                                    pocId: poc.id,
                                    pocName: poc.name,
                                  ),
                                  icon: const Icon(
                                    Icons.phone_rounded,
                                    size: 15,
                                  ),
                                  label: const Text(
                                    'Call POC',
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          if (canManagePoc && !poc.isPrimary) ...[
                            if (canCall) const SizedBox(width: 8),
                            Expanded(
                              child: SizedBox(
                                height: 32,
                                child: OutlinedButton.icon(
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: const Color(0xFF0F766E),
                                    side: const BorderSide(
                                      color: Color(0xFF99F6E4),
                                    ),
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                    ),
                                  ),
                                  onPressed: () => _makePrimaryPoc(poc),
                                  icon: const Icon(
                                    Icons.star_outline_rounded,
                                    size: 15,
                                  ),
                                  label: const Text(
                                    'Set Primary',
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Color pobPocBackground(SupportPoc poc) =>
      poc.isPrimary ? const Color(0xFFF0FDFA) : const Color(0xFFF8FAFC);

  Widget _buildSummaryCard(SupportHistory history) {
    final summary = history.summary;
    final hasSummary =
        (summary.currentUnresolvedIssue ?? '').trim().isNotEmpty ||
        (summary.lastReportedProblem ?? '').trim().isNotEmpty ||
        (summary.lastConversationSummary ?? '').trim().isNotEmpty ||
        (summary.nextRecommendedAction ?? '').trim().isNotEmpty ||
        summary.solutionsAttempted.isNotEmpty;
    return WacrmCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SupportSectionHeader(title: 'Support Summary'),
          const SizedBox(height: 4),
          if (!hasSummary)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text(
                'No Support interactions recorded yet. Add the first interaction to build customer history.',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted),
              ),
            )
          else ...[
            if ((summary.currentUnresolvedIssue ?? '').trim().isNotEmpty)
              _summaryBlock(
                'Current Unresolved Issue',
                summary.currentUnresolvedIssue!,
                color: const Color(0xFFDC2626),
              ),
            if ((summary.lastReportedProblem ?? '').trim().isNotEmpty)
              _summaryBlock(
                'Last Reported Problem',
                summary.lastReportedProblem!,
                color: const Color(0xFFD97706),
              ),
            if ((summary.lastConversationSummary ?? '').trim().isNotEmpty)
              _summaryBlock(
                'Last Conversation',
                summary.lastConversationSummary!,
              ),
            if ((summary.nextRecommendedAction ?? '').trim().isNotEmpty)
              _summaryBlock(
                'Next Recommended Action',
                summary.nextRecommendedAction!,
                color: const Color(0xFF2563EB),
              ),
            if (summary.solutionsAttempted.isNotEmpty) ...[
              const SizedBox(height: 6),
              const Text(
                'Solutions Attempted',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textMuted,
                ),
              ),
              const SizedBox(height: 4),
              ...summary.solutionsAttempted
                  .take(5)
                  .map(
                    (solution) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.check_circle_outline_rounded,
                            size: 13,
                            color: AppColors.success,
                          ),
                          const SizedBox(width: 5),
                          Expanded(
                            child: Text(
                              solution,
                              style: const TextStyle(
                                fontSize: 11,
                                color: AppColors.textMain,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
            ],
            if (summary.interactionCount > 0) ...[
              const SizedBox(height: 6),
              Text(
                '${summary.interactionCount} interaction(s) recorded',
                style: const TextStyle(
                  fontSize: 10,
                  color: AppColors.textLight,
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _summaryBlock(String label, String value, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w700,
              color: AppColors.textMuted,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontSize: 12,
              color: color ?? AppColors.textMain,
              height: 1.35,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildScheduledFollowups(
    SupportHistory history, {
    required bool canCreateFollowup,
    required bool canEditFollowup,
  }) {
    return WacrmCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SupportSectionHeader(
            title: 'Scheduled Support Follow-ups',
            actionLabel: canCreateFollowup ? 'Add' : null,
            onAction: canCreateFollowup ? () => _scheduleFollowup(history) : null,
          ),
          const SizedBox(height: 4),
          if (history.scheduledFollowups.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text(
                'No pending Support follow-ups for this customer.',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted),
              ),
            )
          else
            ...history.scheduledFollowups.map(
              (followup) => Container(
                margin: const EdgeInsets.only(top: 8),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFFEFCE8),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFFDE68A)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(
                          Icons.alarm_rounded,
                          size: 16,
                          color: Color(0xFFD97706),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            '${supportFormatDate(followup.followupDate)}'
                            '${(followup.followupTime ?? '').trim().isNotEmpty ? ' • ${followup.followupTime}' : ''}',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF92400E),
                            ),
                          ),
                        ),
                        WacrmBadge(
                          label: followup.priority,
                          backgroundColor: const Color(0xFFFEF3C7),
                          textColor: const Color(0xFFB45309),
                          fontSize: 8,
                        ),
                      ],
                    ),
                    if ((followup.notes ?? '').trim().isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        followup.notes!,
                        style: const TextStyle(
                          fontSize: 11,
                          color: Color(0xFF78350F),
                        ),
                      ),
                    ],
                    if (canEditFollowup) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          TextButton.icon(
                            style: TextButton.styleFrom(
                              foregroundColor: AppColors.accent,
                              padding: EdgeInsets.zero,
                              minimumSize: const Size(0, 28),
                              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            ),
                            onPressed: () =>
                                _editScheduledFollowup(history, followup),
                            icon: const Icon(Icons.edit_outlined, size: 15),
                            label: const Text(
                              'Edit',
                              style: TextStyle(fontSize: 11),
                            ),
                          ),
                          const SizedBox(width: 12),
                          TextButton.icon(
                            style: TextButton.styleFrom(
                              foregroundColor: AppColors.success,
                              padding: EdgeInsets.zero,
                              minimumSize: const Size(0, 28),
                              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            ),
                            onPressed: () =>
                                _completeScheduledFollowup(history, followup),
                            icon: const Icon(Icons.check_rounded, size: 15),
                            label: const Text(
                              'Complete',
                              style: TextStyle(fontSize: 11),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildInteractionHistory(
    SupportHistory history, {
    required bool canAddInteraction,
  }) {
    final interactions = history.interactions;
    return WacrmCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SupportSectionHeader(
            title: 'Support Interaction History',
            actionLabel: canAddInteraction ? 'Add' : null,
            onAction: canAddInteraction ? () => _addInteraction(history) : null,
          ),
          const SizedBox(height: 4),
          if (interactions.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text(
                'No calls, problems or solutions recorded yet.',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted),
              ),
            )
          else
            ...interactions.asMap().entries.map((entry) {
              final interaction = entry.value;
              return Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Column(
                      children: [
                        Container(
                          width: 26,
                          height: 26,
                          decoration: const BoxDecoration(
                            color: Color(0xFFEFF6FF),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            interaction.hasPendingIssue
                                ? Icons.report_problem_outlined
                                : Icons.support_agent_rounded,
                            size: 14,
                            color: interaction.hasPendingIssue
                                ? const Color(0xFFDC2626)
                                : const Color(0xFF2563EB),
                          ),
                        ),
                        if (entry.key != interactions.length - 1)
                          Container(
                            width: 1.5,
                            height: 52,
                            color: AppColors.border,
                          ),
                      ],
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFFF8FAFC),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AppColors.border),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    interaction.interactionType,
                                    style: const TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                      color: AppColors.textMain,
                                    ),
                                  ),
                                ),
                                Text(
                                  supportFormatDateTime(
                                    interaction.interactionAt,
                                  ),
                                  style: const TextStyle(
                                    fontSize: 9,
                                    color: AppColors.textLight,
                                  ),
                                ),
                              ],
                            ),
                            if ((interaction.pocName ?? '').trim().isNotEmpty)
                              Padding(
                                padding: const EdgeInsets.only(top: 2),
                                child: Text(
                                  'POC: ${interaction.pocName}'
                                  '${(interaction.pocPhone ?? '').trim().isNotEmpty ? ' • ${interaction.pocPhone}' : ''}',
                                  style: const TextStyle(
                                    fontSize: 10,
                                    color: Color(0xFF0F766E),
                                  ),
                                ),
                              ),
                            if ((interaction.handlingEmployeeName ?? '')
                                .trim()
                                .isNotEmpty)
                              Padding(
                                padding: const EdgeInsets.only(top: 1),
                                child: Text(
                                  'Handled by ${interaction.handlingEmployeeName}',
                                  style: const TextStyle(
                                    fontSize: 9,
                                    color: AppColors.textLight,
                                  ),
                                ),
                              ),
                            if ((interaction.discussion ?? '')
                                .trim()
                                .isNotEmpty)
                              _timelineField(
                                'Discussion',
                                interaction.discussion!,
                              ),
                            if ((interaction.problemReported ?? '')
                                .trim()
                                .isNotEmpty)
                              _timelineField(
                                'Problem',
                                interaction.problemReported!,
                                color: const Color(0xFFDC2626),
                              ),
                            if ((interaction.troubleshooting ?? '')
                                .trim()
                                .isNotEmpty)
                              _timelineField(
                                'Troubleshooting',
                                interaction.troubleshooting!,
                              ),
                            if ((interaction.solutionProvided ?? '')
                                .trim()
                                .isNotEmpty)
                              _timelineField(
                                'Solution',
                                interaction.solutionProvided!,
                                color: const Color(0xFF16A34A),
                              ),
                            if ((interaction.pendingIssues ?? '')
                                .trim()
                                .isNotEmpty)
                              _timelineField(
                                'Pending Issue',
                                interaction.pendingIssues!,
                                color: const Color(0xFFD97706),
                              ),
                            if ((interaction.nextAction ?? '')
                                .trim()
                                .isNotEmpty)
                              _timelineField(
                                'Next Action',
                                interaction.nextAction!,
                                color: const Color(0xFF2563EB),
                              ),
                            if ((interaction.followUpAt ?? '')
                                .trim()
                                .isNotEmpty)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Text(
                                  'Follow-up: ${supportFormatDateTime(interaction.followUpAt)}',
                                  style: const TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w600,
                                    color: Color(0xFFD97706),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  Widget _timelineField(String label, String value, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: RichText(
        text: TextSpan(
          style: const TextStyle(fontSize: 11, color: AppColors.textMain),
          children: [
            TextSpan(
              text: '$label: ',
              style: const TextStyle(
                fontWeight: FontWeight.w700,
                color: AppColors.textMuted,
              ),
            ),
            TextSpan(
              text: value,
              style: TextStyle(color: color ?? AppColors.textMain),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCallHistory(List<CallLogModel> calls) {
    return WacrmCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SupportSectionHeader(title: 'Support Call History'),
          const SizedBox(height: 4),
          if (calls.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text(
                'No CRM calls logged for this customer.',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted),
              ),
            )
          else
            ...calls
                .take(12)
                .map(
                  (call) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 5),
                    child: Row(
                      children: [
                        Icon(
                          call.callType.toUpperCase() == 'INBOUND'
                              ? Icons.call_received_rounded
                              : Icons.call_made_rounded,
                          size: 16,
                          color: call.callStatus.toUpperCase() == 'ANSWERED'
                              ? AppColors.success
                              : AppColors.textLight,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${call.callStatus} • ${call.customerNumber}',
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: AppColors.textMain,
                                ),
                              ),
                              Text(
                                [
                                  supportFormatDateTime(call.createdAt),
                                  if ((call.pocName ?? '').trim().isNotEmpty)
                                    'POC: ${call.pocName}',
                                  '${call.durationSeconds}s',
                                ].join(' • '),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 9,
                                  color: AppColors.textLight,
                                ),
                              ),
                            ],
                          ),
                        ),
                        if ((call.recordingUrl ?? '').trim().isNotEmpty)
                          const Icon(
                            Icons.mic_rounded,
                            size: 14,
                            color: AppColors.accent,
                          ),
                      ],
                    ),
                  ),
                ),
        ],
      ),
    );
  }
}
