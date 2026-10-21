class WhatsAppConversationModel {
  final int id;
  final int? leadId;
  final String? leadName;
  final String phone;
  final String contactName;
  final int? assignedTo;
  final String? assignedEmployeeName;
  final int unreadCount;
  final bool isArchived;
  final String? lastMessageText;
  final String? lastMessageAt;
  final String? createdAt;

  WhatsAppConversationModel({
    required this.id,
    this.leadId,
    this.leadName,
    required this.phone,
    required this.contactName,
    this.assignedTo,
    this.assignedEmployeeName,
    this.unreadCount = 0,
    this.isArchived = false,
    this.lastMessageText,
    this.lastMessageAt,
    this.createdAt,
  });

  factory WhatsAppConversationModel.fromJson(Map<String, dynamic> json) {
    return WhatsAppConversationModel(
      id: json['id'] ?? 0,
      leadId: json['lead_id'],
      leadName: json['lead_name'],
      phone: json['phone'] ?? '',
      contactName: json['contact_name'] ?? json['lead_name'] ?? json['phone'] ?? '',
      assignedTo: json['assigned_to'],
      assignedEmployeeName: json['assigned_employee_name'],
      unreadCount: json['unread_count'] ?? 0,
      isArchived: json['is_archived'] ?? false,
      lastMessageText: json['last_message_text'],
      lastMessageAt: json['last_message_at'],
      createdAt: json['created_at'],
    );
  }
}

class WhatsAppMessageModel {
  final int id;
  final int conversationId;
  final int? leadId;
  final int? senderEmployeeId;
  final String? senderEmployeeName;
  final String direction; // INBOUND, OUTBOUND
  final String messageType; // text, template, image, document
  final String? body;
  final String? mediaUrl;
  final String? caption;
  final String? templateName;
  final String status;
  final String? sentAt;
  final String? createdAt;

  WhatsAppMessageModel({
    required this.id,
    required this.conversationId,
    this.leadId,
    this.senderEmployeeId,
    this.senderEmployeeName,
    required this.direction,
    required this.messageType,
    this.body,
    this.mediaUrl,
    this.caption,
    this.templateName,
    required this.status,
    this.sentAt,
    this.createdAt,
  });

  factory WhatsAppMessageModel.fromJson(Map<String, dynamic> json) {
    return WhatsAppMessageModel(
      id: json['id'] ?? 0,
      conversationId: json['conversation_id'] ?? 0,
      leadId: json['lead_id'],
      senderEmployeeId: json['sender_employee_id'],
      senderEmployeeName: json['sender_employee_name'],
      direction: json['direction'] ?? 'OUTBOUND',
      messageType: json['message_type'] ?? 'text',
      body: json['body'],
      mediaUrl: json['media_url'],
      caption: json['caption'],
      templateName: json['template_name'],
      status: json['status'] ?? 'SENT',
      sentAt: json['sent_at'],
      createdAt: json['created_at'],
    );
  }
}
