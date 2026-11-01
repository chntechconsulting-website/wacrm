import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/constants/api_endpoints.dart';
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

  group('resolveRecordingUrl', () {
    test('returns null when no recording URL is stored', () {
      expect(MobileRecordingService.resolveRecordingUrl(null), isNull);
      expect(MobileRecordingService.resolveRecordingUrl('   '), isNull);
    });

    test('keeps an absolute API media URL', () {
      final resolved = MobileRecordingService.resolveRecordingUrl(
        'https://www.wapluscrm.in/api/ivr/media/recordings/12/call.m4a',
      );
      expect(
        resolved,
        'https://www.wapluscrm.in/api/ivr/media/recordings/12/call.m4a',
      );
    });

    test('rewrites legacy /uploads recording links onto the API media route', () {
      final resolved = MobileRecordingService.resolveRecordingUrl(
        'https://www.wapluscrm.in/uploads/recordings/12/call.m4a',
      );
      expect(
        resolved,
        'https://www.wapluscrm.in/api/ivr/media/recordings/12/call.m4a',
      );
    });

    test('rebases managed uploads onto the configured backend', () {
      ApiEndpoints.baseUrl = 'http://192.168.1.20:8000';
      addTearDown(() => ApiEndpoints.baseUrl = ApiEndpoints.productionBaseUrl);

      final resolved = MobileRecordingService.resolveRecordingUrl(
        'https://www.wapluscrm.in/uploads/recordings/12/call.m4a',
      );
      expect(
        resolved,
        'http://192.168.1.20:8000/api/ivr/media/recordings/12/call.m4a',
      );
    });

    test('leaves external PBX recordings untouched', () {
      const external =
          'https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/call.mp3';
      expect(
        MobileRecordingService.resolveRecordingUrl(external),
        external,
      );
    });
  });
}
