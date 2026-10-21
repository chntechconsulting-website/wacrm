import 'package:flutter/material.dart';
import '../data/dashboard_repository.dart';
import '../models/dashboard_stats_model.dart';

class DashboardProvider extends ChangeNotifier {
  final DashboardRepository _repository = DashboardRepository();

  DashboardStatsModel? _stats;
  bool _isLoading = false;
  String? _errorMessage;

  DashboardStatsModel? get stats => _stats;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchDashboardStats({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _stats = await _repository.getDashboardStats();
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
