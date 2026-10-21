class CustomerModel {
  final int id;
  final String name;
  final String phone;
  final String? email;
  final String? company;
  final int? leadId;
  final String? createdAt;
  final String status;

  CustomerModel({
    required this.id,
    required this.name,
    required this.phone,
    this.email,
    this.company,
    this.leadId,
    this.createdAt,
    this.status = 'ACTIVE',
  });

  factory CustomerModel.fromJson(Map<String, dynamic> json) {
    return CustomerModel(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      phone: json['phone'] ?? '',
      email: json['email'],
      company: json['company'],
      leadId: json['lead_id'],
      createdAt: json['created_at'],
      status: json['status'] ?? 'ACTIVE',
    );
  }
}
