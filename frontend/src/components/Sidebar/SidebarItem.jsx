import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import SidebarBadge from './SidebarBadge';
import SidebarTooltip from './SidebarTooltip';

const SidebarItem = ({ 
  to, 
  icon: IconComponent, 
  label, 
  badgeCount, 
  badgeVariant = 'slate',
  isCollapsed, 
  onClick,
  exactMatch = true,
  customIconClass = ''
}) => {
  const location = useLocation();
  const [isHovered, setIsHovered] = useState(false);

  // Strict active check so ONLY the matching route highlights (supports query parameters like ?tab=)
  const toPath = to.split('?')[0];
  const toSearch = to.includes('?') ? '?' + to.split('?')[1] : '';

  let isActive = false;
  if (toSearch) {
    isActive = location.pathname === toPath && location.search === toSearch;
  } else if (exactMatch) {
    isActive = location.pathname === toPath && (!location.search || location.search === '');
  } else {
    isActive = location.pathname === toPath || (toPath !== '/' && location.pathname.startsWith(toPath + '/'));
  }

  return (
    <div 
      className="sidebar-item-wrapper"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <NavLink
        to={to}
        end={exactMatch}
        onClick={onClick}
        className={() => 
          `sidebar-item ${isActive ? 'active' : ''}`
        }
        aria-current={(isActive) ? 'page' : undefined}
        aria-label={label}
      >
        <div className="icon-wrapper" style={{ position: 'relative' }}>
          {IconComponent && (
            <IconComponent 
              size={18} 
              className={`nav-icon ${customIconClass}`} 
            />
          )}
          {isCollapsed && Number(badgeCount) > 0 && (
            <span 
              style={{
                position: 'absolute',
                top: '-3px',
                right: '-3px',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: badgeVariant === 'red' ? '#ef4444' : '#2563eb',
                border: '1.5px solid #ffffff'
              }} 
            />
          )}
        </div>

        {!isCollapsed && (
          <>
            <span className="sidebar-item-label">{label}</span>
            <SidebarBadge count={badgeCount} variant={badgeVariant} />
          </>
        )}
      </NavLink>

      {/* Tooltip on hover when collapsed */}
      {isCollapsed && (
        <SidebarTooltip label={label} isVisible={isHovered} />
      )}
    </div>
  );
};

export default SidebarItem;
