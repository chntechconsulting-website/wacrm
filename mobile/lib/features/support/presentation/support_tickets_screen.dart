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
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../models/support_ticket_model.dart';
import '../providers/support_provider.dart';

class SupportTicketsScreen extends StatefulWidget {
  const SupportTicketsScreen({super.key});

  @override
  State<SupportTicketsScreen> createState() => _SupportTicketsScreenState();
}

class _SupportTicketsScreenState extends State<SupportTicketsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SupportProvider>().fetchTickets();
    });
  }

  void _callNumber(String phone) async {
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final uri = Uri.parse('tel:$cleanPhone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  void _updateStatus(SupportTicketModel ticket) async {
    final stages = [
      'PENDING_CONTACT',
      'IN_TRAINING',
      'INSTALLATION_PENDING',
      'LIVE',
      'COMPLETED',
    ];

    final picked = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
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
                'Update Onboarding Stage',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textMain),
              ),
              const SizedBox(height: 12),
              ...stages.map((s) {
                final isCurrent = s == ticket.status;
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: PingoMascotWidget(
                    pose: s == 'LIVE' || s == 'COMPLETED' ? PingoPoses.celebrate : PingoPoses.action,
                    height: 32,
                  ),
                  title: Text(
                    s.replaceAll('_', ' '),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: isCurrent ? FontWeight.w700 : FontWeight.w500,
                      color: isCurrent ? AppColors.primary : AppColors.textMain,
                    ),
                  ),
                  trailing: isCurrent ? const Icon(Icons.check_circle_rounded, color: AppColors.primary, size: 20) : null,
                  onTap: () => Navigator.pop(ctx, s),
                );
              }),
            ],
          ),
        ),
      ),
    );

    if (picked != null && picked != ticket.status && mounted) {
      final success = await context.read<SupportProvider>().updateStatus(ticket.id, picked);
      if (success && mounted) {
        PingoPopupDialog.show(
          context,
          title: 'Onboarding Stage Updated',
          subtitle: '${ticket.customerName} marked as $picked.',
          badge: picked,
          pose: picked == 'LIVE' || picked == 'COMPLETED' ? PingoPoses.celebrate : PingoPoses.action,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SupportProvider>();
    final tickets = provider.tickets;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Support & Onboarding'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => provider.fetchTickets(),
          ),
        ],
      ),
      body: provider.isLoading && tickets.isEmpty
          ? const LoadingIndicator(message: 'Loading support queue...')
          : provider.errorMessage != null && tickets.isEmpty
              ? ErrorView(
                  message: provider.errorMessage!,
                  onRetry: () => provider.fetchTickets(),
                )
              : tickets.isEmpty
                  ? const EmptyState(
                      title: 'No Support Onboardings',
                      subtitle: 'Clients handed off from Finance will appear here for onboarding and installation.',
                      pingoPose: PingoPoses.salute,
                    )
                  : RefreshIndicator(
                      color: AppColors.primary,
                      onRefresh: () => provider.fetchTickets(showLoading: false),
                      child: ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: tickets.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final t = tickets[index];

                          return WacrmCard(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Expanded(
                                      child: Text(
                                        t.customerName,
                                        style: const TextStyle(
                                          fontSize: 15,
                                          fontWeight: FontWeight.w700,
                                          color: AppColors.textMain,
                                        ),
                                      ),
                                    ),
                                    WacrmBadge.status(t.status),
                                  ],
                                ),
                                if (t.companyName != null && t.companyName!.isNotEmpty) ...[
                                  const SizedBox(height: 2),
                                  Text(
                                    t.companyName!,
                                    style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
                                  ),
                                ],
                                const Divider(height: 20),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Row(
                                      children: [
                                        const Icon(Icons.person_pin_circle_outlined, size: 16, color: AppColors.textLight),
                                        const SizedBox(width: 4),
                                        Text(
                                          t.assignedToName ?? 'Support Team',
                                          style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                                        ),
                                      ],
                                    ),
                                    if (t.biometricDeviceCount > 0)
                                      WacrmBadge(
                                        label: '${t.biometricDeviceCount} Biometric Hardware',
                                        backgroundColor: const Color(0xFFFEF3C7),
                                        textColor: const Color(0xFFD97706),
                                        fontSize: 10,
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 14),

                                // Actions
                                Row(
                                  children: [
                                    Expanded(
                                      child: WacrmButton(
                                        text: 'Update Stage',
                                        icon: Icons.sync_alt_rounded,
                                        type: WacrmButtonType.outline,
                                        height: 38,
                                        onPressed: () => _updateStatus(t),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: WacrmButton(
                                        text: 'Call Client',
                                        icon: Icons.phone_rounded,
                                        height: 38,
                                        onPressed: () => _callNumber(t.phone),
                                      ),
                                    ),
                                  ],
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
