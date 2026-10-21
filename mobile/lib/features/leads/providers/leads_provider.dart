import 'package:flutter/material.dart';
import '../data/leads_repository.dart';
import '../models/lead_model.dart';

class LeadsProvider extends ChangeNotifier {
  final LeadsRepository _repository = LeadsRepository();

  List<LeadModel> _leads = [];
  List<EmployeeOption> _employees = [];
  bool _isLoading = false;
  bool _isLoadingMore = false;
  bool _hasMore = true;
  String? _errorMessage;

  String? _searchQuery;
  String _selectedStatus = 'ALL';
  String _selectedPriority = 'ALL';
  int _currentSkip = 0;
  static const int _pageSize = 20;

  List<LeadModel> get leads => _leads;
  List<EmployeeOption> get employees => _employees;
  bool get isLoading => _isLoading;
  bool get isLoadingMore => _isLoadingMore;
  bool get hasMore => _hasMore;
  String? get errorMessage => _errorMessage;
  String get selectedStatus => _selectedStatus;
  String get selectedPriority => _selectedPriority;

  Future<void> fetchLeads({bool refresh = false}) async {
    if (refresh) {
      _currentSkip = 0;
      _hasMore = true;
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    } else {
      if (_isLoadingMore || !_hasMore) return;
      _isLoadingMore = true;
      notifyListeners();
    }

    try {
      final fetched = await _repository.getLeads(
        skip: _currentSkip,
        limit: _pageSize,
        search: _searchQuery,
        status: _selectedStatus == 'ALL' ? null : _selectedStatus,
        priority: _selectedPriority == 'ALL' ? null : _selectedPriority,
      );

      if (refresh) {
        _leads = fetched;
      } else {
        _leads.addAll(fetched);
      }

      if (fetched.length < _pageSize) {
        _hasMore = false;
      } else {
        _currentSkip += fetched.length;
      }
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      _isLoadingMore = false;
      notifyListeners();
    }
  }

  void search(String query) {
    _searchQuery = query.trim();
    fetchLeads(refresh: true);
  }

  void setStatusFilter(String status) {
    _selectedStatus = status;
    fetchLeads(refresh: true);
  }

  void setPriorityFilter(String priority) {
    _selectedPriority = priority;
    fetchLeads(refresh: true);
  }

  Future<void> fetchEmployees() async {
    if (_employees.isNotEmpty) return;
    try {
      _employees = await _repository.getEmployees();
      notifyListeners();
    } catch (_) {}
  }

  Future<LeadModel?> updateLeadStatus(int leadId, String status) async {
    try {
      final updated = await _repository.updateLeadStatus(leadId, status);
      final index = _leads.indexWhere((l) => l.id == leadId);
      if (index != -1) {
        _leads[index] = updated;
        notifyListeners();
      }
      return updated;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return null;
    }
  }

  Future<bool> assignLead(int leadId, int employeeId, {String? notes}) async {
    try {
      final updated = await _repository.assignLead(leadId, employeeId, notes: notes);
      final index = _leads.indexWhere((l) => l.id == leadId);
      if (index != -1) {
        _leads[index] = updated;
        notifyListeners();
      }
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> createLead(Map<String, dynamic> data) async {
    try {
      final created = await _repository.createLead(data);
      _leads.insert(0, created);
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> updateLead(int id, Map<String, dynamic> data) async {
    try {
      final updated = await _repository.updateLead(id, data);
      final index = _leads.indexWhere((l) => l.id == id);
      if (index != -1) {
        _leads[index] = updated;
        notifyListeners();
      }
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> deleteLead(int id) async {
    try {
      await _repository.deleteLead(id);
      _leads.removeWhere((l) => l.id == id);
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }
}
