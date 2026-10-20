import React from 'react';

const SidebarTooltip = ({ label, isVisible }) => {
  if (!isVisible || !label) return null;

  return (
    <div className="sidebar-tooltip" role="tooltip">
      {label}
    </div>
  );
};

export default SidebarTooltip;
