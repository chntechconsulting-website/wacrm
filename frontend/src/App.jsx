import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { DialerProvider } from './context/DialerContext';
import { FollowupReminderProvider } from './context/FollowupReminderContext';
import { PingoPopupProvider } from './context/PingoPopupContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';

// Public Auth & Compliance Pages
import Login from './pages/Login';
import PrivacyPolicyPage from './pages/Public/PrivacyPolicyPage';
import DataDeletionPage from './pages/Public/DataDeletionPage';

// CRM Module Pages
import DashboardPage from './pages/Dashboard/DashboardPage';

// LEADS Pages
import LeadsPage from './pages/Leads/LeadsPage';
import CreateLeadPage from './pages/Leads/CreateLeadPage';
import ImportLeadsPage from './pages/Leads/ImportLeadsPage';
import MetaLeadsPage from './pages/Leads/MetaLeadsPage';
import WebsiteLeadsPage from './pages/Leads/WebsiteLeadsPage';
import ManualLeadsPage from './pages/Leads/ManualLeadsPage';
import MyLeadsPage from './pages/Leads/MyLeadsPage';

// COMMUNICATION Pages
import CallLogsPage from './pages/Communication/CallLogsPage';
import FollowupsPage from './pages/Communication/FollowupsPage';
import ActivitiesPage from './pages/Communication/ActivitiesPage';
import WhatsAppPage from './pages/Communication/WhatsAppPage';

// ORGANIZATION Pages
import CompaniesPage from './pages/Organization/CompaniesPage';
import ContactsPage from './pages/Organization/ContactsPage';

// REPORTS & ANALYTICS Pages
import ReportsPage from './pages/Reports/ReportsPage';
import AnalyticsPage from './pages/Reports/AnalyticsPage';

// SETTINGS & USERS Pages
import SettingsPage from './pages/Settings/SettingsPage';
import IntegrationsPage from './pages/Settings/IntegrationsPage';
import MetaIntegrationPage from './pages/Settings/MetaIntegrationPage';
import UsersRolesPage from './pages/Settings/UsersRolesPage';
import NotificationsPage from './pages/Settings/NotificationsPage';
import DeleteRequestsPage from './pages/Settings/DeleteRequestsPage';

// EMPLOYEE MONITORING Pages
import EmployeeMonitoringPage from './pages/EmployeeMonitoring/index';
import EmployeeDetailPage from './pages/EmployeeMonitoring/EmployeeDetailPage';

// WA QUOTES & INVOICES Pages
import WAQuotesPage from './pages/WAQuotes/WAQuotesPage';

// WORKFLOW Pages (Sales -> Finance -> Support)
import FinanceQueuePage from './pages/Workflow/FinanceQueuePage';
import SupportQueuePage from './pages/Workflow/SupportQueuePage';

// 404 Not Found Page
import NotFoundPage from './pages/NotFound/NotFoundPage';

function App() {
  return (
    <AuthProvider>
      <DialerProvider>
        <Router>
          <FollowupReminderProvider>
            <PingoPopupProvider>
              <Routes>
          {/* Public Authentication & Meta Compliance Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/privacy" element={<PrivacyPolicyPage />} />
          <Route path="/data-deletion" element={<DataDeletionPage />} />

          {/* Protected Main CRM Application Routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              {/* Root & Index redirect to dashboard */}
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />

              {/* Dashboard */}
              <Route path="/dashboard" element={<DashboardPage />} />

              {/* LEADS Section Routes */}
              <Route path="/leads" element={<LeadsPage />} />
              <Route path="/leads/create" element={<CreateLeadPage />} />
              <Route path="/leads/import" element={<ImportLeadsPage />} />
              <Route path="/leads/meta" element={<MetaLeadsPage />} />
              <Route path="/leads/website" element={<WebsiteLeadsPage />} />
              <Route path="/leads/manual" element={<ManualLeadsPage />} />
              <Route path="/leads/my" element={<MyLeadsPage />} />

              {/* COMMUNICATION Section Routes */}
              <Route path="/communication/calls" element={<CallLogsPage />} />
              <Route path="/communication/followups" element={<FollowupsPage />} />
              <Route path="/communication/activities" element={<ActivitiesPage />} />
              <Route path="/communication/whatsapp" element={<WhatsAppPage />} />

              {/* EMPLOYEE MONITORING Section Routes */}
              <Route path="/employee-monitoring" element={<EmployeeMonitoringPage />} />
              <Route path="/employee-monitoring/:employeeId" element={<EmployeeDetailPage />} />

              {/* WA QUOTES & INVOICES Section Routes */}
              <Route path="/waquotes" element={<ErrorBoundary><WAQuotesPage /></ErrorBoundary>} />

              {/* WORKFLOW (Sales -> Finance -> Support) Section Routes */}
              <Route path="/finance" element={<ErrorBoundary><FinanceQueuePage /></ErrorBoundary>} />
              <Route path="/support" element={<ErrorBoundary><SupportQueuePage /></ErrorBoundary>} />

              {/* REPORTS & ANALYTICS Section Routes */}
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/analytics" element={<ReportsPage />} />

              {/* SETTINGS & USERS Section Routes */}
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/settings/account" element={<SettingsPage />} />
              <Route path="/settings/integrations" element={<IntegrationsPage />} />
              <Route path="/settings/integrations/meta" element={<MetaIntegrationPage />} />
              <Route path="/integrations/meta" element={<MetaIntegrationPage />} />
              <Route path="/settings/delete-requests" element={<DeleteRequestsPage />} />
              <Route path="/organization/delete-requests" element={<DeleteRequestsPage />} />
              <Route path="/users" element={<UsersRolesPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/profile" element={<SettingsPage />} />

              {/* Fallback 404 Page inside layout */}
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
            </PingoPopupProvider>
          </FollowupReminderProvider>
        </Router>
      </DialerProvider>
    </AuthProvider>
  );
}

export default App;
