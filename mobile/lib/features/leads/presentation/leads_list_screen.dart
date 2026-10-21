import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';
import 'lead_create_edit_screen.dart';
import 'lead_detail_screen.dart';

class LeadsListScreen extends StatefulWidget {
  const LeadsListScreen({super.key});

  @override
  State<LeadsListScreen> createState() => _LeadsListScreenState();
}

class _LeadsListScreenState extends State<LeadsListScreen> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  final List<String> _statusFilters = [
    'ALL',
    'NEW',
    'ASSIGNED',
    'CONTACTED',
    'INTERESTED',
    'FOLLOW_UP',
    'QUALIFIED',
    'CONVERTED',
    'LOST',
  ];

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LeadsProvider>().fetchLeads(refresh: true);
    });
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      context.read<LeadsProvider>().fetchLeads();
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _callNumber(String phone) async {
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final uri = Uri.parse('tel:$cleanPhone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<LeadsProvider>();
    final leads = provider.leads;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Leads Management'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: () => provider.fetchLeads(refresh: true),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.white,
        icon: const Icon(Icons.add_rounded),
        label: const Text('New Lead', style: TextStyle(fontWeight: FontWeight.w700)),
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const LeadCreateEditScreen()),
          );
        },
      ),
      body: Column(
        children: [
          // Search & Filter Header
          Container(
            color: AppColors.card,
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            child: Column(
              children: [
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search leads by name, phone, or company...',
                    prefixIcon: const Icon(Icons.search_rounded, color: AppColors.textLight, size: 20),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear_rounded, size: 18),
                            onPressed: () {
                              _searchController.clear();
                              provider.search('');
                            },
                          )
                        : null,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    isDense: true,
                  ),
                  onChanged: (val) => provider.search(val),
                ),
                const SizedBox(height: 10),
                // Horizontal Status Filters
                SizedBox(
                  height: 32,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _statusFilters.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 6),
                    itemBuilder: (context, index) {
                      final s = _statusFilters[index];
                      final isSelected = provider.selectedStatus == s;

                      return ChoiceChip(
                        label: Text(
                          s.replaceAll('_', ' '),
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                            color: isSelected ? AppColors.white : AppColors.textMain,
                          ),
                        ),
                        selected: isSelected,
                        selectedColor: AppColors.primary,
                        backgroundColor: AppColors.cardHover,
                        side: BorderSide(
                          color: isSelected ? AppColors.primary : AppColors.border,
                        ),
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        visualDensity: VisualDensity.compact,
                        showCheckmark: false,
                        onSelected: (_) => provider.setStatusFilter(s),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),

          // Main Leads List
          Expanded(
            child: provider.isLoading && leads.isEmpty
                ? const LoadingIndicator(message: 'Loading leads...')
                : provider.errorMessage != null && leads.isEmpty
                    ? ErrorView(
                        message: provider.errorMessage!,
                        onRetry: () => provider.fetchLeads(refresh: true),
                      )
                    : leads.isEmpty
                        ? EmptyState(
                            title: 'No Leads Found',
                            subtitle: provider.selectedStatus != 'ALL'
                                ? 'No leads with status "${provider.selectedStatus}".'
                                : 'Try adding a new lead or adjusting your search.',
                            pingoPose: PingoPoses.inspect,
                            actionLabel: 'Create Lead',
                            onAction: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(builder: (_) => const LeadCreateEditScreen()),
                              );
                            },
                          )
                        : RefreshIndicator(
                            color: AppColors.primary,
                            onRefresh: () => provider.fetchLeads(refresh: true),
                            child: ListView.separated(
                              controller: _scrollController,
                              padding: const EdgeInsets.fromLTRB(16, 12, 16, 80),
                              itemCount: leads.length + (provider.isLoadingMore ? 1 : 0),
                              separatorBuilder: (_, __) => const SizedBox(height: 10),
                              itemBuilder: (context, index) {
                                if (index == leads.length) {
                                  return const Center(
                                    child: Padding(
                                      padding: EdgeInsets.all(12),
                                      child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primary),
                                    ),
                                  );
                                }

                                final lead = leads[index];
                                return _buildLeadCard(context, lead);
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildLeadCard(BuildContext context, LeadModel lead) {
    return WacrmCard(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => LeadDetailScreen(lead: lead)),
        );
      },
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: AppColors.primaryLight,
                child: Text(
                  lead.name.isNotEmpty ? lead.name[0].toUpperCase() : 'L',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: AppColors.primary,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      lead.name,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (lead.company != null && lead.company!.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        lead.company!,
                        style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  WacrmBadge.status(lead.status),
                  if (lead.priority != null) ...[
                    const SizedBox(height: 4),
                    WacrmBadge.priority(lead.priority!),
                  ],
                ],
              ),
            ],
          ),
          const Divider(height: 18),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Row(
                  children: [
                    const Icon(Icons.person_outline_rounded, size: 14, color: AppColors.textLight),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        lead.assignedToName ?? 'Unassigned',
                        style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Icon(Icons.share_location_outlined, size: 14, color: AppColors.textLight),
                    const SizedBox(width: 4),
                    Text(
                      lead.source ?? 'Manual',
                      style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                    ),
                  ],
                ),
              ),
              InkWell(
                onTap: () => _callNumber(lead.phone),
                borderRadius: BorderRadius.circular(20),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.primaryLight,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.phone_rounded, size: 13, color: AppColors.primary),
                      SizedBox(width: 4),
                      Text(
                        'Call',
                        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.primary),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
