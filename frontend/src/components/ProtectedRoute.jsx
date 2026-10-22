import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ allowedRoles = [], requiredModule = null, requiredAction = 'view' }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Loading application...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // System Administrator has super-access across every module
  if (user.role === 'ADMIN') {
    return <Outlet />;
  }

  // Dynamic Module Permission Check with resilient role fallback
  if (requiredModule) {
    const normRole = (user.role || '').toUpperCase();
    const isSalesManager = normRole === 'SALES_MANAGER' || normRole === 'MANAGER';
    const isSalesExec = normRole === 'SALES_EXECUTIVE' || normRole === 'SALES' || normRole === 'EMPLOYEE';
    const isSalesRole = isSalesManager || isSalesExec;
    const isSupportRole = ['SUPPORT_MANAGER', 'SUPPORT_EXECUTIVE', 'SUPPORT'].includes(normRole);
    const isFinance = normRole === 'FINANCE';

    const isCoreSalesModule = isSalesRole && ['dashboard', 'leads', 'customers', 'contacts', 'quotations', 'calls', 'whatsapp', 'followups', 'activities'].includes(requiredModule);
    const isSalesManagerModule = isSalesManager && ['invoices', 'reports', 'analytics', 'employees'].includes(requiredModule);
    const isCoreSupportModule = isSupportRole && ['dashboard', 'customers', 'contacts', 'support_tickets', 'calls', 'whatsapp', 'activities'].includes(requiredModule);
    const isFinanceModule = isFinance && ['dashboard', 'payments', 'invoices', 'customers', 'reports'].includes(requiredModule);

    const modPerm = user.permissions?.[requiredModule];
    const hasAccess = modPerm?.has_access === true || isCoreSalesModule || isSalesManagerModule || isCoreSupportModule || isFinanceModule;

    if (!hasAccess) {
      return (
        <div className="unauthorized-container" style={{ padding: '60px 20px', textAlign: 'center' }}>
          <h2 style={{ color: 'var(--danger)', marginBottom: '12px' }}>Access Denied (403 Forbidden)</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem' }}>
            Your assigned role does not have access permissions for module: <strong>{requiredModule}</strong>.
          </p>
        </div>
      );
    }

    if (modPerm && requiredAction && modPerm[`can_${requiredAction}`] === false) {
      return (
        <div className="unauthorized-container" style={{ padding: '60px 20px', textAlign: 'center' }}>
          <h2 style={{ color: 'var(--danger)', marginBottom: '12px' }}>Access Denied (403 Forbidden)</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem' }}>
            Your assigned role does not have permission to <strong>{requiredAction}</strong> in module: <strong>{requiredModule}</strong>.
          </p>
        </div>
      );
    }
  }

  // Fallback role-based check
  if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    return (
      <div className="unauthorized-container" style={{ padding: '60px 20px', textAlign: 'center' }}>
        <h2 style={{ color: 'var(--danger)', marginBottom: '12px' }}>Access Denied</h2>
        <p style={{ color: 'var(--text-muted)' }}>You do not have permission to view this page.</p>
      </div>
    );
  }

  return <Outlet />;
};

export default ProtectedRoute;
