/// Phone-number helpers shared by DooCTI and mobile SIM calling.
///
/// CRM numbers are often stored with spaces, dashes, brackets or a `00`
/// international prefix. Dialers reject some of those forms, so every number is
/// normalized to a single dial-safe string before it is used.
class PhoneUtils {
  const PhoneUtils._();

  /// Normalizes a customer phone number for `tel:` URIs and CRM call logging.
  ///
  /// Keeps one leading `+` and digits only. Returns an empty string when the
  /// input contains no digits, which callers should treat as "no phone number".
  static String normalize(String? raw) {
    if (raw == null) return '';
    final mapped = _mapUnicodeDigits(raw.trim());
    if (mapped.isEmpty) return '';

    var digits = mapped.replaceAll(RegExp(r'[^0-9+]'), '');
    if (digits.isEmpty) return '';

    final hasInternationalPrefix =
        digits.startsWith('+') || digits.startsWith('00');

    // Drop every plus, then re-add exactly one at the start when needed.
    digits = digits.replaceAll('+', '');
    if (digits.startsWith('00')) {
      digits = digits.substring(2);
    }
    if (digits.isEmpty) return '';

    return hasInternationalPrefix ? '+$digits' : digits;
  }

  /// Returns true when [raw] contains enough digits to be dialled.
  static bool isDialable(String? raw) {
    return normalize(raw).replaceAll('+', '').length >= 3;
  }

  /// Normalizes free-form dial-pad input. Unlike [normalize], this keeps `*`
  /// and `#` so USSD/service codes such as `*123#` still work.
  static String normalizeDialInput(String? raw) {
    if (raw == null) return '';
    final mapped = _mapUnicodeDigits(raw.trim());
    var value = mapped.replaceAll(RegExp(r'[^0-9+*#]'), '');
    final hasLeadingPlus = value.startsWith('+');
    value = value.replaceAll('+', '');
    if (value.isEmpty) return '';
    return hasLeadingPlus ? '+$value' : value;
  }

  /// Picks the first dialable number from the candidates (e.g. phone, then
  /// WhatsApp number) and returns it normalized, or an empty string.
  static String firstDialable(Iterable<String?> candidates) {
    for (final candidate in candidates) {
      final normalized = normalize(candidate);
      if (normalized.replaceAll('+', '').length >= 3) {
        return normalized;
      }
    }
    return '';
  }

  static String _mapUnicodeDigits(String value) {
    if (!value.runes.any((rune) => rune > 0x7F)) return value;
    final buffer = StringBuffer();
    for (final rune in value.runes) {
      final digit = _unicodeDigitValue(rune);
      if (digit != null) {
        buffer.writeCharCode(0x30 + digit);
      } else {
        buffer.writeCharCode(rune);
      }
    }
    return buffer.toString();
  }

  static int? _unicodeDigitValue(int rune) {
    // Arabic-Indic, Eastern Arabic-Indic, Devanagari, Bengali and Tamil digits.
    const ranges = <int, List<int>>{
      0x0660: [0x0669], // ٠-٩
      0x06F0: [0x06F9], // ۰-۹
      0x0966: [0x096F], // ०-९
      0x09E6: [0x09EF], // ০-৯
      0x0BE6: [0x0BEF], // ௦-௯
    };
    for (final entry in ranges.entries) {
      if (rune >= entry.key && rune <= entry.value.first) {
        return rune - entry.key;
      }
    }
    return null;
  }
}
