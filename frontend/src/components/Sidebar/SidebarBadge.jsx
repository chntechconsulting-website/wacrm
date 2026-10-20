import React from 'react';

const formatBadgeCount = (count) => {
  if (typeof count === 'string') return count;
  if (typeof count !== 'number' || isNaN(count)) return null;
  if (count >= 1000000) {
    return (count / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
  }
  if (count >= 1000) {
    return (count / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
  }
  return count.toString();
};

const SidebarBadge = ({ count, variant = 'slate' }) => {
  if (count === undefined || count === null || count === 0 || count === '0') {
    return null;
  }

  const formatted = formatBadgeCount(count);
  if (!formatted) return null;

  return (
    <span className={`sidebar-badge badge-${variant}`}>
      {formatted}
    </span>
  );
};

export default SidebarBadge;
