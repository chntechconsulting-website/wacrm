class UserModel {
  final int id;
  final String username;
  final String role;
  final String? department;
  final int? reportingManagerId;
  final String? reportingManagerName;
  final String? reportingManagerRole;
  final int? employeeId;
  final String name;
  final String email;
  final String? phone;
  final String status;
  final bool isActive;
  final int directReportsCount;

  /// Backend-resolved role permission matrix: `module -> {has_access,
  /// can_view, can_create, ... , view_scope}`. This is the same payload the
  /// web app uses, so mobile never has to hardcode role capabilities.
  final Map<String, dynamic> permissions;

  UserModel({
    required this.id,
    required this.username,
    required this.role,
    this.department,
    this.reportingManagerId,
    this.reportingManagerName,
    this.reportingManagerRole,
    this.employeeId,
    required this.name,
    required this.email,
    this.phone,
    required this.status,
    required this.isActive,
    this.directReportsCount = 0,
    this.permissions = const {},
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    final rawPermissions = json['permissions'];
    return UserModel(
      id: json['id'] ?? 0,
      username: json['username'] ?? '',
      role: (json['role'] ?? 'EMPLOYEE').toString().toUpperCase(),
      department: json['department'],
      reportingManagerId: json['reporting_manager_id'] ?? json['manager_id'],
      reportingManagerName:
          json['reporting_manager_name'] ?? json['manager_name'],
      reportingManagerRole: json['reporting_manager_role'],
      employeeId: json['employee_id'],
      name: json['name'] ?? json['username'] ?? '',
      email: json['email'] ?? '',
      phone: json['phone'],
      status:
          json['status'] ?? (json['is_active'] == true ? 'ACTIVE' : 'INACTIVE'),
      isActive: json['is_active'] ?? (json['status'] == 'ACTIVE'),
      directReportsCount: json['direct_reports_count'] ?? 0,
      permissions: rawPermissions is Map
          ? Map<String, dynamic>.from(rawPermissions)
          : const {},
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'role': role,
      'department': department,
      'reporting_manager_id': reportingManagerId,
      'reporting_manager_name': reportingManagerName,
      'reporting_manager_role': reportingManagerRole,
      'employee_id': employeeId,
      'name': name,
      'email': email,
      'phone': phone,
      'status': status,
      'is_active': isActive,
      'direct_reports_count': directReportsCount,
      'permissions': permissions,
    };
  }

  // Role Checks matching backend hierarchy service
  bool get isAdmin => role == 'ADMIN';
  bool get isSalesManager => role == 'SALES_MANAGER' || role == 'MANAGER';
  bool get isSalesExecutive =>
      role == 'SALES_EXECUTIVE' || role == 'SALES' || role == 'EMPLOYEE';
  bool get isSupportManager => role == 'SUPPORT_MANAGER';
  bool get isSupportExecutive =>
      role == 'SUPPORT_EXECUTIVE' || role == 'SUPPORT';
  bool get isFinance => role == 'FINANCE';

  bool get isSupportDepartment =>
      (department ?? '').trim().toUpperCase() == 'SUPPORT';

  /// A legacy `MANAGER` account placed in the Support department is a Support
  /// manager on the backend, never a Sales manager.
  bool get isSupportManagerWorkspace =>
      !isAdmin &&
      (isSupportManager || (isSupportDepartment && role == 'MANAGER'));

  /// Support employees and managers share the Support mobile workspace.
  bool get isSupportWorkspace =>
      !isAdmin &&
      (isSupportManagerWorkspace || isSupportExecutive || isSupportDepartment);

  bool get isSalesWorkspace =>
      !isSupportWorkspace && (isAdmin || isSalesManager || isSalesExecutive);

  // Cross-team visibility permissions (strictly mirror backend rules)
  bool get canViewSales => isAdmin || isSalesManager || isSalesExecutive;
  bool get canViewSupport => isAdmin || isSupportManager || isSupportExecutive;
  bool get canViewFinance => isAdmin || isFinance;
  bool get canManageUsers => isAdmin;
  bool get canDeleteLeads => isAdmin || isSalesManager;

  Map<String, dynamic>? permissionFor(String module) {
    final value = permissions[module.trim().toLowerCase()];
    return value is Map ? Map<String, dynamic>.from(value) : null;
  }

  /// Checks the backend permission matrix returned by `/auth/me` and
  /// `/auth/login`. Admin remains a superuser. When an older cached session has
  /// no permission payload yet, conservative role defaults are used until the
  /// next `/auth/me` refresh replaces them.
  bool hasPermission(String module, String action) {
    if (isAdmin) return true;
    final permission = permissionFor(module);
    if (permission == null) {
      return _legacyPermission(module, action);
    }
    if (permission['has_access'] != true) return false;
    return permission['can_${action.trim().toLowerCase()}'] == true;
  }

  String viewScopeFor(String module) {
    if (isAdmin) return 'company';
    final permission = permissionFor(module);
    if (permission == null || permission['has_access'] != true) {
      return 'none';
    }
    final scope = (permission['view_scope'] ?? 'own').toString().trim();
    return scope.isEmpty ? 'own' : scope.toLowerCase();
  }

  bool get canViewSupportFollowups => hasPermission('followups', 'view');
  bool get canCreateSupportFollowup => hasPermission('followups', 'create');
  bool get canEditSupportFollowup => hasPermission('followups', 'edit');
  bool get canAddSupportInteraction =>
      hasPermission('support_tickets', 'create') ||
      hasPermission('activities', 'create');
  bool get canEditSupportTicket => hasPermission('support_tickets', 'edit');
  bool get canManageSupportPoc =>
      hasPermission('support_tickets', 'edit') ||
      hasPermission('support_tickets', 'create');
  bool get canCallSupportCustomer =>
      hasPermission('calls', 'call') ||
      hasPermission('customers', 'call') ||
      hasPermission('leads', 'call');

  bool _legacyPermission(String module, String action) {
    final mod = module.trim().toLowerCase();
    final act = action.trim().toLowerCase();
    const supportModules = {
      'dashboard',
      'customers',
      'contacts',
      'support_tickets',
      'calls',
      'whatsapp',
      'activities',
      'followups',
      'leads',
    };
    if (isSupportWorkspace) {
      if (!supportModules.contains(mod)) return false;
      if (act == 'view') return true;
      if (act == 'create' || act == 'edit') {
        return {
          'support_tickets',
          'activities',
          'followups',
          'calls',
          'whatsapp',
        }.contains(mod);
      }
      if (act == 'call') {
        return {'calls', 'customers', 'leads'}.contains(mod);
      }
      return false;
    }
    if (isSalesWorkspace) {
      if (mod == 'dashboard' || mod == 'leads' || mod == 'followups') {
        return act == 'view' || act == 'create' || act == 'edit';
      }
      if (mod == 'calls') {
        return act == 'view' || act == 'create' || act == 'call';
      }
    }
    return false;
  }

  // Clean, consistent Department display label
  String get departmentDisplay {
    final d = (department ?? '').toUpperCase().trim();
    if (d == 'ADMIN' || d == 'ADMINISTRATION') return 'Administration';
    if (d == 'SALES') return 'Sales';
    if (d == 'SUPPORT') return 'Support';
    if (d == 'FINANCE') return 'Finance';
    if (d.isNotEmpty) return d[0].toUpperCase() + d.substring(1).toLowerCase();
    if (isAdmin) return 'Administration';
    if (isSupportManager || isSupportExecutive) return 'Support';
    if (isFinance) return 'Finance';
    return 'Sales';
  }
}
