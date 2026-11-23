import 'package:flutter/material.dart';

import '../data/support_repository.dart';
import '../models/support_models.dart';
import '../../calls/data/calls_repository.dart';
import '../../calls/models/call_log_model.dart';

class SupportCustomersProvider extends ChangeNotifier {
  final SupportRepository _repository = SupportRepository();

  final List<SupportCustomer> _customers = [];
  int _total = 0;
  int _page = 1;
  final int _limit = 30;
  bool _isLoading = false;
  bool _isLoadingMore = false;
  String? _errorMessage;
  String _search = '';
  String _statusFilter = 'ALL';
  String _priorityFilter = 'ALL';
  String _sourceFilter = 'ALL';

  SupportHistory? _selectedHistory;
  SupportPurchaseDetails? _selectedPurchaseDetails;
  List<CallLogModel> _selectedCalls = [];
  bool _isDetailLoading = false;
  String? _detailError;
  int? _detailLeadId;

  List<SupportBackupCustomer> _backupCustomers = [];
  bool _isBackupLoading = false;
  String? _backupError;

  SupportAssignmentState? _supportAssignment;
  bool _isAssignmentLoading = false;
  String? _assignmentError;
  List<SupportAssignTeamMember> _assignTeamMembers = [];
  bool _isAssignTeamLoading = false;
  bool _isSavingAssignment = false;

  List<SupportCustomer> get customers => List.unmodifiable(_customers);
  int get total => _total;
  int get page => _page;
  bool get hasMore => _customers.length < _total;
  bool get isLoading => _isLoading;
  bool get isLoadingMore => _isLoadingMore;
  String? get errorMessage => _errorMessage;
  String get search => _search;
  String get statusFilter => _statusFilter;
  String get priorityFilter => _priorityFilter;
  String get sourceFilter => _sourceFilter;
  SupportHistory? get selectedHistory => _selectedHistory;
  SupportPurchaseDetails? get selectedPurchaseDetails =>
      _selectedPurchaseDetails ?? _selectedHistory?.purchaseDetails;
  List<CallLogModel> get selectedCalls => List.unmodifiable(_selectedCalls);
  bool get isDetailLoading => _isDetailLoading;
  String? get detailError => _detailError;
  int? get detailLeadId => _detailLeadId;
  List<SupportBackupCustomer> get backupCustomers =>
      List.unmodifiable(_backupCustomers);
  bool get isBackupLoading => _isBackupLoading;
  String? get backupError => _backupError;
  SupportAssignmentState? get supportAssignment => _supportAssignment;
  bool get isAssignmentLoading => _isAssignmentLoading;
  String? get assignmentError => _assignmentError;
  List<SupportAssignTeamMember> get assignTeamMembers =>
      List.unmodifiable(_assignTeamMembers);
  bool get isAssignTeamLoading => _isAssignTeamLoading;
  bool get isSavingAssignment => _isSavingAssignment;

  Future<void> fetchCustomers({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }
    try {
      final result = await _repository.getAssignedCustomers(
        search: _search,
        status: _statusFilter,
        priority: _priorityFilter,
        source: _sourceFilter,
        skip: 0,
        limit: _limit,
      );
      _customers
        ..clear()
        ..addAll(result.items);
      _total = result.total;
      _page = result.page;
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadMore() async {
    if (_isLoadingMore || !hasMore || _isLoading) return;
    _isLoadingMore = true;
    notifyListeners();
    try {
      final result = await _repository.getAssignedCustomers(
        search: _search,
        status: _statusFilter,
        priority: _priorityFilter,
        source: _sourceFilter,
        skip: _customers.length,
        limit: _limit,
      );
      final knownIds = _customers.map((customer) => customer.leadId).toSet();
      for (final customer in result.items) {
        if (knownIds.add(customer.leadId)) {
          _customers.add(customer);
        }
      }
      _total = result.total;
      _page = result.page;
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoadingMore = false;
      notifyListeners();
    }
  }

  void setSearch(String value) {
    _search = value;
  }

  void setStatusFilter(String value) {
    _statusFilter = value;
    fetchCustomers();
  }

  void setPriorityFilter(String value) {
    _priorityFilter = value;
    fetchCustomers();
  }

  void setSourceFilter(String value) {
    _sourceFilter = value;
    fetchCustomers();
  }

  void clearFilters() {
    _statusFilter = 'ALL';
    _priorityFilter = 'ALL';
    _sourceFilter = 'ALL';
    _search = '';
    fetchCustomers();
  }

  SupportCustomer? findCustomer(int leadId) {
    for (final customer in _customers) {
      if (customer.leadId == leadId) return customer;
    }
    return null;
  }

  Future<SupportAssignmentState?> _safeAssignment(int leadId) async {
    try {
      return await _repository.getSupportAssignment(leadId);
    } catch (_) {
      return null;
    }
  }

  Future<void> loadCustomerDetail(int leadId, {int? customerId}) async {
    _detailLeadId = leadId;
    _isDetailLoading = true;
    _detailError = null;
    _selectedPurchaseDetails = null;
    _selectedCalls = [];
    _assignmentError = null;
    notifyListeners();
    try {
      final results = await Future.wait<dynamic>([
        _repository.getCustomerHistory(leadId, customerId: customerId),
        CallsRepository()
            .getCalls(leadId: leadId, pageSize: 50)
            .catchError((_) => <CallLogModel>[]),
        _safeAssignment(leadId),
      ]);
      final history = results[0] as SupportHistory;
      _selectedHistory = history;
      _selectedCalls = results[1] as List<CallLogModel>;
      _supportAssignment = results[2] as SupportAssignmentState?;
      if (history.purchaseDetails == null) {
        _selectedPurchaseDetails = await _repository.getPurchaseDetails(leadId);
      }
      _detailError = null;
    } catch (e) {
      _selectedHistory = null;
      _detailError = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isDetailLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadSupportAssignment(int leadId) async {
    _isAssignmentLoading = true;
    _assignmentError = null;
    notifyListeners();
    try {
      _supportAssignment = await _repository.getSupportAssignment(leadId);
    } catch (e) {
      _assignmentError = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isAssignmentLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadAssignTeamMembers() async {
    _isAssignTeamLoading = true;
    notifyListeners();
    try {
      _assignTeamMembers =
          await _repository.getSupportAssignTeamMembers();
    } catch (_) {
      _assignTeamMembers = [];
    } finally {
      _isAssignTeamLoading = false;
      notifyListeners();
    }
  }

  /// Returns `null` on success, or the backend error message.
  Future<String?> assignSupportOwner({
    required int leadId,
    required int employeeId,
    String? reason,
  }) async {
    _isSavingAssignment = true;
    notifyListeners();
    try {
      _supportAssignment = await _repository.assignSupportOwner(
        leadId: leadId,
        employeeId: employeeId,
        reason: reason,
      );
      await fetchCustomers(showLoading: false);
      await loadCustomerDetail(
        leadId,
        customerId: _selectedHistory?.customerId,
      );
      return null;
    } catch (e) {
      final message = e.toString().replaceAll('ApiException: ', '');
      _assignmentError = message;
      return message;
    } finally {
      _isSavingAssignment = false;
      notifyListeners();
    }
  }

  Future<void> refreshCustomerDetail() async {
    final leadId = _detailLeadId ?? _selectedHistory?.leadId;
    if (leadId == null) return;
    await loadCustomerDetail(
      leadId,
      customerId: _selectedHistory?.customerId,
    );
  }

  Future<bool> addInteraction(
    int leadId,
    Map<String, dynamic> payload,
  ) async {
    try {
      await _repository.addInteraction(leadId, payload);
      await loadCustomerDetail(
        leadId,
        customerId: _selectedHistory?.customerId,
      );
      await fetchCustomers(showLoading: false);
      return true;
    } catch (e) {
      _detailError = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> addPoc(
    int leadId,
    Map<String, dynamic> payload, {
    int? customerId,
  }) async {
    try {
      await _repository.createCustomerPoc(
        leadId,
        payload,
        customerId: customerId,
      );
      await loadCustomerDetail(leadId, customerId: customerId);
      return true;
    } catch (e) {
      _detailError = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> setPrimaryPoc(int pocId) async {
    final leadId = _detailLeadId;
    if (leadId == null) return false;
    try {
      await _repository.setPrimaryPoc(pocId);
      await loadCustomerDetail(
        leadId,
        customerId: _selectedHistory?.customerId,
      );
      return true;
    } catch (e) {
      _detailError = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> updatePoc(int pocId, Map<String, dynamic> payload) async {
    final leadId = _detailLeadId;
    if (leadId == null) return false;
    try {
      await _repository.updateCustomerPoc(pocId, payload);
      await loadCustomerDetail(
        leadId,
        customerId: _selectedHistory?.customerId,
      );
      return true;
    } catch (e) {
      _detailError = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<void> clearDetail() {
    _selectedHistory = null;
    _selectedPurchaseDetails = null;
    _selectedCalls = [];
    _supportAssignment = null;
    _assignmentError = null;
    _detailError = null;
    _detailLeadId = null;
    notifyListeners();
    return Future.value();
  }

  Future<void> fetchBackupCustomers({bool showLoading = true}) async {
    if (showLoading) {
      _isBackupLoading = true;
      _backupError = null;
      notifyListeners();
    }
    try {
      _backupCustomers = await _repository.getBackupCustomers();
      _backupError = null;
    } catch (e) {
      _backupError = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isBackupLoading = false;
      notifyListeners();
    }
  }
}
