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
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] ?? 0,
      username: json['username'] ?? '',
      role: (json['role'] ?? 'EMPLOYEE').toString().toUpperCase(),
      department: json['department'],
      reportingManagerId: json['reporting_manager_id'] ?? json['manager_id'],
      reportingManagerName: json['reporting_manager_name'] ?? json['manager_name'],
      reportingManagerRole: json['reporting_manager_role'],
      employeeId: json['employee_id'],
      name: json['name'] ?? json['username'] ?? '',
      email: json['email'] ?? '',
      phone: json['phone'],
      status: json['status'] ?? (json['is_active'] == true ? 'ACTIVE' : 'INACTIVE'),
      isActive: json['is_active'] ?? (json['status'] == 'ACTIVE'),
      directReportsCount: json['direct_reports_count'] ?? 0,
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
    };
  }

  // Role Checks matching backend hierarchy service
  bool get isAdmin => role == 'ADMIN';
  bool get isSalesManager => role == 'SALES_MANAGER' || role == 'MANAGER';
  bool get isSalesExecutive => role == 'SALES_EXECUTIVE' || role == 'SALES' || role == 'EMPLOYEE';
  bool get isSupportManager => role == 'SUPPORT_MANAGER';
  bool get isSupportExecutive => role == 'SUPPORT_EXECUTIVE' || role == 'SUPPORT';
  bool get isFinance => role == 'FINANCE';

  // Cross-team visibility permissions (strictly mirror backend rules)
  bool get canViewSales => isAdmin || isSalesManager || isSalesExecutive;
  bool get canViewSupport => isAdmin || isSupportManager || isSupportExecutive;
  bool get canViewFinance => isAdmin || isFinance;
  bool get canManageUsers => isAdmin;
  bool get canDeleteLeads => isAdmin || isSalesManager;

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
