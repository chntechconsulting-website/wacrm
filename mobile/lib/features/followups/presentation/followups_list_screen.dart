import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_drawer.dart';
import '../models/followup_model.dart';
import '../providers/followups_provider.dart';
import 'followup_create_edit_dialog.dart';

class FollowupsListScreen extends StatefulWidget {
  const FollowupsListScreen({super.key});

  @override
  State<FollowupsListScreen> createState() => _FollowupsListScreenState();
}

class _FollowupsListScreenState extends State<FollowupsListScreen> {
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final p = context.read<FollowupsProvider>();
      p.fetchFollowups();
      p.fetchActiveReminders();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _callNumber(String phone) async {
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final uri = Uri.parse('tel:$cleanPhone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  void _toggleCompleted(FollowupModel followup) async {
    final newStatus = followup.status == 'Completed' ? 'Pending' : 'Completed';
    final provider = context.read<FollowupsProvider>();
    final success = await provider.updateStatus(followup.id, newStatus);

    if (success && mounted) {
      if (newStatus == 'Completed') {
        PingoPopupDialog.show(
          context,
          title: 'Follow-up Completed!',
          subtitle: 'Completed interaction with ${followup.leadName}.',
          badge: 'COMPLETED',
          pose: PingoPoses.celebrate,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<FollowupsProvider>();
    final followups = provider.followups;
    final reminders = provider.reminders;

    return Scaffold(
      backgroundColor: AppColors.background,
      drawer: const WacrmDrawer(currentTabIndex: 2),
      appBar: AppBar(
        title: const Text('Follow-ups & Reminders'),
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
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.white,
        icon: const Icon(Icons.add_alarm_rounded),
        label: const Text('Schedule', style: TextStyle(fontWeight: FontWeight.w700)),
        onPressed: () => FollowupCreateEditDialog.show(context),
      ),
      body: Column(
        children: [
          // Search & Filter Header
          Container(
            color: AppColors.card,
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 8),
            child: Column(
              children: [
                // Search Bar
                Container(
                  height: 40,
                  decoration: BoxDecoration(
                    color: const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: TextField(
                    controller: _searchController,
                    decoration: InputDecoration(
                      hintText: 'Search client, phone, notes...',
                      hintStyle: const TextStyle(fontSize: 13, color: AppColors.textLight),
                      prefixIcon: const Icon(Icons.search_rounded, size: 20, color: AppColors.textLight),
                      suffixIcon: _searchController.text.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear_rounded, size: 18),
                              onPressed: () {
                                _searchController.clear();
                                provider.search('');
                              },
                            )
                          : null,
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onChanged: (val) => provider.search(val),
                  ),
                ),
                const SizedBox(height: 8),

                // Status Chips
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildFilterChip('Pending', provider.statusFilter == 'Pending', () => provider.setFilter('Pending')),
                      const SizedBox(width: 8),
                      _buildFilterChip('Completed', provider.statusFilter == 'Completed', () => provider.setFilter('Completed')),
                      const SizedBox(width: 8),
                      _buildFilterChip('Cancelled', provider.statusFilter == 'Cancelled', () => provider.setFilter('Cancelled')),
                      const SizedBox(width: 8),
                      _buildFilterChip('All Statuses', provider.statusFilter == 'ALL', () => provider.setFilter('ALL')),
                    ],
                  ),
                ),
                const SizedBox(height: 6),

                // Due Date Chips
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildFilterChip('All Dates', provider.dateFilter == 'ALL', () => provider.setDateFilter('ALL')),
                      const SizedBox(width: 8),
                      _buildFilterChip('Today', provider.dateFilter == 'today', () => provider.setDateFilter('today')),
                      const SizedBox(width: 8),
                      _buildFilterChip('Upcoming', provider.dateFilter == 'upcoming', () => provider.setDateFilter('upcoming')),
                      const SizedBox(width: 8),
                      _buildFilterChip('Overdue', provider.dateFilter == 'overdue', () => provider.setDateFilter('overdue')),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Active Reminders Banner
          if (reminders.isNotEmpty) ...[
            Container(
              margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF3C7),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFF59E0B).withValues(alpha: 0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.notifications_active_rounded, color: Color(0xFFD97706), size: 20),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '${reminders.length} Due / Upcoming Reminder(s)',
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF92400E),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ...reminders.take(2).map((r) {
                    return Padding(
                      padding: const EdgeInsets.only(top: 4.0),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              '• ${r.leadName} (${r.followupDate} ${r.followupTime})',
                              style: const TextStyle(fontSize: 12, color: Color(0xFF78350F), fontWeight: FontWeight.w600),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          TextButton(
                            style: TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(48, 24)),
                            onPressed: () => provider.dismissReminder(r.id),
                            child: const Text('Dismiss', style: TextStyle(fontSize: 11, color: Color(0xFFB45309))),
                          ),
                        ],
                      ),
                    );
                  }),
                ],
              ),
            ),
          ],

          // Follow-ups List
          Expanded(
            child: provider.isLoading && followups.isEmpty
                ? const LoadingIndicator(message: 'Loading follow-ups...')
                : provider.errorMessage != null && followups.isEmpty
                    ? ErrorView(
                        message: provider.errorMessage!,
                        onRetry: () => provider.fetchFollowups(),
                      )
                    : followups.isEmpty
                        ? EmptyState(
                            title: 'No Follow-ups Found',
                            subtitle: 'No follow-up tasks match your selected filter.',
                            pingoPose: PingoPoses.salute,
                            actionLabel: 'Schedule Now',
                            onAction: () => FollowupCreateEditDialog.show(context),
                          )
                        : RefreshIndicator(
                            color: AppColors.primary,
                            onRefresh: () async {
                              await provider.fetchFollowups(showLoading: false);
                              await provider.fetchActiveReminders();
                            },
                            child: ListView.separated(
                              padding: const EdgeInsets.fromLTRB(16, 12, 16, 110),
                              itemCount: followups.length,
                              separatorBuilder: (_, _) => const SizedBox(height: 10),
                              itemBuilder: (context, index) {
                                final f = followups[index];
                                final isDone = f.status == 'Completed';

                                return InkWell(
                                  borderRadius: BorderRadius.circular(16),
                                  onTap: () {
                                    FollowupCreateEditDialog.show(
                                      context,
                                      followupToEdit: f,
                                    );
                                  },
                                  child: WacrmCard(
                                    padding: const EdgeInsets.all(14),
                                    child: Row(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        // Checkbox for completion
                                        SizedBox(
                                          width: 24,
                                          height: 24,
                                          child: Checkbox(
                                            value: isDone,
                                            activeColor: AppColors.success,
                                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                                            onChanged: (_) => _toggleCompleted(f),
                                          ),
                                        ),
                                        const SizedBox(width: 12),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Row(
                                                children: [
                                                  Expanded(
                                                    child: Text(
                                                      f.leadName,
                                                      style: TextStyle(
                                                        fontSize: 14,
                                                        fontWeight: FontWeight.w700,
                                                        color: isDone ? AppColors.textLight : AppColors.textMain,
                                                        decoration: isDone ? TextDecoration.lineThrough : null,
                                                      ),
                                                    ),
                                                  ),
                                                  WacrmBadge.status(f.status),
                                                  const SizedBox(width: 6),
                                                  WacrmBadge.priority(f.priority),
                                                ],
                                              ),
                                              const SizedBox(height: 4),
                                              Row(
                                                children: [
                                                  const Icon(Icons.calendar_today_outlined, size: 12, color: AppColors.textLight),
                                                  const SizedBox(width: 4),
                                                  Text(
                                                    '${f.followupDate} at ${f.followupTime}',
                                                    style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                                                  ),
                                                ],
                                              ),
                                              if (f.notes != null && f.notes!.isNotEmpty) ...[
                                                const SizedBox(height: 6),
                                                Text(
                                                  f.notes!,
                                                  style: const TextStyle(fontSize: 12, color: AppColors.textMain),
                                                ),
                                              ],
                                            ],
                                          ),
                                        ),
                                        Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            IconButton(
                                              icon: const Icon(Icons.edit_calendar_rounded, color: Color(0xFF2563EB), size: 20),
                                              tooltip: 'Reschedule / Edit',
                                              onPressed: () {
                                                FollowupCreateEditDialog.show(
                                                  context,
                                                  followupToEdit: f,
                                                );
                                              },
                                            ),
                                            if (f.leadPhone.isNotEmpty)
                                              IconButton(
                                                icon: const Icon(Icons.phone_rounded, color: AppColors.primary, size: 20),
                                                tooltip: 'Call Client',
                                                onPressed: () => _callNumber(f.leadPhone),
                                              ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, bool isSelected, VoidCallback onTap) {
    return ChoiceChip(
      label: Text(
        label,
        style: TextStyle(
          fontSize: 12,
          fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
          color: isSelected ? AppColors.white : AppColors.textMain,
        ),
      ),
      selected: isSelected,
      selectedColor: AppColors.primary,
      backgroundColor: AppColors.cardHover,
      side: BorderSide(color: isSelected ? AppColors.primary : AppColors.border),
      onSelected: (_) => onTap(),
      showCheckmark: false,
    );
  }
}
