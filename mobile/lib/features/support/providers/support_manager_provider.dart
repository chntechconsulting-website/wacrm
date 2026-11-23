import 'package:flutter/material.dart';

import '../data/support_repository.dart';
import '../models/support_models.dart';

class SupportTeamPerformanceRow {
  final SupportEmployee employee;
  final int assignedCustomers;
  final int openIssues;
  final int backupCustomers;

  const SupportTeamPerformanceRow({
    required this.employee,
    required this.assignedCustomers,
    required this.openIssues,
    required this.backupCustomers,
  });
}

class SupportManagerProvider extends ChangeNotifier {
  final SupportRepository _repository = SupportRepository();

  SupportManagerOverview? _overview;
  List<SupportEmployee> _employees = [];
  List<SupportLeave> _leaves = [];
  List<SupportBackupCustomer> _backupCustomers = [];
  List<SupportCustomer> _assignedCustomers = [];
  int _assignedTotal = 0;
  bool _isLoading = false;
  String? _errorMessage;

  SupportManagerOverview? get overview => _overview;
  List<SupportEmployee> get employees => List.unmodifiable(_employees);
  List<SupportLeave> get leaves => List.unmodifiable(_leaves);
  List<SupportBackupCustomer> get backupCustomers =>
      List.unmodifiable(_backupCustomers);
  List<SupportCustomer> get assignedCustomers =>
      List.unmodifiable(_assignedCustomers);
  int get assignedTotal => _assignedTotal;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  List<SupportCustomer> get trialCustomers {
    final trials = _assignedCustomers
        .where((customer) =>
            customer.trialEndDate != null &&
            (customer.trialStatus ?? '').toUpperCase() != 'NONE')
        .toList();
    trials.sort((a, b) {
      final aDays = a.trialDaysRemaining ?? 9999;
      final bDays = b.trialDaysRemaining ?? 9999;
      return aDays.compareTo(bDays);
    });
    return List.unmodifiable(trials);
  }

  List<SupportTeamPerformanceRow> get teamPerformance {
    final issueCounts = <int, int>{};
    for (final issue in _overview?.pendingIssues ?? const <SupportPendingIssue>[]) {
      final id = issue.handlingEmployeeId;
      if (id != null) {
        issueCounts[id] = (issueCounts[id] ?? 0) + 1;
      }
    }
    final backupCounts = <int, int>{};
    for (final coverage in _overview?.activeCoverage ?? const <SupportCoverage>[]) {
      final id = coverage.backupEmployeeId;
      if (id != null) {
        backupCounts[id] = (backupCounts[id] ?? 0) + 1;
      }
    }
    final rows = _employees.map((employee) {
      final localAssignments = _assignedCustomers
          .where((customer) =>
              customer.assignedSupportExecutiveId == employee.employeeId)
          .length;
      return SupportTeamPerformanceRow(
        employee: employee,
        assignedCustomers: employee.assignedCustomerCount > 0
            ? employee.assignedCustomerCount
            : localAssignments,
        openIssues: issueCounts[employee.employeeId] ?? 0,
        backupCustomers: employee.temporaryCoverageCount > 0
            ? employee.temporaryCoverageCount
            : (backupCounts[employee.employeeId] ?? 0),
      );
    }).toList();
    rows.sort((a, b) => b.assignedCustomers.compareTo(a.assignedCustomers));
    return List.unmodifiable(rows);
  }

  Future<void> fetchAll({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }
    try {
      final results = await Future.wait<dynamic>([
        _repository.getManagerOverview(),
        _repository.getSupportEmployees(),
        _repository.getLeaves(includePast: true),
        _repository.getBackupCustomers(),
      ]);
      _overview = results[0] as SupportManagerOverview;
      _employees = results[1] as List<SupportEmployee>;
      _leaves = results[2] as List<SupportLeave>;
      _backupCustomers = results[3] as List<SupportBackupCustomer>;
      await _loadAssignedCustomers();
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> _loadAssignedCustomers() async {
    const pageSize = 200;
    const maxPages = 5;
    final loaded = <SupportCustomer>[];
    var total = 0;
    for (var page = 0; page < maxPages; page++) {
      final result = await _repository.getAssignedCustomers(
        skip: page * pageSize,
        limit: pageSize,
      );
      total = result.total;
      loaded.addAll(result.items);
      if (result.items.isEmpty || loaded.length >= total) break;
    }
    _assignedCustomers = loaded;
    _assignedTotal = total;
  }
}
