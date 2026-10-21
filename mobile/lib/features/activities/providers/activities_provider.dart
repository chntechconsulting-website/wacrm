import 'package:flutter/material.dart';
import '../data/activities_repository.dart';
import '../models/activity_model.dart';

class ActivitiesProvider extends ChangeNotifier {
  final ActivitiesRepository _repository = ActivitiesRepository();

  List<ActivityModel> _activities = [];
  bool _isLoading = false;
  String? _errorMessage;

  List<ActivityModel> get activities => _activities;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchActivities({int? leadId, bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _activities = await _repository.getActivities(leadId: leadId);
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> createActivity(Map<String, dynamic> data) async {
    try {
      final act = await _repository.createActivity(data);
      _activities.insert(0, act);
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }
}
