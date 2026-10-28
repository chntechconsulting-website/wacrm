import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { RefreshCw, AlertCircle, LogOut } from 'lucide-react';

const ProtectedRoute = ({ allowedRoles = [], requiredModule = null, requiredAction = 'view' }) => {
  const { user, loading, authError, retryAuth, logout } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen" style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0f172a',
        color: '#94a3b8',
        gap: '16px',
        padding: '24px',
        textAlign: 'center'
      }}>
        <div className="spinner" style={{
          width: '42px',
          height: '42px',
          border: '3px solid rgba(56, 189, 248, 0.2)',
          borderTopColor: '#38bdf8',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite'
        }}></div>
        <p style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
          Loading application...
        </p>
      </div>
    );
  }

  // If there was an unrecoverable connection failure during startup and no cached session:
  if (authError && !user) {
    return (
      <div className="loading-screen" style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0f172a',
        color: '#cbd5e1',
        gap: '18px',
        padding: '24px',
        textAlign: 'center'
      }}>
        <div style={{
          width: '54px',
          height: '54px',
          borderRadius: '16px',
          backgroundColor: 'rgba(239, 68, 68, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#f87171'
        }}>
          <AlertCircle size={28} />
        </div>
        <div style={{ maxWidth: '420px' }}>
          <h3 style={{ margin: '0 0 8px', color: '#ffffff', fontSize: '1.15rem', fontWeight: 700 }}>
            Unable to Connect to Server
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.5 }}>
            {authError.includes('timeout') 
              ? 'The server took too long to respond. Please verify your connection or retry.'
              : 'The CRM backend service is temporarily restarting or unreachable. Please try again in a moment.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', marginTop: '6px' }}>
          <button
            type="button"
            onClick={retryAuth}
            style={{
              padding: '10px 18px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: '#2563eb',
              color: '#ffffff',
              fontSize: '0.85rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <RefreshCw size={15} />
            <span>Retry Connection</span>
          </button>
          <button
            type="button"
            onClick={() => {
              logout();
              window.location.href = '/login';
            }}
            style={{
              padding: '10px 16px',
              borderRadius: '8px',
              border: '1px solid #334155',
              backgroundColor: 'transparent',
              color: '#94a3b8',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <LogOut size={15} />
            <span>Go to Login</span>
          </button>
        </div>
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
