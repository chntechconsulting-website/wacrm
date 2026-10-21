class DealSummaryModel {
  final int leadId;
  final String leadName;
  final String? companyName;
  final String? phone;
  final String status;
  final bool hasProforma;
  final String? proformaNumber;
  final double? proformaAmount;
  final bool isWon;
  final bool isHandedOffToFinance;
  final String? financeStatus;
  final bool isPaymentConfirmed;
  final String? taxInvoiceNumber;
  final bool hasBiometric;
  final int biometricDeviceCount;

  DealSummaryModel({
    required this.leadId,
    required this.leadName,
    this.companyName,
    this.phone,
    required this.status,
    required this.hasProforma,
    this.proformaNumber,
    this.proformaAmount,
    required this.isWon,
    required this.isHandedOffToFinance,
    this.financeStatus,
    required this.isPaymentConfirmed,
    this.taxInvoiceNumber,
    this.hasBiometric = false,
    this.biometricDeviceCount = 0,
  });

  factory DealSummaryModel.fromJson(Map<String, dynamic> json) {
    return DealSummaryModel(
      leadId: json['lead_id'] ?? 0,
      leadName: json['lead_name'] ?? 'Deal',
      companyName: json['company_name'],
      phone: json['phone'],
      status: json['status'] ?? 'WON',
      hasProforma: json['has_proforma'] ?? false,
      proformaNumber: json['proforma_number'],
      proformaAmount: (json['proforma_amount'] as num?)?.toDouble(),
      isWon: json['is_won'] ?? false,
      isHandedOffToFinance: json['is_handed_off_to_finance'] ?? false,
      financeStatus: json['finance_status'],
      isPaymentConfirmed: json['is_payment_confirmed'] ?? false,
      taxInvoiceNumber: json['tax_invoice_number'],
      hasBiometric: json['has_biometric'] ?? false,
      biometricDeviceCount: json['biometric_device_count'] ?? 0,
    );
  }
}

class FinanceHandoffModel {
  final int id;
  final int leadId;
  final String leadName;
  final String? companyName;
  final String phone;
  final String proformaNumber;
  final double amount;
  final String paymentStatus;
  final String? invoiceNumber;
  final String? createdAt;

  FinanceHandoffModel({
    required this.id,
    required this.leadId,
    required this.leadName,
    this.companyName,
    required this.phone,
    required this.proformaNumber,
    required this.amount,
    required this.paymentStatus,
    this.invoiceNumber,
    this.createdAt,
  });

  factory FinanceHandoffModel.fromJson(Map<String, dynamic> json) {
    return FinanceHandoffModel(
      id: json['id'] ?? 0,
      leadId: json['lead_id'] ?? 0,
      leadName: json['customer_name'] ?? json['lead_name'] ?? 'Client',
      companyName: json['company_name'],
      phone: json['customer_phone'] ?? json['phone'] ?? '',
      proformaNumber: json['proforma_invoice_number'] ?? json['proforma_number'] ?? '',
      amount: (json['total_amount'] ?? json['amount'] as num?)?.toDouble() ?? 0.0,
      paymentStatus: json['payment_status'] ?? 'PENDING',
      invoiceNumber: json['tax_invoice_number'],
      createdAt: json['created_at'],
    );
  }
}
