import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/utils/phone_utils.dart';

void main() {
  group('PhoneUtils.normalize', () {
    test('strips spaces, dashes and brackets', () {
      expect(PhoneUtils.normalize('+91 98765-43210'), '+919876543210');
      expect(PhoneUtils.normalize('(080) 1234 5678'), '08012345678');
    });

    test('keeps a single leading plus', () {
      expect(PhoneUtils.normalize('+91 (98765) 43210'), '+919876543210');
      expect(PhoneUtils.normalize('++91 98765 43210'), '+919876543210');
    });

    test('converts a 00 international prefix to plus', () {
      expect(PhoneUtils.normalize('0091 98765 43210'), '+919876543210');
    });

    test('returns empty for non-numeric or empty input', () {
      expect(PhoneUtils.normalize(null), '');
      expect(PhoneUtils.normalize(''), '');
      expect(PhoneUtils.normalize('   '), '');
      expect(PhoneUtils.normalize('N/A'), '');
      expect(PhoneUtils.normalize('—'), '');
    });

    test('converts common non-ASCII digits', () {
      expect(PhoneUtils.normalize('९८७६५४३२१०'), '9876543210');
      expect(PhoneUtils.normalize('٠٩٨٧٦٥٤٣٢١٠'), '09876543210');
    });
  });

  group('PhoneUtils.isDialable', () {
    test('requires at least three digits', () {
      expect(PhoneUtils.isDialable('12'), isFalse);
      expect(PhoneUtils.isDialable('112'), isTrue);
      expect(PhoneUtils.isDialable('+91 98765 43210'), isTrue);
      expect(PhoneUtils.isDialable('N/A'), isFalse);
    });
  });

  group('PhoneUtils.normalizeDialInput', () {
    test('keeps USSD stars and hashes', () {
      expect(PhoneUtils.normalizeDialInput('*123#'), '*123#');
      expect(PhoneUtils.normalizeDialInput('*123# extra'), '*123#');
      expect(PhoneUtils.normalizeDialInput('+91 98*76'), '+9198*76');
    });
  });

  group('PhoneUtils.firstDialable', () {
    test('falls back to the WhatsApp number when phone is invalid', () {
      expect(
        PhoneUtils.firstDialable(['', 'N/A', '+91 98765 43210']),
        '+919876543210',
      );
      expect(PhoneUtils.firstDialable(['', null]), '');
    });
  });
}
