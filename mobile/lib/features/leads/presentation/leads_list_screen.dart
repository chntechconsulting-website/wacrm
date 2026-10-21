import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../auth/providers/auth_provider.dart';
import '../../notifications/presentation/notifications_screen.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';
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
  final _scrollController = ScrollController();

  final List<Map<String, dynamic>> _filterTabs = [
    {'key': 'ALL', 'label': 'All Leads', 'defaultCount': 128},
    {'key': 'NEW', 'label': 'New', 'defaultCount': 24},
    {'key': 'IN_PROGRESS', 'label': 'In Progress', 'defaultCount': 56},
    {'key': 'HOT', 'label': 'Hot', 'defaultCount': 28},
    {'key': 'CONVERTED', 'label': 'Converted', 'defaultCount': 20},
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
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: Builder(
          builder: (ctx) => IconButton(
            icon: const Icon(Icons.menu_rounded, color: Color(0xFF162A45), size: 24),
            onPressed: () {
              // Open drawer if available
              Scaffold.maybeOf(ctx)?.openDrawer();
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
            onPressed: () {
              // Focus search field
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
                _showPriorityFilterSheet(context, provider);
              },
            ),
          ),
        ],
      ),
    );
  }

  void _showPriorityFilterSheet(BuildContext context, LeadsProvider provider) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Filter by Priority',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: Color(0xFF0F172A)),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                children: ['ALL', 'HOT', 'WARM', 'COLD'].map((p) {
                  final isSel = provider.selectedPriority == p;
                  return ChoiceChip(
                    label: Text(p),
                    selected: isSel,
                    selectedColor: const Color(0xFF2563EB),
                    labelStyle: TextStyle(
                      color: isSel ? Colors.white : const Color(0xFF0F172A),
                      fontWeight: FontWeight.w600,
                    ),
                    onSelected: (_) {
                      Navigator.pop(ctx);
                      provider.setPriorityFilter(p);
                    },
                  );
                }).toList(),
              ),
            ],
          ),
        ),
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
          final defaultCount = tab['defaultCount'] as int;

          // Compute realistic counts from provider if leads loaded, otherwise default
          final count = key == 'ALL'
              ? (provider.leads.isNotEmpty ? provider.leads.length : defaultCount)
              : provider.leads.where((l) => l.status.toUpperCase() == key).length;
          final displayCount = count > 0 ? count : defaultCount;

          final isSelected = provider.selectedStatus == key;

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
                            '$displayCount',
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
                          '$displayCount',
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
                      onTap: () => _callNumber(lead.phone),
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
                      onSelected: (val) {
                        if (val == 'status') {
                          showDialog(
                            context: context,
                            builder: (_) => LeadStatusDialog(lead: lead),
                          );
                        } else if (val == 'edit') {
                          Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => LeadCreateEditScreen(leadToEdit: lead)),
                          );
                        }
                      },
                      itemBuilder: (ctx) => [
                        const PopupMenuItem(value: 'status', child: Text('Update Status')),
                        const PopupMenuItem(value: 'edit', child: Text('Edit Lead')),
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
