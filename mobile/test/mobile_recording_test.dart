import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/services/mobile_recording_service.dart';

void main() {
  group('PickedRecording', () {
    test('parses native picker / share metadata', () {
      final recording = PickedRecording.fromMap(<String, dynamic>{
        'path': '/data/cache/recording_uploads/1700_call.m4a',
        'name': 'Call recording 2026-10-31.m4a',
        'size': 2048,
        'mimeType': 'audio/mp4',
      });

      expect(recording.path, contains('recording_uploads'));
      expect(recording.name, 'Call recording 2026-10-31.m4a');
      expect(recording.size, 2048);
      expect(recording.mimeType, 'audio/mp4');
      expect(recording.sizeLabel, '2 KB');
    });

    test('falls back safely when optional metadata is missing', () {
      final recording = PickedRecording.fromMap(<String, dynamic>{
        'path': '/tmp/call.mp3',
      });

      expect(recording.name, 'recording');
      expect(recording.size, 0);
      expect(recording.mimeType, 'audio/*');
      expect(recording.sizeLabel, '0 B');
    });
  });
}
