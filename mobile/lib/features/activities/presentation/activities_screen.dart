import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/utils/date_formatter.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../../leads/providers/leads_provider.dart';
import '../models/activity_model.dart';
import '../providers/activities_provider.dart';

class ActivitiesScreen extends StatefulWidget {
  final int? leadId;
  final String? leadName;

  const ActivitiesScreen({super.key, this.leadId, this.leadName});

  @override
  State<ActivitiesScreen> createState() => _ActivitiesScreenState();
}

class _ActivitiesScreenState extends State<ActivitiesScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ActivitiesProvider>().fetchActivities(leadId: widget.leadId);
    });
  }

  void _showAddActivityDialog() {
    int? selectedLeadId = widget.leadId;
    String selectedType = 'CALL';
    final notesController = TextEditingController();
    bool isSubmitting = false;

    final types = ['CALL', 'MEETING', 'FIELD_VISIT', 'WHATSAPP', 'NOTE', 'EMAIL'];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) {
          final leads = ctx.watch<LeadsProvider>().leads;

          return Padding(
            padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
            child: Container(
              decoration: const BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
              ),
              padding: const EdgeInsets.all(20),
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
                    const Text(
                      'Log Customer Activity',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textMain),
                    ),
                    const SizedBox(height: 14),
                    if (widget.leadName != null)
                      WacrmTextField(
                        label: 'Lead',
                        hintText: widget.leadName,
                        readOnly: true,
                        prefixIcon: Icons.person_outline_rounded,
                      )
                    else ...[
                      const Text(
                        'Select Lead *',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                      ),
                      const SizedBox(height: 6),
                      DropdownButtonFormField<int>(
                        value: selectedLeadId,
                        hint: const Text('Select a lead...'),
                        items: leads.map((l) {
                          return DropdownMenuItem<int>(value: l.id, child: Text(l.name));
                        }).toList(),
                        onChanged: (val) => setModalState(() => selectedLeadId = val),
                      ),
                      const SizedBox(height: 12),
                    ],
                    const Text(
                      'Activity Type',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textMain),
                    ),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<String>(
                      value: selectedType,
                      items: types.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                      onChanged: (val) {
                        if (val != null) setModalState(() => selectedType = val);
                      },
                    ),
                    const SizedBox(height: 14),
                    WacrmTextField(
                      controller: notesController,
                      label: 'Interaction Summary / Note *',
                      hintText: 'e.g. Discussed pricing for 10 users software license...',
                      maxLines: 3,
                    ),
                    const SizedBox(height: 20),
                    WacrmButton(
                      text: 'Save Activity Log',
                      isLoading: isSubmitting,
                      icon: Icons.check_circle_outline_rounded,
                      onPressed: () async {
                        if (selectedLeadId == null || notesController.text.trim().isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Please select a lead and provide notes')),
                          );
                          return;
                        }

                        setModalState(() => isSubmitting = true);
                        final success = await context.read<ActivitiesProvider>().createActivity({
                          'lead_id': selectedLeadId,
                          'activity_type': selectedType,
                          'description': notesController.text.trim(),
                        });
                        setModalState(() => isSubmitting = false);

                        if (context.mounted && success) {
                          Navigator.pop(ctx);
                        }
                      },
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ActivitiesProvider>();
    final activities = provider.activities;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(widget.leadName != null ? 'Activities - ${widget.leadName}' : 'Activity Timeline'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => provider.fetchActivities(leadId: widget.leadId),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.white,
        icon: const Icon(Icons.add_rounded),
        label: const Text('Log Activity', style: TextStyle(fontWeight: FontWeight.w700)),
        onPressed: _showAddActivityDialog,
      ),
      body: provider.isLoading && activities.isEmpty
          ? const LoadingIndicator(message: 'Loading timeline...')
          : provider.errorMessage != null && activities.isEmpty
              ? ErrorView(
                  message: provider.errorMessage!,
                  onRetry: () => provider.fetchActivities(leadId: widget.leadId),
                )
              : activities.isEmpty
                  ? EmptyState(
                      title: 'No Activities Logged',
                      subtitle: 'Start recording calls, client meetings, or customer updates.',
                      pingoPose: PingoPoses.inspect,
                      actionLabel: 'Log Activity',
                      onAction: _showAddActivityDialog,
                    )
                  : RefreshIndicator(
                      color: AppColors.primary,
                      onRefresh: () => provider.fetchActivities(leadId: widget.leadId, showLoading: false),
                      child: ListView.separated(
                        padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
                        itemCount: activities.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final act = activities[index];
                          return _buildActivityCard(act);
                        },
                      ),
                    ),
    );
  }

  Widget _buildActivityCard(ActivityModel act) {
    IconData icon = Icons.notes_rounded;
    Color iconColor = AppColors.primary;
    final type = act.activityType.toUpperCase();

    if (type.contains('FIELD_VISIT') || type.contains('VISIT')) {
      icon = Icons.add_location_alt_rounded;
      iconColor = const Color(0xFF0284C7);
    } else if (type.contains('CALL')) {
      icon = Icons.phone_in_talk_rounded;
      iconColor = AppColors.accent;
    } else if (type.contains('MEETING')) {
      icon = Icons.groups_rounded;
      iconColor = const Color(0xFF8B5CF6);
    } else if (type.contains('WHATSAPP')) {
      icon = Icons.chat_bubble_outline_rounded;
      iconColor = const Color(0xFF25D366);
    } else if (type.contains('STATUS')) {
      icon = Icons.sync_alt_rounded;
      iconColor = AppColors.warning;
    }

    return WacrmCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: iconColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 18, color: iconColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    WacrmBadge(
                      label: act.activityType.replaceAll('_', ' '),
                      backgroundColor: iconColor.withValues(alpha: 0.1),
                      textColor: iconColor,
                    ),
                    Text(
                      DateFormatter.timeAgo(act.createdAt),
                      style: const TextStyle(fontSize: 11, color: AppColors.textLight),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  act.description,
                  style: const TextStyle(fontSize: 13, color: AppColors.textMain, height: 1.4),
                ),
                if (act.leadName != null && widget.leadName == null) ...[
                  const SizedBox(height: 6),
                  Text(
                    'Lead: ${act.leadName}',
                    style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.primary),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
