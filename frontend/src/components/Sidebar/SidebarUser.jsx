import React, { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { ChevronDown, LogOut, User, Settings as SettingsIcon } from 'lucide-react';

const SidebarUser = ({ isCollapsed }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const containerRef = useRef(null);

  const userName = user?.employee_name || user?.username || 'Chandra Mohan';
  const userDept = user?.department || '';
  const userRole = user?.role || 'Administrator';
  const userEmail = user?.email || `${(user?.username || 'user').toLowerCase()}@chncrm.com`;
  
  const initials = userName
    .split(' ')
    .filter(Boolean)
    .map(n => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase() || 'CM';

  const handleLogout = async () => {
    setIsDropdownOpen(false);
    await logout();
    navigate('/login');
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="sidebar-user-section" ref={containerRef}>
      {/* Popover Menu */}
      {isDropdownOpen && !isCollapsed && (
        <div className="user-dropdown-popover" role="menu">
          <div className="popover-header">
            <p className="popover-user-name" title={userName}>{userName}</p>
            <p className="popover-user-email" title={userEmail}>
              {userDept ? `${userDept} • ` : ''}{userRole}
            </p>
            <p style={{ margin: '2px 0 0', fontSize: '0.72rem', color: '#94a3b8' }}>{userEmail}</p>
          </div>
          <div className="popover-divider" />
          
          <NavLink 
            to="/profile" 
            className="popover-menu-item"
            onClick={() => setIsDropdownOpen(false)}
            role="menuitem"
          >
            <User size={15} />
            <span>My Profile</span>
          </NavLink>

          <NavLink 
            to="/settings/account" 
            className="popover-menu-item"
            onClick={() => setIsDropdownOpen(false)}
            role="menuitem"
          >
            <SettingsIcon size={15} />
            <span>Account Settings</span>
          </NavLink>

          <div className="popover-divider" />

          <button 
            type="button"
            className="popover-menu-item logout"
            onClick={handleLogout}
            role="menuitem"
          >
            <LogOut size={15} />
            <span>Logout</span>
          </button>
        </div>
      )}

      {/* User Card */}
      <div 
        className="user-profile-card"
        onClick={() => setIsDropdownOpen(prev => !prev)}
        title={isCollapsed ? `${userName} (${userRole})` : undefined}
        role="button"
        tabIndex={0}
        aria-expanded={isDropdownOpen}
        aria-label="User profile menu"
      >
        <div className="user-avatar" aria-hidden="true">
          <span>{initials}</span>
        </div>

        {!isCollapsed && (
          <>
            <div className="user-details">
              <div className="user-name-row">
                <span className="user-name" title={userName}>{userName}</span>
                <span className="online-dot" title="Online" aria-label="Online status"></span>
              </div>
              <span className="user-role-title">
                {userDept ? `${userDept} • ` : ''}{userRole}
              </span>
            </div>
            <ChevronDown 
              size={16} 
              className={`user-dropdown-arrow ${isDropdownOpen ? 'open' : ''}`} 
            />
          </>
        )}
      </div>

      {/* Direct Logout Button */}
      <button 
        type="button"
        className="sidebar-logout-btn"
        onClick={handleLogout}
        title="Logout"
        aria-label="Logout"
      >
        <div className="icon-wrapper">
          <LogOut size={18} />
        </div>
        {!isCollapsed && <span>Logout</span>}
      </button>
    </div>
  );
};

export default SidebarUser;
