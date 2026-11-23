import 'dart:async';

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
import '../../../core/widgets/wacrm_drawer.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/support_models.dart';
import '../providers/support_customers_provider.dart';
import 'support_customer_detail_screen.dart';
import 'support_dialogs.dart';
import 'support_widgets.dart';

class SupportCustomersScreen extends StatefulWidget {
  const SupportCustomersScreen({super.key});

  @override
  State<SupportCustomersScreen> createState() => _SupportCustomersScreenState();
}

class _SupportCustomersScreenState extends State<SupportCustomersScreen> {
  static const _statuses = [
    'NEW',
    'ONBOARDING',
    'INSTALLATION_PENDING',
    'INSTALLATION_COMPLETED',
    'TRAINING',
    'ACTIVE',
    'ISSUE_RAISED',
    'RESOLVED',
  ];
  static const _priorities = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'];
  static const _sources = [
    'Website',
    'WhatsApp',
    'Referral',
    'Walk-in',
    'Campaign',
  ];

  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  Timer? _searchDebounce;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SupportCustomersProvider>().fetchCustomers();
    });
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final position = _scrollController.position;
    if (position.pixels >= position.maxScrollExtent - 220) {
      context.read<SupportCustomersProvider>().loadMore();
    }
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 400), () {
      if (!mounted) return;
      final provider = context.read<SupportCustomersProvider>();
      provider.setSearch(value);
      provider.fetchCustomers();
    });
  }

  void _callCustomer(SupportCustomer customer) {
    final poc = customer.primaryPoc;
    final phone = (poc?.mobile ?? '').trim().isNotEmpty
        ? poc!.mobile
        : (customer.phone ?? '');
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
      leadId: customer.leadId,
      contactName: customer.displayCompany,
      customerPocId: poc?.id,
      pocName: poc?.name,
    );
  }

  Future<void> _openFilters() async {
    final provider = context.read<SupportCustomersProvider>();
    String status = provider.statusFilter;
    String priority = provider.priorityFilter;
    String source = provider.sourceFilter;

    final applied = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setSheetState) => Container(
          decoration: const BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child: SafeArea(
            child: SingleChildScrollView(
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
                    'Filter Support Customers',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textMain,
                    ),
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    value: status,
                    decoration: const InputDecoration(
                      labelText: 'Support Status',
                    ),
                    items: [
                      const DropdownMenuItem(
                        value: 'ALL',
                        child: Text('All statuses'),
                      ),
                      ..._statuses.map(
                        (value) => DropdownMenuItem(
                          value: value,
                          child: Text(supportStatusLabel(value)),
                        ),
                      ),
                    ],
                    onChanged: (value) =>
                        setSheetState(() => status = value ?? 'ALL'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: priority,
                    decoration: const InputDecoration(labelText: 'Priority'),
                    items: [
                      const DropdownMenuItem(
                        value: 'ALL',
                        child: Text('All priorities'),
                      ),
                      ..._priorities.map(
                        (value) =>
                            DropdownMenuItem(value: value, child: Text(value)),
                      ),
                    ],
                    onChanged: (value) =>
                        setSheetState(() => priority = value ?? 'ALL'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: source,
                    decoration: const InputDecoration(labelText: 'Source'),
                    items: [
                      const DropdownMenuItem(
                        value: 'ALL',
                        child: Text('All sources'),
                      ),
                      ..._sources.map(
                        (value) =>
                            DropdownMenuItem(value: value, child: Text(value)),
                      ),
                    ],
                    onChanged: (value) =>
                        setSheetState(() => source = value ?? 'ALL'),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () {
                            Navigator.pop(sheetContext, true);
                            provider.setStatusFilter('ALL');
                            provider.setPriorityFilter('ALL');
                            provider.setSourceFilter('ALL');
                            _searchController.clear();
                          },
                          child: const Text('Clear All'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.primary,
                            foregroundColor: Colors.white,
                            elevation: 0,
                          ),
                          onPressed: () {
                            provider.setStatusFilter(status);
                            provider.setPriorityFilter(priority);
                            provider.setSourceFilter(source);
                            Navigator.pop(sheetContext, true);
                          },
                          child: const Text('Apply Filters'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );

    if (applied == null) return;
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SupportCustomersProvider>();
    final customers = provider.customers;
    final user = context.watch<AuthProvider>().currentUser;
    final canCall = user?.canCallSupportCustomer ?? false;
    final canCreateFollowup = user?.canCreateSupportFollowup ?? false;
    final hasFilters =
        provider.statusFilter != 'ALL' ||
        provider.priorityFilter != 'ALL' ||
        provider.sourceFilter != 'ALL';

    return Scaffold(
      backgroundColor: AppColors.background,
      drawer: const WacrmDrawer(currentTabIndex: 1),
      appBar: AppBar(
        title: const Text('Support Customers'),
        actions: [
          IconButton(
            icon: Icon(
              hasFilters ? Icons.filter_alt_rounded : Icons.filter_alt_outlined,
              color: hasFilters ? AppColors.primary : null,
            ),
            tooltip: 'Filters',
            onPressed: _openFilters,
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => provider.fetchCustomers(),
          ),
        ],
      ),
      floatingActionButton: canCreateFollowup
          ? FloatingActionButton.extended(
              heroTag: 'supportCustomersFollowupFab',
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.add_alarm_rounded),
              label: const Text(
                'Follow-up',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              onPressed: () async {
                final created = await SupportFollowupSheet.show(
                  context,
                  customers: provider.customers,
                );
                if (created == true && mounted) {
                  provider.fetchCustomers(showLoading: false);
                }
              },
            )
          : null,
      body: Column(
        children: [
          Container(
            color: AppColors.card,
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
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
                      hintText: 'Search company, contact, phone, POC...',
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
                                provider.setSearch('');
                                provider.fetchCustomers();
                                setState(() {});
                              },
                            )
                          : null,
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onChanged: (value) {
                      _onSearchChanged(value);
                      setState(() {});
                    },
                  ),
                ),
                if (provider.statusFilter != 'ALL' ||
                    provider.priorityFilter != 'ALL' ||
                    provider.sourceFilter != 'ALL') ...[
                  const SizedBox(height: 8),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        if (provider.statusFilter != 'ALL')
                          _activeFilterChip(
                            supportStatusLabel(provider.statusFilter),
                            () => provider.setStatusFilter('ALL'),
                          ),
                        if (provider.priorityFilter != 'ALL')
                          _activeFilterChip(
                            provider.priorityFilter,
                            () => provider.setPriorityFilter('ALL'),
                          ),
                        if (provider.sourceFilter != 'ALL')
                          _activeFilterChip(
                            provider.sourceFilter,
                            () => provider.setSourceFilter('ALL'),
                          ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 2),
            child: Row(
              children: [
                Text(
                  '${provider.total} authorized customer(s)',
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.textMuted,
                  ),
                ),
                const Spacer(),
                if (hasFilters)
                  Text(
                    'Filtered',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: AppColors.primary.withValues(alpha: 0.9),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: provider.isLoading && customers.isEmpty
                ? const LoadingIndicator(
                    message: 'Loading assigned Support customers...',
                  )
                : provider.errorMessage != null && customers.isEmpty
                ? ErrorView(
                    message: provider.errorMessage!,
                    onRetry: () => provider.fetchCustomers(),
                  )
                : customers.isEmpty
                ? EmptyState(
                    title: 'No Support Customers',
                    subtitle: 'No assigned customers match the current search and filters.',
                    pingoPose: PingoPoses.inspect,
                    actionLabel: hasFilters ? 'Clear Filters' : null,
                    onAction: hasFilters
                        ? () {
                            provider.clearFilters();
                            _searchController.clear();
                            setState(() {});
                          }
                        : null,
                  )
                : RefreshIndicator(
                    color: AppColors.primary,
                    onRefresh: () =>
                        provider.fetchCustomers(showLoading: false),
                    child: ListView.separated(
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 110),
                      itemCount: customers.length + (provider.hasMore ? 1 : 0),
                      separatorBuilder: (_, _) => const SizedBox(height: 10),
                      itemBuilder: (context, index) {
                        if (index >= customers.length) {
                          return const Padding(
                            padding: EdgeInsets.symmetric(vertical: 14),
                            child: Center(
                              child: SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2.4,
                                  color: AppColors.primary,
                                ),
                              ),
                            ),
                          );
                        }
                        final customer = customers[index];
                        return _customerCard(customer, canCall: canCall);
                      },
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _activeFilterChip(String label, VoidCallback onRemove) {
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: InputChip(
        label: Text(label, style: const TextStyle(fontSize: 10)),
        onDeleted: onRemove,
        deleteIcon: const Icon(Icons.close_rounded, size: 13),
        visualDensity: VisualDensity.compact,
        backgroundColor: AppColors.primaryLight,
        side: BorderSide.none,
        labelStyle: const TextStyle(
          color: AppColors.primary,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _customerCard(SupportCustomer customer, {required bool canCall}) {
    final poc = customer.primaryPoc;
    final contactPerson = customer.contactPerson.trim().isNotEmpty
        ? customer.contactPerson
        : customer.name;
    return WacrmCard(
      padding: const EdgeInsets.all(14),
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => SupportCustomerDetailScreen(
            leadId: customer.leadId,
            customerId: customer.customerId,
            initialCustomer: customer,
          ),
        ),
      ),
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
                      customer.displayCompany,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                    if (customer.displayCompany != contactPerson)
                      Text(
                        contactPerson,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textMuted,
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              SupportStatusBadge(status: customer.supportStatus),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              WacrmBadge(
                label: customer.priority.toUpperCase(),
                backgroundColor: _priorityColor(customer.priority)
                    .withValues(alpha: 0.12),
                textColor: _priorityColor(customer.priority),
                fontSize: 9,
              ),
              if (customer.isTrial)
                WacrmBadge(
                  label: customer.isTrialExpired
                      ? 'TRIAL EXPIRED'
                      : customer.trialDaysRemaining != null
                      ? 'TRIAL • ${customer.trialDaysRemaining}D'
                      : 'TRIAL',
                  backgroundColor: const Color(0xFFF3E8FF),
                  textColor: const Color(0xFF9333EA),
                  fontSize: 9,
                ),
              if (customer.assignedSupportExecutiveName != null)
                WacrmBadge(
                  label: customer.assignedSupportExecutiveName!,
                  backgroundColor: const Color(0xFFEFF6FF),
                  textColor: const Color(0xFF2563EB),
                  icon: Icons.person_outline_rounded,
                  fontSize: 9,
                ),
            ],
          ),
          const Divider(height: 18),
          if (poc != null) ...[
            Row(
              children: [
                const Icon(
                  Icons.contact_phone_rounded,
                  size: 16,
                  color: Color(0xFF0F766E),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'POC: ${poc.name}${poc.isPrimary ? ' (Primary)' : ''}'
                    ' • ${poc.mobile}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF0F766E),
                    ),
                  ),
                ),
                if (canCall)
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    icon: const Icon(
                      Icons.phone_rounded,
                      size: 18,
                      color: AppColors.success,
                    ),
                    onPressed: () => DooctiCallService.makeCall(
                      context,
                      phone: poc.mobile,
                      leadId: customer.leadId,
                      contactName: customer.displayCompany,
                      customerPocId: poc.id,
                      pocName: poc.name,
                    ),
                  ),
              ],
            ),
          ] else
            Row(
              children: [
                const Icon(
                  Icons.phone_outlined,
                  size: 16,
                  color: AppColors.textLight,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    customer.phone?.trim().isNotEmpty == true
                        ? customer.phone!
                        : 'No POC or phone saved',
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textMuted,
                    ),
                  ),
                ),
                if (canCall && (customer.phone ?? '').trim().isNotEmpty)
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    icon: const Icon(
                      Icons.phone_rounded,
                      size: 18,
                      color: AppColors.success,
                    ),
                    onPressed: () => _callCustomer(customer),
                  ),
              ],
            ),
          if (customer.nextFollowupDate != null) ...[
            const SizedBox(height: 2),
            Row(
              children: [
                const Icon(
                  Icons.alarm_rounded,
                  size: 15,
                  color: Color(0xFFD97706),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Next follow-up: ${supportFormatDate(customer.nextFollowupDate)}'
                    '${(customer.nextFollowupTime ?? '').trim().isNotEmpty ? ' • ${customer.nextFollowupTime}' : ''}',
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xFFD97706),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Color _priorityColor(String priority) {
    switch (priority.trim().toUpperCase()) {
      case 'URGENT':
      case 'HIGH':
        return const Color(0xFFDC2626);
      case 'MEDIUM':
        return const Color(0xFFD97706);
      default:
        return const Color(0xFF16A34A);
    }
  }
}
