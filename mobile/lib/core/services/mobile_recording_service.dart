import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../constants/api_endpoints.dart';
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
  final String checksum;

  const PickedRecording({
    required this.path,
    required this.name,
    required this.size,
    required this.mimeType,
    this.durationSeconds,
    this.checksum = '',
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
      checksum: (map['checksum'] ?? '').toString(),
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

  /// Opens an in-app playback dialog for a verified recording.
  ///
  /// Playback must use the stored media URL. The upload endpoint
  /// (`/calls/{id}/recording`) only accepts POST, so pointing MediaPlayer at it
  /// fails with an opaque Android media error.
  static Future<void> play(BuildContext context, {required String? url}) async {
    final resolved = resolveRecordingUrl(url);
    if (resolved == null) {
      if (context.mounted) {
        _showError(
          context,
          'This call has no playable recording URL yet. Wait for the upload '
          'to finish and refresh.',
        );
      }
      return;
    }
    final token = await TokenStorage.getToken();
    if (token == null || token.isEmpty) {
      if (context.mounted) _showError(context, 'Your session has expired.');
      return;
    }
    if (!context.mounted) return;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _RecordingPlaybackDialog(url: resolved, token: token),
    );
  }

  /// Turns an API recording URL into something MediaPlayer can open.
  ///
  /// - Stored `/uploads/...` paths are absolute.
  /// - URLs that point at another origin's `/uploads/` are rebased onto the
  ///   configured backend, so a recording uploaded by a dev/staging server is
  ///   not played from the production domain (and vice versa).
  /// - External recording providers (S3, Oracle, PBX) are left untouched.
  static String? resolveRecordingUrl(String? rawUrl) {
    final raw = (rawUrl ?? '').trim();
    if (raw.isEmpty) return null;
    final uri = Uri.tryParse(raw);
    if (uri == null) return null;

    // Older backend responses (and legacy rows) point at the generic
    // `/uploads/...` mount, which production reverse proxies do not forward to
    // FastAPI. Managed recordings are always playable through the API media
    // route, on whichever backend the app is configured to use.
    const managedUploads = '/uploads/recordings/';
    const mediaRoute = '/ivr/media/recordings/';
    if (uri.path.contains(managedUploads)) {
      final suffix = uri.path.substring(
        uri.path.indexOf(managedUploads) + managedUploads.length,
      );
      return '${ApiEndpoints.apiPrefix}$mediaRoute$suffix';
    }

    if (!uri.hasScheme) {
      return '${ApiEndpoints.baseUrl.replaceAll(RegExp(r'/+$'), '')}$raw';
    }
    final base = Uri.tryParse(ApiEndpoints.baseUrl);
    final isManagedUpload = uri.path.contains('/media/recordings/');
    if (isManagedUpload && base != null && base.host.isNotEmpty) {
      if (uri.host != base.host || uri.port != base.port) {
        final authority = base.hasPort ? '${base.host}:${base.port}' : base.host;
        final query = uri.hasQuery ? '?${uri.query}' : '';
        return '${base.scheme}://$authority${uri.path}$query';
      }
    }
    return raw;
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
