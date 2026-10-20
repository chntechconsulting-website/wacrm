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

  // Dynamic Module Permission Check
  if (requiredModule) {
    const modPerm = user.permissions?.[requiredModule];
    if (!modPerm || !modPerm.has_access) {
      return (
        <div className="unauthorized-container" style={{ padding: '60px 20px', textAlign: 'center' }}>
          <h2 style={{ color: 'var(--danger)', marginBottom: '12px' }}>Access Denied (403 Forbidden)</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem' }}>
            Your assigned role does not have access permissions for module: <strong>{requiredModule}</strong>.
          </p>
        </div>
      );
    }

    if (requiredAction && !modPerm[`can_${requiredAction}`]) {
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
