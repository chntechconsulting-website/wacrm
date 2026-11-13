import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { DialerProvider } from './context/DialerContext';
import { FollowupReminderProvider } from './context/FollowupReminderContext';
import { PingoPopupProvider } from './context/PingoPopupContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';

// Route-level code splitting keeps the initial login/dashboard payload small
// instead of shipping every CRM module in one 4 MB bundle.
const lazyPage = (loader) => React.lazy(loader);

// Public Auth & Compliance Pages
const Login = lazyPage(() => import('./pages/Login'));
const PrivacyPolicyPage = lazyPage(() => import('./pages/Public/PrivacyPolicyPage'));
const TermsAndConditionsPage = lazyPage(() => import('./pages/Public/TermsAndConditionsPage'));
const DataDeletionPage = lazyPage(() => import('./pages/Public/DataDeletionPage'));

// CRM Module Pages
const DashboardPage = lazyPage(() => import('./pages/Dashboard/DashboardPage'));

// LEADS Pages
const LeadsPage = lazyPage(() => import('./pages/Leads/LeadsPage'));
const CreateLeadPage = lazyPage(() => import('./pages/Leads/CreateLeadPage'));
const ImportLeadsPage = lazyPage(() => import('./pages/Leads/ImportLeadsPage'));
const MetaLeadsPage = lazyPage(() => import('./pages/Leads/MetaLeadsPage'));
const WhatsAppAdLeadsPage = lazyPage(() => import('./pages/Leads/WhatsAppAdLeadsPage'));
const WebsiteLeadsPage = lazyPage(() => import('./pages/Leads/WebsiteLeadsPage'));
const ManualLeadsPage = lazyPage(() => import('./pages/Leads/ManualLeadsPage'));
const MyLeadsPage = lazyPage(() => import('./pages/Leads/MyLeadsPage'));

// WEBSITE ENQUIRIES Pages
const BrochureDownloadPeoplePage = lazyPage(() => import('./pages/WebsiteEnquiries/BrochureDownloadPeoplePage'));

// COMMUNICATION Pages
const CallLogsPage = lazyPage(() => import('./pages/Communication/CallLogsPage'));
const FollowupsPage = lazyPage(() => import('./pages/Communication/FollowupsPage'));
const ActivitiesPage = lazyPage(() => import('./pages/Communication/ActivitiesPage'));
const WhatsAppPage = lazyPage(() => import('./pages/Communication/WhatsAppPage'));

// ORGANIZATION Pages
const CompaniesPage = lazyPage(() => import('./pages/Organization/CompaniesPage'));
const ContactsPage = lazyPage(() => import('./pages/Organization/ContactsPage'));

// REPORTS & ANALYTICS Pages
const ReportsPage = lazyPage(() => import('./pages/Reports/ReportsPage'));
const AnalyticsPage = lazyPage(() => import('./pages/Reports/AnalyticsPage'));

// SETTINGS & USERS Pages
const SettingsPage = lazyPage(() => import('./pages/Settings/SettingsPage'));
const IntegrationsPage = lazyPage(() => import('./pages/Settings/IntegrationsPage'));
const MetaIntegrationPage = lazyPage(() => import('./pages/Settings/MetaIntegrationPage'));
const WhatsAppConnectionPage = lazyPage(() => import('./pages/Settings/WhatsAppConnectionPage'));
const UsersRolesPage = lazyPage(() => import('./pages/Settings/UsersRolesPage'));
const ProfilePage = lazyPage(() => import('./pages/Profile/ProfilePage'));
const NotificationsPage = lazyPage(() => import('./pages/Settings/NotificationsPage'));
const DeleteRequestsPage = lazyPage(() => import('./pages/Settings/DeleteRequestsPage'));

// Admin Panel Pages
const AdminPanelPage = lazyPage(() => import('./pages/Admin/AdminPanelPage'));

// TEAM INSIGHTS & EMPLOYEE MONITORING Pages
const TeamInsightsPage = lazyPage(() => import('./pages/TeamInsights/TeamInsightsPage'));
const EmployeeMonitoringPage = lazyPage(() => import('./pages/EmployeeMonitoring/index'));
const EmployeeDetailPage = lazyPage(() => import('./pages/EmployeeMonitoring/EmployeeDetailPage'));

// WA QUOTES & INVOICES Pages
const WAQuotesPage = lazyPage(() => import('./pages/WAQuotes/WAQuotesPage'));

// WORKFLOW Pages (Sales -> Finance -> Support)
const FinanceQueuePage = lazyPage(() => import('./pages/Workflow/FinanceQueuePage'));
const SupportQueuePage = lazyPage(() => import('./pages/Workflow/SupportQueuePage'));
const SupportAssignedLeadsPage = lazyPage(() => import('./pages/Support/SupportAssignedLeadsPage'));
const SupportManagerPage = lazyPage(() => import('./pages/Support/SupportManagerPage'));
const BackupCustomersPage = lazyPage(() => import('./pages/Support/BackupCustomersPage'));

// FINANCE DEPARTMENT Pages
const InvoicesPage = lazyPage(() => import('./pages/Finance/InvoicesPage'));
const PaymentsPage = lazyPage(() => import('./pages/Finance/PaymentsPage'));
const CustomerPurchasesPage = lazyPage(() => import('./pages/Finance/CustomerPurchasesPage'));
const SubscriptionsPage = lazyPage(() => import('./pages/Finance/SubscriptionsPage'));
const RefundsPage = lazyPage(() => import('./pages/Finance/RefundsPage'));
const FinancialReportsPage = lazyPage(() => import('./pages/Finance/FinancialReportsPage'));

// 404 Not Found Page
const NotFoundPage = lazyPage(() => import('./pages/NotFound/NotFoundPage'));

const RouteFallback = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '40vh',
    color: '#64748b',
    fontSize: '0.9rem',
    fontWeight: 600
  }}>
    Loading…
  </div>
);

function App() {
  return (
    <AuthProvider>
      <DialerProvider>
        <Router>
          <FollowupReminderProvider>
            <PingoPopupProvider>
              <Suspense fallback={<RouteFallback />}>
              <Routes>
          {/* Public Authentication & Meta Compliance Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/privacy" element={<PrivacyPolicyPage />} />
          <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
          <Route path="/terms" element={<TermsAndConditionsPage />} />
          <Route path="/terms-and-conditions" element={<TermsAndConditionsPage />} />
          <Route path="/data-deletion" element={<DataDeletionPage />} />

          {/* Protected Main CRM Application Routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              {/* Root & Index redirect to dashboard */}
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />

              {/* Dashboard */}
              <Route element={<ProtectedRoute requiredModule="dashboard" />}>
                <Route path="/dashboard" element={<DashboardPage />} />
              </Route>

              {/* LEADS Section Routes */}
              <Route path="/leads" element={<LeadsPage />} />
              <Route path="/leads/create" element={<CreateLeadPage />} />
              <Route path="/leads/import" element={<ImportLeadsPage />} />
              <Route path="/leads/meta" element={<MetaLeadsPage />} />
              <Route path="/leads/whatsapp-ads" element={<WhatsAppAdLeadsPage />} />
              <Route path="/leads/website" element={<WebsiteLeadsPage />} />
              <Route path="/leads/manual" element={<ManualLeadsPage />} />
              <Route path="/leads/my" element={<MyLeadsPage />} />

              {/* WEBSITE ENQUIRIES Section Routes */}
              <Route element={<ProtectedRoute requiredModule="brochure_downloads" />}>
                <Route path="/website-enquiries/brochure-downloads" element={<BrochureDownloadPeoplePage />} />
                <Route path="/brochure-downloads" element={<BrochureDownloadPeoplePage />} />
              </Route>

              {/* COMMUNICATION Section Routes */}
              <Route path="/communication/calls" element={<CallLogsPage />} />
              <Route path="/communication/followups" element={<FollowupsPage />} />
              <Route path="/communication/activities" element={<ActivitiesPage />} />
              <Route element={<ProtectedRoute requiredModule="whatsapp" />}>
                <Route path="/communication/whatsapp" element={<WhatsAppPage />} />
              </Route>

              {/* TEAM INSIGHTS & EMPLOYEE MONITORING Section Routes */}
              <Route path="/team-insights" element={<TeamInsightsPage />} />
              <Route path="/employee-monitoring" element={<TeamInsightsPage />} />
              <Route path="/employee-monitoring/field-tracker" element={<EmployeeMonitoringPage />} />
              <Route path="/employee-monitoring/:employeeId" element={<EmployeeDetailPage />} />

              {/* WA QUOTES & INVOICES Section Routes */}
              <Route path="/waquotes" element={<ErrorBoundary><WAQuotesPage /></ErrorBoundary>} />

              {/* WORKFLOW (Sales -> Finance -> Support) Section Routes */}
              {/* FINANCE DEPARTMENT Section Routes */}
              <Route path="/finance" element={<Navigate to="/dashboard" replace />} />
              <Route path="/finance/invoices" element={<ErrorBoundary><InvoicesPage /></ErrorBoundary>} />
              <Route path="/finance/payments" element={<ErrorBoundary><PaymentsPage /></ErrorBoundary>} />
              <Route path="/finance/customer-purchases" element={<ErrorBoundary><CustomerPurchasesPage /></ErrorBoundary>} />
              <Route path="/finance/subscriptions" element={<ErrorBoundary><SubscriptionsPage /></ErrorBoundary>} />
              <Route path="/finance/refunds" element={<ErrorBoundary><RefundsPage /></ErrorBoundary>} />
              <Route path="/finance/reports" element={<ErrorBoundary><FinancialReportsPage /></ErrorBoundary>} />
              <Route path="/finance/queue" element={<ErrorBoundary><FinanceQueuePage /></ErrorBoundary>} />
              <Route path="/support" element={<ErrorBoundary><SupportQueuePage /></ErrorBoundary>} />
              <Route path="/support/assigned-leads" element={<ErrorBoundary><SupportAssignedLeadsPage /></ErrorBoundary>} />
              <Route path="/support/leads" element={<ErrorBoundary><SupportAssignedLeadsPage /></ErrorBoundary>} />
              <Route path="/support/backup-customers" element={<ErrorBoundary><BackupCustomersPage /></ErrorBoundary>} />
              <Route element={<ProtectedRoute allowedRoles={['ADMIN', 'SUPPORT_MANAGER']} />}>
                <Route path="/support/manager" element={<ErrorBoundary><SupportManagerPage /></ErrorBoundary>} />
              </Route>

              {/* REPORTS & ANALYTICS Section Routes */}
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/reports/export" element={<ReportsPage />} />
              <Route path="/analytics" element={<ReportsPage />} />

              {/* SETTINGS & USERS Section Routes */}
              <Route element={<ProtectedRoute requiredModule="settings" />}>
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/settings/account" element={<SettingsPage />} />
              </Route>
              <Route path="/settings/integrations" element={<IntegrationsPage />} />
              <Route path="/settings/integrations/meta" element={<MetaIntegrationPage />} />
              <Route path="/integrations/meta" element={<MetaIntegrationPage />} />
              <Route element={<ProtectedRoute requiredModule="whatsapp_connection" />}>
                <Route path="/settings/whatsapp-connection" element={<WhatsAppConnectionPage />} />
              </Route>
              <Route path="/settings/delete-requests" element={<DeleteRequestsPage />} />
              <Route path="/organization/delete-requests" element={<DeleteRequestsPage />} />
              <Route path="/users" element={<UsersRolesPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/profile" element={<ProfilePage />} />

              {/* Admin Panel (Admin-only route guard) */}
              <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
                <Route path="/admin" element={<AdminPanelPage />} />
              </Route>

              {/* Fallback 404 Page inside layout */}
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
              </Suspense>
            </PingoPopupProvider>
          </FollowupReminderProvider>
        </Router>
      </DialerProvider>
    </AuthProvider>
  );
}

export default App;
