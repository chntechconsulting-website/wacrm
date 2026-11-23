import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/services/doocti_call_service.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/support_models.dart';
import '../providers/support_customers_provider.dart';
import 'support_customer_detail_screen.dart';
import 'support_widgets.dart';

class SupportBackupScreen extends StatefulWidget {
  const SupportBackupScreen({super.key});

  @override
  State<SupportBackupScreen> createState() => _SupportBackupScreenState();
}

class _SupportBackupScreenState extends State<SupportBackupScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SupportCustomersProvider>().fetchBackupCustomers();
    });
  }

  void _openDetail(SupportBackupCustomer backup) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => SupportCustomerDetailScreen(
          leadId: backup.history.leadId,
          customerId: backup.history.customerId,
        ),
      ),
    );
  }

  void _call(SupportBackupCustomer backup) {
    final poc = backup.history.primaryPoc;
    final phone = (poc?.mobile ?? '').trim().isNotEmpty
        ? poc!.mobile
        : (backup.history.phone ?? '');
    if (phone.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No phone number saved for this customer.'),
        ),
      );
      return;
    }
    DooctiCallService.makeCall(
      context,
      phone: phone,
      leadId: backup.history.leadId,
      contactName: backup.history.customerName,
      customerPocId: poc?.id,
      pocName: poc?.name,
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SupportCustomersProvider>();
    final backups = provider.backupCustomers;
    final canCall =
        context.watch<AuthProvider>().currentUser?.canCallSupportCustomer ==
        true;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Backup & Handover'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => provider.fetchBackupCustomers(),
          ),
        ],
      ),
      body: provider.isBackupLoading && backups.isEmpty
          ? const LoadingIndicator(message: 'Loading backup assignments...')
          : provider.backupError != null && backups.isEmpty
          ? ErrorView(
              message: provider.backupError!,
              onRetry: () => provider.fetchBackupCustomers(),
            )
          : backups.isEmpty
          ? const EmptyState(
              title: 'No Backup Assignments',
              subtitle:
                  'Temporary coverage customers appear here when a Support colleague is on approved leave. '
                  'Only authorized assignments are shown.',
              pingoPose: PingoPoses.salute,
            )
          : RefreshIndicator(
              color: AppColors.primary,
              onRefresh: () =>
                  provider.fetchBackupCustomers(showLoading: false),
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                children: [
                  WacrmCard(
                    backgroundColor: const Color(0xFFEFF6FF),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.info_outline_rounded,
                          size: 18,
                          color: Color(0xFF2563EB),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'You are handling ${backups.length} temporary coverage customer(s). '
                            'The permanent owner and previous Support history are preserved.',
                            style: const TextStyle(
                              fontSize: 11,
                              color: Color(0xFF1E40AF),
                              height: 1.35,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  ...backups.map(
                    (backup) => _backupCard(backup, canCall: canCall),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _backupCard(
    SupportBackupCustomer backup, {
    required bool canCall,
  }) {
    final history = backup.history;
    final coverage = backup.coverage;
    final pending = (history.summary.currentUnresolvedIssue ?? '').trim();
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: WacrmCard(
        padding: const EdgeInsets.all(14),
        onTap: () => _openDetail(backup),
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
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textMain,
                        ),
                      ),
                      if ((history.customerName).trim().isNotEmpty &&
                          (history.companyName ?? '').trim().isNotEmpty)
                        Text(
                          history.customerName,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.textMuted,
                          ),
                        ),
                    ],
                  ),
                ),
                const WacrmBadge(
                  label: 'BACKUP',
                  backgroundColor: Color(0xFFEFF6FF),
                  textColor: Color(0xFF2563EB),
                  icon: Icons.swap_horiz_rounded,
                  fontSize: 8,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(9),
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(9),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                children: [
                  _handoverRow(
                    'Original Employee',
                    coverage?.originalEmployeeName ??
                        history.originalSupportEmployeeName ??
                        'Not recorded',
                    const Color(0xFF64748B),
                  ),
                  const SizedBox(height: 4),
                  _handoverRow(
                    'Current Handling',
                    coverage?.backupEmployeeName ??
                        history.currentHandlingEmployeeName ??
                        'You',
                    const Color(0xFF2563EB),
                  ),
                  if (backup.leave != null) ...[
                    const SizedBox(height: 4),
                    _handoverRow(
                      'Coverage Reason',
                      '${backup.leave!.leaveType} • ${backup.leave!.status}',
                      const Color(0xFFD97706),
                    ),
                  ],
                  const SizedBox(height: 4),
                  _handoverRow(
                    'Coverage Period',
                    '${supportFormatDate(coverage?.startDate)} → ${supportFormatDate(coverage?.endDate)}',
                    const Color(0xFF0F766E),
                  ),
                ],
              ),
            ),
            if (pending.isNotEmpty) ...[
              const SizedBox(height: 8),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.report_problem_outlined,
                    size: 15,
                    color: Color(0xFFDC2626),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      pending,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 11,
                        color: Color(0xFFB91C1C),
                      ),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 6),
            Row(
              children: [
                const Icon(
                  Icons.history_rounded,
                  size: 14,
                  color: AppColors.textLight,
                ),
                const SizedBox(width: 4),
                Text(
                  '${history.interactions.length} interaction(s)'
                  '${history.pocs.isNotEmpty ? ' • ${history.pocs.length} POC(s)' : ''}',
                  style: const TextStyle(
                    fontSize: 10,
                    color: AppColors.textLight,
                  ),
                ),
                const Spacer(),
                if (canCall &&
                    ((history.phone ?? '').trim().isNotEmpty ||
                        history.primaryPoc != null))
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    icon: const Icon(
                      Icons.phone_rounded,
                      size: 18,
                      color: AppColors.success,
                    ),
                    onPressed: () => _call(backup),
                  ),
                const Icon(
                  Icons.chevron_right_rounded,
                  size: 18,
                  color: AppColors.textLight,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _handoverRow(String label, String value, Color color) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 100,
          child: Text(
            label,
            style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ),
      ],
    );
  }
}
