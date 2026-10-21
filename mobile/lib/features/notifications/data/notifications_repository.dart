import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/notification_model.dart';

class NotificationsRepository {
  final ApiClient _client = ApiClient();

  Future<List<NotificationModel>> getNotifications() async {
    final response = await _client.get(ApiEndpoints.notifications);
    if (response is List) {
      return response.map((json) => NotificationModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<void> markAsRead(int id) async {
    await _client.put(ApiEndpoints.markNotificationRead(id));
  }

  Future<void> markAllAsRead() async {
    await _client.post(ApiEndpoints.markAllNotificationsRead);
  }

  Future<void> clearAll() async {
    await _client.delete(ApiEndpoints.clearAllNotifications);
  }
}
