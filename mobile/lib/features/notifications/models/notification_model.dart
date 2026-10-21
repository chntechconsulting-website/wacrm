class NotificationModel {
  final int id;
  final String title;
  final String message;
  final String? type;
  final bool isRead;
  final String? link;
  final String? createdAt;

  NotificationModel({
    required this.id,
    required this.title,
    required this.message,
    this.type,
    required this.isRead,
    this.link,
    this.createdAt,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id'] ?? 0,
      title: json['title'] ?? 'Notification',
      message: json['message'] ?? '',
      type: json['type'] ?? 'INFO',
      isRead: json['is_read'] ?? false,
      link: json['link'],
      createdAt: json['created_at'],
    );
  }
}
