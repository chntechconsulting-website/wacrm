import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/network/api_exceptions.dart';
import '../../../core/services/automatic_call_sync_service.dart';
import '../../../core/services/device_call_log_sync_service.dart';
import '../../../core/services/mobile_sim_call_service.dart';
import '../../../core/services/office_sim_service.dart';
import '../../../core/services/pending_call_sync_queue.dart';
import '../../../core/utils/date_formatter.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../auth/providers/auth_provider.dart';
import '../../calls/providers/calls_provider.dart';

/// Lets an employee register the SIM card that belongs to the company.
///
/// The selected SIM is identified by Android's subscription id and/or phone
/// account, never by slot alone. When the SIM is replaced or its identity
/// changes, synchronization stops until the employee re-verifies here.
class OfficeSimSetupScreen extends StatefulWidget {
  const OfficeSimSetupScreen({super.key});

  @override
  State<OfficeSimSetupScreen> createState() => _OfficeSimSetupScreenState();
}

class _OfficeSimSetupScreenState extends State<OfficeSimSetupScreen>
    with WidgetsBindingObserver {
  bool _loading = true;
  bool _saving = false;
  bool _syncBusy = false;
  String? _error;
  String? _notice;
  MobileSimPermissionStatus? _permission;
  List<SimAccount> _sims = const [];
  OfficeSimMapping? _mapping;
  int? _selectedSubscriptionId;
  int _pendingSyncCount = 0;
  bool? _ignoringBatteryOptimizations;

  bool get _isAndroid => !kIsWeb && Platform.isAndroid;

  String get _employeeKey =>
      context.read<AuthProvider>().currentUser?.id.toString() ?? 'default';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refreshAutomaticStatus();
    }
  }

  Future<void> _refreshAutomaticStatus() async {
    if (!_isAndroid || !mounted) return;
    final employeeKey = _employeeKey;
    final pending = await PendingCallSyncQueue.pendingCount(employeeKey);
    final ignoringBattery =
        await MobileSimCallService.isIgnoringBatteryOptimizations();
    if (!mounted) return;
    setState(() {
      _pendingSyncCount = pending;
      _ignoringBatteryOptimizations = ignoringBattery;
    });
  }

  Future<void> _load({bool forceMapping = false}) async {
    if (!_isAndroid) {
      setState(() {
        _loading = false;
        _error =
            'Office SIM configuration is available in the Android app only.';
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    final employeeKey = _employeeKey;
    try {
      final permission = await MobileSimCallService.permissionStatus();
      var sims = const <SimAccount>[];
      if (permission.readPhoneState) {
        sims = await MobileSimCallService.getSimAccounts();
      }
      final mapping = await OfficeSimService.fetch(force: forceMapping);
      final pending = await PendingCallSyncQueue.pendingCount(employeeKey);
      final ignoringBattery =
          await MobileSimCallService.isIgnoringBatteryOptimizations();
      int? selected = mapping?.subscriptionId;
      if (selected == null && mapping != null) {
        final matched = OfficeSimService.matchSim(mapping, sims);
        selected = matched?.subscriptionId;
      }
      if (!mounted) return;
      setState(() {
        _permission = permission;
        _sims = sims;
        _mapping = mapping;
        _selectedSubscriptionId = selected;
        _pendingSyncCount = pending;
        _ignoringBatteryOptimizations = ignoringBattery;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Unable to read SIM information: $error';
      });
    }
  }

  Future<void> _requestPermission() async {
    try {
      final status = await MobileSimCallService.requestPermissions();
      if (!mounted) return;
      setState(() => _permission = status);
      if (status.readPhoneState) {
        await _load(forceMapping: true);
      } else {
        await MobileSimCallService.openAppSettings();
      }
    } on PlatformException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message ?? 'Phone permission was denied.');
    }
  }

  Future<void> _save() async {
    final selected = _selectedSim();
    if (selected == null) {
      setState(() => _notice = 'Select the SIM that belongs to your office.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
      _notice = null;
    });
    try {
      final mapping = await OfficeSimService.save(selected);
      if (!mounted) return;
      setState(() {
        _mapping = mapping;
        _saving = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Office SIM verified. Enable call-log sync to import only new calls.',
          ),
          backgroundColor: AppColors.success,
        ),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = error.message;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'Unable to save the Office SIM: $error';
      });
    }
  }

  Future<void> _clear() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove Office SIM?'),
        content: const Text(
          'Automatic call synchronization will be paused on this device until '
          'an Office SIM is registered again.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _saving = true);
    await OfficeSimService.clear();
    if (!mounted) return;
    setState(() {
      _saving = false;
      _mapping = null;
      _selectedSubscriptionId = null;
    });
  }

  /// Enables or resumes incremental call-log sync.
  ///
  /// A baseline is captured *before* the backend activates the session, so
  /// every call already present in Android's call log is excluded. Resuming
  /// after a pause behaves identically: calls made while paused are skipped.
  Future<void> _startSync({required bool resume}) async {
    final mapping = _mapping;
    if (mapping == null) {
      setState(() => _notice = 'Save your Office SIM before enabling sync.');
      return;
    }
    setState(() {
      _syncBusy = true;
      _error = null;
      _notice = null;
    });
    try {
      var permission = await MobileSimCallService.permissionStatus();
      if (!permission.readCallLog) {
        permission = await MobileSimCallService.requestPermissions();
      }
      if (!permission.readCallLog) {
        if (!mounted) return;
        setState(() {
          _permission = permission;
          _syncBusy = false;
          _notice =
              'Call-log access is required to synchronize calls. Allow it in '
              'Android settings, then try again.';
        });
        await MobileSimCallService.openAppSettings();
        return;
      }

      final baseline = await DeviceCallLogSyncService.captureBaseline();
      if (baseline == null) {
        if (!mounted) return;
        setState(() {
          _syncBusy = false;
          _error =
              'Unable to read the Android call log, so a safe sync baseline '
              'could not be created. No calls were imported.';
        });
        return;
      }

      final updated = await OfficeSimService.activateSync(
        baselineDateMs: baseline.dateMillis,
        baselineId: baseline.callLogId,
        resume: resume,
      );
      if (!mounted) return;
      setState(() {
        _mapping = updated;
        _syncBusy = false;
        _permission = permission;
      });
      await AutomaticCallSyncService.scheduleOneOffSync();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            resume
                ? 'Sync resumed. Calls made while paused will not be imported.'
                : 'Sync enabled. Only calls received after now will be imported.',
          ),
          backgroundColor: AppColors.success,
        ),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _syncBusy = false;
        _error = error.message;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _syncBusy = false;
        _error = 'Unable to enable call-log sync: $error';
      });
    }
  }

  /// Manual fallback that uses the exact same queue and upload pipeline as
  /// the native background worker. It also retries permanently-failed queue
  /// entries that automatic passes leave alone.
  Future<void> _syncNow() async {
    if (_syncBusy) return;
    final callsProvider = context.read<CallsProvider>();
    setState(() {
      _syncBusy = true;
      _error = null;
      _notice = null;
    });
    try {
      var permission = await MobileSimCallService.permissionStatus();
      if (!permission.readCallLog) {
        permission = await MobileSimCallService.requestPermissions();
      }
      if (!permission.readCallLog) {
        if (!mounted) return;
        setState(() {
          _permission = permission;
          _syncBusy = false;
          _notice =
              'Call-log access is required to synchronize calls. Allow it in '
              'Android settings, then try again.';
        });
        await MobileSimCallService.openAppSettings();
        return;
      }

      final employeeKey = _employeeKey;
      final result = await DeviceCallLogSyncService.sync(
        callsProvider,
        employeeKey: employeeKey,
        forceRetryPending: true,
      );
      final mapping = await OfficeSimService.fetch(force: true);
      final pending = await PendingCallSyncQueue.pendingCount(employeeKey);
      final ignoringBattery =
          await MobileSimCallService.isIgnoringBatteryOptimizations();
      if (!mounted) return;
      setState(() {
        _syncBusy = false;
        _permission = permission;
        _pendingSyncCount = pending;
        _ignoringBatteryOptimizations = ignoringBattery;
        if (mapping != null) _mapping = mapping;
        if (result.error != null && result.synced == 0) {
          _error = result.error;
        }
      });

      if (result.shouldRetry) {
        await AutomaticCallSyncService.scheduleOneOffSync();
      }
      if (!mounted) return;
      final message = result.synced > 0
          ? '${result.synced} call(s) synced.'
          : pending > 0
          ? '$pending call(s) are still waiting for CRM confirmation.'
          : 'No new calls to sync.';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: result.synced > 0
              ? AppColors.success
              : AppColors.warning,
        ),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _syncBusy = false;
        _error = error.message;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _syncBusy = false;
        _error = 'Unable to sync call logs: $error';
      });
    }
  }

  Future<void> _openBatteryOptimizationSettings() async {
    await MobileSimCallService.openBatteryOptimizationSettings();
    if (!mounted) return;
    setState(() {
      _notice =
          'Set WACRM to Unrestricted / allow background activity, then return '
          'here. Samsung, Vivo and Oppo may also require Auto-start or '
          'Background app refresh to be enabled.';
    });
  }

  Future<void> _pauseSync() async {
    setState(() {
      _syncBusy = true;
      _error = null;
      _notice = null;
    });
    try {
      final updated = await OfficeSimService.pauseSync();
      if (!mounted) return;
      setState(() {
        _mapping = updated;
        _syncBusy = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Sync paused. No calls will be imported until you resume.',
          ),
          backgroundColor: AppColors.warning,
        ),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _syncBusy = false;
        _error = error.message;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _syncBusy = false;
        _error = 'Unable to pause call-log sync: $error';
      });
    }
  }

  SimAccount? _selectedSim() {
    for (final sim in _sims) {
      if (sim.subscriptionId == _selectedSubscriptionId) return sim;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: AppColors.navy),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'Office SIM',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w800,
            color: AppColors.textMain,
          ),
        ),
        centerTitle: false,
      ),
      body: RefreshIndicator(
        onRefresh: () => _load(forceMapping: true),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          children: [
            _buildIntro(),
            const SizedBox(height: 16),
            if (_loading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 40),
                child: Center(child: CircularProgressIndicator()),
              )
            else ...[
              if (_error != null) _buildMessage(_error!, AppColors.danger),
              if (_notice != null) _buildMessage(_notice!, AppColors.warning),
              if (_permission != null && !_permission!.readPhoneState)
                _buildPermissionCard()
              else ...[
                _buildMappingStatus(),
                if (_permission != null && !_permission!.readCallLog) ...[
                  const SizedBox(height: 12),
                  _buildCallLogPermissionCard(),
                ],
                if (_mapping != null) ...[
                  const SizedBox(height: 16),
                  _buildSyncCard(_mapping!),
                ],
                if (_mapping?.syncActive == true &&
                    _ignoringBatteryOptimizations == false) ...[
                  const SizedBox(height: 16),
                  _buildBatteryCard(),
                ],
                const SizedBox(height: 16),
                _buildSimList(),
                const SizedBox(height: 18),
                WacrmButton(
                  text: _mapping == null
                      ? 'Save as Office SIM'
                      : 'Re-verify Office SIM',
                  icon: Icons.verified_user_outlined,
                  isLoading: _saving,
                  onPressed: _saving ? null : _save,
                ),
                if (_mapping != null) ...[
                  const SizedBox(height: 10),
                  TextButton.icon(
                    onPressed: _saving ? null : _clear,
                    icon: const Icon(Icons.delete_outline_rounded, size: 18),
                    label: const Text('Remove Office SIM mapping'),
                    style: TextButton.styleFrom(
                      foregroundColor: AppColors.danger,
                    ),
                  ),
                ],
              ],
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildIntro() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.sim_card_rounded, color: Colors.white, size: 22),
              SizedBox(width: 8),
              Text(
                'Only your Office SIM is synchronized',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: Colors.white,
                ),
              ),
            ],
          ),
          SizedBox(height: 8),
          Text(
            'Calls and recordings from your personal SIM never reach the CRM. '
            'The CRM identifies the SIM from Android subscription and phone '
            'account data — never from the SIM slot or phone number alone. '
            'Re-verification is required if the SIM is removed or replaced.',
            style: TextStyle(
              fontSize: 12,
              height: 1.5,
              color: Color(0xFFCBD5E1),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessage(String text, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: 12, color: color, height: 1.4),
      ),
    );
  }

  Widget _buildPermissionCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Phone permission required',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: AppColors.textMain,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Allow phone access so the CRM can read the installed SIM '
            'subscriptions and match calls to your Office SIM.',
            style: TextStyle(
              fontSize: 12,
              height: 1.4,
              color: AppColors.textMuted,
            ),
          ),
          const SizedBox(height: 12),
          WacrmButton(
            text: 'Allow phone access',
            icon: Icons.phone_android_rounded,
            onPressed: _requestPermission,
          ),
        ],
      ),
    );
  }

  Widget _buildCallLogPermissionCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(
                Icons.assignment_late_outlined,
                size: 18,
                color: AppColors.warning,
              ),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Call-log access is off',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textMain,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            'Android needs call-log access before incoming, outgoing and '
            'missed device calls can be synchronized automatically. WACRM '
            'only reads the phone call log; it never deletes it.',
            style: TextStyle(
              fontSize: 12,
              height: 1.4,
              color: AppColors.textMuted,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: WacrmButton(
                  text: 'Allow call-log access',
                  icon: Icons.phone_android_rounded,
                  onPressed: _requestPermission,
                ),
              ),
              const SizedBox(width: 8),
              TextButton(
                onPressed: MobileSimCallService.openAppSettings,
                child: const Text('App settings'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBatteryCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(
                Icons.battery_alert_rounded,
                size: 18,
                color: AppColors.warning,
              ),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Keep background sync reliable',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textMain,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            'Android battery optimization can delay automatic sync after a '
            'call. Allow WACRM to run in the background. On Samsung enable '
            'Unrestricted battery usage; on Vivo/Oppo also allow Auto-start '
            'and Background app refresh. If Android force-stops WACRM, '
            'automatic sync resumes the next time the app is opened.',
            style: TextStyle(
              fontSize: 11.5,
              height: 1.45,
              color: AppColors.textMuted,
            ),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: _openBatteryOptimizationSettings,
            icon: const Icon(Icons.settings_rounded, size: 18),
            label: const Text('Open battery settings'),
          ),
        ],
      ),
    );
  }

  Widget _buildMappingStatus() {
    final mapping = _mapping;
    if (mapping == null) {
      return _buildMessage(
        'No Office SIM is registered. Call synchronization is paused until '
        'you select your office SIM below.',
        AppColors.warning,
      );
    }
    final verified = mapping.isVerified;
    final matched = OfficeSimService.matchSim(mapping, _sims);
    final installed = matched != null;
    final color = verified && installed ? AppColors.success : AppColors.warning;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                verified && installed
                    ? Icons.verified_rounded
                    : Icons.warning_amber_rounded,
                size: 18,
                color: color,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  verified ? 'Office SIM verified' : 'Re-verification required',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: color,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          _buildDetailRow('SIM', mapping.label),
          if (mapping.simSlot != null)
            _buildDetailRow(
              'Slot',
              'SIM ${mapping.simSlot! + 1} (display only)',
            ),
          if ((mapping.phoneNumber ?? '').isNotEmpty)
            _buildDetailRow('Number', mapping.phoneNumber!),
          if (mapping.subscriptionId != null)
            _buildDetailRow('Subscription', '#${mapping.subscriptionId}'),
          if ((mapping.phoneAccountId ?? '').isNotEmpty)
            _buildDetailRow('Phone account', mapping.phoneAccountId!),
          if (!installed)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'The registered SIM is not currently present on this device.',
                style: TextStyle(fontSize: 11.5, color: AppColors.warning),
              ),
            ),
          if (!verified && (mapping.verificationReason ?? '').trim().isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                mapping.verificationReason!,
                style: const TextStyle(
                  fontSize: 11.5,
                  color: AppColors.warning,
                  height: 1.4,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSyncCard(OfficeSimMapping mapping) {
    final status = mapping.syncStatus;
    final (label, color) = switch (status) {
      'ACTIVE' => ('Sync active', AppColors.success),
      'PAUSED' => ('Sync paused', AppColors.warning),
      'REQUIRES_SIM_VERIFICATION' => (
        'Re-verification required',
        AppColors.danger,
      ),
      _ => ('Sync not enabled', AppColors.textMuted),
    };
    final canEnable =
        mapping.isVerified &&
        !mapping.syncActive &&
        !mapping.syncRequiresVerification;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.sync_rounded, size: 18, color: color),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: color,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            'Enabling sync captures the current Android call log as a '
            'baseline. Calls from before that moment, including calls made '
            'while sync was paused, are never imported. While sync is active, '
            'new calls are uploaded automatically in the background after they '
            'end — no need to open this screen.',
            style: TextStyle(
              fontSize: 11.5,
              height: 1.4,
              color: AppColors.textMuted,
            ),
          ),
          if (mapping.syncActivatedAt != null)
            _buildDetailRow(
              'Activated',
              DateFormatter.formatDateTime(mapping.syncActivatedAt),
            ),
          _buildDetailRow(
            'Last sync',
            mapping.lastSuccessfulSyncAt != null
                ? DateFormatter.formatDateTime(mapping.lastSuccessfulSyncAt)
                : 'Not yet',
          ),
          _buildDetailRow(
            'Pending sync',
            _pendingSyncCount == 0
                ? 'All calls confirmed'
                : '$_pendingSyncCount call(s) waiting',
          ),
          if (mapping.syncBaselineDateMs != null &&
              mapping.syncBaselineDateMs! > 0)
            _buildDetailRow(
              'Baseline',
              DateFormatter.formatDateTime(
                DateTime.fromMillisecondsSinceEpoch(
                  mapping.syncBaselineDateMs!,
                ),
              ),
            ),
          if (mapping.syncRequiresVerification)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'Replace or re-verify the Office SIM below, then enable sync '
                'again to create a fresh baseline.',
                style: TextStyle(fontSize: 11.5, color: AppColors.warning),
              ),
            ),
          const SizedBox(height: 10),
          if (mapping.syncActive)
            Row(
              children: [
                Expanded(
                  child: WacrmButton(
                    text: 'Sync now',
                    icon: Icons.sync_rounded,
                    isLoading: _syncBusy,
                    onPressed: _syncBusy ? null : _syncNow,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _syncBusy ? null : _pauseSync,
                    icon: const Icon(Icons.pause_rounded, size: 18),
                    label: const Text('Pause sync'),
                  ),
                ),
              ],
            )
          else if (canEnable)
            WacrmButton(
              text: mapping.syncPaused ? 'Resume sync' : 'Enable sync',
              icon: Icons.play_arrow_rounded,
              isLoading: _syncBusy,
              onPressed: _syncBusy
                  ? null
                  : () => _startSync(resume: mapping.syncPaused),
            ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 11.5,
                color: AppColors.textMuted,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w600,
                color: AppColors.textMain,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSimList() {
    if (_sims.isEmpty) {
      return _buildMessage(
        'No active SIM was found. Insert your Office SIM and pull to refresh.',
        AppColors.warning,
      );
    }
    return Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          for (var i = 0; i < _sims.length; i++) ...[
            if (i > 0) const Divider(height: 1, indent: 52),
            _buildSimTile(_sims[i]),
          ],
        ],
      ),
    );
  }

  Widget _buildSimTile(SimAccount sim) {
    final isOffice =
        _mapping != null &&
        OfficeSimService.matchSim(_mapping!, [sim])?.subscriptionId ==
            sim.subscriptionId;
    return InkWell(
      onTap: () => setState(() => _selectedSubscriptionId = sim.subscriptionId),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        child: Row(
          children: [
            Radio<int>(
              value: sim.subscriptionId,
              groupValue: _selectedSubscriptionId,
              activeColor: AppColors.primary,
              onChanged: (value) {
                if (value != null) {
                  setState(() => _selectedSubscriptionId = value);
                }
              },
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          sim.label,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textMain,
                          ),
                        ),
                      ),
                      if (isOffice)
                        Container(
                          margin: const EdgeInsets.only(left: 8),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.successLight,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: const Text(
                            'OFFICE',
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                              color: AppColors.success,
                            ),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(
                    [
                      'SIM ${sim.slotIndex + 1}',
                      if (sim.carrierName.trim().isNotEmpty) sim.carrierName,
                      if ((sim.phoneNumber ?? '').trim().isNotEmpty)
                        sim.phoneNumber!,
                      if (sim.subscriptionId >= 0) '#${sim.subscriptionId}',
                    ].join(' • '),
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textMuted,
                    ),
                  ),
                  if (sim.subscriptionId < 0 &&
                      (sim.phoneAccountId ?? '').trim().isEmpty)
                    const Padding(
                      padding: EdgeInsets.only(top: 3),
                      child: Text(
                        'This SIM exposes no stable identity on this device, so '
                        'it cannot be verified.',
                        style: TextStyle(
                          fontSize: 10.5,
                          color: AppColors.warning,
                        ),
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
}
