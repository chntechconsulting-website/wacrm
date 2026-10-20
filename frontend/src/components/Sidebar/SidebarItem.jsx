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
        <div className="icon-wrapper">
          {IconComponent && (
            <IconComponent 
              size={18} 
              className={`nav-icon ${customIconClass}`} 
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
