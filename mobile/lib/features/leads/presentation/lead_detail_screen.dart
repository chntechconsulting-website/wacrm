import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/network/api_client.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../core/utils/date_formatter.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/lead_model.dart';
import '../providers/leads_provider.dart';
import 'lead_assign_dialog.dart';
import 'lead_create_edit_screen.dart';
import 'lead_status_dialog.dart';
import '../../activities/presentation/activities_screen.dart';
import '../../field_visits/presentation/field_visit_form_screen.dart';
import '../../calls/data/calls_repository.dart';
import '../../whatsapp/data/whatsapp_repository.dart';

class LeadDetailScreen extends StatefulWidget {
  final LeadModel lead;

  const LeadDetailScreen({super.key, required this.lead});

  @override
  State<LeadDetailScreen> createState() => _LeadDetailScreenState();
}

class _LeadDetailScreenState extends State<LeadDetailScreen> {
  late LeadModel _lead;
  bool _isDownloading = false;

  @override
  void initState() {
    super.initState();
    _lead = widget.lead;
  }

  void _callNumber(String phone) {
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d+]'), '');
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Calling $cleanPhone',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              const Text(
                'Choose how you want to connect with this lead:',
                style: TextStyle(fontSize: 13, color: AppColors.textMuted),
              ),
              const SizedBox(height: 16),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.phone_in_talk_rounded, color: AppColors.primary),
                ),
                title: const Text('Dial via Mobile SIM', style: TextStyle(fontWeight: FontWeight.w600)),
                subtitle: const Text('Dial using device phone app & optionally log call'),
                onTap: () async {
                  Navigator.pop(ctx);
                  final uri = Uri.parse('tel:$cleanPhone');
                  if (await canLaunchUrl(uri)) {
                    await launchUrl(uri);
                    if (mounted) {
                      _showManualCallLogDialog(cleanPhone);
                    }
                  }
                },
              ),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.accent.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.cloud_queue_rounded, color: AppColors.accent),
                ),
                title: const Text('Cloud Click-to-Call Bridge', style: TextStyle(fontWeight: FontWeight.w600)),
                subtitle: const Text('Trigger automatic cloud IVR callback bridge'),
                onTap: () async {
                  Navigator.pop(ctx);
                  try {
                    await CallsRepository().initiateIvrCall(phone: cleanPhone, leadId: _lead.id);
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Cloud IVR call initiated successfully.'),
                          backgroundColor: AppColors.success,
                        ),
                      );
                    }
                  } catch (e) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('IVR Error: ${e.toString().replaceAll('ApiException: ', '')}'),
                          backgroundColor: AppColors.danger,
                        ),
                      );
                    }
                  }
                },
              ),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.edit_note_rounded, color: AppColors.warning),
                ),
                title: const Text('Log Completed Call to CRM', style: TextStyle(fontWeight: FontWeight.w600)),
                subtitle: const Text('Record notes, status, and duration for this call'),
                onTap: () {
                  Navigator.pop(ctx);
                  _showManualCallLogDialog(cleanPhone);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showManualCallLogDialog(String phone) {
    final notesController = TextEditingController();
    final durationController = TextEditingController(text: '60');
    String selectedStatus = 'COMPLETED';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Log Call to CRM', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Phone: $phone', style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.textMain)),
                const SizedBox(height: 12),
                const Text('Call Status:', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                DropdownButton<String>(
                  value: selectedStatus,
                  isExpanded: true,
                  items: const [
                    DropdownMenuItem(value: 'COMPLETED', child: Text('Completed')),
                    DropdownMenuItem(value: 'MISSED', child: Text('Missed / No Answer')),
                    DropdownMenuItem(value: 'BUSY', child: Text('Busy')),
                    DropdownMenuItem(value: 'FAILED', child: Text('Failed')),
                  ],
                  onChanged: (val) {
                    if (val != null) setDialogState(() => selectedStatus = val);
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: durationController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Duration (Seconds)',
                    hintText: 'e.g. 120',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: notesController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Discussion Notes',
                    hintText: 'e.g. Discussed pricing quotation',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                final duration = int.tryParse(durationController.text.trim()) ?? 0;
                final notes = notesController.text.trim();
                Navigator.pop(ctx);
                try {
                  await CallsRepository().logManualCall(
                    customerPhone: phone,
                    callStatus: selectedStatus,
                    durationSeconds: duration,
                    leadId: _lead.id,
                    notes: notes.isNotEmpty ? notes : null,
                  );
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Call successfully logged to CRM.'),
                        backgroundColor: AppColors.success,
                      ),
                    );
                  }
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Failed to log call: ${e.toString().replaceAll('ApiException: ', '')}'),
                        backgroundColor: AppColors.danger,
                      ),
                    );
                  }
                }
              },
              child: const Text('Save Log'),
            ),
          ],
        ),
      ),
    );
  }

  void _openWhatsApp(String phone) {
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d]'), '');
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'WhatsApp ($cleanPhone)',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              const Text(
                'Select messaging method:',
                style: TextStyle(fontSize: 13, color: AppColors.textMuted),
              ),
              const SizedBox(height: 16),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFF25D366).withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.chat_bubble_rounded, color: Color(0xFF25D366)),
                ),
                title: const Text('Open WhatsApp App', style: TextStyle(fontWeight: FontWeight.w600)),
                subtitle: const Text('Launch WhatsApp with customer conversation directly'),
                onTap: () async {
                  Navigator.pop(ctx);
                  final uri = Uri.parse('https://wa.me/$cleanPhone');
                  if (await canLaunchUrl(uri)) {
                    await launchUrl(uri, mode: LaunchMode.externalApplication);
                  }
                },
              ),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.send_rounded, color: AppColors.primary),
                ),
                title: const Text('Send via WA!CRM API', style: TextStyle(fontWeight: FontWeight.w600)),
                subtitle: const Text('Send official template or outbound CRM WhatsApp message'),
                onTap: () {
                  Navigator.pop(ctx);
                  _showSendWhatsAppDialog(cleanPhone);
                },
              ),
            ],
          ),
        ),
      ),
    );
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
                      backgroundColor: AppColors.success,
                    ),
                  );
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('WhatsApp error: ${e.toString().replaceAll('ApiException: ', '')}'),
                      backgroundColor: AppColors.danger,
                    ),
                  );
                }
              }
            },
            child: const Text('Send Message'),
          ),
        ],
      ),
    );
  }

  void _sendEmail(String email) async {
    final uri = Uri.parse('mailto:$email');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  void _downloadQuotation() async {
    setState(() => _isDownloading = true);
    try {
      final client = ApiClient();
      final bytes = await client.downloadBytes(ApiEndpoints.downloadQuotation(_lead.id));

      if (mounted) {
        PingoPopupDialog.show(
          context,
          title: 'Quotation Downloaded',
          subtitle: 'Document for ${_lead.name} saved (${bytes.lengthInBytes} bytes).',
          badge: 'DOWNLOADED',
          pose: PingoPoses.celebrate,
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to download: ${e.toString()}'),
            backgroundColor: AppColors.danger,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isDownloading = false);
      }
    }
  }

  void _deleteLead() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Lead', style: TextStyle(fontWeight: FontWeight.w700)),
        content: Text('Are you sure you want to delete lead "${_lead.name}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      final success = await context.read<LeadsProvider>().deleteLead(_lead.id);
      if (success && mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lead "${_lead.name}" deleted')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;

    // Keep lead in sync with provider
    final currentFromProvider = context.watch<LeadsProvider>().leads.firstWhere(
          (l) => l.id == _lead.id,
          orElse: () => _lead,
        );
    _lead = currentFromProvider;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Lead Details'),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit_outlined),
            tooltip: 'Edit Lead',
            onPressed: () async {
              final updated = await Navigator.push<bool>(
                context,
                MaterialPageRoute(
                  builder: (_) => LeadCreateEditScreen(leadToEdit: _lead),
                ),
              );
              if (updated == true) {
                setState(() {});
              }
            },
          ),
          if (user?.canDeleteLeads == true)
            IconButton(
              icon: const Icon(Icons.delete_outline_rounded, color: AppColors.danger),
              tooltip: 'Delete Lead',
              onPressed: _deleteLead,
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Top Lead Info Card
            WacrmCard(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      CircleAvatar(
                        radius: 26,
                        backgroundColor: AppColors.primaryLight,
                        child: Text(
                          _lead.name.isNotEmpty ? _lead.name[0].toUpperCase() : 'L',
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                            color: AppColors.primary,
                          ),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _lead.name,
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                                color: AppColors.textMain,
                              ),
                            ),
                            if (_lead.company != null && _lead.company!.isNotEmpty) ...[
                              const SizedBox(height: 2),
                              Text(
                                _lead.company!,
                                style: const TextStyle(
                                  fontSize: 14,
                                  color: AppColors.textMuted,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              runSpacing: 6,
                              children: [
                                WacrmBadge.status(_lead.status),
                                if (_lead.priority != null) WacrmBadge.priority(_lead.priority!),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Quick Actions Bar
            Row(
              children: [
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.phone_in_talk_rounded,
                    label: 'Call',
                    color: AppColors.primary,
                    onTap: () => _callNumber(_lead.phone),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.chat_bubble_outline_rounded,
                    label: 'WhatsApp',
                    color: const Color(0xFF25D366),
                    onTap: () => _openWhatsApp(_lead.phone),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.add_location_alt_rounded,
                    label: 'Field Visit',
                    color: const Color(0xFF0284C7),
                    onTap: () async {
                      final recorded = await Navigator.push<bool>(
                        context,
                        MaterialPageRoute(
                          builder: (_) => FieldVisitFormScreen(preselectedLead: _lead),
                        ),
                      );
                      if (!mounted) return;
                      if (recorded == true) {
                        context.read<LeadsProvider>().fetchLeads();
                      }
                    },
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.history_rounded,
                    label: 'Activities',
                    color: const Color(0xFF8B5CF6),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ActivitiesScreen(leadId: _lead.id, leadName: _lead.name),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.sync_alt_rounded,
                    label: 'Update Status',
                    color: AppColors.accent,
                    onTap: () => LeadStatusDialog.show(context, _lead),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.person_add_alt_rounded,
                    label: 'Assign Lead',
                    color: AppColors.warning,
                    onTap: () => LeadAssignDialog.show(context, _lead),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Contact & Details
            WacrmCard(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Contact & Sourcing',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textMain,
                    ),
                  ),
                  const Divider(height: 22),
                  _buildDetailRow('Phone Number', _lead.phone, Icons.phone_outlined, onTap: () => _callNumber(_lead.phone)),
                  if (_lead.email != null && _lead.email!.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    _buildDetailRow('Email Address', _lead.email!, Icons.mail_outline_rounded, onTap: () => _sendEmail(_lead.email!)),
                  ],
                  const SizedBox(height: 12),
                  _buildDetailRow('Lead Source', _lead.source ?? 'Manual', Icons.share_location_outlined),
                  const SizedBox(height: 12),
                  _buildDetailRow('Assigned To', _lead.assignedToName ?? 'Unassigned', Icons.account_circle_outlined),
                  if (_lead.createdAt != null) ...[
                    const SizedBox(height: 12),
                    _buildDetailRow('Created On', DateFormatter.formatDateTime(_lead.createdAt), Icons.calendar_today_outlined),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Requirements & Notes
            if (_lead.requirement != null && _lead.requirement!.isNotEmpty) ...[
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Requirement & Notes',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                    const Divider(height: 22),
                    Text(
                      _lead.requirement!,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textMain,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],

            // Quotations & Billing Integration
            if (_lead.quotationNumber != null || _lead.quotationAmount != null) ...[
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Quotation & Billing',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textMain,
                          ),
                        ),
                        if (_lead.quotationStatus != null)
                          WacrmBadge.status(_lead.quotationStatus!),
                      ],
                    ),
                    const Divider(height: 22),
                    if (_lead.quotationNumber != null)
                      _buildDetailRow('Quote Number', _lead.quotationNumber!, Icons.description_outlined),
                    if (_lead.quotationAmount != null) ...[
                      const SizedBox(height: 12),
                      _buildDetailRow(
                        'Total Amount',
                        CurrencyFormatter.formatInr(_lead.quotationAmount),
                        Icons.payments_outlined,
                      ),
                    ],
                    const SizedBox(height: 16),
                    WacrmButton(
                      text: 'Download Quotation PDF',
                      icon: Icons.picture_as_pdf_outlined,
                      type: WacrmButtonType.outline,
                      isLoading: _isDownloading,
                      onPressed: _downloadQuotation,
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Column(
          children: [
            Icon(icon, size: 20, color: color),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value, IconData icon, {VoidCallback? onTap}) {
    return InkWell(
      onTap: onTap,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: AppColors.textMuted),
          const SizedBox(width: 10),
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.textMuted,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 13,
                color: onTap != null ? AppColors.primary : AppColors.textMain,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
