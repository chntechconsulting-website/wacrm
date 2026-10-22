class LeadModel {
  final int id;
  final String name;
  final String? firstName;
  final String? lastName;
  final String phone;
  final String? whatsappNumber;
  final String? email;
  final String? designation;
  final String? company;
  final String? industry;
  final String? website;
  final String? companySize;
  final String? city;
  final String? state;
  final String? source;
  final String status;
  final String? priority;
  final String? rating;
  final String? campaignName;
  final String? requirement;
  final String? requirementNotes;
  final String? followupDate;
  final String? followupTime;
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
    this.firstName,
    this.lastName,
    required this.phone,
    this.whatsappNumber,
    this.email,
    this.designation,
    this.company,
    this.industry,
    this.website,
    this.companySize,
    this.city,
    this.state,
    this.source,
    required this.status,
    this.priority,
    this.rating,
    this.campaignName,
    this.requirement,
    this.requirementNotes,
    this.followupDate,
    this.followupTime,
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
      firstName: json['first_name'],
      lastName: json['last_name'],
      phone: json['phone'] ?? '',
      whatsappNumber: json['whatsapp_number'],
      email: json['email'],
      designation: json['designation'],
      company: json['company'],
      industry: json['industry'],
      website: json['website'],
      companySize: json['company_size'],
      city: json['city'],
      state: json['state'],
      source: json['source'] ?? 'Manual',
      status: json['status'] ?? 'NEW',
      priority: json['priority'] ?? 'MEDIUM',
      rating: json['rating'],
      campaignName: json['campaign_name'],
      requirement: json['requirement'] ?? json['notes'] ?? json['requirement_notes'],
      requirementNotes: json['requirement_notes'] ?? json['requirement'] ?? json['notes'],
      followupDate: json['followup_date']?.toString(),
      followupTime: json['followup_time']?.toString(),
      assignedTo: json['assigned_to'],
      assignedToName: json['assigned_to_name'] ?? json['employee_name'] ?? json['assigned_employee_name'],
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
      if (firstName != null) 'first_name': firstName,
      if (lastName != null) 'last_name': lastName,
      'phone': phone,
      if (whatsappNumber != null) 'whatsapp_number': whatsappNumber,
      if (email != null) 'email': email,
      if (designation != null) 'designation': designation,
      if (company != null) 'company': company,
      if (industry != null) 'industry': industry,
      if (website != null) 'website': website,
      if (companySize != null) 'company_size': companySize,
      if (city != null) 'city': city,
      if (state != null) 'state': state,
      'source': source,
      'status': status,
      'priority': priority,
      if (rating != null) 'rating': rating,
      if (campaignName != null) 'campaign_name': campaignName,
      'requirement': requirement,
      if (requirementNotes != null) 'requirement_notes': requirementNotes,
      if (followupDate != null) 'followup_date': followupDate,
      if (followupTime != null) 'followup_time': followupTime,
      if (assignedTo != null) 'assigned_to': assignedTo,
    };
  }

  LeadModel copyWith({
    String? name,
    String? firstName,
    String? lastName,
    String? phone,
    String? whatsappNumber,
    String? email,
    String? designation,
    String? company,
    String? industry,
    String? website,
    String? companySize,
    String? city,
    String? state,
    String? source,
    String? status,
    String? priority,
    String? rating,
    String? campaignName,
    String? requirement,
    String? requirementNotes,
    String? followupDate,
    String? followupTime,
    int? assignedTo,
    String? assignedToName,
  }) {
    return LeadModel(
      id: id,
      name: name ?? this.name,
      firstName: firstName ?? this.firstName,
      lastName: lastName ?? this.lastName,
      phone: phone ?? this.phone,
      whatsappNumber: whatsappNumber ?? this.whatsappNumber,
      email: email ?? this.email,
      designation: designation ?? this.designation,
      company: company ?? this.company,
      industry: industry ?? this.industry,
      website: website ?? this.website,
      companySize: companySize ?? this.companySize,
      city: city ?? this.city,
      state: state ?? this.state,
      source: source ?? this.source,
      status: status ?? this.status,
      priority: priority ?? this.priority,
      rating: rating ?? this.rating,
      campaignName: campaignName ?? this.campaignName,
      requirement: requirement ?? this.requirement,
      requirementNotes: requirementNotes ?? this.requirementNotes,
      followupDate: followupDate ?? this.followupDate,
      followupTime: followupTime ?? this.followupTime,
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
  final String? designation;

  EmployeeOption({
    required this.id,
    required this.name,
    this.email,
    this.role,
    this.designation,
  });

  factory EmployeeOption.fromJson(Map<String, dynamic> json) {
    return EmployeeOption(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      email: json['email'],
      role: json['role'],
      designation: json['designation'] ?? json['role'],
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
