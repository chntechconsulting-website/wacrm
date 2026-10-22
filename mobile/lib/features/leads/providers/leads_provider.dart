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
  String _selectedSource = 'ALL';
  String _selectedPriority = 'ALL';
  int? _assignedToFilter;
  bool? _isReinquiryFilter;
  String? _dateFilter;
  String? _startDate;
  String? _endDate;
  Map<String, int> _leadStats = {};
  int _currentSkip = 0;
  static const int _pageSize = 20;

  List<LeadModel> get leads => _leads;
  List<EmployeeOption> get employees => _employees;
  bool get isLoading => _isLoading;
  bool get isLoadingMore => _isLoadingMore;
  bool get hasMore => _hasMore;
  String? get errorMessage => _errorMessage;
  String get selectedStatus => _selectedStatus;
  String get selectedSource => _selectedSource;
  String get selectedPriority => _selectedPriority;
  int? get assignedToFilter => _assignedToFilter;
  bool? get isReinquiryFilter => _isReinquiryFilter;
  String? get dateFilter => _dateFilter;
  String? get searchQuery => _searchQuery;
  Map<String, int> get leadStats => _leadStats;
  LeadsRepository get repository => _repository;

  Future<void> fetchLeadStats() async {
    try {
      _leadStats = await _repository.getLeadStats();
      notifyListeners();
    } catch (_) {}
  }

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
        source: _selectedSource == 'ALL' ? null : _selectedSource,
        priority: _selectedPriority == 'ALL' ? null : _selectedPriority,
        assignedTo: _assignedToFilter,
        isReinquiry: _isReinquiryFilter,
        dateFilter: _dateFilter,
        startDate: _startDate,
        endDate: _endDate,
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
    _searchQuery = query.trim().isEmpty ? null : query.trim();
    fetchLeads(refresh: true);
  }

  void setStatusFilter(String status) {
    _selectedStatus = status;
    fetchLeads(refresh: true);
  }

  void setSourceFilter(String source) {
    _selectedSource = source;
    fetchLeads(refresh: true);
  }

  void setPriorityFilter(String priority) {
    _selectedPriority = priority;
    fetchLeads(refresh: true);
  }

  void setAssignedToFilter(int? empId) {
    _assignedToFilter = empId;
    fetchLeads(refresh: true);
  }

  void setIsReinquiryFilter(bool? reinquiry) {
    _isReinquiryFilter = reinquiry;
    fetchLeads(refresh: true);
  }

  void setDateFilter(String? date) {
    _dateFilter = date;
    fetchLeads(refresh: true);
  }

  void clearFilters() {
    _selectedStatus = 'ALL';
    _selectedSource = 'ALL';
    _selectedPriority = 'ALL';
    _assignedToFilter = null;
    _isReinquiryFilter = null;
    _dateFilter = null;
    _startDate = null;
    _endDate = null;
    _searchQuery = null;
    fetchLeads(refresh: true);
    fetchLeadStats();
  }

  Future<List<SupportManagerOption>> getSupportManagers() async {
    return _repository.getSupportManagers();
  }

  Future<List<ProformaOption>> getLeadProformas(int leadId) async {
    return _repository.getLeadProformas(leadId);
  }

  Future<bool> markDealWon(int leadId, Map<String, dynamic> payload) async {
    try {
      await _repository.markLeadWon(leadId, payload);
      final index = _leads.indexWhere((l) => l.id == leadId);
      if (index != -1) {
        _leads[index] = _leads[index].copyWith(status: 'WON');
      }
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
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
