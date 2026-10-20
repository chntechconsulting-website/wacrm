import React from 'react';
import { ChevronRight } from 'lucide-react';

const SidebarSection = ({ 
  title, 
  isOpen, 
  onToggle, 
  isCollapsed, 
  children 
}) => {
  if (isCollapsed) {
    return (
      <div className="sidebar-section">
        <div className="sidebar-section-divider" />
        <div className="sidebar-nav-group">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="sidebar-section">
      <button 
        type="button"
        className="sidebar-section-header" 
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-label={`Toggle ${title} section`}
      >
        <span>{title}</span>
        <ChevronRight 
          size={14} 
          className={`sidebar-section-arrow ${isOpen ? 'rotated' : ''}`} 
        />
      </button>

      {isOpen && (
        <div className="sidebar-nav-group">
          {children}
        </div>
      )}
    </div>
  );
};

export default SidebarSection;
