import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../models/quotation_model.dart';
import '../providers/quotations_provider.dart';

class QuotationsListScreen extends StatefulWidget {
  const QuotationsListScreen({super.key});

  @override
  State<QuotationsListScreen> createState() => _QuotationsListScreenState();
}

class _QuotationsListScreenState extends State<QuotationsListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<QuotationsProvider>().fetchDocuments();
    });
  }

  void _downloadDocument(QuotationModel doc) async {
    final provider = context.read<QuotationsProvider>();
    final bytes = await provider.downloadPdf(doc.id, doc.docType);

    if (bytes != null && mounted) {
      PingoPopupDialog.showSuccessModal(
        context,
        title: '${doc.docType.toUpperCase()} Downloaded!',
        subtitle: 'Document #${doc.docNumber} has been downloaded and prepared successfully.',
        pose: PingoPoses.celebrate,
      );
    }
  }

  void _generateProforma(QuotationModel doc) async {
    final provider = context.read<QuotationsProvider>();
    final success = await provider.convertQuoteToProforma(doc.id);

    if (success && mounted) {
      PingoPopupDialog.showSuccessModal(
        context,
        title: 'Proforma Invoice Generated!',
        subtitle: 'Quotation #${doc.docNumber} converted into Proforma Invoice successfully.',
        pose: PingoPoses.victory,
      );
    }
  }

  void _syncToWebsite(QuotationModel doc) async {
    if (doc.productCategory.contains('bio')) {
      // Strictly enforce rule: Biometric proformas can never sync!
      PingoPopupDialog.show(
        context,
        title: 'Biometric Proforma Excluded',
        subtitle: 'Rule Enforced: Biometric hardware documents remain exclusively in CRM.',
        badge: 'BLOCKED (RULE)',
        pose: PingoPoses.idea,
      );
      return;
    }

    final provider = context.read<QuotationsProvider>();
    final res = await provider.syncToWebsite(doc.id);

    if (res != null && mounted) {
      final msg = res['message'] ?? 'Proforma synchronized to WAHRMS website.';
      PingoPopupDialog.showSuccessModal(
        context,
        title: 'Website Synced!',
        subtitle: msg,
        pose: PingoPoses.celebrate,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<QuotationsProvider>();
    final docs = provider.documents;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Quotations & Invoices'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => provider.fetchDocuments(),
          ),
        ],
      ),
      body: Column(
        children: [
          // Filter Tabs
          Container(
            color: AppColors.card,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(
              children: [
                _buildFilterChip('All', provider.selectedDocType == 'all', () => provider.setDocType('all')),
                const SizedBox(width: 8),
                _buildFilterChip('Quotations', provider.selectedDocType == 'quotation', () => provider.setDocType('quotation')),
                const SizedBox(width: 8),
                _buildFilterChip('Proformas', provider.selectedDocType == 'proforma', () => provider.setDocType('proforma')),
                const SizedBox(width: 8),
                _buildFilterChip('Invoices', provider.selectedDocType == 'invoice', () => provider.setDocType('invoice')),
              ],
            ),
          ),

          // Main Documents List
          Expanded(
            child: provider.isLoading && docs.isEmpty
                ? const LoadingIndicator(message: 'Loading documents...')
                : provider.errorMessage != null && docs.isEmpty
                    ? ErrorView(
                        message: provider.errorMessage!,
                        onRetry: () => provider.fetchDocuments(),
                      )
                    : docs.isEmpty
                        ? const EmptyState(
                            title: 'No Documents Found',
                            subtitle: 'Quotations and Proforma Invoices will appear here.',
                            pingoPose: PingoPoses.inspect,
                          )
                        : RefreshIndicator(
                            color: AppColors.primary,
                            onRefresh: () => provider.fetchDocuments(showLoading: false),
                            child: ListView.separated(
                              padding: const EdgeInsets.all(16),
                              itemCount: docs.length,
                              separatorBuilder: (_, __) => const SizedBox(height: 12),
                              itemBuilder: (context, index) {
                                final doc = docs[index];
                                final isBio = doc.productCategory.contains('bio');

                                return WacrmCard(
                                  padding: const EdgeInsets.all(16),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                Text(
                                                  doc.customerName,
                                                  style: const TextStyle(
                                                    fontSize: 15,
                                                    fontWeight: FontWeight.w700,
                                                    color: AppColors.textMain,
                                                  ),
                                                ),
                                                if (doc.companyName != null && doc.companyName!.isNotEmpty) ...[
                                                  const SizedBox(height: 2),
                                                  Text(
                                                    doc.companyName!,
                                                    style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                                                  ),
                                                ],
                                              ],
                                            ),
                                          ),
                                          WacrmBadge.status(doc.status),
                                        ],
                                      ),
                                      const Divider(height: 20),
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                '${doc.docType.toUpperCase()} #${doc.docNumber}',
                                                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                              ),
                                              const SizedBox(height: 4),
                                              Row(
                                                children: [
                                                  WacrmBadge(
                                                    label: isBio ? 'BIOMETRIC HARDWARE' : 'WAHRMS SOFTWARE',
                                                    backgroundColor: isBio
                                                        ? const Color(0xFFFEF3C7)
                                                        : AppColors.primaryLight,
                                                    textColor: isBio
                                                        ? const Color(0xFFD97706)
                                                        : AppColors.primary,
                                                    fontSize: 10,
                                                  ),
                                                  const SizedBox(width: 6),
                                                  Text(
                                                    '${doc.lineItems.length} item(s)',
                                                    style: const TextStyle(fontSize: 11, color: AppColors.textLight),
                                                  ),
                                                ],
                                              ),
                                            ],
                                          ),
                                          Column(
                                            crossAxisAlignment: CrossAxisAlignment.end,
                                            children: [
                                              const Text('Grand Total', style: TextStyle(fontSize: 11, color: AppColors.textLight)),
                                              const SizedBox(height: 2),
                                              Text(
                                                CurrencyFormatter.formatInr(doc.grandTotal),
                                                style: const TextStyle(
                                                  fontSize: 15,
                                                  fontWeight: FontWeight.w800,
                                                  color: AppColors.primary,
                                                ),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 14),

                                      // Actions
                                      Row(
                                        children: [
                                          Expanded(
                                            child: WacrmButton(
                                              text: 'Download PDF',
                                              icon: Icons.picture_as_pdf_outlined,
                                              type: WacrmButtonType.outline,
                                              height: 38,
                                              onPressed: () => _downloadDocument(doc),
                                            ),
                                          ),
                                          if (doc.docType == 'quotation') ...[
                                            const SizedBox(width: 8),
                                            Expanded(
                                              child: WacrmButton(
                                                text: 'Make Proforma',
                                                icon: Icons.receipt_long_rounded,
                                                height: 38,
                                                onPressed: () => _generateProforma(doc),
                                              ),
                                            ),
                                          ] else if (doc.docType == 'proforma') ...[
                                            const SizedBox(width: 8),
                                            Expanded(
                                              child: WacrmButton(
                                                text: isBio ? 'Biometric (CRM Only)' : 'Sync to Web',
                                                icon: isBio ? Icons.lock_outline_rounded : Icons.cloud_upload_outlined,
                                                type: isBio ? WacrmButtonType.secondary : WacrmButtonType.primary,
                                                height: 38,
                                                onPressed: () => _syncToWebsite(doc),
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
