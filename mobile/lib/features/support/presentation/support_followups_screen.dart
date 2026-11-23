import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/services/doocti_call_service.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_drawer.dart';
import '../../auth/providers/auth_provider.dart';
import '../../followups/models/followup_model.dart';
import '../../followups/providers/followups_provider.dart';
import '../providers/support_customers_provider.dart';
import 'support_dialogs.dart';
import 'support_widgets.dart';

class SupportFollowupsScreen extends StatefulWidget {
  const SupportFollowupsScreen({super.key});

  @override
  State<SupportFollowupsScreen> createState() => _SupportFollowupsScreenState();
}

class _SupportFollowupsScreenState extends State<SupportFollowupsScreen> {
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<FollowupsProvider>();
      provider.fetchFollowups();
      provider.fetchActiveReminders();
      final customers = context.read<SupportCustomersProvider>();
      if (customers.customers.isEmpty) {
        customers.fetchCustomers(showLoading: false);
      }
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _call(FollowupModel followup) {
    DooctiCallService.makeCall(
      context,
      phone: followup.leadPhone,
      leadId: followup.leadId,
      contactName: followup.leadName,
    );
  }

  Future<void> _schedule() async {
    final customers = context.read<SupportCustomersProvider>().customers;
    final saved = await SupportFollowupSheet.show(
      context,
      customers: customers,
    );
    if (saved == true && mounted) {
      await context.read<FollowupsProvider>().fetchFollowups(
        showLoading: false,
      );
    }
  }

  Future<void> _edit(FollowupModel followup) async {
    final saved = await SupportFollowupSheet.show(
      context,
      preselectedLeadId: followup.leadId,
      preselectedLeadName: followup.leadName,
      followupToEdit: followup,
    );
    if (saved == true && mounted) {
      await context.read<FollowupsProvider>().fetchFollowups(
        showLoading: false,
      );
    }
  }

  Future<void> _complete(FollowupModel followup) async {
    final confirmed = await confirmSupportFollowupCompletion(
      context,
      followup.leadName,
    );
    if (!confirmed || !mounted) return;
    final provider = context.read<FollowupsProvider>();
    final success = await provider.updateStatus(followup.id, 'Completed');
    if (!mounted) return;
    if (success) {
      PingoPopupDialog.show(
        context,
        title: 'Follow-up Completed!',
        subtitle: 'Completed Support follow-up with ${followup.leadName}.',
        badge: 'COMPLETED',
        pose: PingoPoses.celebrate,
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            provider.errorMessage ?? 'Unable to complete this follow-up.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<FollowupsProvider>();
    final followups = provider.followups;
    final reminders = provider.reminders;
    final user = context.watch<AuthProvider>().currentUser;
    final canCreate = user?.canCreateSupportFollowup ?? false;
    final canEdit = user?.canEditSupportFollowup ?? false;
    final canCall = user?.canCallSupportCustomer ?? false;

    return Scaffold(
      backgroundColor: AppColors.background,
      drawer: const WacrmDrawer(currentTabIndex: 2),
      appBar: AppBar(
        title: const Text('Support Follow-ups'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () {
              provider.fetchFollowups();
              provider.fetchActiveReminders();
            },
          ),
        ],
      ),
      floatingActionButton: canCreate
          ? FloatingActionButton.extended(
              heroTag: 'supportFollowupsScheduleFab',
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.add_alarm_rounded),
              label: const Text(
                'Schedule',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              onPressed: _schedule,
            )
          : null,
      body: Column(
        children: [
          Container(
            color: AppColors.card,
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 8),
            child: Column(
              children: [
                Container(
                  height: 40,
                  decoration: BoxDecoration(
                    color: const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: TextField(
                    controller: _searchController,
                    decoration: InputDecoration(
                      hintText: 'Search Support customer, phone, notes...',
                      hintStyle: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textLight,
                      ),
                      prefixIcon: const Icon(
                        Icons.search_rounded,
                        size: 20,
                        color: AppColors.textLight,
                      ),
                      suffixIcon: _searchController.text.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear_rounded, size: 18),
                              onPressed: () {
                                _searchController.clear();
                                provider.search('');
                                setState(() {});
                              },
                            )
                          : null,
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onChanged: (value) {
                      provider.search(value);
                      setState(() {});
                    },
                  ),
                ),
                const SizedBox(height: 8),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _filterChip(
                        'Pending',
                        provider.statusFilter == 'Pending',
                        () => provider.setFilter('Pending'),
                      ),
                      const SizedBox(width: 7),
                      _filterChip(
                        'Overdue',
                        provider.dateFilter == 'overdue',
                        () => provider.setDateFilter('overdue'),
                      ),
                      const SizedBox(width: 7),
                      _filterChip(
                        'Today',
                        provider.dateFilter == 'today',
                        () => provider.setDateFilter('today'),
                      ),
                      const SizedBox(width: 7),
                      _filterChip(
                        'Upcoming',
                        provider.dateFilter == 'upcoming',
                        () => provider.setDateFilter('upcoming'),
                      ),
                      const SizedBox(width: 7),
                      _filterChip(
                        'Completed',
                        provider.statusFilter == 'Completed',
                        () => provider.setFilter('Completed'),
                      ),
                      const SizedBox(width: 7),
                      _filterChip(
                        'All',
                        provider.statusFilter == 'ALL' &&
                            provider.dateFilter == 'ALL',
                        () {
                          provider.setDateFilter('ALL');
                          provider.setFilter('ALL');
                        },
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 6),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _priorityChip('All priorities', 'ALL'),
                      const SizedBox(width: 7),
                      _priorityChip('High', 'HIGH'),
                      const SizedBox(width: 7),
                      _priorityChip('Medium', 'MEDIUM'),
                      const SizedBox(width: 7),
                      _priorityChip('Low', 'LOW'),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (reminders.isNotEmpty) ...[
            Container(
              margin: const EdgeInsets.fromLTRB(16, 10, 16, 2),
              padding: const EdgeInsets.all(11),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF3C7),
                borderRadius: BorderRadius.circular(11),
                border: Border.all(
                  color: const Color(0xFFF59E0B).withValues(alpha: 0.3),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(
                        Icons.notifications_active_rounded,
                        color: Color(0xFFD97706),
                        size: 18,
                      ),
                      const SizedBox(width: 7),
                      Expanded(
                        child: Text(
                          '${reminders.length} due / upcoming Support reminder(s)',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF92400E),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  ...reminders
                      .take(3)
                      .map(
                        (reminder) => Row(
                          children: [
                            Expanded(
                              child: Text(
                                '• ${reminder.leadName} (${reminder.followupDate} ${reminder.followupTime})',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: Color(0xFF78350F),
                                ),
                              ),
                            ),
                            TextButton(
                              style: TextButton.styleFrom(
                                padding: EdgeInsets.zero,
                                minimumSize: const Size(44, 24),
                              ),
                              onPressed: () =>
                                  provider.dismissReminder(reminder.id),
                              child: const Text(
                                'Dismiss',
                                style: TextStyle(
                                  fontSize: 10,
                                  color: Color(0xFFB45309),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                ],
              ),
            ),
          ],
          Expanded(
            child: provider.isLoading && followups.isEmpty
                ? const LoadingIndicator(
                    message: 'Loading Support follow-ups...',
                  )
                : provider.errorMessage != null && followups.isEmpty
                ? ErrorView(
                    message: provider.errorMessage!,
                    onRetry: () => provider.fetchFollowups(),
                  )
                : followups.isEmpty
                ? EmptyState(
                    title: 'No Support Follow-ups',
                    subtitle:
                        'No follow-up tasks match the selected Support filter.',
                    pingoPose: PingoPoses.salute,
                    actionLabel: canCreate ? 'Schedule Now' : null,
                    onAction: canCreate ? _schedule : null,
                  )
                : RefreshIndicator(
                    color: AppColors.primary,
                    onRefresh: () async {
                      await provider.fetchFollowups(showLoading: false);
                      await provider.fetchActiveReminders();
                    },
                    child: ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 10, 16, 110),
                      itemCount: followups.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 10),
                      itemBuilder: (context, index) => _followupCard(
                        followups[index],
                        canEdit: canEdit,
                        canCall: canCall,
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _filterChip(String label, bool selected, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? AppColors.primary : const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: selected ? Colors.white : AppColors.textMuted,
          ),
        ),
      ),
    );
  }

  Widget _priorityChip(String label, String value) {
    final provider = context.read<FollowupsProvider>();
    final selected = provider.priorityFilter == value;
    return _filterChip(label, selected, () {
      provider.setPriorityFilter(value);
      setState(() {});
    });
  }

  Widget _followupCard(
    FollowupModel followup, {
    required bool canEdit,
    required bool canCall,
  }) {
    final isDone = followup.status == 'Completed';
    final isCancelled = followup.status == 'Cancelled';
    final overdue =
        !isDone &&
        !isCancelled &&
        _isOverdue(followup.followupDate, followup.followupTime);
    return WacrmCard(
      padding: const EdgeInsets.all(13),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: overdue
                      ? const Color(0xFFFEE2E2)
                      : const Color(0xFFFEF3C7),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(
                  overdue ? Icons.warning_amber_rounded : Icons.alarm_rounded,
                  size: 18,
                  color: overdue
                      ? const Color(0xFFDC2626)
                      : const Color(0xFFD97706),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      followup.leadName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDone
                            ? AppColors.textLight
                            : AppColors.textMain,
                        decoration: isDone ? TextDecoration.lineThrough : null,
                      ),
                    ),
                    Text(
                      '${supportFormatDate(followup.followupDate)}'
                      ' • ${followup.followupTime}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              WacrmBadge(
                label: overdue ? 'OVERDUE' : followup.status.toUpperCase(),
                backgroundColor: overdue
                    ? const Color(0xFFFEE2E2)
                    : isDone
                    ? const Color(0xFFDCFCE7)
                    : isCancelled
                    ? const Color(0xFFF1F5F9)
                    : const Color(0xFFEFF6FF),
                textColor: overdue
                    ? const Color(0xFFDC2626)
                    : isDone
                    ? const Color(0xFF16A34A)
                    : isCancelled
                    ? const Color(0xFF64748B)
                    : const Color(0xFF2563EB),
                fontSize: 8,
              ),
            ],
          ),
          if ((followup.notes ?? '').trim().isNotEmpty) ...[
            const SizedBox(height: 7),
            Text(
              followup.notes!,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
            ),
          ],
          const SizedBox(height: 7),
          Row(
            children: [
              WacrmBadge(
                label: followup.priority,
                backgroundColor: const Color(0xFFF8FAFC),
                textColor: AppColors.textMuted,
                fontSize: 8,
              ),
              if ((followup.assignedToName ?? '').trim().isNotEmpty) ...[
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    followup.assignedToName!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 10,
                      color: AppColors.textLight,
                    ),
                  ),
                ),
              ],
              const Spacer(),
              if (canCall &&
                  followup.leadPhone.trim().isNotEmpty &&
                  !isDone)
                IconButton(
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(
                    Icons.phone_rounded,
                    size: 18,
                    color: AppColors.success,
                  ),
                  tooltip: 'Call customer',
                  onPressed: () => _call(followup),
                ),
              if (canEdit && !isDone) ...[
                IconButton(
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(
                    Icons.edit_outlined,
                    size: 18,
                    color: AppColors.accent,
                  ),
                  tooltip: 'Edit follow-up',
                  onPressed: () => _edit(followup),
                ),
                IconButton(
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(
                    Icons.check_circle_outline_rounded,
                    size: 19,
                    color: AppColors.success,
                  ),
                  tooltip: 'Complete follow-up',
                  onPressed: () => _complete(followup),
                ),
              ],
              if (isDone && canEdit)
                TextButton(
                  style: TextButton.styleFrom(
                    padding: EdgeInsets.zero,
                    minimumSize: const Size(0, 28),
                  ),
                  onPressed: () => _edit(followup),
                  child: const Text('View', style: TextStyle(fontSize: 11)),
                ),
            ],
          ),
        ],
      ),
    );
  }

  bool _isOverdue(String date, String time) {
    try {
      final parsedDate = DateTime.parse(date);
      TimeOfDay parsedTime = const TimeOfDay(hour: 23, minute: 59);
      final rawTime = time.trim();
      if (rawTime.isNotEmpty) {
        final match = RegExp(
          r'(\d{1,2}):(\d{2})\s*(AM|PM)?',
          caseSensitive: false,
        ).firstMatch(rawTime);
        if (match != null) {
          var hour = int.parse(match.group(1)!);
          final minute = int.parse(match.group(2)!);
          final period = (match.group(3) ?? '').toUpperCase();
          if (period == 'PM' && hour < 12) hour += 12;
          if (period == 'AM' && hour == 12) hour = 0;
          parsedTime = TimeOfDay(hour: hour, minute: minute);
        }
      }
      final due = DateTime(
        parsedDate.year,
        parsedDate.month,
        parsedDate.day,
        parsedTime.hour,
        parsedTime.minute,
      );
      return due.isBefore(DateTime.now());
    } catch (_) {
      return false;
    }
  }
}
