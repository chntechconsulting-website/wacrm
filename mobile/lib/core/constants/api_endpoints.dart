class ApiEndpoints {
  // Production Base URL (Directly connects to live hosted backend)
  static const String productionBaseUrl = 'https://www.wapluscrm.in';

  // Development Base URLs
  // For Android Emulator: 10.0.2.2 maps to host machine localhost
  // For physical device on same LAN or desktop/web: 127.0.0.1 or LAN IP
  static const String defaultAndroidEmulatorUrl = 'http://10.0.2.2:8000';
  static const String defaultLocalhostUrl = 'http://127.0.0.1:8000';

  static String get defaultWebUrl {
    final host = Uri.base.host;
    if (host.isNotEmpty && host != 'localhost' && host != '127.0.0.1') {
      return 'http://$host:8000';
    }
    return productionBaseUrl;
  }

  // Base URL defaults directly to live production backend
  static String baseUrl = productionBaseUrl;

  // Base API prefix cleanly handles /api suffix and trailing slashes
  static String get apiPrefix {
    final cleaned = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    if (cleaned.endsWith('/api')) {
      return cleaned;
    }
    return '$cleaned/api';
  }

  // Auth
  static String get login => '$apiPrefix/auth/login';
  static String get token => '$apiPrefix/auth/token';
  static String get me => '$apiPrefix/auth/me';
  static String get logout => '$apiPrefix/auth/logout';
  static String get changePassword => '$apiPrefix/auth/change-password';

  // Users & Hierarchy
  static String get users => '$apiPrefix/users';
  static String get eligibleManagers => '$apiPrefix/users/eligible-managers';
  static String userById(int id) => '$apiPrefix/users/$id';
  static String resetPassword(int id) => '$apiPrefix/users/$id/reset-password';
  static String toggleUserStatus(int id) => '$apiPrefix/users/$id/toggle-status';
  static String get auditLogs => '$apiPrefix/users/audit-logs';

  // Employees
  static String get employees => '$apiPrefix/employees';

  // Leads
  static String get leads => '$apiPrefix/leads';
  static String get leadStats => '$apiPrefix/leads/stats';
  static String get myLeads => '$apiPrefix/leads/my';
  static String leadById(int id) => '$apiPrefix/leads/$id';
  static String leadStatus(int id) => '$apiPrefix/leads/$id/status';
  static String leadAssign(int id) => '$apiPrefix/leads/$id/assign';
  static String leadNotes(int id) => '$apiPrefix/leads/$id/notes';
  static String leadProformas(int id) => '$apiPrefix/leads/$id/proformas';
  static String leadWon(int id) => '$apiPrefix/leads/$id/won';
  static String leadAssignments(int id) => '$apiPrefix/leads/$id/assignments';
  static String downloadQuotation(int id) => '$apiPrefix/leads/$id/download-quotation';
  static String downloadProforma(int id) => '$apiPrefix/leads/$id/download-proforma';
  static String downloadInvoice(int id) => '$apiPrefix/leads/$id/download-invoice';

  // Customers
  static String get customers => '$apiPrefix/customers';
  static String customerById(int id) => '$apiPrefix/customers/$id';

  // Activities
  static String get activities => '$apiPrefix/activities';

  // Field Visits
  static String get fieldVisits => '$apiPrefix/field-visits';
  static String fieldVisitById(int id) => '$apiPrefix/field-visits/$id';
  static String employeeFieldVisits(int empId) => '$apiPrefix/employee-monitoring/$empId/field-visits';

  // Follow-ups & Reminders
  static String get followups => '$apiPrefix/followups';
  static String followupById(int id) => '$apiPrefix/followups/$id';
  static String get activeReminders => '$apiPrefix/followups/reminders/active';
  static String snoozeReminder(int id) => '$apiPrefix/followups/$id/snooze';
  static String dismissReminder(int id) => '$apiPrefix/followups/$id/dismiss-reminder';

  // Dashboard & Reports
  static String get dashboardStats => '$apiPrefix/reports/dashboard';
  static String get salesOverview => '$apiPrefix/reports/sales-overview';

  // Workflow & Deals
  static String dealSummary(int leadId) => '$apiPrefix/workflow/deal/$leadId/summary';
  static String dealProformas(int leadId) => '$apiPrefix/workflow/deal/$leadId/proformas';
  static String dealTimeline(int leadId) => '$apiPrefix/workflow/deal/$leadId/timeline';
  static String dealWon(int leadId) => '$apiPrefix/workflow/deal/$leadId/won';
  static String dealHandoffToFinance(int leadId) => '$apiPrefix/workflow/deal/$leadId/handoff-to-finance';
  static String get financeHandoffs => '$apiPrefix/workflow/finance/handoffs';
  static String financeHandoffById(int id) => '$apiPrefix/workflow/finance/handoffs/$id';
  static String confirmFinancePayment(int id) => '$apiPrefix/workflow/finance/handoffs/$id/confirm-payment';
  static String downloadFinanceInvoice(int id) => '$apiPrefix/workflow/finance/handoffs/$id/download-invoice';

  // Support Onboarding
  static String get supportHandoffs => '$apiPrefix/workflow/support/handoffs';
  static String supportHandoffById(int id) => '$apiPrefix/workflow/support/handoffs/$id';
  static String supportHandoffStatus(int id) => '$apiPrefix/workflow/support/handoffs/$id/status';
  static String supportHandoffReassign(int id) => '$apiPrefix/workflow/support/handoffs/$id/reassign';
  static String get supportManagers => '$apiPrefix/workflow/support-managers';

  // Quotations & Proformas (WAQuote)
  static String get waquoteDocuments => '$apiPrefix/integrations/waquote/documents';
  static String waquoteDocumentById(dynamic id) => '$apiPrefix/integrations/waquote/documents/$id';
  static String get waquoteBundles => '$apiPrefix/integrations/waquote/bundles';
  static String generateProforma(dynamic quoteId) => '$apiPrefix/integrations/waquote/quotations/$quoteId/generate-proforma';
  static String syncDestinationProforma(dynamic id) => '$apiPrefix/integrations/waquote/proformas/$id/sync-destination';
  static String downloadWaquotePdf(dynamic id) => '$apiPrefix/integrations/waquote/quotations/$id/download';
  static String downloadWaquoteProformaPdf(dynamic id) => '$apiPrefix/integrations/waquote/proformas/$id/download';
  static String downloadWaquoteInvoicePdf(dynamic id) => '$apiPrefix/integrations/waquote/invoices/$id/download';

  // IVR & Call Logs
  static String get ivrCalls => '$apiPrefix/ivr/calls';
  static String get initiateCall => '$apiPrefix/ivr/call';
  static String get manualCall => '$apiPrefix/ivr/manual-call';
  static String get manualCallLegacy => '$apiPrefix/ivr/calls/manual';
  static String ivrCallById(int id) => '$apiPrefix/ivr/calls/$id';
  static String ivrCallRecording(int id) => '$apiPrefix/ivr/calls/$id/recording';
  static String disconnectCall(int id) => '$apiPrefix/ivr/calls/$id/disconnect';

  // WhatsApp
  static String get whatsappConversations => '$apiPrefix/whatsapp/conversations';
  static String whatsappLeadMessages(int leadId) => '$apiPrefix/whatsapp/conversations/by-lead/$leadId';
  static String get whatsappSendMessage => '$apiPrefix/whatsapp/send-message';

  // Notifications
  static String get notifications => '$apiPrefix/notifications';
  static String markNotificationRead(int id) => '$apiPrefix/notifications/$id/read';
  static String get markAllNotificationsRead => '$apiPrefix/notifications/mark-all-read';
  static String get clearAllNotifications => '$apiPrefix/notifications/clear-all';
}
