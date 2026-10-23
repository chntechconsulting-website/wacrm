import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/services/doocti_call_service.dart';
import '../../../core/widgets/wacrm_wave_nav_bar.dart';
import '../../activities/presentation/activities_screen.dart';
import '../../field_visits/presentation/field_visit_form_screen.dart';
import '../../followups/presentation/followup_create_edit_dialog.dart';
import '../../quotations/presentation/quotations_list_screen.dart';
import '../../whatsapp/data/whatsapp_repository.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';
import 'deal_won_dialog.dart';
import 'lead_assign_dialog.dart';
import 'lead_create_edit_screen.dart';
import 'lead_status_dialog.dart';

class LeadDetailScreen extends StatefulWidget {
  final LeadModel lead;

  const LeadDetailScreen({super.key, required this.lead});

  @override
  State<LeadDetailScreen> createState() => _LeadDetailScreenState();
}

class _LeadDetailScreenState extends State<LeadDetailScreen> {
  late LeadModel _lead;
  int _activeTabIndex = 0; // 0: Overview, 1: Activities, 2: Quotes, 3: Files

  @override
  void initState() {
    super.initState();
    _lead = widget.lead;
  }

  String _getInitials(String name) {
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.length >= 2) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    } else if (parts.isNotEmpty && parts[0].isNotEmpty) {
      return parts[0].substring(0, parts[0].length >= 2 ? 2 : 1).toUpperCase();
    }
    return 'TS';
  }

  void _callNumber(String phone) {
    DooctiCallService.makeCall(
      context,
      phone: phone,
      leadId: _lead.id,
      contactName: _lead.name,
    );
  }

  void _openWhatsApp(String phone) async {
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d]'), '');
    final url = 'https://wa.me/$cleanPhone?text=Hello%20${Uri.encodeComponent(_lead.name)},%20connecting%20from%20WA!CRM';
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      _showSendWhatsAppDialog(phone);
    }
  }

  void _showSendWhatsAppDialog(String phone) {
    final messageController = TextEditingController(
      text: 'Hello ${_lead.name}, thank you for speaking with us today!',
    );

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Send CRM WhatsApp Message', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('To: ${_lead.name} ($phone)', style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            TextField(
              controller: messageController,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Message Body',
                hintText: 'Type your message...',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF25D366)),
            onPressed: () async {
              final text = messageController.text.trim();
              if (text.isEmpty) return;
              Navigator.pop(ctx);
              try {
                await WhatsAppRepository().sendMessage(
                  leadId: _lead.id,
                  phoneNumber: phone,
                  messageText: text,
                );
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('WhatsApp message sent successfully via CRM.'),
                      backgroundColor: Color(0xFF10B981),
                    ),
                  );
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('WhatsApp error: ${e.toString().replaceAll('ApiException: ', '')}'),
                      backgroundColor: const Color(0xFFE5252A),
                    ),
                  );
                }
              }
            },
            child: const Text('Send Message', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _sendEmail(String? email) async {
    if (email == null || email.isEmpty) return;
    final uri = Uri.parse('mailto:$email');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  void _openMap() async {
    final query = Uri.encodeComponent(_lead.company ?? _lead.name);
    final uri = Uri.parse('https://www.google.com/maps/search/?api=1&query=$query');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  Future<void> _updateLeadStatus() async {
    final changed = await showDialog<bool>(
      context: context,
      builder: (_) => LeadStatusDialog(lead: _lead),
    );
    if (changed == true && mounted) {
      context.read<LeadsProvider>().fetchLeads(refresh: true);
      context.read<LeadsProvider>().fetchLeadStats();
      _fetchLatestLead();
    }
  }

  Future<void> _markDealWon() async {
    final won = await DealWonDialog.show(context, _lead);
    if (won == true && mounted) {
      context.read<LeadsProvider>().fetchLeads(refresh: true);
      context.read<LeadsProvider>().fetchLeadStats();
      _fetchLatestLead();
    }
  }

  Future<void> _scheduleFollowup() async {
    final created = await FollowupCreateEditDialog.show(
      context,
      preselectedLeadId: _lead.id,
      preselectedLeadName: _lead.company ?? _lead.name,
    );
    if (created == true && mounted) {
      context.read<LeadsProvider>().fetchLeads(refresh: true);
      _fetchLatestLead();
    }
  }

  Future<void> _fetchLatestLead() async {
    try {
      final updated = await context.read<LeadsProvider>().repository.getLeadById(_lead.id);
      if (mounted) {
        setState(() {
          _lead = updated;
        });
      }
    } catch (_) {}
  }

  void _showMoreActionsSheet() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),
              ListTile(
                leading: const Icon(Icons.emoji_events_rounded, color: Color(0xFF10B981)),
                title: const Text('Close Deal as WON', style: TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF10B981))),
                subtitle: const Text('Complete support handoff and proforma invoice'),
                onTap: () {
                  Navigator.pop(ctx);
                  _markDealWon();
                },
              ),
              ListTile(
                leading: const Icon(Icons.calendar_month_rounded, color: Color(0xFFF59E0B)),
                title: const Text('Schedule Follow-up', style: TextStyle(fontWeight: FontWeight.w600)),
                onTap: () {
                  Navigator.pop(ctx);
                  _scheduleFollowup();
                },
              ),
              ListTile(
                leading: const Icon(Icons.add_location_alt_rounded, color: Color(0xFF0284C7)),
                title: const Text('Record Field Visit', style: TextStyle(fontWeight: FontWeight.w600)),
                onTap: () async {
                  Navigator.pop(ctx);
                  final recorded = await Navigator.push<bool>(
                    context,
                    MaterialPageRoute(
                      builder: (_) => FieldVisitFormScreen(preselectedLead: _lead),
                    ),
                  );
                  if (recorded == true && mounted) {
                    context.read<LeadsProvider>().fetchLeads();
                  }
                },
              ),
              ListTile(
                leading: const Icon(Icons.person_add_alt_rounded, color: Color(0xFF6366F1)),
                title: const Text('Assign Executive', style: TextStyle(fontWeight: FontWeight.w600)),
                onTap: () {
                  Navigator.pop(ctx);
                  LeadAssignDialog.show(context, _lead);
                },
              ),
              ListTile(
                leading: const Icon(Icons.receipt_long_rounded, color: Color(0xFF8B5CF6)),
                title: const Text('Quotations & Estimates', style: TextStyle(fontWeight: FontWeight.w600)),
                onTap: () {
                  Navigator.pop(ctx);
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const QuotationsListScreen()));
                },
              ),
              ListTile(
                leading: const Icon(Icons.edit_outlined, color: Color(0xFF2563EB)),
                title: const Text('Edit Lead Information', style: TextStyle(fontWeight: FontWeight.w600)),
                onTap: () async {
                  Navigator.pop(ctx);
                  final updated = await Navigator.push<bool>(
                    context,
                    MaterialPageRoute(
                      builder: (_) => LeadCreateEditScreen(leadToEdit: _lead),
                    ),
                  );
                  if (updated == true && mounted) {
                    _fetchLatestLead();
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatCreatedDate(String? raw) {
    if (raw == null || raw.isEmpty) return '16 Oct 2026';
    try {
      final dt = DateTime.parse(raw);
      final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return '${dt.day} ${months[dt.month - 1]} ${dt.year}';
    } catch (_) {
      return '16 Oct 2026';
    }
  }

  @override
  Widget build(BuildContext context) {
    // Keep lead in sync with provider
    final currentFromProvider = context.watch<LeadsProvider>().leads.firstWhere(
          (l) => l.id == _lead.id,
          orElse: () => _lead,
        );
    _lead = currentFromProvider;

    final displayName = _lead.company != null && _lead.company!.isNotEmpty ? _lead.company! : _lead.name;
    final initials = _getInitials(displayName);
    final subtitle = _lead.requirement ?? (_lead.company != null ? _lead.name : 'Corporate Software Solutions');

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF0F172A), size: 24),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'Lead Details',
          style: TextStyle(
            color: Color(0xFF0F172A),
            fontSize: 18,
            fontWeight: FontWeight.w800,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.more_vert_rounded, color: Color(0xFF0F172A), size: 22),
            onPressed: _showMoreActionsSheet,
          ),
        ],
      ),
      bottomNavigationBar: WacrmWaveNavBar(
        currentIndex: 1, // Leads tab active
        onTap: (idx) {
          if (idx != 1) {
            Navigator.pop(context);
          }
        },
        onAdd: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const LeadCreateEditScreen()),
          );
        },
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 1. Top Hero Profile Card
            _buildProfileCard(displayName, initials, subtitle),

            const SizedBox(height: 16),

            // 2. 5 Quick Action Buttons (Call, WhatsApp, Email, Map, More)
            _buildQuickActionButtons(),

            const SizedBox(height: 16),

            // 3. Sub-Navigation Tabs (Overview, Activities, Quotes, Files)
            _buildSubNavTabs(),

            const SizedBox(height: 18),

            // 4. Basic Information Section
            _buildBasicInformationSection(),

            const SizedBox(height: 18),

            // 5. Lead Status Section
            _buildLeadStatusSection(),
          ],
        ),
      ),
    );
  }

  // ==========================================
  // HERO PROFILE CARD
  // ==========================================
  Widget _buildProfileCard(String displayName, String initials, String subtitle) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          // Initials Avatar
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: const Color(0xFF2563EB),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                  blurRadius: 10,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Center(
              child: Text(
                initials,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.5,
                ),
              ),
            ),
          ),

          const SizedBox(width: 14),

          // Name, Category & Badges
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  displayName,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF0F172A),
                    letterSpacing: -0.2,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF64748B),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    // Hot Lead Badge
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2.5),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFFF1F2),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: const Color(0xFFFFE4E6)),
                      ),
                      child: Text(
                        _lead.priority == 'HOT' || _lead.status.contains('HOT') ? 'Hot Lead' : _lead.status.replaceAll('_', ' '),
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFFE5252A),
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                    // Source Badge
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2.5),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF1F5F9),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        _lead.source ?? 'Website',
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF475569),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(width: 8),

          // Quick Call Circular Button
          InkWell(
            onTap: () => _callNumber(_lead.phone),
            borderRadius: BorderRadius.circular(20),
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white,
                border: Border.all(color: const Color(0xFFE2E8F0)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: const Icon(
                Icons.phone_rounded,
                size: 18,
                color: Color(0xFF0F172A),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================
  // 5 QUICK ACTION BUTTONS
  // ==========================================
  Widget _buildQuickActionButtons() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceAround,
      children: [
        _buildCircleActionButton(
          icon: Icons.phone_rounded,
          label: 'Call',
          bgColor: const Color(0xFF10B981),
          onTap: () => _callNumber(_lead.phone),
        ),
        _buildCircleActionButton(
          icon: Icons.chat_bubble_rounded,
          label: 'WhatsApp',
          bgColor: const Color(0xFF25D366),
          onTap: () => _openWhatsApp(_lead.phone),
        ),
        _buildCircleActionButton(
          icon: Icons.mail_rounded,
          label: 'Email',
          bgColor: const Color(0xFFEF4444),
          onTap: () => _sendEmail(_lead.email),
        ),
        _buildCircleActionButton(
          icon: Icons.location_on_rounded,
          label: 'Map',
          bgColor: const Color(0xFF8B5CF6),
          onTap: _openMap,
        ),
        _buildCircleActionButton(
          icon: Icons.more_horiz_rounded,
          label: 'More',
          bgColor: const Color(0xFFE2E8F0),
          iconColor: const Color(0xFF475569),
          onTap: _showMoreActionsSheet,
        ),
      ],
    );
  }

  Widget _buildCircleActionButton({
    required IconData icon,
    required String label,
    required Color bgColor,
    Color iconColor = Colors.white,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: bgColor,
              boxShadow: [
                BoxShadow(
                  color: bgColor.withValues(alpha: 0.35),
                  blurRadius: 8,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Icon(icon, size: 22, color: iconColor),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: Color(0xFF475569),
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================
  // SUB NAVIGATION TABS
  // ==========================================
  Widget _buildSubNavTabs() {
    final tabs = [
      {'label': 'Overview', 'icon': Icons.dashboard_customize_rounded},
      {'label': 'Activities', 'icon': Icons.checklist_rounded},
      {'label': 'Quotes', 'icon': Icons.receipt_long_rounded},
      {'label': 'Files', 'icon': Icons.attach_file_rounded},
    ];

    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(14),
      ),
      padding: const EdgeInsets.all(3),
      child: Row(
        children: List.generate(tabs.length, (index) {
          final tab = tabs[index];
          final isSelected = _activeTabIndex == index;
          return Expanded(
            child: GestureDetector(
              onTap: () {
                setState(() => _activeTabIndex = index);
                if (index == 1) {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ActivitiesScreen(leadId: _lead.id, leadName: _lead.name),
                    ),
                  );
                } else if (index == 2) {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => const QuotationsListScreen(),
                    ),
                  );
                }
              },
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                decoration: BoxDecoration(
                  color: isSelected ? const Color(0xFFE5252A) : Colors.transparent,
                  borderRadius: BorderRadius.circular(11),
                  boxShadow: isSelected
                      ? [
                          BoxShadow(
                            color: const Color(0xFFE5252A).withValues(alpha: 0.3),
                            blurRadius: 6,
                            offset: const Offset(0, 2),
                          ),
                        ]
                      : null,
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      tab['icon'] as IconData,
                      size: 15,
                      color: isSelected ? Colors.white : const Color(0xFF64748B),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      tab['label'] as String,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
                        color: isSelected ? Colors.white : const Color(0xFF64748B),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  // ==========================================
  // BASIC INFORMATION SECTION
  // ==========================================
  Widget _buildBasicInformationSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section Header
        const Row(
          children: [
            Icon(Icons.shield_outlined, size: 17, color: Color(0xFF162A45)),
            SizedBox(width: 6),
            Text(
              'Basic Information',
              style: TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w800,
                color: Color(0xFF0F172A),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),

        // Information Card
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.03),
                blurRadius: 10,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          child: Column(
            children: [
              _buildInfoRow(
                icon: Icons.person_pin_rounded,
                label: 'Contact Person',
                value: _lead.name,
              ),
              const Divider(height: 20, color: Color(0xFFF1F5F9)),
              _buildInfoRow(
                icon: Icons.phone_outlined,
                label: 'Phone',
                value: _lead.phone,
                actionIcon: Icons.phone_rounded,
                onActionTap: () => _callNumber(_lead.phone),
                isPhone: true,
              ),
              const Divider(height: 20, color: Color(0xFFF1F5F9)),
              _buildInfoRow(
                icon: Icons.mail_outline_rounded,
                label: 'Email',
                value: _lead.email ?? 'arun@techsolutions.com',
                actionIcon: Icons.mail_rounded,
                onActionTap: () => _sendEmail(_lead.email),
                isEmail: true,
              ),
              const Divider(height: 20, color: Color(0xFFF1F5F9)),
              _buildInfoRow(
                icon: Icons.info_outline_rounded,
                label: 'Source',
                value: _lead.source ?? 'Website',
              ),
              const Divider(height: 20, color: Color(0xFFF1F5F9)),
              _buildInfoRow(
                icon: Icons.person_outline_rounded,
                label: 'Assigned To',
                value: _lead.assignedToName ?? 'Chandra Mohan',
              ),
              const Divider(height: 20, color: Color(0xFFF1F5F9)),
              _buildInfoRow(
                icon: Icons.calendar_today_rounded,
                label: 'Created On',
                value: _formatCreatedDate(_lead.createdAt),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildInfoRow({
    required IconData icon,
    required String label,
    required String value,
    IconData? actionIcon,
    VoidCallback? onActionTap,
    bool isPhone = false,
    bool isEmail = false,
  }) {
    return Row(
      children: [
        Icon(icon, size: 18, color: const Color(0xFF64748B)),
        const SizedBox(width: 10),
        SizedBox(
          width: 95,
          child: Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: Color(0xFF64748B),
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: (isPhone || isEmail) ? const Color(0xFF2563EB) : const Color(0xFF0F172A),
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
        if (actionIcon != null)
          GestureDetector(
            onTap: onActionTap,
            child: Container(
              padding: const EdgeInsets.all(4),
              child: Icon(
                actionIcon,
                size: 16,
                color: const Color(0xFF2563EB),
              ),
            ),
          ),
      ],
    );
  }

  // ==========================================
  // LEAD STATUS SECTION
  // ==========================================
  Widget _buildLeadStatusSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section Header
        const Row(
          children: [
            Icon(Icons.bar_chart_rounded, size: 18, color: Color(0xFF162A45)),
            SizedBox(width: 6),
            Text(
              'Lead Status',
              style: TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w800,
                color: Color(0xFF0F172A),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),

        // Dropdown Container
        GestureDetector(
          onTap: _updateLeadStatus,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.03),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Row(
              children: [
                const Icon(Icons.flag_rounded, size: 18, color: Color(0xFFE5252A)),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    _lead.status.replaceAll('_', ' '),
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF0F172A),
                    ),
                  ),
                ),
                const Icon(Icons.keyboard_arrow_down_rounded, size: 20, color: Color(0xFF64748B)),
              ],
            ),
          ),
        ),

        const SizedBox(height: 12),

        // Action Buttons Row: 'Update Status' & 'Close Deal WON'
        Row(
          children: [
            Expanded(
              child: SizedBox(
                height: 48,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFE5252A),
                    foregroundColor: Colors.white,
                    elevation: 3,
                    shadowColor: const Color(0xFFE5252A).withValues(alpha: 0.35),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(24),
                    ),
                  ),
                  onPressed: _updateLeadStatus,
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.sync_rounded, size: 18),
                      SizedBox(width: 6),
                      Text(
                        'Update Status',
                        style: TextStyle(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.2,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            if (_lead.status.toUpperCase() != 'WON' && _lead.status.toUpperCase() != 'CONVERTED') ...[
              const SizedBox(width: 10),
              SizedBox(
                height: 48,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF10B981),
                    foregroundColor: Colors.white,
                    elevation: 3,
                    shadowColor: const Color(0xFF10B981).withValues(alpha: 0.35),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(24),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                  ),
                  onPressed: _markDealWon,
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.emoji_events_rounded, size: 18),
                      SizedBox(width: 6),
                      Text(
                        'Mark WON',
                        style: TextStyle(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.2,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }
}
