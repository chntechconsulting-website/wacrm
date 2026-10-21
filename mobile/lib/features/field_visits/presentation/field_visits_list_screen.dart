import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/field_visit_model.dart';
import '../providers/field_visits_provider.dart';
import 'field_visit_form_screen.dart';

class FieldVisitsListScreen extends StatefulWidget {
  final int? initialLeadId;
  final int? initialEmployeeId;

  const FieldVisitsListScreen({
    super.key,
    this.initialLeadId,
    this.initialEmployeeId,
  });

  @override
  State<FieldVisitsListScreen> createState() => _FieldVisitsListScreenState();
}

class _FieldVisitsListScreenState extends State<FieldVisitsListScreen> {
  final _searchController = TextEditingController();
  int _selectedTab = 0; // 0: All / Team, 1: My Visits

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadVisits();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _loadVisits() {
    final user = context.read<AuthProvider>().currentUser;
    int? filterEmpId = widget.initialEmployeeId;

    if (_selectedTab == 1 && user != null) {
      filterEmpId = user.id;
    }

    context.read<FieldVisitsProvider>().fetchFieldVisits(
      leadId: widget.initialLeadId,
      employeeId: filterEmpId,
    );
  }

  String _formatDateTime(String? raw) {
    if (raw == null || raw.isEmpty) return 'Recent';
    try {
      final dt = DateTime.parse(raw);
      return DateFormat('dd MMM yyyy, hh:mm a').format(dt);
    } catch (_) {
      return raw;
    }
  }

  Color _getOutcomeColor(String outcome) {
    final o = outcome.toLowerCase();
    if (o.contains('won') || o.contains('deal')) {
      return const Color(0xFF047857);
    } else if (o.contains('quotation') || o.contains('quoted')) {
      return const Color(0xFF0D9488);
    } else if (o.contains('follow')) {
      return const Color(0xFFD97706);
    } else if (o.contains('interested')) {
      return const Color(0xFF2563EB);
    } else if (o.contains('not') || o.contains('lost') || o.contains('closed')) {
      return const Color(0xFFDC2626);
    }
    return const Color(0xFF6B7280);
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final provider = context.watch<FieldVisitsProvider>();
    final visits = provider.visits;

    final isManagerOrAdmin = user?.role == 'ADMIN' || user?.role == 'MANAGER' || user?.role == 'SALES_MANAGER';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Field Visits'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_location_alt_rounded),
            tooltip: 'Record Visit',
            onPressed: () async {
              final recorded = await Navigator.push<bool>(
                context,
                MaterialPageRoute(builder: (_) => const FieldVisitFormScreen()),
              );
              if (recorded == true && mounted) {
                _loadVisits();
              }
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        icon: const Icon(Icons.add_location_alt_rounded, color: Colors.white),
        label: const Text('Record Visit', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
        onPressed: () async {
          final recorded = await Navigator.push<bool>(
            context,
            MaterialPageRoute(builder: (_) => const FieldVisitFormScreen()),
          );
          if (recorded == true && mounted) {
            _loadVisits();
          }
        },
      ),
      body: RefreshIndicator(
        onRefresh: () async => _loadVisits(),
        child: Column(
          children: [
            // Search Bar & Filter Controls
            Container(
              color: AppColors.card,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Column(
                children: [
                  TextField(
                    controller: _searchController,
                    decoration: InputDecoration(
                      hintText: 'Search by client, agent, outcome, address...',
                      prefixIcon: const Icon(Icons.search_rounded, color: AppColors.textMuted),
                      suffixIcon: _searchController.text.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear_rounded, size: 18),
                              onPressed: () {
                                _searchController.clear();
                                provider.setSearchQuery('');
                              },
                            )
                          : null,
                      filled: true,
                      fillColor: AppColors.inputBackground,
                      contentPadding: const EdgeInsets.symmetric(vertical: 0, horizontal: 16),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                    ),
                    onChanged: (q) => provider.setSearchQuery(q),
                  ),
                  if (isManagerOrAdmin) ...[
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: InkWell(
                            onTap: () {
                              setState(() => _selectedTab = 0);
                              _loadVisits();
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              decoration: BoxDecoration(
                                color: _selectedTab == 0 ? AppColors.primary : AppColors.inputBackground,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Center(
                                child: Text(
                                  user?.role == 'ADMIN' ? 'Company Visits' : 'Team Visits',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: _selectedTab == 0 ? Colors.white : AppColors.textMuted,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: InkWell(
                            onTap: () {
                              setState(() => _selectedTab = 1);
                              _loadVisits();
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              decoration: BoxDecoration(
                                color: _selectedTab == 1 ? AppColors.primary : AppColors.inputBackground,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Center(
                                child: Text(
                                  'My Visits Only',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: _selectedTab == 1 ? Colors.white : AppColors.textMuted,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),

            // Main Content Area
            Expanded(
              child: Builder(
                builder: (ctx) {
                  if (provider.isLoading) {
                    return const Center(child: LoadingIndicator());
                  }

                  if (provider.errorMessage != null) {
                    return ErrorView(
                      message: provider.errorMessage!,
                      onRetry: _loadVisits,
                    );
                  }

                  if (visits.isEmpty) {
                    return EmptyState(
                      title: 'No Field Visits Found',
                      subtitle: _searchController.text.isNotEmpty
                          ? 'No field visits match "${_searchController.text}".'
                          : 'Record your customer field visits with photos, GPS, and follow-ups.',
                    );
                  }

                  return ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
                    itemCount: visits.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (ctx, index) {
                      final visit = visits[index];
                      return _buildVisitCard(visit);
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVisitCard(FieldVisitModel visit) {
    final outcomeColor = _getOutcomeColor(visit.visitOutcome);

    return WacrmCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: Client Name & Outcome Badge
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      visit.customerName,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Visited by: ${visit.employeeName}',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              WacrmBadge(
                label: visit.visitOutcome,
                backgroundColor: outcomeColor.withValues(alpha: 0.12),
                textColor: outcomeColor,
              ),
            ],
          ),
          const Divider(height: 18),

          // Date & Location Info Row
          Row(
            children: [
              const Icon(Icons.schedule_rounded, size: 14, color: AppColors.textMuted),
              const SizedBox(width: 6),
              Text(
                _formatDateTime(visit.checkinTime),
                style: const TextStyle(fontSize: 12, color: AppColors.textMuted, fontWeight: FontWeight.w500),
              ),
            ],
          ),
          if (visit.checkinAddress != null && visit.checkinAddress!.isNotEmpty) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                const Icon(Icons.location_on_outlined, size: 14, color: AppColors.primary),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    visit.checkinAddress!,
                    style: const TextStyle(fontSize: 12, color: AppColors.textMain, fontWeight: FontWeight.w500),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],

          // Customer Requirements
          if (visit.customerRequirements != null && visit.customerRequirements!.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.inputBackground,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.format_quote_rounded, size: 16, color: AppColors.textMuted),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Requirements: ${visit.customerRequirements}',
                      style: const TextStyle(fontSize: 12, color: AppColors.textMain),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ],

          // Notes
          if (visit.notes != null && visit.notes!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              visit.notes!,
              style: const TextStyle(fontSize: 12, color: AppColors.textMuted, fontStyle: FontStyle.italic),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],

          // Follow-up scheduled banner
          if (visit.followup != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF3C7).withValues(alpha: 0.6),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFFDE68A)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.alarm_on_rounded, size: 16, color: Color(0xFFD97706)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Follow-up: ${visit.followup!['followup_date']} at ${visit.followup!['followup_time'] ?? "10:00 AM"} (${visit.followup!['priority'] ?? "MED"} Priority)',
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF92400E),
                      ),
                    ),
                  ),
                  const WacrmBadge(
                    label: '1h REMINDER',
                    backgroundColor: Color(0xFFFDE68A),
                    textColor: Color(0xFF78350F),
                    fontSize: 9,
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
