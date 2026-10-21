import 'package:flutter/material.dart';
import '../data/followups_repository.dart';
import '../models/followup_model.dart';

class FollowupsProvider extends ChangeNotifier {
  final FollowupsRepository _repository = FollowupsRepository();

  List<FollowupModel> _followups = [];
  List<FollowupReminderModel> _reminders = [];
  bool _isLoading = false;
  String? _errorMessage;
  String _statusFilter = 'Pending';

  List<FollowupModel> get followups => _followups;
  List<FollowupReminderModel> get reminders => _reminders;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String get statusFilter => _statusFilter;

  Future<void> fetchFollowups({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _followups = await _repository.getFollowups(
        status: _statusFilter == 'ALL' ? null : _statusFilter,
      );
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> fetchActiveReminders() async {
    try {
      _reminders = await _repository.getActiveReminders();
      notifyListeners();
    } catch (_) {}
  }

  void setFilter(String status) {
    _statusFilter = status;
    fetchFollowups();
  }

  Future<bool> createFollowup(Map<String, dynamic> data) async {
    try {
      final created = await _repository.createFollowup(data);
      _followups.insert(0, created);
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> updateStatus(int id, String newStatus) async {
    try {
      final updated = await _repository.updateFollowup(id, {'status': newStatus});
      final index = _followups.indexWhere((f) => f.id == id);
      if (index != -1) {
        if (_statusFilter != 'ALL' && _statusFilter != newStatus) {
          _followups.removeAt(index);
        } else {
          _followups[index] = updated;
        }
        notifyListeners();
      }
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<void> snoozeReminder(int id, {int minutes = 30}) async {
    await _repository.snoozeReminder(id, minutes: minutes);
    _reminders.removeWhere((r) => r.id == id);
    notifyListeners();
  }

  Future<void> dismissReminder(int id) async {
    await _repository.dismissReminder(id);
    _reminders.removeWhere((r) => r.id == id);
    notifyListeners();
  }
}
