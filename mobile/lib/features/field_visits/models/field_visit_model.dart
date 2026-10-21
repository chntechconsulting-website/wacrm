class FieldVisitModel {
  final int id;
  final int employeeId;
  final String employeeName;
  final int? leadId;
  final String? leadName;
  final int? customerId;
  final String customerName;
  final String? checkinTime;
  final String? checkoutTime;
  final String? checkinLat;
  final String? checkinLng;
  final String? checkinAddress;
  final String? photoUrl;
  final String? visitingCardUrl;
  final String? customerRequirements;
  final String visitOutcome;
  final String? notes;
  final String status;
  final int? followupId;
  final Map<String, dynamic>? followup;
  final String? clientToken;

  FieldVisitModel({
    required this.id,
    required this.employeeId,
    required this.employeeName,
    this.leadId,
    this.leadName,
    this.customerId,
    required this.customerName,
    this.checkinTime,
    this.checkoutTime,
    this.checkinLat,
    this.checkinLng,
    this.checkinAddress,
    this.photoUrl,
    this.visitingCardUrl,
    this.customerRequirements,
    required this.visitOutcome,
    this.notes,
    required this.status,
    this.followupId,
    this.followup,
    this.clientToken,
  });

  factory FieldVisitModel.fromJson(Map<String, dynamic> json) {
    return FieldVisitModel(
      id: json['id'] ?? 0,
      employeeId: json['employee_id'] ?? 0,
      employeeName: json['employee_name'] ?? 'Field Agent',
      leadId: json['lead_id'],
      leadName: json['lead_name'],
      customerId: json['customer_id'],
      customerName: json['customer_name'] ?? 'Customer',
      checkinTime: json['checkin_time']?.toString(),
      checkoutTime: json['checkout_time']?.toString(),
      checkinLat: json['checkin_lat']?.toString(),
      checkinLng: json['checkin_lng']?.toString(),
      checkinAddress: json['checkin_address']?.toString(),
      photoUrl: json['photo_url']?.toString(),
      visitingCardUrl: json['visiting_card_url']?.toString(),
      customerRequirements: json['customer_requirements']?.toString(),
      visitOutcome: json['visit_outcome'] ?? 'Completed',
      notes: json['notes']?.toString(),
      status: json['status'] ?? 'COMPLETED',
      followupId: json['followup_id'],
      followup: json['followup'] is Map<String, dynamic> ? json['followup'] : null,
      clientToken: json['client_token']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'employee_id': employeeId,
      'employee_name': employeeName,
      'lead_id': leadId,
      'customer_id': customerId,
      'customer_name': customerName,
      'checkin_time': checkinTime,
      'checkout_time': checkoutTime,
      'checkin_lat': checkinLat,
      'checkin_lng': checkinLng,
      'checkin_address': checkinAddress,
      'photo_url': photoUrl,
      'visiting_card_url': visitingCardUrl,
      'customer_requirements': customerRequirements,
      'visit_outcome': visitOutcome,
      'notes': notes,
      'status': status,
      'followup_id': followupId,
      'client_token': clientToken,
    };
  }
}
