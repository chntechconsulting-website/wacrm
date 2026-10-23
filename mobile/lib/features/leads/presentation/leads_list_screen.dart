import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/services/doocti_call_service.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_drawer.dart';
import '../../auth/presentation/profile_screen.dart';
import '../../auth/providers/auth_provider.dart';
import '../../followups/presentation/followup_create_edit_dialog.dart';
import '../../notifications/presentation/notifications_screen.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';
import 'deal_won_dialog.dart';
import 'lead_create_edit_screen.dart';
import 'lead_detail_screen.dart';
import 'lead_status_dialog.dart';

class LeadsListScreen extends StatefulWidget {
  const LeadsListScreen({super.key});

  @override
  State<LeadsListScreen> createState() => _LeadsListScreenState();
}

class _LeadsListScreenState extends State<LeadsListScreen> {
  final _searchController = TextEditingController();
  final _searchFocusNode = FocusNode();
  final _scrollController = ScrollController();

  final List<Map<String, dynamic>> _filterTabs = [
    {'key': 'ALL', 'label': 'All Leads', 'statKey': 'allLeads'},
    {'key': 'NEW', 'label': 'New', 'statKey': 'newLeads'},
    {'key': 'IN_PROGRESS', 'label': 'In Progress', 'statKey': 'inProgressLeads'},
    {'key': 'HOT', 'label': 'Hot', 'statKey': 'hotLeads'},
    {'key': 'WON', 'label': 'Won', 'statKey': 'wonLeads'},
  ];

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final p = context.read<LeadsProvider>();
      p.fetchLeads(refresh: true);
      p.fetchLeadStats();
      p.fetchEmployees();
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
    _searchFocusNode.dispose();
    _scrollController.dispose();
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

  Color _getAvatarColor(String name) {
    final colors = [
      const Color(0xFF2563EB), // Blue (Tech Solutions)
      const Color(0xFF10B981), // Emerald (GreenMart)
      const Color(0xFF8B5CF6), // Purple (Sri Computers)
      const Color(0xFFF97316), // Orange (Kevin Groups)
      const Color(0xFF0284C7), // Sky Blue (LR Technologies)
      const Color(0xFFE11D48), // Rose
    ];
    if (name.isEmpty) return colors[0];
    return colors[name.codeUnits.reduce((a, b) => a + b) % colors.length];
  }

  String _getInitials(String name) {
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.length >= 2) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    } else if (parts.isNotEmpty && parts[0].isNotEmpty) {
      return parts[0].substring(0, parts[0].length >= 2 ? 2 : 1).toUpperCase();
    }
    return 'LD';
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<LeadsProvider>();
    final user = context.watch<AuthProvider>().currentUser;
    final leads = provider.leads;

    final userInitials = (user?.name != null && user!.name.isNotEmpty)
        ? _getInitials(user.name)
        : 'CM';

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      drawer: const WacrmDrawer(currentTabIndex: 1),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: Builder(
          builder: (ctx) => IconButton(
            icon: const Icon(Icons.menu_rounded, color: Color(0xFF162A45), size: 24),
            tooltip: 'Navigation Menu',
            onPressed: () {
              Scaffold.of(ctx).openDrawer();
            },
          ),
        ),
        title: Image.asset(
          'assets/images/logo.png',
          height: 26,
          fit: BoxFit.contain,
        ),
        centerTitle: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.search_rounded, color: Color(0xFF162A45), size: 22),
            tooltip: 'Search Leads',
            onPressed: () {
              _searchFocusNode.requestFocus();
            },
          ),
          IconButton(
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.notifications_none_rounded, color: Color(0xFF162A45), size: 23),
                Positioned(
                  right: 1,
                  top: 1,
                  child: Container(
                    width: 7,
                    height: 7,
                    decoration: const BoxDecoration(
                      color: Color(0xFFE5252A),
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              ],
            ),
            tooltip: 'Notifications',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const NotificationsScreen()),
              );
            },
          ),
          Padding(
            padding: const EdgeInsets.only(right: 16, left: 4),
            child: Center(
              child: InkWell(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const ProfileScreen()),
                  );
                },
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  width: 32,
                  height: 32,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: Color(0xFF162A45),
                  ),
                  child: Center(
                    child: Text(
                      userInitials,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFE5252A),
        foregroundColor: Colors.white,
        elevation: 4,
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const LeadCreateEditScreen()),
          );
        },
        child: const Icon(Icons.add_rounded, size: 28),
      ),
      body: Column(
        children: [
          // 1. Leads Hero Header Card with 3D Pingo & Growth Arrow
          _buildHeroBanner(),

          // 2. Search Field and Blue Filter Button
          _buildSearchAndFilterBar(provider),

          // 3. Horizontal Filter Tabs (All Leads 128, New 24, In Progress 56, etc.)
          _buildFilterTabs(provider),

          const SizedBox(height: 8),

          // 4. Main Leads List
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
                            color: const Color(0xFFE5252A),
                            onRefresh: () => provider.fetchLeads(refresh: true),
                            child: ListView.separated(
                              controller: _scrollController,
                              padding: const EdgeInsets.fromLTRB(16, 4, 16, 90),
                              itemCount: leads.length + (provider.isLoadingMore ? 1 : 0),
                              separatorBuilder: (_, _) => const SizedBox(height: 10),
                              itemBuilder: (context, index) {
                                if (index == leads.length) {
                                  return const Center(
                                    child: Padding(
                                      padding: EdgeInsets.all(12),
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: Color(0xFFE5252A),
                                      ),
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

  // ==========================================
  // HERO BANNER (LEADS)
  // ==========================================
  Widget _buildHeroBanner() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 12),
      height: 114,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF1E3A5F),
            Color(0xFF162A45),
            Color(0xFF0F172A),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF162A45).withValues(alpha: 0.25),
            blurRadius: 14,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Stack(
          children: [
            // Ambient soft glow
            Positioned(
              right: -20,
              top: -20,
              width: 140,
              height: 140,
              child: Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFF2563EB).withValues(alpha: 0.25),
                ),
              ),
            ),

            // Left Text Content
            const Positioned(
              left: 18,
              top: 20,
              bottom: 20,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'Leads',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                      color: Colors.white,
                      letterSpacing: -0.3,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Find new opportunities,\nturn them into customers.',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF94A3B8),
                      height: 1.25,
                    ),
                  ),
                ],
              ),
            ),

            // Right Mascot & 3D Growth Scene
            Positioned(
              right: 12,
              bottom: 0,
              width: 150,
              height: 110,
              child: Stack(
                alignment: Alignment.bottomRight,
                clipBehavior: Clip.none,
                children: [
                  // 4 3D Pillars
                  Positioned(
                    right: 6,
                    bottom: 12,
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        _buildMiniPillar(18, const Color(0xFF93C5FD)),
                        const SizedBox(width: 4),
                        _buildMiniPillar(32, const Color(0xFF60A5FA)),
                        const SizedBox(width: 4),
                        _buildMiniPillar(48, const Color(0xFF3B82F6)),
                        const SizedBox(width: 4),
                        _buildMiniPillar(68, const Color(0xFF2563EB)),
                      ],
                    ),
                  ),

                  // 3D Red Growth Arrow
                  Positioned(
                    right: 10,
                    top: 14,
                    child: Icon(
                      Icons.trending_up_rounded,
                      size: 54,
                      color: const Color(0xFFE5252A),
                    ),
                  ),

                  // Pingo Mascot (Pointing high)
                  const Positioned(
                    left: 0,
                    bottom: 0,
                    child: PingoMascotWidget(
                      pose: PingoPoses.victory,
                      height: 108,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMiniPillar(double height, Color color) {
    return Container(
      width: 10,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(4),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.35),
            blurRadius: 4,
            offset: const Offset(1, 2),
          ),
        ],
      ),
    );
  }

  // ==========================================
  // SEARCH & FILTER BAR
  // ==========================================
  Widget _buildSearchAndFilterBar(LeadsProvider provider) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          // Search Input Container
          Expanded(
            child: Container(
              height: 44,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: const Color(0xFFE2E8F0)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.02),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: TextField(
                controller: _searchController,
                focusNode: _searchFocusNode,
                style: const TextStyle(fontSize: 13, color: Color(0xFF0F172A)),
                decoration: InputDecoration(
                  hintText: 'Search leads, company, phone...',
                  hintStyle: const TextStyle(fontSize: 12.5, color: Color(0xFF94A3B8)),
                  prefixIcon: const Icon(Icons.search_rounded, color: Color(0xFF94A3B8), size: 20),
                  suffixIcon: _searchController.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear_rounded, size: 18, color: Color(0xFF94A3B8)),
                          onPressed: () {
                            _searchController.clear();
                            provider.search('');
                          },
                        )
                      : null,
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(vertical: 11),
                ),
                onChanged: (val) => provider.search(val),
              ),
            ),
          ),
          const SizedBox(width: 10),
          // Royal Blue Filter Button
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFF2563EB),
              borderRadius: BorderRadius.circular(14),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                  blurRadius: 8,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: IconButton(
              icon: const Icon(Icons.tune_rounded, color: Colors.white, size: 20),
              onPressed: () {
                _showFilterSheet(context, provider);
              },
            ),
          ),
        ],
      ),
    );
  }

  void _showFilterSheet(BuildContext context, LeadsProvider provider) {
    String selectedStatus = provider.selectedStatus;
    String selectedSource = provider.selectedSource;
    String selectedPriority = provider.selectedPriority;
    int? assignedTo = provider.assignedToFilter;
    String? dateFilter = provider.dateFilter;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) {
          return Container(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.85,
            ),
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            child: SafeArea(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Handle bar
                  Center(
                    child: Container(
                      margin: const EdgeInsets.only(top: 12, bottom: 8),
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade300,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),

                  // Header with Reset button
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.tune_rounded, color: Color(0xFF2563EB), size: 22),
                            SizedBox(width: 8),
                            Text(
                              'Filter Leads',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w800,
                                color: Color(0xFF0F172A),
                              ),
                            ),
                          ],
                        ),
                        TextButton(
                          onPressed: () {
                            setSheetState(() {
                              selectedStatus = 'ALL';
                              selectedSource = 'ALL';
                              selectedPriority = 'ALL';
                              assignedTo = null;
                              dateFilter = null;
                            });
                          },
                          child: const Text(
                            'Reset All',
                            style: TextStyle(
                              color: Color(0xFFE5252A),
                              fontWeight: FontWeight.w700,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const Divider(height: 1),

                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                      children: [
                        // 1. Status Filter
                        const Text(
                          'Lead Status',
                          style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: Color(0xFF334155)),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            'ALL',
                            'NEW LEAD',
                            'RE-INQUIRY',
                            'CONTACTED',
                            'INTERESTED',
                            'QUALIFIED',
                            'DEMO / MEETING',
                            'PROPOSAL SENT',
                            'NEGOTIATION',
                            'FOLLOW-UP',
                            'WON',
                            'LOST',
                          ].map((st) {
                            final isSel = selectedStatus.toUpperCase() == st.toUpperCase() ||
                                (st == 'ALL' && selectedStatus == 'ALL') ||
                                (st == 'NEW LEAD' && selectedStatus == 'NEW') ||
                                (st == 'WON' && selectedStatus == 'CONVERTED');
                            return ChoiceChip(
                              label: Text(st),
                              selected: isSel,
                              selectedColor: const Color(0xFFE5252A),
                              backgroundColor: const Color(0xFFF1F5F9),
                              labelStyle: TextStyle(
                                color: isSel ? Colors.white : const Color(0xFF334155),
                                fontSize: 11.5,
                                fontWeight: isSel ? FontWeight.w700 : FontWeight.w500,
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                                side: BorderSide(
                                  color: isSel ? const Color(0xFFE5252A) : const Color(0xFFE2E8F0),
                                ),
                              ),
                              onSelected: (_) {
                                setSheetState(() => selectedStatus = st);
                              },
                            );
                          }).toList(),
                        ),

                        const SizedBox(height: 18),

                        // 2. Lead Source Filter
                        const Text(
                          'Lead Source',
                          style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: Color(0xFF334155)),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: ['ALL', 'META', 'WEBSITE', 'MANUAL', 'EXCEL', 'REFERRAL'].map((src) {
                            final isSel = selectedSource.toUpperCase() == src.toUpperCase();
                            return ChoiceChip(
                              label: Text(src),
                              selected: isSel,
                              selectedColor: const Color(0xFF2563EB),
                              backgroundColor: const Color(0xFFF1F5F9),
                              labelStyle: TextStyle(
                                color: isSel ? Colors.white : const Color(0xFF334155),
                                fontSize: 11.5,
                                fontWeight: isSel ? FontWeight.w700 : FontWeight.w500,
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                                side: BorderSide(
                                  color: isSel ? const Color(0xFF2563EB) : const Color(0xFFE2E8F0),
                                ),
                              ),
                              onSelected: (_) {
                                setSheetState(() => selectedSource = src);
                              },
                            );
                          }).toList(),
                        ),

                        const SizedBox(height: 18),

                        // 3. Priority / Rating Filter
                        const Text(
                          'Priority / Rating',
                          style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: Color(0xFF334155)),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: ['ALL', 'Hot', 'Warm', 'Cold'].map((pri) {
                            final isSel = selectedPriority.toUpperCase() == pri.toUpperCase();
                            return ChoiceChip(
                              label: Text(pri),
                              selected: isSel,
                              selectedColor: const Color(0xFFF59E0B),
                              backgroundColor: const Color(0xFFF1F5F9),
                              labelStyle: TextStyle(
                                color: isSel ? Colors.white : const Color(0xFF334155),
                                fontSize: 11.5,
                                fontWeight: isSel ? FontWeight.w700 : FontWeight.w500,
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                                side: BorderSide(
                                  color: isSel ? const Color(0xFFF59E0B) : const Color(0xFFE2E8F0),
                                ),
                              ),
                              onSelected: (_) {
                                setSheetState(() => selectedPriority = pri);
                              },
                            );
                          }).toList(),
                        ),

                        const SizedBox(height: 18),

                        // 4. Assigned Team Member Filter
                        if (provider.employees.isNotEmpty) ...[
                          const Text(
                            'Assigned Team Member',
                            style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: Color(0xFF334155)),
                          ),
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF8FAFC),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFCBD5E1)),
                            ),
                            child: DropdownButtonHideUnderline(
                              child: DropdownButton<int?>(
                                value: assignedTo,
                                isExpanded: true,
                                hint: const Text('All Team Members', style: TextStyle(fontSize: 13)),
                                items: [
                                  const DropdownMenuItem<int?>(
                                    value: null,
                                    child: Text('All Team Members', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                                  ),
                                  ...provider.employees.map((emp) => DropdownMenuItem<int?>(
                                        value: emp.id,
                                        child: Text(
                                          '${emp.name} (${emp.role})',
                                          style: const TextStyle(fontSize: 13),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      )),
                                ],
                                onChanged: (val) {
                                  setSheetState(() => assignedTo = val);
                                },
                              ),
                            ),
                          ),
                          const SizedBox(height: 18),
                        ],

                        // 5. Date Received Filter
                        const Text(
                          'Lead Received Date',
                          style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: Color(0xFF334155)),
                        ),
                        const SizedBox(height: 8),
                        InkWell(
                          onTap: () async {
                            final now = DateTime.now();
                            final picked = await showDatePicker(
                              context: context,
                              initialDate: now,
                              firstDate: DateTime(2020),
                              lastDate: now.add(const Duration(days: 365)),
                            );
                            if (picked != null) {
                              final formatted = "${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}";
                              setSheetState(() => dateFilter = formatted);
                            }
                          },
                          borderRadius: BorderRadius.circular(12),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF8FAFC),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFCBD5E1)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.calendar_today_rounded, size: 18, color: Color(0xFF64748B)),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    dateFilter ?? 'Any Date',
                                    style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600,
                                      color: dateFilter != null ? const Color(0xFF0F172A) : const Color(0xFF94A3B8),
                                    ),
                                  ),
                                ),
                                if (dateFilter != null)
                                  GestureDetector(
                                    onTap: () {
                                      setSheetState(() => dateFilter = null);
                                    },
                                    child: const Icon(Icons.close_rounded, size: 18, color: Color(0xFF94A3B8)),
                                  ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),
                      ],
                    ),
                  ),

                  // Bottom Action Buttons
                  Padding(
                    padding: const EdgeInsets.all(20),
                    child: SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF2563EB),
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                          elevation: 2,
                        ),
                        onPressed: () {
                          Navigator.pop(ctx);
                          provider.setStatusFilter(selectedStatus);
                          provider.setSourceFilter(selectedSource);
                          provider.setPriorityFilter(selectedPriority);
                          provider.setAssignedToFilter(assignedTo);
                          provider.setDateFilter(dateFilter);
                        },
                        child: const Text(
                          'Apply Filters',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // ==========================================
  // HORIZONTAL FILTER CHIPS (TABS)
  // ==========================================
  Widget _buildFilterTabs(LeadsProvider provider) {
    return Container(
      height: 48,
      margin: const EdgeInsets.only(top: 10),
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        scrollDirection: Axis.horizontal,
        itemCount: _filterTabs.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final tab = _filterTabs[index];
          final key = tab['key'] as String;
          final label = tab['label'] as String;
          final statKey = tab['statKey'] as String;

          final count = provider.leadStats[statKey] ??
              (key == 'ALL'
                  ? provider.leads.length
                  : provider.leads.where((l) {
                      final s = l.status.toUpperCase();
                      if (key == 'NEW') return s.contains('NEW');
                      if (key == 'IN_PROGRESS') return s.contains('PROGRESS') || s == 'CONTACTED' || s == 'INTERESTED';
                      if (key == 'HOT') return (l.priority?.toUpperCase() == 'HOT' || l.priority?.toUpperCase() == 'HIGH' || l.rating?.toUpperCase() == 'HOT');
                      if (key == 'WON') return s == 'WON' || s == 'CONVERTED';
                      return s == key;
                    }).length);

          final isSelected = provider.selectedStatus == key || (key == 'WON' && provider.selectedStatus == 'CONVERTED');

          return GestureDetector(
            onTap: () => provider.setStatusFilter(key),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              decoration: BoxDecoration(
                color: isSelected ? const Color(0xFFE5252A) : Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: isSelected ? const Color(0xFFE5252A) : const Color(0xFFF1F5F9),
                  width: 1.2,
                ),
                boxShadow: isSelected
                    ? [
                        BoxShadow(
                          color: const Color(0xFFE5252A).withValues(alpha: 0.3),
                          blurRadius: 8,
                          offset: const Offset(0, 3),
                        ),
                      ]
                    : [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.02),
                          blurRadius: 4,
                          offset: const Offset(0, 1),
                        ),
                      ],
              ),
              child: isSelected
                  ? Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          label,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.25),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            '$count',
                            style: const TextStyle(
                              fontSize: 10.5,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ],
                    )
                  : Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          label,
                          style: const TextStyle(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF475569),
                          ),
                        ),
                        Text(
                          '$count',
                          style: const TextStyle(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF94A3B8),
                          ),
                        ),
                      ],
                    ),
            ),
          );
        },
      ),
    );
  }

  // ==========================================
  // LEAD CARD
  // ==========================================
  Widget _buildLeadCard(BuildContext context, LeadModel lead) {
    final avatarColor = _getAvatarColor(lead.company ?? lead.name);
    final initials = _getInitials(lead.company ?? lead.name);

    return InkWell(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => LeadDetailScreen(lead: lead)),
        );
      },
      borderRadius: BorderRadius.circular(18),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Row(
          children: [
            // Left Initials Avatar
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: avatarColor,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: avatarColor.withValues(alpha: 0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Center(
                child: Text(
                  initials,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14.5,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
            ),

            const SizedBox(width: 12),

            // Middle Info Column
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Lead Company / Name
                  Text(
                    lead.company ?? lead.name,
                    style: const TextStyle(
                      fontSize: 14.5,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF0F172A),
                      letterSpacing: -0.2,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),

                  const SizedBox(height: 4),

                  // Badges Row (Status Pill + Source Pill)
                  Row(
                    children: [
                      _buildStatusPill(lead.status, lead.priority),
                      const SizedBox(width: 6),
                      _buildSourcePill(lead.source ?? 'Website'),
                    ],
                  ),

                  const SizedBox(height: 4),

                  // Executive Name / Contact Person
                  Text(
                    lead.assignedToName ?? lead.name,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF64748B),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),

            // Right Actions & Date Column
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Circular Call Button
                    InkWell(
                      onTap: () => _callNumber(lead.phone, leadId: lead.id, contactName: lead.name),
                      borderRadius: BorderRadius.circular(18),
                      child: Container(
                        width: 34,
                        height: 34,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: const Color(0xFFF8FAFC),
                          border: Border.all(color: const Color(0xFFE2E8F0)),
                        ),
                        child: const Icon(
                          Icons.phone_rounded,
                          size: 16,
                          color: Color(0xFF0F172A),
                        ),
                      ),
                    ),
                    const SizedBox(width: 4),
                    // 3-dots more menu
                    PopupMenuButton<String>(
                      icon: const Icon(Icons.more_vert_rounded, size: 18, color: Color(0xFF94A3B8)),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      onSelected: (val) async {
                        if (val == 'status') {
                          final changed = await showDialog<bool>(
                            context: context,
                            builder: (_) => LeadStatusDialog(lead: lead),
                          );
                          if (changed == true && mounted) {
                            context.read<LeadsProvider>().fetchLeads(refresh: true);
                            context.read<LeadsProvider>().fetchLeadStats();
                          }
                        } else if (val == 'won') {
                          final won = await DealWonDialog.show(context, lead);
                          if (won == true && mounted) {
                            context.read<LeadsProvider>().fetchLeads(refresh: true);
                            context.read<LeadsProvider>().fetchLeadStats();
                          }
                        } else if (val == 'followup') {
                          final created = await FollowupCreateEditDialog.show(
                            context,
                            preselectedLeadId: lead.id,
                            preselectedLeadName: lead.company ?? lead.name,
                          );
                          if (created == true && mounted) {
                            context.read<LeadsProvider>().fetchLeads(refresh: true);
                          }
                        } else if (val == 'edit') {
                          final edited = await Navigator.push<bool>(
                            context,
                            MaterialPageRoute(builder: (_) => LeadCreateEditScreen(leadToEdit: lead)),
                          );
                          if (edited == true && mounted) {
                            context.read<LeadsProvider>().fetchLeads(refresh: true);
                          }
                        }
                      },
                      itemBuilder: (ctx) => [
                        const PopupMenuItem(
                          value: 'status',
                          child: Row(
                            children: [
                              Icon(Icons.flag_outlined, size: 16, color: Color(0xFF2563EB)),
                              SizedBox(width: 8),
                              Text('Update Status'),
                            ],
                          ),
                        ),
                        const PopupMenuItem(
                          value: 'won',
                          child: Row(
                            children: [
                              Icon(Icons.emoji_events_outlined, size: 16, color: Color(0xFF10B981)),
                              SizedBox(width: 8),
                              Text('Close Deal as WON', style: TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.w600)),
                            ],
                          ),
                        ),
                        const PopupMenuItem(
                          value: 'followup',
                          child: Row(
                            children: [
                              Icon(Icons.calendar_month_outlined, size: 16, color: Color(0xFFF59E0B)),
                              SizedBox(width: 8),
                              Text('Schedule Follow-up'),
                            ],
                          ),
                        ),
                        const PopupMenuItem(
                          value: 'edit',
                          child: Row(
                            children: [
                              Icon(Icons.edit_outlined, size: 16, color: Color(0xFF64748B)),
                              SizedBox(width: 8),
                              Text('Edit Lead'),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                // Formatted Date
                Text(
                  _formatDate(lead.createdAt),
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF94A3B8),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusPill(String status, String? priority) {
    final s = status.toUpperCase();
    final p = priority?.toUpperCase();

    Color bgColor = const Color(0xFFF1F5F9);
    Color textColor = const Color(0xFF475569);
    String label = status.replaceAll('_', ' ');

    if (p == 'HOT' || s.contains('HOT')) {
      bgColor = const Color(0xFFE5252A);
      textColor = Colors.white;
      label = 'Hot';
    } else if (p == 'WARM' || s.contains('INTERESTED') || s.contains('FOLLOW_UP')) {
      bgColor = const Color(0xFFF59E0B);
      textColor = Colors.white;
      label = 'Warm';
    } else if (s.contains('NEW')) {
      bgColor = const Color(0xFF2563EB);
      textColor = Colors.white;
      label = 'New';
    } else if (s.contains('COLD') || s.contains('LOST')) {
      bgColor = const Color(0xFF64748B);
      textColor = Colors.white;
      label = 'Cold';
    } else if (s.contains('CONVERTED') || s.contains('WON')) {
      bgColor = const Color(0xFF10B981);
      textColor = Colors.white;
      label = 'Converted';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2.5),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: textColor,
        ),
      ),
    );
  }

  Widget _buildSourcePill(String source) {
    Color bgColor = const Color(0xFFEEF2F6);
    Color textColor = const Color(0xFF475569);

    final s = source.toLowerCase();
    if (s.contains('meta') || s.contains('ad')) {
      bgColor = const Color(0xFFF3E8FF);
      textColor = const Color(0xFF7C3AED);
    } else if (s.contains('excel')) {
      bgColor = const Color(0xFFECFDF5);
      textColor = const Color(0xFF059669);
    } else if (s.contains('website')) {
      bgColor = const Color(0xFFF1F5F9);
      textColor = const Color(0xFF475569);
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2.5),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        source,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: textColor,
        ),
      ),
    );
  }

  String _formatDate(String? raw) {
    if (raw == null || raw.isEmpty) return '16 Oct';
    try {
      final dt = DateTime.parse(raw);
      final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return '${dt.day} ${months[dt.month - 1]}';
    } catch (_) {
      return '16 Oct';
    }
  }
}
