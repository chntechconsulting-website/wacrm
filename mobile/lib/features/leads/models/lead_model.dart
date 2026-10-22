class LeadModel {
  final int id;
  final String name;
  final String phone;
  final String? email;
  final String? company;
  final String? source;
  final String status;
  final String? priority;
  final String? rating;
  final String? requirement;
  final int? assignedTo;
  final String? assignedToName;
  final int? quotationId;
  final String? quotationNumber;
  final String? quotationStatus;
  final double? quotationAmount;
  final String? createdAt;
  final String? updatedAt;

  LeadModel({
    required this.id,
    required this.name,
    required this.phone,
    this.email,
    this.company,
    this.source,
    required this.status,
    this.priority,
    this.rating,
    this.requirement,
    this.assignedTo,
    this.assignedToName,
    this.quotationId,
    this.quotationNumber,
    this.quotationStatus,
    this.quotationAmount,
    this.createdAt,
    this.updatedAt,
  });

  factory LeadModel.fromJson(Map<String, dynamic> json) {
    return LeadModel(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      phone: json['phone'] ?? '',
      email: json['email'],
      company: json['company'],
      source: json['source'] ?? 'Manual',
      status: json['status'] ?? 'NEW',
      priority: json['priority'] ?? 'MEDIUM',
      rating: json['rating'],
      requirement: json['requirement'] ?? json['notes'],
      assignedTo: json['assigned_to'],
      assignedToName: json['assigned_to_name'] ?? json['employee_name'],
      quotationId: json['quotetask_quotation_id'] != null
          ? int.tryParse(json['quotetask_quotation_id'].toString())
          : null,
      quotationNumber: json['quotetask_quotation_number'],
      quotationStatus: json['quotetask_quotation_status'],
      quotationAmount: (json['quotetask_quotation_amount'] as num?)?.toDouble(),
      createdAt: json['created_at'],
      updatedAt: json['updated_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'phone': phone,
      'email': email,
      'company': company,
      'source': source,
      'status': status,
      'priority': priority,
      'requirement': requirement,
      if (assignedTo != null) 'assigned_to': assignedTo,
    };
  }

  LeadModel copyWith({
    String? name,
    String? phone,
    String? email,
    String? company,
    String? source,
    String? status,
    String? priority,
    String? requirement,
    int? assignedTo,
    String? assignedToName,
  }) {
    return LeadModel(
      id: id,
      name: name ?? this.name,
      phone: phone ?? this.phone,
      email: email ?? this.email,
      company: company ?? this.company,
      source: source ?? this.source,
      status: status ?? this.status,
      priority: priority ?? this.priority,
      requirement: requirement ?? this.requirement,
      assignedTo: assignedTo ?? this.assignedTo,
      assignedToName: assignedToName ?? this.assignedToName,
      quotationId: quotationId,
      quotationNumber: quotationNumber,
      quotationStatus: quotationStatus,
      quotationAmount: quotationAmount,
      createdAt: createdAt,
      updatedAt: updatedAt,
    );
  }
}

class EmployeeOption {
  final int id;
  final String name;
  final String? email;
  final String? role;

  EmployeeOption({
    required this.id,
    required this.name,
    this.email,
    this.role,
  });

  factory EmployeeOption.fromJson(Map<String, dynamic> json) {
    return EmployeeOption(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      email: json['email'],
      role: json['role'],
    );
  }
}

class SupportManagerOption {
  final int id;
  final String name;
  final String? username;
  final String? email;
  final String? role;
  final String? department;

  SupportManagerOption({
    required this.id,
    required this.name,
    this.username,
    this.email,
    this.role,
    this.department,
  });

  factory SupportManagerOption.fromJson(Map<String, dynamic> json) {
    return SupportManagerOption(
      id: json['id'] ?? 0,
      name: json['name'] ?? json['username'] ?? 'Support Manager',
      username: json['username'],
      email: json['email'],
      role: json['role'],
      department: json['department'],
    );
  }
}

class ProformaOption {
  final int id;
  final String docNumber;
  final double grandTotal;
  final int licenceCount;
  final String paymentStatus;
  final double amountPaid;
  final String? productSummary;
  final String? productCategory;
  final String? selectedBundle;
  final int biometricDeviceCount;

  ProformaOption({
    required this.id,
    required this.docNumber,
    required this.grandTotal,
    this.licenceCount = 1,
    this.paymentStatus = 'PAYMENT_PENDING',
    this.amountPaid = 0.0,
    this.productSummary,
    this.productCategory,
    this.selectedBundle,
    this.biometricDeviceCount = 0,
  });

  factory ProformaOption.fromJson(Map<String, dynamic> json) {
    return ProformaOption(
      id: json['id'] ?? 0,
      docNumber: json['doc_number'] ?? 'PI-${json['id']}',
      grandTotal: (json['grand_total'] as num?)?.toDouble() ?? (json['total_amount'] as num?)?.toDouble() ?? 0.0,
      licenceCount: (json['licence_count'] as num?)?.toInt() ?? 1,
      paymentStatus: json['payment_status'] ?? 'PAYMENT_PENDING',
      amountPaid: (json['amount_paid'] as num?)?.toDouble() ?? 0.0,
      productSummary: json['product_summary'] ?? json['product_category'] ?? 'WAHRMS Business Solution',
      productCategory: json['product_category'] ?? 'WAHRMS',
      selectedBundle: json['selected_bundle'],
      biometricDeviceCount: (json['biometric_device_count'] as num?)?.toInt() ?? 0,
    );
  }
}
