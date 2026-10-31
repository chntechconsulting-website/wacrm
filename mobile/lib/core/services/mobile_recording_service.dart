import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../constants/api_endpoints.dart';
import '../network/api_client.dart';
import '../network/api_exceptions.dart';
import '../network/token_storage.dart';
import 'mobile_sim_call_service.dart';

/// A recording file the employee explicitly picked or shared into WACRM.
///
/// The CRM never captures cellular audio itself. This model only describes a
/// file produced by the device's own dialer / recorder.
class PickedRecording {
  final String path;
  final String name;
  final int size;
  final String mimeType;
  final int? durationSeconds;

  const PickedRecording({
    required this.path,
    required this.name,
    required this.size,
    required this.mimeType,
    this.durationSeconds,
  });

  factory PickedRecording.fromMap(Map<String, dynamic> map) {
    final durationMs = (map['durationMs'] as num?)?.toInt();
    return PickedRecording(
      path: (map['path'] ?? '').toString(),
      name: (map['name'] ?? 'recording').toString(),
      size: (map['size'] as num?)?.toInt() ?? 0,
      mimeType: (map['mimeType'] ?? 'audio/*').toString(),
      durationSeconds: durationMs != null && durationMs > 0
          ? (durationMs / 1000).round()
          : null,
    );
  }

  String get sizeLabel {
    if (size >= 1024 * 1024) {
      return '${(size / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    if (size >= 1024) {
      return '${(size / 1024).toStringAsFixed(0)} KB';
    }
    return '$size B';
  }
}

/// Upload and playback helpers for authorised Mobile SIM call recordings.
class MobileRecordingService {
  static final ApiClient _client = ApiClient();

  /// Opens the Android document picker. Returns null when cancelled.
  static Future<PickedRecording?> pick() async {
    final map = await MobileSimCallService.pickRecordingFile();
    if (map == null) return null;
    return PickedRecording.fromMap(map);
  }

  /// Returns a file shared into WACRM from the OEM recorder / file manager.
  static Future<PickedRecording?> consumeShared() async {
    final map = await MobileSimCallService.consumeSharedRecordingFile();
    if (map == null) return null;
    return PickedRecording.fromMap(map);
  }

  static void setSharedHandler(
    void Function(Map<String, dynamic> recording)? handler,
  ) {
    MobileSimCallService.setSharedRecordingHandler(handler);
  }

  /// Confirms and uploads a recording for [callId]. The backend verifies the
  /// audio signature and only then links it to the call.
  static Future<bool> attachToCall(
    BuildContext context, {
    required int callId,
    PickedRecording? recording,
  }) async {
    PickedRecording? picked = recording;
    if (picked == null) {
      try {
        picked = await pick();
      } on PlatformException catch (error) {
        if (context.mounted) {
          _showError(
            context,
            error.message ?? 'Could not open the file picker.',
          );
        }
        return false;
      }
    }
    if (picked == null) return false;
    if (!context.mounted) return false;

    if (!File(picked.path).existsSync()) {
      _showError(context, 'That file is no longer available. Pick it again.');
      return false;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(
          'Attach call recording?',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${picked!.name} (${picked.sizeLabel})',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 10),
            const Text(
              'This file will be uploaded to CRM storage and linked to this '
              'call. Only attach a recording you are authorised to store and '
              'share with your team.',
              style: TextStyle(fontSize: 13, height: 1.4),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Upload'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return false;

    try {
      await _client.postMultipart(
        ApiEndpoints.ivrCallRecording(callId),
        file: File(picked.path),
        fields: {
          if (picked.durationSeconds != null)
            'duration_seconds': '${picked.durationSeconds}',
        },
      );
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Recording uploaded and linked to this call.'),
            backgroundColor: Color(0xFF10B981),
          ),
        );
      }
      return true;
    } on ApiException catch (error) {
      if (context.mounted) _showError(context, error.message);
      return false;
    } catch (error) {
      if (context.mounted) {
        _showError(context, 'Could not upload the recording: $error');
      }
      return false;
    }
  }

  /// Opens an in-app playback dialog for a verified recording.
  static Future<void> play(BuildContext context, int callId) async {
    final token = await TokenStorage.getToken();
    if (token == null || token.isEmpty) {
      if (context.mounted) _showError(context, 'Your session has expired.');
      return;
    }
    if (!context.mounted) return;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _RecordingPlaybackDialog(
        url: ApiEndpoints.ivrCallRecording(callId),
        token: token,
      ),
    );
  }

  static void _showError(BuildContext context, String message) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(
          'Call recording',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }
}

class _RecordingPlaybackDialog extends StatefulWidget {
  final String url;
  final String token;

  const _RecordingPlaybackDialog({required this.url, required this.token});

  @override
  State<_RecordingPlaybackDialog> createState() =>
      _RecordingPlaybackDialogState();
}

class _RecordingPlaybackDialogState extends State<_RecordingPlaybackDialog> {
  bool _starting = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    try {
      await MobileSimCallService.playRecording(
        url: widget.url,
        token: widget.token,
      );
      if (!mounted) return;
      setState(() => _starting = false);
    } on PlatformException catch (error) {
      if (!mounted) return;
      setState(() {
        _starting = false;
        _error = error.message ?? 'This recording could not be played.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _starting = false;
        _error = 'This recording could not be played: $error';
      });
    }
  }

  @override
  void dispose() {
    MobileSimCallService.stopRecordingPlayback();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text(
        'Call recording',
        style: TextStyle(fontWeight: FontWeight.w700),
      ),
      content: Row(
        children: [
          if (_error == null)
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else
            const Icon(Icons.error_outline_rounded, color: Color(0xFFDC2626)),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              _error ??
                  (_starting
                      ? 'Preparing recording...'
                      : 'Playing recording through this device.'),
              style: const TextStyle(fontSize: 13, height: 1.4),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(_error == null ? 'Stop' : 'Close'),
        ),
      ],
    );
  }
}
