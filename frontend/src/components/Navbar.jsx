import React from 'react';
import { useAuth } from '../context/AuthContext';
import { LogOut, User as UserIcon, Shield, Building2 } from 'lucide-react';
import PingoQuickGuide from './Common/PingoQuickGuide';

const Navbar = () => {
  const { user, logout } = useAuth();

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="brand-logo">
          <Building2 size={24} className="logo-icon" />
        </div>
        <div className="brand-title">
          <h1>WaCRM</h1>
          
        </div>
      </div>

      <div className="navbar-user">
        <PingoQuickGuide />
        <div className="user-info">
          <span className="user-name">{user?.employee_name || user?.username}</span>
          <span className={`role-badge role-${user?.role?.toLowerCase()}`}>
            <Shield size={12} /> {user?.role}
          </span>
        </div>
        <button onClick={logout} className="logout-btn" title="Sign Out">
          <LogOut size={18} />
          <span>Logout</span>
        </button>
      </div>
    </header>
  );
};

export default Navbar;
