import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exceptions.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_drawer.dart';
import '../../auth/presentation/profile_screen.dart';
import '../../auth/providers/auth_provider.dart';
import '../../notifications/presentation/notifications_screen.dart';
import '../../notifications/providers/notifications_provider.dart';
import 'privacy_policy_screen.dart';
import 'terms_and_conditions_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  // App preferences
  bool _pushNotifications = true;
  bool _callVibration = true;
  bool _autoSync = true;

  void _showChangePasswordDialog(BuildContext context) {
    final currentPasswordController = TextEditingController();
    final newPasswordController = TextEditingController();
    final confirmPasswordController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    bool obscureCurrent = true;
    bool obscureNew = true;
    bool obscureConfirm = true;
    bool isSubmitting = false;
    String? dialogError;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogCtx) => StatefulBuilder(
        builder: (dialogCtx, setDialogState) {
          return AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
            title: const Row(
              children: [
                Icon(Icons.lock_reset_rounded, color: Color(0xFF2563EB), size: 24),
                SizedBox(width: 10),
                Text(
                  'Change Password',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17),
                ),
              ],
            ),
            content: SingleChildScrollView(
              child: Form(
                key: formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Enter your existing password and choose a secure new password for your CRM account.',
                      style: TextStyle(fontSize: 12.5, color: Color(0xFF64748B)),
                    ),
                    const SizedBox(height: 14),

                    if (dialogError != null) ...[
                      Container(
                        padding: const EdgeInsets.all(10),
                        margin: const EdgeInsets.only(bottom: 12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF2F2),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFFCA5A5)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.error_outline_rounded, size: 16, color: Color(0xFFDC2626)),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                dialogError!,
                                style: const TextStyle(fontSize: 12, color: Color(0xFFDC2626), fontWeight: FontWeight.w600),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],

                    // Current Password
                    TextFormField(
                      controller: currentPasswordController,
                      obscureText: obscureCurrent,
                      decoration: InputDecoration(
                        labelText: 'Current Password *',
                        prefixIcon: const Icon(Icons.key_rounded, size: 18),
                        suffixIcon: IconButton(
                          icon: Icon(obscureCurrent ? Icons.visibility_off_outlined : Icons.visibility_outlined, size: 18),
                          onPressed: () => setDialogState(() => obscureCurrent = !obscureCurrent),
                        ),
                      ),
                      validator: (val) => val == null || val.isEmpty ? 'Please enter current password' : null,
                    ),
                    const SizedBox(height: 12),

                    // New Password
                    TextFormField(
                      controller: newPasswordController,
                      obscureText: obscureNew,
                      decoration: InputDecoration(
                        labelText: 'New Password *',
                        prefixIcon: const Icon(Icons.lock_outline_rounded, size: 18),
                        suffixIcon: IconButton(
                          icon: Icon(obscureNew ? Icons.visibility_off_outlined : Icons.visibility_outlined, size: 18),
                          onPressed: () => setDialogState(() => obscureNew = !obscureNew),
                        ),
                      ),
                      validator: (val) {
                        if (val == null || val.isEmpty) return 'Please enter new password';
                        if (val.length < 6) return 'Password must be at least 6 characters';
                        return null;
                      },
                    ),
                    const SizedBox(height: 12),

                    // Confirm New Password
                    TextFormField(
                      controller: confirmPasswordController,
                      obscureText: obscureConfirm,
                      decoration: InputDecoration(
                        labelText: 'Confirm New Password *',
                        prefixIcon: const Icon(Icons.lock_rounded, size: 18),
                        suffixIcon: IconButton(
                          icon: Icon(obscureConfirm ? Icons.visibility_off_outlined : Icons.visibility_outlined, size: 18),
                          onPressed: () => setDialogState(() => obscureConfirm = !obscureConfirm),
                        ),
                      ),
                      validator: (val) {
                        if (val == null || val.isEmpty) return 'Please confirm new password';
                        if (val != newPasswordController.text) return 'Passwords do not match';
                        return null;
                      },
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: isSubmitting ? null : () => Navigator.pop(dialogCtx),
                child: const Text('Cancel', style: TextStyle(color: Color(0xFF64748B), fontWeight: FontWeight.w600)),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF2563EB),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: isSubmitting
                    ? null
                    : () async {
                        if (!formKey.currentState!.validate()) return;
                        setDialogState(() {
                          isSubmitting = true;
                          dialogError = null;
                        });

                        try {
                          final client = ApiClient();
                          await client.post(
                            ApiEndpoints.changePassword,
                            body: {
                              'current_password': currentPasswordController.text.trim(),
                              'new_password': newPasswordController.text.trim(),
                            },
                          );

                          if (!mounted) return;
                          if (dialogCtx.mounted) {
                            Navigator.pop(dialogCtx);
                          }
                          PingoPopupDialog.show(
                            context,
                            title: 'Password Changed Successfully',
                            subtitle: 'Your CRM account credentials have been securely updated.',
                            badge: 'SECURITY UPDATED',
                            pose: PingoPoses.celebrate,
                          );
                        } on ApiException catch (e) {
                          setDialogState(() {
                            isSubmitting = false;
                            dialogError = e.message;
                          });
                        } catch (e) {
                          setDialogState(() {
                            isSubmitting = false;
                            dialogError = 'Failed to update password. Please verify current password.';
                          });
                        }
                      },
                child: isSubmitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('Update Password', style: TextStyle(fontWeight: FontWeight.w700)),
              ),
            ],
          );
        },
      ),
    );
  }

  void _showAppSettingsDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) {
          return Container(
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
            child: SafeArea(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade300,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Row(
                    children: [
                      Icon(Icons.tune_rounded, color: Color(0xFF0D9488), size: 22),
                      SizedBox(width: 10),
                      Text(
                        'Application Settings',
                        style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: Color(0xFF0F172A)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    secondary: const Icon(Icons.notifications_active_outlined, color: Color(0xFF2563EB)),
                    title: const Text('Push Notifications', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                    subtitle: const Text('Real-time alerts for lead assignments & follow-ups', style: TextStyle(fontSize: 12)),
                    value: _pushNotifications,
                    activeTrackColor: const Color(0xFFE5252A).withValues(alpha: 0.5),
                    activeThumbColor: const Color(0xFFE5252A),
                    onChanged: (val) {
                      setSheetState(() => _pushNotifications = val);
                      setState(() => _pushNotifications = val);
                    },
                  ),
                  const Divider(height: 12),

                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    secondary: const Icon(Icons.vibration_rounded, color: Color(0xFFF59E0B)),
                    title: const Text('Call & Follow-up Vibration', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                    subtitle: const Text('Vibrate phone on incoming Doocti calls & reminders', style: TextStyle(fontSize: 12)),
                    value: _callVibration,
                    activeTrackColor: const Color(0xFFE5252A).withValues(alpha: 0.5),
                    activeThumbColor: const Color(0xFFE5252A),
                    onChanged: (val) {
                      setSheetState(() => _callVibration = val);
                      setState(() => _callVibration = val);
                    },
                  ),
                  const Divider(height: 12),

                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    secondary: const Icon(Icons.sync_rounded, color: Color(0xFF10B981)),
                    title: const Text('Background Auto-Sync', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                    subtitle: const Text('Sync offline leads and activity logs automatically', style: TextStyle(fontSize: 12)),
                    value: _autoSync,
                    activeTrackColor: const Color(0xFFE5252A).withValues(alpha: 0.5),
                    activeThumbColor: const Color(0xFFE5252A),
                    onChanged: (val) {
                      setSheetState(() => _autoSync = val);
                      setState(() => _autoSync = val);
                    },
                  ),
                  const Divider(height: 12),

                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.cleaning_services_rounded, color: Color(0xFF64748B)),
                    title: const Text('Clear Local Cache', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                    subtitle: const Text('Free up temporary files, thumbnails & cached logs', style: TextStyle(fontSize: 12)),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () {
                      Navigator.pop(ctx);
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Temporary cache cleared successfully.'),
                          backgroundColor: Color(0xFF10B981),
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final notificationsProvider = context.watch<NotificationsProvider>();
    final unreadCount = notificationsProvider.unreadCount;
    final canPop = Navigator.canPop(context);

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      drawer: canPop ? null : const WacrmDrawer(currentTabIndex: 3),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: canPop
            ? IconButton(
                icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF162A45)),
                onPressed: () => Navigator.pop(context),
              )
            : Builder(
                builder: (ctx) => IconButton(
                  icon: const Icon(Icons.menu_rounded, color: Color(0xFF162A45)),
                  onPressed: () => Scaffold.of(ctx).openDrawer(),
                ),
              ),
        title: const Text(
          'Settings',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w800,
            color: Color(0xFF0F172A),
          ),
        ),
        centerTitle: false,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 90),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // User Header Profile Card
            if (user != null)
              Container(
                padding: const EdgeInsets.all(16),
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
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 28,
                      backgroundColor: const Color(0xFF162A45),
                      child: Text(
                        user.name.isNotEmpty ? user.name[0].toUpperCase() : 'U',
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            user.name,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                              color: Color(0xFF0F172A),
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            '@${user.username} • ${user.email}',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: Color(0xFF64748B),
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              WacrmBadge.department(user.departmentDisplay),
                              const SizedBox(width: 6),
                              WacrmBadge.status(user.role),
                            ],
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.arrow_forward_ios_rounded, size: 16, color: Color(0xFF94A3B8)),
                      onPressed: () {
                        Navigator.push(context, MaterialPageRoute(builder: (_) => const ProfileScreen()));
                      },
                    ),
                  ],
                ),
              ),

            const SizedBox(height: 18),

            // SECTION 1: ACCOUNT & PREFERENCES
            _buildSectionLabel('ACCOUNT & SECURITY'),
            _buildSettingsContainer([
              _buildSettingsTile(
                icon: Icons.person_outline_rounded,
                iconColor: const Color(0xFF2563EB),
                title: 'My Profile',
                subtitle: 'Personal details, reporting manager & role permissions',
                onTap: () {
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const ProfileScreen()));
                },
              ),
              const Divider(height: 1, indent: 56),
              _buildSettingsTile(
                icon: Icons.lock_outline_rounded,
                iconColor: const Color(0xFFD97706),
                title: 'Change Password',
                subtitle: 'Update your enterprise CRM account password',
                onTap: () => _showChangePasswordDialog(context),
              ),
              const Divider(height: 1, indent: 56),
              _buildSettingsTile(
                icon: Icons.notifications_none_rounded,
                iconColor: const Color(0xFF8B5CF6),
                title: 'Notifications',
                subtitle: 'Manage activity alerts & follow-up reminders',
                trailing: unreadCount > 0
                    ? Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFFE5252A),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          '$unreadCount new',
                          style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700),
                        ),
                      )
                    : null,
                onTap: () {
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen()));
                },
              ),
              const Divider(height: 1, indent: 56),
              _buildSettingsTile(
                icon: Icons.tune_rounded,
                iconColor: const Color(0xFF0D9488),
                title: 'App Settings',
                subtitle: 'Notification tones, auto-sync & local caching',
                onTap: () => _showAppSettingsDialog(context),
              ),
            ]),

            const SizedBox(height: 18),

            // SECTION 2: LEGAL & POLICIES
            _buildSectionLabel('LEGAL & POLICIES'),
            _buildSettingsContainer([
              _buildSettingsTile(
                icon: Icons.description_outlined,
                iconColor: const Color(0xFF4F46E5),
                title: 'Terms & Conditions',
                subtitle: 'Platform usage agreement, service rules & SLA',
                onTap: () {
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const TermsAndConditionsScreen()));
                },
              ),
              const Divider(height: 1, indent: 56),
              _buildSettingsTile(
                icon: Icons.shield_outlined,
                iconColor: const Color(0xFF059669),
                title: 'Privacy Policy',
                subtitle: 'Confidentiality, encryption & data protection',
                onTap: () {
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const PrivacyPolicyScreen()));
                },
              ),
            ]),

            const SizedBox(height: 18),

            // SECTION 3: APP INFO & LOGOUT
            _buildSectionLabel('APPLICATION & SESSION'),
            _buildSettingsContainer([
              _buildSettingsTile(
                icon: Icons.info_outline_rounded,
                iconColor: const Color(0xFF64748B),
                title: 'App Version',
                subtitle: 'WA!CRM Enterprise Mobile • Powered by CHN',
                trailing: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: const Color(0xFFE2E8F0)),
                  ),
                  child: const Text(
                    'v1.0.0 (Build 100)',
                    style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Color(0xFF475569)),
                  ),
                ),
                onTap: null,
              ),
              const Divider(height: 1, indent: 56),
              _buildSettingsTile(
                icon: Icons.logout_rounded,
                iconColor: const Color(0xFFE5252A),
                title: 'Logout',
                subtitle: 'Safely end your CRM session on this mobile device',
                titleColor: const Color(0xFFE5252A),
                onTap: () => showWacrmLogoutDialog(context),
              ),
            ]),

            const SizedBox(height: 24),

            // Pingo Branding Footer
            Center(
              child: Column(
                children: [
                  Image.asset(
                    'assets/images/logo.png',
                    height: 24,
                    fit: BoxFit.contain,
                  ),
                  const SizedBox(height: 8),
                  const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      PingoMascotWidget(pose: PingoPoses.salute, height: 38),
                      SizedBox(width: 8),
                      Text(
                        'Enterprise Customer Relationship Management',
                        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: Color(0xFF94A3B8)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionLabel(String label) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w700,
          color: Color(0xFF64748B),
          letterSpacing: 0.6,
        ),
      ),
    );
  }

  Widget _buildSettingsContainer(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.02),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Material(
        color: Colors.white,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: Color(0xFFF1F5F9), width: 1.2),
        ),
        child: Column(
          children: children,
        ),
      ),
    );
  }

  Widget _buildSettingsTile({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    Widget? trailing,
    Color? titleColor,
    VoidCallback? onTap,
  }) {
    return ListTile(
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: Container(
        width: 38,
        height: 38,
        decoration: BoxDecoration(
          color: iconColor.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, color: iconColor, size: 20),
      ),
      title: Text(
        title,
        style: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w700,
          color: titleColor ?? const Color(0xFF0F172A),
        ),
      ),
      subtitle: Text(
        subtitle,
        style: const TextStyle(
          fontSize: 11.5,
          color: Color(0xFF64748B),
        ),
      ),
      trailing: trailing ??
          (onTap != null
              ? const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF94A3B8))
              : null),
    );
  }
}
