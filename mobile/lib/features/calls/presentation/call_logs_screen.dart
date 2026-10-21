import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
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
import '../providers/calls_provider.dart';

class CallLogsScreen extends StatefulWidget {
  const CallLogsScreen({super.key});

  @override
  State<CallLogsScreen> createState() => _CallLogsScreenState();
}

class _CallLogsScreenState extends State<CallLogsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CallsProvider>().fetchCalls();
    });
  }

  void _callNumber(String phone) async {
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final uri = Uri.parse('tel:$cleanPhone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  void _showLogManualCallDialog() {
    final phoneController = TextEditingController();
    final durationController = TextEditingController(text: '60');
    final notesController = TextEditingController();
    String callStatus = 'ANSWERED';
    bool isSubmitting = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) {
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
                      'Log Phone Call into CRM',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textMain),
                    ),
                    const SizedBox(height: 14),
                    WacrmTextField(
                      controller: phoneController,
                      label: 'Client Phone Number *',
                      hintText: 'e.g. 9876543210',
                      keyboardType: TextInputType.phone,
                      prefixIcon: Icons.phone_outlined,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Call Status', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                              const SizedBox(height: 6),
                              DropdownButtonFormField<String>(
                                value: callStatus,
                                items: ['ANSWERED', 'MISSED', 'BUSY', 'NO_ANSWER'].map((s) {
                                  return DropdownMenuItem(value: s, child: Text(s));
                                }).toList(),
                                onChanged: (val) {
                                  if (val != null) setModalState(() => callStatus = val);
                                },
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: WacrmTextField(
                            controller: durationController,
                            label: 'Duration (Seconds)',
                            keyboardType: TextInputType.number,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    WacrmTextField(
                      controller: notesController,
                      label: 'Call Discussion Summary',
                      hintText: 'Discussed client requirements, scheduled demo...',
                      maxLines: 2,
                    ),
                    const SizedBox(height: 20),
                    WacrmButton(
                      text: 'Save Call Log',
                      isLoading: isSubmitting,
                      icon: Icons.check_rounded,
                      onPressed: () async {
                        if (phoneController.text.trim().isEmpty) return;

                        setModalState(() => isSubmitting = true);
                        final success = await context.read<CallsProvider>().logManualCall(
                              customerNumber: phoneController.text.trim(),
                              callStatus: callStatus,
                              durationSeconds: int.tryParse(durationController.text) ?? 60,
                              notes: notesController.text.trim(),
                            );
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
    final provider = context.watch<CallsProvider>();
    final calls = provider.calls;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Call Logs & Telephony'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => provider.fetchCalls(),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.white,
        icon: const Icon(Icons.add_call),
        label: const Text('Log Call', style: TextStyle(fontWeight: FontWeight.w700)),
        onPressed: _showLogManualCallDialog,
      ),
      body: provider.isLoading && calls.isEmpty
          ? const LoadingIndicator(message: 'Loading call records...')
          : provider.errorMessage != null && calls.isEmpty
              ? ErrorView(
                  message: provider.errorMessage!,
                  onRetry: () => provider.fetchCalls(),
                )
              : calls.isEmpty
                  ? EmptyState(
                      title: 'No Call Logs Found',
                      subtitle: 'Interactions via Doocti or manual phone calls will be logged here.',
                      pingoPose: PingoPoses.inspect,
                      actionLabel: 'Log Call',
                      onAction: _showLogManualCallDialog,
                    )
                  : RefreshIndicator(
                      color: AppColors.primary,
                      onRefresh: () => provider.fetchCalls(showLoading: false),
                      child: ListView.separated(
                        padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
                        itemCount: calls.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (context, index) {
                          final call = calls[index];
                          final isAnswered = call.callStatus == 'ANSWERED' || call.callStatus == 'COMPLETED';

                          return WacrmCard(
                            padding: const EdgeInsets.all(14),
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: isAnswered ? AppColors.successLight : AppColors.dangerLight,
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Icon(
                                    call.callType == 'INBOUND'
                                        ? Icons.call_received_rounded
                                        : Icons.call_made_rounded,
                                    color: isAnswered ? AppColors.success : AppColors.danger,
                                    size: 20,
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
                                              call.leadName ?? call.customerNumber,
                                              style: const TextStyle(
                                                fontSize: 14,
                                                fontWeight: FontWeight.w700,
                                                color: AppColors.textMain,
                                              ),
                                            ),
                                          ),
                                          WacrmBadge.status(call.callStatus),
                                        ],
                                      ),
                                      const SizedBox(height: 3),
                                      Text(
                                        '${call.customerNumber} • ${call.formattedDuration}',
                                        style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        DateFormatter.formatDateTime(call.createdAt),
                                        style: const TextStyle(fontSize: 11, color: AppColors.textLight),
                                      ),
                                    ],
                                  ),
                                ),
                                IconButton(
                                  icon: const Icon(Icons.phone_rounded, color: AppColors.primary, size: 20),
                                  onPressed: () => _callNumber(call.customerNumber),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
