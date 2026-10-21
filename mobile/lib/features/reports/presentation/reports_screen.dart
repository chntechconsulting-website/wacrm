import 'package:flutter/material.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/network/api_client.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../models/sales_overview_model.dart';

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key});

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  SalesOverviewModel? _report;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _fetchReport();
  }

  void _fetchReport() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final client = ApiClient();
      final response = await client.get(ApiEndpoints.salesOverview);
      if (mounted) {
        setState(() {
          _report = SalesOverviewModel.fromJson(response);
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceAll('ApiException: ', '');
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Sales Analytics & Reports'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _fetchReport,
          ),
        ],
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Generating Executive Report...')
          : _errorMessage != null
              ? ErrorView(message: _errorMessage!, onRetry: _fetchReport)
              : _report == null
                  ? const EmptyState(title: 'No Report Data', subtitle: 'Analytics data is currently unavailable.')
                  : RefreshIndicator(
                      color: AppColors.primary,
                      onRefresh: () async => _fetchReport(),
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Summary Cards
                            Row(
                              children: [
                                Expanded(
                                  child: _buildMetricTile(
                                    'Total Pipeline Leads',
                                    '${_report!.totalLeads}',
                                    Icons.people_alt_rounded,
                                    AppColors.primary,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: _buildMetricTile(
                                    'Total Converted',
                                    '${_report!.totalCustomers}',
                                    Icons.check_circle_rounded,
                                    AppColors.success,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            Row(
                              children: [
                                Expanded(
                                  child: _buildMetricTile(
                                    'Total Revenue',
                                    CurrencyFormatter.formatInr(_report!.totalRevenue),
                                    Icons.currency_rupee_rounded,
                                    AppColors.accent,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: _buildMetricTile(
                                    'Conversion Rate',
                                    '${_report!.conversionRate.toStringAsFixed(1)}%',
                                    Icons.trending_up_rounded,
                                    AppColors.warning,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 20),

                            // 7-Stage Sales Funnel
                            if (_report!.funnelStages.isNotEmpty) ...[
                              const Text(
                                'Sales Conversion Funnel',
                                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textMain),
                              ),
                              const SizedBox(height: 10),
                              WacrmCard(
                                padding: const EdgeInsets.all(16),
                                child: Column(
                                  children: _report!.funnelStages.map((stage) {
                                    final pct = (stage.percentage / 100.0).clamp(0.0, 1.0);
                                    return Padding(
                                      padding: const EdgeInsets.symmetric(vertical: 6.0),
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                            children: [
                                              Text(
                                                stage.stage,
                                                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                              ),
                                              Text(
                                                '${stage.count} leads (${stage.percentage.toStringAsFixed(1)}%)',
                                                style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                                              ),
                                            ],
                                          ),
                                          const SizedBox(height: 6),
                                          ClipRRect(
                                            borderRadius: BorderRadius.circular(4),
                                            child: LinearProgressIndicator(
                                              value: pct,
                                              minHeight: 8,
                                              backgroundColor: AppColors.border,
                                              valueColor: const AlwaysStoppedAnimation<Color>(AppColors.primary),
                                            ),
                                          ),
                                        ],
                                      ),
                                    );
                                  }).toList(),
                                ),
                              ),
                              const SizedBox(height: 20),
                            ],

                            // Source Distribution
                            if (_report!.sources.isNotEmpty) ...[
                              const Text(
                                'Leads by Acquisition Source',
                                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textMain),
                              ),
                              const SizedBox(height: 10),
                              WacrmCard(
                                padding: const EdgeInsets.all(16),
                                child: Column(
                                  children: _report!.sources.map((src) {
                                    return Padding(
                                      padding: const EdgeInsets.symmetric(vertical: 6.0),
                                      child: Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Row(
                                            children: [
                                              const Icon(Icons.circle, size: 8, color: AppColors.primary),
                                              const SizedBox(width: 8),
                                              Text(
                                                src.source,
                                                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                                              ),
                                            ],
                                          ),
                                          Text(
                                            '${src.count} leads',
                                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
                                          ),
                                        ],
                                      ),
                                    );
                                  }).toList(),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
    );
  }

  Widget _buildMetricTile(String title, String value, IconData icon, Color color) {
    return WacrmCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(title, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.textMuted)),
              Icon(icon, size: 16, color: color),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: color),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
