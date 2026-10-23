import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/services/doocti_call_service.dart';
import '../../../core/utils/date_formatter.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../providers/customers_provider.dart';

class CustomersListScreen extends StatefulWidget {
  const CustomersListScreen({super.key});

  @override
  State<CustomersListScreen> createState() => _CustomersListScreenState();
}

class _CustomersListScreenState extends State<CustomersListScreen> {
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CustomersProvider>().fetchCustomers();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _callNumber(String phone, {int? leadId, String? contactName}) {
    DooctiCallService.makeCall(
      context,
      phone: phone,
      leadId: leadId,
      contactName: contactName,
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CustomersProvider>();
    final customers = provider.customers;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Customer Directory'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => provider.fetchCustomers(),
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            color: AppColors.card,
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search customers by name, company, phone...',
                prefixIcon: const Icon(Icons.search_rounded, color: AppColors.textLight, size: 20),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                isDense: true,
              ),
              onChanged: (val) => provider.search(val),
            ),
          ),
          Expanded(
            child: provider.isLoading && customers.isEmpty
                ? const LoadingIndicator(message: 'Loading customers...')
                : provider.errorMessage != null && customers.isEmpty
                    ? ErrorView(
                        message: provider.errorMessage!,
                        onRetry: () => provider.fetchCustomers(),
                      )
                    : customers.isEmpty
                        ? const EmptyState(
                            title: 'No Customers Yet',
                            subtitle: 'Converted leads will automatically appear in this directory.',
                            pingoPose: PingoPoses.inspect,
                          )
                        : RefreshIndicator(
                            color: AppColors.primary,
                            onRefresh: () => provider.fetchCustomers(showLoading: false),
                            child: ListView.separated(
                              padding: const EdgeInsets.all(16),
                              itemCount: customers.length,
                              separatorBuilder: (_, __) => const SizedBox(height: 10),
                              itemBuilder: (context, index) {
                                final cust = customers[index];
                                return WacrmCard(
                                  padding: const EdgeInsets.all(14),
                                  child: Row(
                                    children: [
                                      CircleAvatar(
                                        radius: 20,
                                        backgroundColor: AppColors.primaryLight,
                                        child: Text(
                                          cust.name.isNotEmpty ? cust.name[0].toUpperCase() : 'C',
                                          style: const TextStyle(
                                            fontWeight: FontWeight.w700,
                                            color: AppColors.primary,
                                            fontSize: 15,
                                          ),
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
                                                    cust.name,
                                                    style: const TextStyle(
                                                      fontSize: 14,
                                                      fontWeight: FontWeight.w700,
                                                      color: AppColors.textMain,
                                                    ),
                                                  ),
                                                ),
                                                WacrmBadge.status(cust.status),
                                              ],
                                            ),
                                            if (cust.company != null && cust.company!.isNotEmpty) ...[
                                              const SizedBox(height: 2),
                                              Text(
                                                cust.company!,
                                                style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                                              ),
                                            ],
                                            const SizedBox(height: 4),
                                            Text(
                                              'Customer since ${DateFormatter.formatDate(cust.createdAt)}',
                                              style: const TextStyle(fontSize: 11, color: AppColors.textLight),
                                            ),
                                          ],
                                        ),
                                      ),
                                      IconButton(
                                        icon: const Icon(Icons.phone_rounded, color: AppColors.primary, size: 20),
                                        onPressed: () => _callNumber(cust.phone, leadId: cust.leadId, contactName: cust.name),
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
}
