import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/services/doocti_call_service.dart';
import '../../../core/services/automatic_call_sync_service.dart';
import '../../../core/services/mobile_call_recording_manager.dart';
import '../../../core/services/mobile_recording_service.dart';
import '../../../core/services/mobile_sim_call_service.dart';
import '../../../core/services/office_sim_service.dart';
import '../../../core/services/recording_upload_service.dart';
import '../../../core/utils/date_formatter.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_badge.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../providers/calls_provider.dart';
import '../models/call_log_model.dart';
import '../../auth/providers/auth_provider.dart';
import 'dialer_screen.dart';

class CallLogsScreen extends StatefulWidget {
  const CallLogsScreen({super.key});

  @override
  State<CallLogsScreen> createState() => _CallLogsScreenState();
}

class _CallLogsScreenState extends State<CallLogsScreen>
    with WidgetsBindingObserver {
  bool _handlingSharedRecording = false;
  bool _processingRecordings = false;
  MobileSimPermissionStatus? _permissionStatus;
  bool _permissionBusy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    MobileRecordingService.setSharedHandler(
      (_) => _maybeHandleSharedRecording(),
    );
    _refreshCallLogPermission();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await context.read<CallsProvider>().fetchCalls();
      if (!mounted) return;
      await _processPendingRecordings();
      if (mounted) _maybeHandleSharedRecording();
    });
  }

  Future<void> _refreshCallLogPermission() async {
    if (!MobileSimCallService.isSupported) return;
    try {
      final status = await MobileSimCallService.permissionStatus();
      if (mounted) setState(() => _permissionStatus = status);
    } catch (_) {
      // Leave the banner hidden when the platform cannot report permissions.
    }
  }

  Future<void> _requestCallLogPermission() async {
    if (_permissionBusy) return;
    setState(() => _permissionBusy = true);
    MobileSimPermissionStatus status;
    try {
      status = await MobileSimCallService.permissionStatus();
      if (!status.readCallLog) {
        status = await MobileSimCallService.requestPermissions();
      }
    } catch (_) {
      if (mounted) setState(() => _permissionBusy = false);
      return;
    }
    if (!mounted) return;
    setState(() {
      _permissionStatus = status;
      _permissionBusy = false;
    });
    if (status.readCallLog) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(
          'Call-log access is off',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        content: const Text(
          'Android needs call-log access before incoming and outgoing device '
          'calls can be synchronized to the CRM. Open App settings and allow '
          'Phone / Call logs access for WACRM.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Not now'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              MobileSimCallService.openAppSettings();
            },
            child: const Text('Open settings'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    MobileRecordingService.setSharedHandler(null);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refreshCallLogPermission();
      _processPendingRecordings();
      _maybeHandleSharedRecording();
    }
  }

  /// Re-queues recent PENDING_SYNC/UPLOAD_FAILED calls (including rows synced
  /// by an older app version) and processes due recording tasks. The queue is
  /// durable, so a call whose dialer has not written its file yet stays here
  /// until WorkManager or the next foreground pass can retry it.
  Future<void> _processPendingRecordings({bool forceRetry = false}) async {
    if (_processingRecordings || !mounted) return;
    _processingRecordings = true;
    try {
      final provider = context.read<CallsProvider>();
      final employeeKey = _employeeKey;
      await RecordingUploadService.enqueueFromCalls(
        provider.calls,
        employeeKey: employeeKey,
      );
      final result = await RecordingUploadService.processQueue(
        employeeKey: employeeKey,
        callsProvider: provider,
        forceRetry: forceRetry,
      );
      if (result.uploaded > 0 && mounted) {
        await provider.fetchCalls(showLoading: false);
      }
      if (result.retryablePending > 0) {
        await AutomaticCallSyncService.scheduleOneOffSync();
      }
    } catch (_) {
      // The durable queue keeps the task for the next pass.
    } finally {
      _processingRecordings = false;
    }
  }

  /// Offers a recording shared into WACRM from the OEM dialer / file manager.
  Future<void> _maybeHandleSharedRecording() async {
    if (_handlingSharedRecording || !mounted) return;
    _handlingSharedRecording = true;
    try {
      final shared = await MobileRecordingService.consumeShared();
      if (shared == null || !mounted) return;

      final provider = context.read<CallsProvider>();
      var mobileCalls = provider.calls
          .where((call) => call.isMobile)
          .take(12)
          .toList();
      if (mobileCalls.isEmpty) {
        await provider.fetchCalls(showLoading: false);
        if (!mounted) return;
        mobileCalls = provider.calls
            .where((call) => call.isMobile)
            .take(12)
            .toList();
      }
      if (mobileCalls.isEmpty) {
        await showDialog<void>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text(
              'Recording received',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            content: const Text(
              'No Mobile SIM call logs were found to attach this recording to. '
              'Make a call first, then share the recording again.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('OK'),
              ),
            ],
          ),
        );
        return;
      }

      final selectedCall = await showModalBottomSheet<CallLogModel>(
        context: context,
        isScrollControlled: true,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        builder: (ctx) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 18),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Attach shared recording',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textMain,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${shared.name} (${shared.sizeLabel}) — choose the Mobile SIM '
                  'call it belongs to.',
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textMuted,
                  ),
                ),
                const SizedBox(height: 12),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 360),
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: mobileCalls.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (_, index) {
                      final call = mobileCalls[index];
                      return Material(
                        color: AppColors.background,
                        borderRadius: BorderRadius.circular(14),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(14),
                          onTap: () => Navigator.pop(ctx, call),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 10,
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.sim_card_rounded,
                                  size: 18,
                                  color: Color(0xFF059669),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        call.leadName ?? call.customerNumber,
                                        style: const TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                      Text(
                                        '${call.customerNumber} • '
                                        '${DateFormatter.formatDateTime(call.createdAt)}',
                                        style: const TextStyle(
                                          fontSize: 11,
                                          color: AppColors.textMuted,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      );
      if (selectedCall == null || !mounted) return;

      final consented = await RecordingConsentService.ensureConsent(
        context,
        employeeKey: _employeeKey,
      );
      if (!consented || !mounted) return;

      final outcome = await RecordingUploadService.uploadPickedRecording(
        callId: selectedCall.id,
        employeeKey: _employeeKey,
        recording: _importedFromPicked(shared),
        phone: selectedCall.customerNumber,
        startedAt: _startedAtFor(selectedCall),
        endedAt: _endedAtFor(selectedCall),
        durationSeconds: selectedCall.durationSeconds,
        direction: selectedCall.callType,
        nativeReference: selectedCall.nativeCallReference,
        simAccountId: selectedCall.simAccountId,
        simSubscriptionId: selectedCall.simSubscriptionId,
      );
      if (!mounted) return;
      final uploaded =
          outcome == RecordingUploadOutcome.uploaded ||
          outcome == RecordingUploadOutcome.duplicate;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_outcomeMessage(outcome)),
          backgroundColor: uploaded
              ? const Color(0xFF10B981)
              : const Color(0xFFDC2626),
        ),
      );
      if (uploaded) {
        await provider.fetchCalls(showLoading: false);
      } else {
        await AutomaticCallSyncService.scheduleOneOffSync();
      }
    } finally {
      _handlingSharedRecording = false;
    }
  }

  String get _employeeKey =>
      context.read<AuthProvider>().currentUser?.id.toString() ?? 'default';

  Future<void> _attachRecording(CallLogModel call) async {
    // Verify the call belongs to the registered Office SIM before the picker or
    // matcher runs. Personal-SIM recordings must never be offered for import.
    final mapping = await OfficeSimService.fetch();
    if (mapping != null) {
      final allowed =
          mapping.isVerified &&
          OfficeSimService.callMatches(
            mapping,
            simAccountId: call.simAccountId,
            subscriptionId: call.simSubscriptionId,
          );
      if (!allowed) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              mapping.isVerified
                  ? 'This call was not handled by your registered Office SIM. '
                        'Its recording cannot be imported.'
                  : 'Your Office SIM must be re-verified before recordings can '
                        'be imported.',
            ),
            backgroundColor: const Color(0xFFB45309),
          ),
        );
        return;
      }
    }

    final employeeKey = _employeeKey;
    final consented = await RecordingConsentService.ensureConsent(
      context,
      employeeKey: employeeKey,
    );
    if (!consented || !mounted) return;

    final capability = await MobileCallRecordingManager.capability();
    if (!mounted) return;

    final choice = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: AppColors.card,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (ctx) => SafeArea(
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 8),
              if (capability.audioPermission)
                ListTile(
                  leading: const Icon(Icons.manage_search_rounded),
                  title: const Text('Find on this device'),
                  subtitle: Text(
                    capability.mediaStoreRecordingCount > 0
                        ? '${capability.mediaStoreRecordingCount} readable recording(s) '
                              'in Android media storage. Only an exact match is attached.'
                        : 'No readable recordings in Android media storage yet. '
                              'Use Choose a file instead.',
                  ),
                  onTap: () => Navigator.pop(ctx, 'auto'),
                )
              else
                ListTile(
                  leading: const Icon(Icons.lock_open_rounded),
                  title: const Text('Allow audio file search'),
                  subtitle: const Text(
                    'Grant read-only audio access so WACRM can look for the '
                    'dialer recording. You can still use the file picker.',
                  ),
                  onTap: () => Navigator.pop(ctx, 'grant'),
                ),
              ListTile(
                leading: const Icon(Icons.folder_open_rounded),
                title: const Text('Choose a recording file'),
                subtitle: const Text(
                  'Open the system document picker (user-authorised access)',
                ),
                onTap: () => Navigator.pop(ctx, 'file'),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                child: Text(
                  capability.mediaStoreRecordingCount == 0 &&
                          capability.audioPermission
                      ? 'Samsung/Vivo/Oppo may keep recordings in a folder '
                            'Android media scan does not index. In that case use '
                            'Choose a file or share from the phone recorder app.'
                      : 'WACRM never records calls. It only imports a file your '
                            'phone already created.',
                  style: const TextStyle(
                    fontSize: 11.5,
                    height: 1.4,
                    color: AppColors.textMuted,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (!mounted || choice == null) return;

    if (choice == 'grant') {
      final status = await MobileSimCallService.requestPermissions();
      if (!mounted) return;
      if (status.readMediaAudio) {
        await _attachRecording(call);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Audio access was not granted. You can still import through '
              'Choose a file.',
            ),
            backgroundColor: Color(0xFFB45309),
          ),
        );
      }
      return;
    }

    ImportedCallRecording? recording;
    if (choice == 'auto') {
      final started = _startedAtFor(call);
      if (started == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'This call has no start time, so a recording cannot be matched '
              'safely. Nothing was attached.',
            ),
            backgroundColor: Color(0xFFB45309),
          ),
        );
        return;
      }
      recording = await MobileCallRecordingManager.findRecordingForCall(
        phone: call.customerNumber,
        startedAt: started,
        endedAt: _endedAtFor(call),
        durationSeconds: call.durationSeconds,
      );
      if (recording == null) {
        // Keep a durable task: the dialer may index the file later, and the
        // same queue retries it automatically with WorkManager.
        await RecordingUploadService.enqueueForCall(
          callId: call.id,
          employeeKey: employeeKey,
          phone: call.customerNumber,
          startedAt: started,
          endedAt: _endedAtFor(call),
          durationSeconds: call.durationSeconds,
          direction: call.callType,
          nativeReference: call.nativeCallReference,
          simAccountId: call.simAccountId,
          simSubscriptionId: call.simSubscriptionId,
          source: 'MANUAL',
        );
        await AutomaticCallSyncService.scheduleOneOffSync();
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'No unambiguous device recording was found yet. The call stays '
              'queued and WACRM will retry automatically. You can also use '
              'Choose a file.',
            ),
            backgroundColor: Color(0xFFB45309),
          ),
        );
        return;
      }
    } else {
      final picked = await _pickRecordingSafely();
      if (!mounted) return;
      if (picked.cancelled || picked.recording == null) return;
      recording = picked.recording;
    }

    if (!mounted || recording == null) return;

    final outcome = await RecordingUploadService.uploadRecordingForCall(
      callId: call.id,
      employeeKey: employeeKey,
      phone: call.customerNumber,
      startedAt: _startedAtFor(call) ?? DateTime.now().toUtc(),
      endedAt: _endedAtFor(call),
      durationSeconds: call.durationSeconds,
      recording: recording,
      direction: call.callType,
      nativeReference: call.nativeCallReference,
      simAccountId: call.simAccountId,
      simSubscriptionId: call.simSubscriptionId,
    );
    if (!mounted) return;
    final uploaded =
        outcome == RecordingUploadOutcome.uploaded ||
        outcome == RecordingUploadOutcome.duplicate;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(_outcomeMessage(outcome)),
        backgroundColor: uploaded
            ? const Color(0xFF10B981)
            : const Color(0xFFDC2626),
      ),
    );
    await context.read<CallsProvider>().fetchCalls(showLoading: false);
    if (!uploaded) {
      await AutomaticCallSyncService.scheduleOneOffSync();
    }
  }

  DateTime? _startedAtFor(CallLogModel call) {
    final raw = call.startedAt ?? call.createdAt;
    return raw == null ? null : DateTime.tryParse(raw)?.toUtc();
  }

  DateTime? _endedAtFor(CallLogModel call) {
    final raw = call.endedAt;
    return raw == null ? null : DateTime.tryParse(raw)?.toUtc();
  }

  ImportedCallRecording _importedFromPicked(PickedRecording picked) {
    final seconds = picked.durationSeconds ?? 0;
    return ImportedCallRecording(
      path: picked.path,
      name: picked.name,
      size: picked.size,
      mimeType: picked.mimeType,
      durationMs: seconds * 1000,
      checksum: picked.checksum,
      source: 'SHARED',
      verified: seconds > 0,
    );
  }

  Future<RecordingPickResult> _pickRecordingSafely() async {
    try {
      return await MobileCallRecordingManager.pickRecordingFile();
    } on PlatformException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              error.message ??
                  'The selected file could not be verified as a recording.',
            ),
            backgroundColor: const Color(0xFFDC2626),
          ),
        );
      }
      return RecordingPickResult.empty;
    }
  }

  String _outcomeMessage(RecordingUploadOutcome outcome) {
    switch (outcome) {
      case RecordingUploadOutcome.uploaded:
        return 'Recording verified, uploaded and linked to this call.';
      case RecordingUploadOutcome.duplicate:
        return 'This recording is already linked to the call.';
      case RecordingUploadOutcome.consentRequired:
        return 'Recording consent is required before importing.';
      case RecordingUploadOutcome.verificationFailed:
        return 'Recording verification failed. The file was not attached.';
      case RecordingUploadOutcome.uploadFailed:
        return 'Recording upload failed. The call stays marked for retry.';
    }
  }

  Future<void> _showRecordingCapability() async {
    final capability = await MobileCallRecordingManager.capability();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(
          'Call recording support',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _capabilityRow('Device', capability.platformLabel),
              _capabilityRow(
                'Android',
                '${capability.androidVersion} (API ${capability.androidSdk})',
              ),
              _capabilityRow('OEM family', capability.oemFamily),
              _capabilityRow(
                'Native dialer',
                capability.nativeDialerPackage ?? 'Not reported',
              ),
              _capabilityRow(
                'Automatic sync',
                capability.automaticSyncLabel,
              ),
              _capabilityRow('OEM support', capability.oemSupportLabel),
              _capabilityRow(
                'Audio permission',
                capability.audioPermission ? 'Granted' : 'Not granted',
              ),
              _capabilityRow(
                'Readable recordings',
                capability.audioPermission
                    ? '${capability.mediaStoreRecordingCount} in media storage'
                    : 'Unavailable until audio access is granted',
              ),
              _capabilityRow(
                'Recording folders',
                capability.recordingFolderHints.isEmpty
                    ? 'None detected'
                    : capability.recordingFolderHints.join(', '),
              ),
              const SizedBox(height: 10),
              const Text(
                RecordingConsentService.disclosureText,
                style: TextStyle(fontSize: 12, height: 1.4),
              ),
              if (capability.notes.isNotEmpty) ...[
                const SizedBox(height: 10),
                ...capability.notes.map(
                  (note) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Text(
                      '• $note',
                      style: const TextStyle(fontSize: 11.5, height: 1.35),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              final diagnostics = [
                'device=${capability.platformLabel}',
                'android=${capability.androidVersion} (API ${capability.androidSdk})',
                'oem=${capability.oemFamily}',
                'dialer=${capability.nativeDialerPackage ?? "unknown"}',
                'audioPermission=${capability.audioPermission}',
                'capability=${capability.recordingCapability}',
                'readableRecordings=${capability.mediaStoreRecordingCount}',
                'folders=${capability.recordingFolderHints.join("|")}',
                'recorders=${capability.oemRecorderPackages.join("|")}',
                'notes=${capability.notes.join(" | ")}',
              ].join('\n');
              Clipboard.setData(ClipboardData(text: diagnostics));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Recording diagnostics copied.'),
                  backgroundColor: Color(0xFF10B981),
                ),
              );
            },
            child: const Text('Copy diagnostics'),
          ),
          if (!capability.audioPermission)
            TextButton(
              onPressed: () async {
                final status = await MobileSimCallService.requestPermissions();
                if (ctx.mounted) Navigator.pop(ctx);
                if (status.readMediaAudio) _showRecordingCapability();
              },
              child: const Text('Grant audio access'),
            ),
          FutureBuilder<bool>(
            future: RecordingConsentService.hasConsent(_employeeKey),
            builder: (context, snapshot) {
              if (snapshot.data != true) return const SizedBox.shrink();
              return TextButton(
                onPressed: () async {
                  await RecordingConsentService.revoke(_employeeKey);
                  if (ctx.mounted) Navigator.pop(ctx);
                },
                child: const Text('Revoke consent'),
              );
            },
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _capabilityRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppColors.textMuted,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 12, height: 1.3),
            ),
          ),
        ],
      ),
    );
  }

  void _callNumber(String phone, {int? leadId, String? contactName}) {
    DooctiCallService.makeCall(
      context,
      phone: phone,
      leadId: leadId,
      contactName: contactName,
    );
  }

  void _showLogManualCallDialog() {
    final phoneController = TextEditingController();
    final durationController = TextEditingController(text: '60');
    final notesController = TextEditingController();
    String callStatus = 'ANSWERED';
    bool isSubmitting = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) {
          return Padding(
            padding: EdgeInsets.only(
              bottom: MediaQuery.of(ctx).viewInsets.bottom,
            ),
            child: Container(
              decoration: const BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
              ),
              padding: const EdgeInsets.all(20),
              child: SafeArea(
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
                      'Log Phone Call into CRM',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textMain,
                      ),
                    ),
                    const SizedBox(height: 14),
                    WacrmTextField(
                      controller: phoneController,
                      label: 'Client Phone Number *',
                      hintText: 'e.g. 9876543210',
                      keyboardType: TextInputType.phone,
                      prefixIcon: Icons.phone_outlined,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Call Status',
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 6),
                              DropdownButtonFormField<String>(
                                value: callStatus,
                                items:
                                    [
                                      'ANSWERED',
                                      'MISSED',
                                      'BUSY',
                                      'NO_ANSWER',
                                    ].map((s) {
                                      return DropdownMenuItem(
                                        value: s,
                                        child: Text(s),
                                      );
                                    }).toList(),
                                onChanged: (val) {
                                  if (val != null)
                                    setModalState(() => callStatus = val);
                                },
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: WacrmTextField(
                            controller: durationController,
                            label: 'Duration (Seconds)',
                            keyboardType: TextInputType.number,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    WacrmTextField(
                      controller: notesController,
                      label: 'Call Discussion Summary',
                      hintText:
                          'Discussed client requirements, scheduled demo...',
                      maxLines: 2,
                    ),
                    const SizedBox(height: 20),
                    WacrmButton(
                      text: 'Save Call Log',
                      isLoading: isSubmitting,
                      icon: Icons.check_rounded,
                      onPressed: () async {
                        if (phoneController.text.trim().isEmpty) return;

                        setModalState(() => isSubmitting = true);
                        final success = await context
                            .read<CallsProvider>()
                            .logManualCall(
                              customerNumber: phoneController.text.trim(),
                              callStatus: callStatus,
                              durationSeconds:
                                  int.tryParse(durationController.text) ?? 60,
                              notes: notesController.text.trim(),
                            );
                        setModalState(() => isSubmitting = false);

                        if (context.mounted && success) {
                          Navigator.pop(ctx);
                        }
                      },
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _callSourceBadge(CallLogModel call) {
    final isMobile = call.isMobile;
    return WacrmBadge(
      label: isMobile ? 'MOBILE' : 'DOOCTI',
      icon: isMobile ? Icons.smartphone_rounded : Icons.cloud_rounded,
      backgroundColor: isMobile
          ? const Color(0xFFECFDF5)
          : const Color(0xFFEFF6FF),
      textColor: isMobile
          ? const Color(0xFF047857)
          : const Color(0xFF1D4ED8),
      fontSize: 9.5,
    );
  }

  Widget _recordingAction({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: const Color(0xFFECFDF5),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFFD1FAE5)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: const Color(0xFF059669)),
            const SizedBox(width: 4),
            Text(
              label,
              style: const TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.w700,
                color: Color(0xFF047857),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _callLogPermissionBanner() {
    final status = _permissionStatus;
    if (status == null || status.readCallLog) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.dangerLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.danger.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.phone_disabled_rounded,
            color: AppColors.danger,
            size: 20,
          ),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'Call-log permission is off. Incoming and outgoing device calls '
              'cannot be synchronized until call-log access is allowed.',
              style: TextStyle(fontSize: 12, color: AppColors.textMain),
            ),
          ),
          const SizedBox(width: 8),
          _permissionBusy
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : TextButton(
                  onPressed: _requestCallLogPermission,
                  child: const Text('Allow'),
                ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CallsProvider>();
    final calls = provider.calls;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Call Logs & Telephony'),
        actions: [
          IconButton(
            tooltip: 'Recording support on this device',
            icon: const Icon(Icons.verified_user_outlined),
            onPressed: _showRecordingCapability,
          ),
          IconButton(
            tooltip: 'Dial pad',
            icon: const Icon(Icons.dialpad_rounded),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const DialerScreen()),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () {
              _refreshCallLogPermission();
              provider.fetchCalls();
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.white,
        icon: const Icon(Icons.add_call),
        label: const Text(
          'Log Call',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        onPressed: _showLogManualCallDialog,
      ),
      body: Column(
        children: [
          _callLogPermissionBanner(),
          Expanded(
            child: provider.isLoading && calls.isEmpty
          ? const LoadingIndicator(message: 'Loading call records...')
          : provider.errorMessage != null && calls.isEmpty
          ? ErrorView(
              message: provider.errorMessage!,
              onRetry: () => provider.fetchCalls(),
            )
          : calls.isEmpty
          ? EmptyState(
              title: 'No Call Logs Found',
              subtitle: 'Calls via DooCTI, mobile SIM or manual phone calls will be logged here.',
              pingoPose: PingoPoses.inspect,
              actionLabel: 'Log Call',
              onAction: _showLogManualCallDialog,
            )
          : RefreshIndicator(
              color: AppColors.primary,
              onRefresh: () => provider.fetchCalls(showLoading: false),
              child: ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
                itemCount: calls.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final call = calls[index];
                  final isAnswered =
                      call.callStatus == 'ANSWERED' ||
                      call.callStatus == 'COMPLETED';

                  return WacrmCard(
                    padding: const EdgeInsets.all(14),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: isAnswered
                                ? AppColors.successLight
                                : AppColors.dangerLight,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(
                            call.callType == 'INBOUND'
                                ? Icons.call_received_rounded
                                : Icons.call_made_rounded,
                            color: isAnswered
                                ? AppColors.success
                                : AppColors.danger,
                            size: 20,
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
                                      call.leadName ?? call.customerNumber,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.textMain,
                                      ),
                                    ),
                                  ),
                                  _callSourceBadge(call),
                                  const SizedBox(width: 6),
                                  WacrmBadge.status(call.callStatus),
                                ],
                              ),
                              const SizedBox(height: 3),
                              Text(
                                '${call.customerNumber} • ${call.formattedDuration}',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.textMuted,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                DateFormatter.formatDateTime(call.createdAt),
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: AppColors.textLight,
                                ),
                              ),
                              if (call.isMobile) ...[
                                const SizedBox(height: 4),
                                Row(
                                  children: [
                                    const Icon(
                                      Icons.sim_card_rounded,
                                      size: 11,
                                      color: Color(0xFF059669),
                                    ),
                                    const SizedBox(width: 4),
                                    Flexible(
                                      child: Text(
                                        '${call.simLabel ?? 'Mobile SIM'}'
                                        ' • ${call.recordingStatusLabel}',
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          fontSize: 10.5,
                                          fontWeight: FontWeight.w600,
                                          color: Color(0xFF059669),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                if (!call.isRecordingAvailable &&
                                    call
                                        .recordingStatusDetailLabel
                                        .isNotEmpty) ...[
                                  const SizedBox(height: 2),
                                  Text(
                                    call.recordingStatusDetailLabel,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontSize: 10.5,
                                      height: 1.3,
                                      color: call.recordingSyncStatus ==
                                              RecordingSyncStatus.uploadFailed
                                          ? const Color(0xFFB91C1C)
                                          : const Color(0xFFB45309),
                                    ),
                                  ),
                                ],
                                const SizedBox(height: 6),
                                Wrap(
                                  spacing: 8,
                                  runSpacing: 4,
                                  children: [
                                    if (call.hasRecording)
                                      _recordingAction(
                                        icon: Icons.play_arrow_rounded,
                                        label: 'Play',
                                        onTap: () =>
                                            MobileRecordingService.play(
                                              context,
                                              url: call.recordingUrl,
                                            ),
                                      ),
                                    _recordingAction(
                                      icon: call.hasRecording
                                          ? Icons.swap_horiz_rounded
                                          : Icons.upload_file_rounded,
                                      label: call.hasRecording
                                          ? 'Replace'
                                          : 'Import recording',
                                      onTap: () => _attachRecording(call),
                                    ),
                                  ],
                                ),
                              ],
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(
                            Icons.phone_rounded,
                            color: AppColors.primary,
                            size: 20,
                          ),
                          onPressed: () => _callNumber(
                            call.customerNumber,
                            leadId: call.leadId,
                            contactName: call.leadName,
                          ),
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
