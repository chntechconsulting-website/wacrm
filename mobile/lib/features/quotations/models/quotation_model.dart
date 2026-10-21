class QuotationModel {
  final dynamic id;
  final String docType; // quotation, proforma, invoice
  final String docNumber;
  final String customerName;
  final String? companyName;
  final String? phone;
  final String? email;
  final String status;
  final String paymentStatus;
  final double subtotal;
  final double taxTotal;
  final double grandTotal;
  final String productCategory; // wahrms, biometric
  final String taxMode; // intra, inter
  final List<LineItemModel> lineItems;
  final String? createdAt;

  QuotationModel({
    required this.id,
    required this.docType,
    required this.docNumber,
    required this.customerName,
    this.companyName,
    this.phone,
    this.email,
    required this.status,
    required this.paymentStatus,
    required this.subtotal,
    required this.taxTotal,
    required this.grandTotal,
    required this.productCategory,
    required this.taxMode,
    required this.lineItems,
    this.createdAt,
  });

  bool get isEligibleForSync =>
      !productCategory.toLowerCase().contains('bio') && docType.toLowerCase() == 'proforma';

  factory QuotationModel.fromJson(Map<String, dynamic> json) {
    final cat = (json['product_category'] ?? json['category'] ?? 'wahrms').toString().toLowerCase();

    return QuotationModel(
      id: json['id'] ?? 0,
      docType: (json['doc_type'] ?? 'quotation').toString().toLowerCase(),
      docNumber: json['doc_number'] ?? '',
      customerName: json['customer_name'] ?? 'Client',
      companyName: json['company_name'],
      phone: json['phone'],
      email: json['email'],
      status: json['status'] ?? 'issued',
      paymentStatus: json['payment_status'] ?? 'unpaid',
      subtotal: (json['subtotal'] as num?)?.toDouble() ?? 0.0,
      taxTotal: (json['tax_total'] as num?)?.toDouble() ?? 0.0,
      grandTotal: (json['grand_total'] as num?)?.toDouble() ?? 0.0,
      productCategory: cat,
      taxMode: json['tax_mode'] ?? 'intra',
      lineItems: (json['line_items'] as List? ?? [])
          .map((i) => LineItemModel.fromJson(i))
          .toList(),
      createdAt: json['created_at'],
    );
  }
}

class LineItemModel {
  final String description;
  final String? hsn;
  final double qty;
  final double rate;
  final double amount;

  LineItemModel({
    required this.description,
    this.hsn,
    required this.qty,
    required this.rate,
    required this.amount,
  });

  factory LineItemModel.fromJson(Map<String, dynamic> json) {
    return LineItemModel(
      description: json['description'] ?? json['name'] ?? '',
      hsn: json['hsn'],
      qty: (json['qty'] as num?)?.toDouble() ?? 1.0,
      rate: (json['rate'] as num?)?.toDouble() ?? 0.0,
      amount: (json['amount'] as num?)?.toDouble() ?? 0.0,
    );
  }
}
