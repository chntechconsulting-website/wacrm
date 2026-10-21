import 'package:intl/intl.dart';

class CurrencyFormatter {
  static String formatInr(dynamic amount) {
    if (amount == null) return '₹0.00';
    double value = 0.0;
    if (amount is num) {
      value = amount.toDouble();
    } else if (amount is String) {
      value = double.tryParse(amount) ?? 0.0;
    }

    final format = NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: 2,
    );
    return format.format(value);
  }

  static String formatCompact(dynamic amount) {
    if (amount == null) return '₹0';
    double value = 0.0;
    if (amount is num) {
      value = amount.toDouble();
    } else if (amount is String) {
      value = double.tryParse(amount) ?? 0.0;
    }

    if (value >= 10000000) {
      return '₹${(value / 10000000).toStringAsFixed(2)} Cr';
    } else if (value >= 100000) {
      return '₹${(value / 100000).toStringAsFixed(2)} L';
    } else if (value >= 1000) {
      return '₹${(value / 1000).toStringAsFixed(1)} k';
    }
    return '₹${value.toStringAsFixed(0)}';
  }
}
