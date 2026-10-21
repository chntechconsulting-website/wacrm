import 'package:flutter/material.dart';
import '../data/notifications_repository.dart';
import '../models/notification_model.dart';

class NotificationsProvider extends ChangeNotifier {
  final NotificationsRepository _repository = NotificationsRepository();

  List<NotificationModel> _notifications = [];
  bool _isLoading = false;
  String? _errorMessage;

  List<NotificationModel> get notifications => _notifications;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  int get unreadCount => _notifications.where((n) => !n.isRead).length;

  Future<void> fetchNotifications({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _notifications = await _repository.getNotifications();
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> markAsRead(int id) async {
    try {
      await _repository.markAsRead(id);
      final index = _notifications.indexWhere((n) => n.id == id);
      if (index != -1) {
        final current = _notifications[index];
        _notifications[index] = NotificationModel(
          id: current.id,
          title: current.title,
          message: current.message,
          type: current.type,
          isRead: true,
          link: current.link,
          createdAt: current.createdAt,
        );
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> markAllAsRead() async {
    try {
      await _repository.markAllAsRead();
      _notifications = _notifications
          .map((n) => NotificationModel(
                id: n.id,
                title: n.title,
                message: n.message,
                type: n.type,
                isRead: true,
                link: n.link,
                createdAt: n.createdAt,
              ))
          .toList();
      notifyListeners();
    } catch (_) {}
  }

  Future<void> clearAll() async {
    try {
      await _repository.clearAll();
      _notifications.clear();
      notifyListeners();
    } catch (_) {}
  }
}
