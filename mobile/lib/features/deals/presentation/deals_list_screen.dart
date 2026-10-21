import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/network/api_client.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/deal_summary_model.dart';
import '../providers/deals_provider.dart';

class DealsListScreen extends StatefulWidget {
  const DealsListScreen({super.key});

  @override
  State<DealsListScreen> createState() => _DealsListScreenState();
}

class _DealsListScreenState extends State<DealsListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DealsProvider>().fetchFinanceHandoffs();
    });
  }

  void _confirmPayment(FinanceHandoffModel handoff) async {
    final refController = TextEditingController();

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirm Payment & Issue Invoice', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Client: ${handoff.leadName}'),
            Text('Proforma: #${handoff.proformaNumber}'),
            Text('Amount: ${CurrencyFormatter.formatInr(handoff.amount)}', style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 14),
            TextField(
              controller: refController,
              decoration: const InputDecoration(
                labelText: 'UTR / Payment Ref (Optional)',
                hintText: 'e.g. UTR-982348234',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.success),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirm & Issue Invoice'),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      final success = await context.read<DealsProvider>().confirmPayment(
            handoff.id,
            paymentRef: refController.text.trim().isNotEmpty ? refController.text.trim() : null,
          );

      if (success && mounted) {
        PingoPopupDialog.show(
          context,
          title: 'Payment Confirmed & Invoice Generated!',
          subtitle: 'Official Tax Invoice created for ${handoff.leadName}.',
          badge: 'TAX INVOICE ISSUED',
          pose: PingoPoses.celebrate,
        );
      }
    }
  }

  void _downloadInvoice(int handoffId) async {
    try {
      final client = ApiClient();
      final bytes = await client.downloadBytes(ApiEndpoints.downloadFinanceInvoice(handoffId));

      if (mounted) {
        PingoPopupDialog.show(
          context,
          title: 'Invoice Downloaded',
          subtitle: 'Tax invoice PDF (${bytes.lengthInBytes} bytes) saved.',
          badge: 'DOWNLOADED',
          pose: PingoPoses.salute,
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to download invoice: $e'), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final provider = context.watch<DealsProvider>();
    final handoffs = provider.financeHandoffs;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Deals & Finance Handoffs'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => provider.fetchFinanceHandoffs(),
          ),
        ],
      ),
      body: provider.isLoading && handoffs.isEmpty
          ? const LoadingIndicator(message: 'Loading deals...')
          : provider.errorMessage != null && handoffs.isEmpty
              ? ErrorView(
                  message: provider.errorMessage!,
                  onRetry: () => provider.fetchFinanceHandoffs(),
                )
              : handoffs.isEmpty
                  ? const EmptyState(
                      title: 'No Pending Finance Deals',
                      subtitle: 'When leads are marked WON with a proforma, they will appear here.',
                      pingoPose: PingoPoses.inspect,
                    )
                  : RefreshIndicator(
                      color: AppColors.primary,
                      onRefresh: () => provider.fetchFinanceHandoffs(showLoading: false),
                      child: ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: handoffs.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final h = handoffs[index];
                          final isPaid = h.paymentStatus == 'PAID' || h.invoiceNumber != null;

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
                                        h.leadName,
                                        style: const TextStyle(
                                          fontSize: 15,
                                          fontWeight: FontWeight.w700,
                                          color: AppColors.textMain,
                                        ),
                                      ),
                                    ),
                                    WacrmBadge.status(h.paymentStatus),
                                  ],
                                ),
                                if (h.companyName != null && h.companyName!.isNotEmpty) ...[
                                  const SizedBox(height: 2),
                                  Text(
                                    h.companyName!,
                                    style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
                                  ),
                                ],
                                const Divider(height: 18),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        const Text('Proforma Invoice', style: TextStyle(fontSize: 11, color: AppColors.textLight)),
                                        const SizedBox(height: 2),
                                        Text('#${h.proformaNumber}', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                                      ],
                                    ),
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.end,
                                      children: [
                                        const Text('Deal Value', style: TextStyle(fontSize: 11, color: AppColors.textLight)),
                                        const SizedBox(height: 2),
                                        Text(
                                          CurrencyFormatter.formatInr(h.amount),
                                          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: AppColors.primary),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                                if (h.invoiceNumber != null) ...[
                                  const SizedBox(height: 10),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                    decoration: BoxDecoration(
                                      color: AppColors.successLight,
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.receipt_long_rounded, size: 16, color: AppColors.success),
                                        const SizedBox(width: 6),
                                        Text(
                                          'Tax Invoice: #${h.invoiceNumber}',
                                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.success),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                                const SizedBox(height: 14),

                                // Action Buttons
                                Row(
                                  children: [
                                    if (!isPaid && (user?.canViewFinance == true || user?.isAdmin == true)) ...[
                                      Expanded(
                                        child: WacrmButton(
                                          text: 'Confirm Payment',
                                          icon: Icons.check_circle_outline_rounded,
                                          height: 40,
                                          onPressed: () => _confirmPayment(h),
                                        ),
                                      ),
                                    ],
                                    if (h.invoiceNumber != null) ...[
                                      Expanded(
                                        child: WacrmButton(
                                          text: 'Download Invoice',
                                          icon: Icons.picture_as_pdf_outlined,
                                          type: WacrmButtonType.outline,
                                          height: 40,
                                          onPressed: () => _downloadInvoice(h.id),
                                        ),
                                      ),
                                    ],
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
