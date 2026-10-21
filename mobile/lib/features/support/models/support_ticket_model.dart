class SupportTicketModel {
  final int id;
  final int leadId;
  final String customerName;
  final String? companyName;
  final String phone;
  final String? email;
  final String status; // PENDING_CONTACT, IN_TRAINING, INSTALLATION_PENDING, LIVE, COMPLETED
  final int? assignedTo;
  final String? assignedToName;
  final int biometricDeviceCount;
  final String? invoiceNumber;
  final String? notes;
  final String? createdAt;

  SupportTicketModel({
    required this.id,
    required this.leadId,
    required this.customerName,
    this.companyName,
    required this.phone,
    this.email,
    required this.status,
    this.assignedTo,
    this.assignedToName,
    this.biometricDeviceCount = 0,
    this.invoiceNumber,
    this.notes,
    this.createdAt,
  });

  factory SupportTicketModel.fromJson(Map<String, dynamic> json) {
    return SupportTicketModel(
      id: json['id'] ?? 0,
      leadId: json['lead_id'] ?? 0,
      customerName: json['customer_name'] ?? 'Client',
      companyName: json['company_name'],
      phone: json['customer_phone'] ?? json['phone'] ?? '',
      email: json['customer_email'] ?? json['email'],
      status: json['status'] ?? json['onboarding_status'] ?? 'PENDING_CONTACT',
      assignedTo: json['assigned_to'] ?? json['assigned_employee_id'],
      assignedToName: json['assigned_to_name'] ?? json['assigned_employee_name'],
      biometricDeviceCount: json['biometric_device_count'] ?? 0,
      invoiceNumber: json['tax_invoice_number'],
      notes: json['notes'],
      createdAt: json['created_at'],
    );
  }
}
