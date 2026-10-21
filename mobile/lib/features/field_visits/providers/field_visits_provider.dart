import 'package:flutter/material.dart';
import '../data/field_visits_repository.dart';
import '../models/field_visit_model.dart';

class FieldVisitsProvider extends ChangeNotifier {
  final FieldVisitsRepository _repository = FieldVisitsRepository();

  List<FieldVisitModel> _visits = [];
  bool _isLoading = false;
  bool _isSubmitting = false;
  String? _errorMessage;
  String _searchQuery = '';

  List<FieldVisitModel> get visits {
    if (_searchQuery.trim().isEmpty) {
      return _visits;
    }
    final q = _searchQuery.toLowerCase().trim();
    return _visits.where((v) {
      final name = v.customerName.toLowerCase();
      final emp = v.employeeName.toLowerCase();
      final outcome = v.visitOutcome.toLowerCase();
      final address = (v.checkinAddress ?? '').toLowerCase();
      final notes = (v.notes ?? '').toLowerCase();
      return name.contains(q) || emp.contains(q) || outcome.contains(q) || address.contains(q) || notes.contains(q);
    }).toList();
  }

  bool get isLoading => _isLoading;
  bool get isSubmitting => _isSubmitting;
  String? get errorMessage => _errorMessage;
  String get searchQuery => _searchQuery;

  void setSearchQuery(String query) {
    _searchQuery = query;
    notifyListeners();
  }

  Future<void> fetchFieldVisits({
    int? employeeId,
    int? leadId,
    int? customerId,
    String? status,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _visits = await _repository.getFieldVisits(
        employeeId: employeeId,
        leadId: leadId,
        customerId: customerId,
        status: status,
      );
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<FieldVisitModel?> submitFieldVisit(Map<String, dynamic> data) async {
    _isSubmitting = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final newVisit = await _repository.submitFieldVisit(data);
      // Prepend to list or update if idempotent response
      final idx = _visits.indexWhere((v) => v.id == newVisit.id);
      if (idx >= 0) {
        _visits[idx] = newVisit;
      } else {
        _visits.insert(0, newVisit);
      }
      return newVisit;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      return null;
    } finally {
      _isSubmitting = false;
      notifyListeners();
    }
  }
}
