import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import SidebarSection from './SidebarSection';
import SidebarItem from './SidebarItem';
import SidebarUser from './SidebarUser';
import './Sidebar.css';

import { 
  Home, 
  Users, 
  PlusSquare, 
  CloudUpload, 
  Share2, 
  Globe, 
  FileText, 
  Star, 
  PhoneCall, 
  CalendarDays, 
  ClipboardList, 
  MessageCircle, 
  BarChart3, 
  PieChart, 
  Settings as SettingsIcon, 
  Sliders,
  ShieldCheck, 
  Bell, 
  ChevronsLeft, 
  ChevronsRight,
  Activity,
  Trash2,
  X,
  CreditCard,
  LifeBuoy,
  TrendingUp,
  Filter,
  Clock,
  Award,
  XCircle
} from 'lucide-react';

// Lite tone color presets for testing
const LITE_THEMES = [
  {
    id: 'white-brown',
    name: 'Clean White & Warm Brown',
    bg: '#FFFFFF',
    bgEnd: '#FAFAF9',
    hover: '#F5F0EB',
    userBg: '#F7F4F0',
    border: '#E8E1DA',
    active: '#EFE7E0',
    activeEnd: '#E6DDD5',
    activeBorder: '#D2C3B5',
    badge: '#EFE7E0',
    btnBg: '#785942',
    btnHover: '#634733',
    btnBorder: '#634733',
    btnBorderHover: '#523A29',
    btnSecondaryBg: '#FAF7F4',
    btnSecondaryBorder: '#E5DCD4',
    btnText: '#FFFFFF'
  },
  {
    id: 'mocha-latte',
    name: 'White & Latte Brown Accents',
    bg: '#FFFFFF',
    bgEnd: '#FAF8F5',
    hover: '#F4ECE4',
    userBg: '#F3EDE6',
    border: '#E6DCD1',
    active: '#EBE0D4',
    activeEnd: '#DFD2C4',
    activeBorder: '#CCAFA1',
    badge: '#EBE0D4',
    btnBg: '#EDE4DA',
    btnHover: '#E0D4C7',
    btnBorder: '#D1C2B2',
    btnBorderHover: '#BFAEA0',
    btnSecondaryBg: '#FCFAF8',
    btnSecondaryBorder: '#EFE7DD',
    btnText: '#4A3728'
  },
  {
    id: 'deep-espresso',
    name: 'Espresso Brown & White Text',
    bg: '#2C221E',
    bgEnd: '#241B18',
    hover: '#3D302A',
    userBg: '#231A17',
    border: '#453831',
    active: '#4A3B34',
    activeEnd: '#3F322C',
    activeBorder: '#5C4A41',
    badge: '#4A3B34',
    btnBg: '#4A3B34',
    btnHover: '#5C4A41',
    btnBorder: '#5C4A41',
    btnBorderHover: '#6E594E',
    btnSecondaryBg: '#362A24',
    btnSecondaryBorder: '#453831',
    btnText: '#FAF6F0'
  },
  {
    id: 'stone',
    name: 'Ash Stone (#EBE8E5)',
    bg: '#EBE8E5',
    bgEnd: '#E2DFDB',
    hover: '#DDD9D4',
    userBg: '#E2DFDB',
    border: '#D7D3CD',
    active: '#DDD9D4',
    activeEnd: '#D4CFC9',
    activeBorder: '#C4BEB7',
    badge: '#DDD9D4',
    btnBg: '#EBE8E5',
    btnHover: '#DDD9D4',
    btnBorder: '#D1CCC4',
    btnBorderHover: '#C4BEB7',
    btnSecondaryBg: '#F8F6F4',
    btnSecondaryBorder: '#E2DFDB',
    btnText: '#1c1917'
  },
  {
    id: 'linen',
    name: 'Warm Linen',
    bg: '#F3F0E9',
    bgEnd: '#EBE6DC',
    hover: '#E5DFC4',
    userBg: '#EAE5DB',
    border: '#DCD6CA',
    active: '#E4DDD0',
    activeEnd: '#D9D1C2',
    activeBorder: '#C8BEAD',
    badge: '#E4DDD0',
    btnBg: '#F3F0E9',
    btnHover: '#E4DDD0',
    btnBorder: '#DCD6CA',
    btnBorderHover: '#C8BEAD',
    btnSecondaryBg: '#FAF8F3',
    btnSecondaryBorder: '#EAE5DB',
    btnText: '#292524'
  },
  {
    id: 'sage',
    name: 'Lite Mint / Sage',
    bg: '#EAF1EC',
    bgEnd: '#DFEAE2',
    hover: '#D3E2D8',
    userBg: '#DEECE2',
    border: '#C9DCD0',
    active: '#D0E3D6',
    activeEnd: '#C2D9C9',
    activeBorder: '#B2CDC0',
    badge: '#D0E3D6',
    btnBg: '#EAF1EC',
    btnHover: '#D0E3D6',
    btnBorder: '#C9DCD0',
    btnBorderHover: '#B2CDC0',
    btnSecondaryBg: '#F4F8F5',
    btnSecondaryBorder: '#DEECE2',
    btnText: '#143823'
  },
  {
    id: 'blush',
    name: 'Lite Rose / Pink',
    bg: '#F8ECEF',
    bgEnd: '#F2DFE4',
    hover: '#E8CCD3',
    userBg: '#F0DCE2',
    border: '#E4C9D1',
    active: '#E9D0D8',
    activeEnd: '#DEC1CA',
    activeBorder: '#D2AFB9',
    badge: '#E9D0D8',
    btnBg: '#F8ECEF',
    btnHover: '#E9D0D8',
    btnBorder: '#E4C9D1',
    btnBorderHover: '#D2AFB9',
    btnSecondaryBg: '#FDF7F8',
    btnSecondaryBorder: '#F0DCE2',
    btnText: '#3b1d28'
  },
  {
    id: 'sky',
    name: 'Lite Ice Blue',
    bg: '#EBF2F7',
    bgEnd: '#DFEAF2',
    hover: '#D2E1EC',
    userBg: '#DEECF4',
    border: '#C8DBE8',
    active: '#CFE0ED',
    activeEnd: '#BFD4E4',
    activeBorder: '#ADC7D9',
    badge: '#CFE0ED',
    btnBg: '#EBF2F7',
    btnHover: '#CFE0ED',
    btnBorder: '#C8DBE8',
    btnBorderHover: '#ADC7D9',
    btnSecondaryBg: '#F5F9FC',
    btnSecondaryBorder: '#DEECF4',
    btnText: '#132c3f'
  },
  {
    id: 'sand',
    name: 'Lite Warm Sand',
    bg: '#F6F2EC',
    bgEnd: '#EDE7DC',
    hover: '#E2DACB',
    userBg: '#EBE4D7',
    border: '#DDD3C1',
    active: '#E3DACB',
    activeEnd: '#D5C9B7',
    activeBorder: '#C7B9A3',
    badge: '#E3DACB',
    btnBg: '#F6F2EC',
    btnHover: '#E3DACB',
    btnBorder: '#DDD3C1',
    btnBorderHover: '#C7B9A3',
    btnSecondaryBg: '#FBF9F6',
    btnSecondaryBorder: '#EBE4D7',
    btnText: '#2e271d'
  },
  {
    id: 'lavender',
    name: 'Lite Lavender',
    bg: '#F0EDF7',
    bgEnd: '#E6E0F1',
    hover: '#D8CEE6',
    userBg: '#E5DFF0',
    border: '#D3C8E4',
    active: '#DDD4EB',
    activeEnd: '#CEC3DF',
    activeBorder: '#BDAECF',
    badge: '#DDD4EB',
    btnBg: '#F0EDF7',
    btnHover: '#DDD4EB',
    btnBorder: '#D3C8E4',
    btnBorderHover: '#BDAECF',
    btnSecondaryBg: '#F8F6FC',
    btnSecondaryBorder: '#E5DFF0',
    btnText: '#2b1c40'
  }
];

const Sidebar = ({ 
  isMobileOpen = false, 
  onMobileClose,
  isCollapsed: externalIsCollapsed,
  onToggleCollapse
}) => {
  const location = useLocation();

  // Active theme tracking with localStorage persistence
  const [activeThemeId, setActiveThemeId] = useState(() => {
    return localStorage.getItem('crm_sidebar_theme') || 'white-brown';
  });

  // Apply theme variables to root document
  useEffect(() => {
    const selected = LITE_THEMES.find(t => t.id === activeThemeId) || LITE_THEMES[0];
    const root = document.documentElement;

    root.style.setProperty('--sidebar-bg', selected.bg);
    root.style.setProperty('--sidebar-bg-end', selected.bgEnd);
    root.style.setProperty('--sidebar-bg-hover', selected.hover);
    root.style.setProperty('--sidebar-bg-user', selected.userBg);
    root.style.setProperty('--sidebar-border', selected.border);
    root.style.setProperty('--sidebar-active', selected.active);
    root.style.setProperty('--sidebar-active-end', selected.activeEnd);
    root.style.setProperty('--sidebar-active-hover', selected.activeEnd);
    root.style.setProperty('--sidebar-active-border', selected.activeBorder);

    // Dynamic button styling matching the chosen sidebar theme
    root.style.setProperty('--theme-btn-bg', selected.btnBg);
    root.style.setProperty('--theme-btn-hover', selected.btnHover);
    root.style.setProperty('--theme-btn-border', selected.btnBorder);
    root.style.setProperty('--theme-btn-border-hover', selected.btnBorderHover);
    root.style.setProperty('--theme-btn-secondary-bg', selected.btnSecondaryBg);
    root.style.setProperty('--theme-btn-secondary-border', selected.btnSecondaryBorder);
    root.style.setProperty('--theme-btn-text', selected.btnText);

    localStorage.setItem('crm_sidebar_theme', activeThemeId);
  }, [activeThemeId]);

  // Screen width tracking for tablet icon-only sidebar
  const [windowWidth, setWindowWidth] = useState(() => typeof window !== 'undefined' ? window.innerWidth : 1200);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Collapse state (internal fallback or external controlled)
  const [internalCollapsed, setInternalCollapsed] = useState(() => {
    return localStorage.getItem('crm_sidebar_collapsed') === 'true';
  });

  const isTablet = windowWidth >= 768 && windowWidth <= 1024;
  const isCollapsed = isMobileOpen 
    ? false 
    : (isTablet ? true : (externalIsCollapsed !== undefined ? externalIsCollapsed : internalCollapsed));

  const toggleSidebar = () => {
    const nextState = !isCollapsed;
    if (onToggleCollapse) {
      onToggleCollapse(nextState);
    } else {
      setInternalCollapsed(nextState);
      localStorage.setItem('crm_sidebar_collapsed', String(nextState));
    }
  };

  // Section collapse states
  const [openSections, setOpenSections] = useState({
    leads: true,
    communication: true,
    sales: true,
    monitoring: true,
    reports: true,
    settings: true
  });

  // Auto-expand section containing current route
  useEffect(() => {
    const path = location.pathname;
    if (path.startsWith('/leads')) {
      setOpenSections(prev => ({ ...prev, leads: true }));
    } else if (path.startsWith('/communication')) {
      setOpenSections(prev => ({ ...prev, communication: true }));
    } else if (path.startsWith('/waquotes') || path.startsWith('/finance') || path.startsWith('/support')) {
      setOpenSections(prev => ({ ...prev, sales: true }));
    } else if (path.startsWith('/employee-monitoring')) {
      setOpenSections(prev => ({ ...prev, monitoring: true }));
    } else if (path === '/reports' || path === '/analytics') {
      setOpenSections(prev => ({ ...prev, reports: true }));
    } else if (path.startsWith('/settings') || path === '/users' || path === '/notifications' || path === '/profile') {
      setOpenSections(prev => ({ ...prev, settings: true }));
    }
  }, [location.pathname]);

  const toggleSection = (sectionKey) => {
    setOpenSections(prev => ({
      ...prev,
      [sectionKey]: !prev[sectionKey]
    }));
  };

  // Dynamic badge counts state (fetched live from database)
  const [counts, setCounts] = useState({
    allLeads: 0,
    metaLeads: 0,
    websiteLeads: 0,
    manualLeads: 0,
    excelLeads: 0,
    myLeads: 0,
    callLogs: 0,
    followups: 0
  });

  // Fetch live stats from API
  useEffect(() => {
    let isMounted = true;
    const fetchCounts = async () => {
      try {
        const res = await API.get('/leads/stats');
        if (isMounted && res.data) {
          setCounts({
            allLeads: res.data.allLeads ?? res.data.totalLeads ?? 0,
            metaLeads: res.data.metaLeads ?? 0,
            websiteLeads: res.data.websiteLeads ?? 0,
            manualLeads: res.data.manualLeads ?? 0,
            excelLeads: res.data.excelLeads ?? 0,
            myLeads: res.data.myLeads ?? 0,
            callLogs: res.data.callLogs ?? 0,
            followups: res.data.followups ?? 0
          });
        }
      } catch (e) {
        // Silently preserve default values if endpoint is unavailable
      }
    };
    fetchCounts();

    const handleStatsEvent = () => fetchCounts();
    window.addEventListener('leadStatsUpdated', handleStatsEvent);

    return () => { 
      isMounted = false; 
      window.removeEventListener('leadStatsUpdated', handleStatsEvent);
    };
  }, []);

  const handleItemClick = () => {
    if (isMobileOpen && onMobileClose) {
      onMobileClose();
    }
  };

  const { user: currentUser } = useAuth();
  const userRole = currentUser?.role || 'EMPLOYEE';
  const isAdmin = userRole === 'ADMIN';
  const isManager = userRole === 'MANAGER' || userRole === 'SALES_MANAGER' || userRole === 'SUPPORT_MANAGER';
  const isFinance = userRole === 'FINANCE';

  // Dynamic DB Permission Helpers
  const hasModule = (moduleKey) => {
    if (isAdmin) return true;
    if (!currentUser?.permissions) return false;
    return Boolean(currentUser.permissions[moduleKey]?.has_access);
  };

  const canAction = (moduleKey, action) => {
    if (isAdmin) return true;
    if (!currentUser?.permissions) return false;
    return Boolean(currentUser.permissions[moduleKey]?.[`can_${action}`]);
  };

  const getScope = (moduleKey) => {
    if (isAdmin) return 'company';
    return currentUser?.permissions?.[moduleKey]?.view_scope || 'none';
  };

  return (
    <>
      {/* Off-canvas mobile backdrop */}
      <div 
        className={`sidebar-mobile-backdrop ${isMobileOpen ? 'active' : ''}`}
        onClick={onMobileClose}
        aria-hidden="true"
      />

      <aside 
        className={`sidebar-container ${isCollapsed ? 'collapsed' : ''} ${isMobileOpen ? 'mobile-open' : ''}`}
        aria-label="Main Navigation Sidebar"
      >
        {/* Brand Header */}
        <div className="sidebar-header">
          <NavLink 
            to="/dashboard" 
            className="sidebar-brand"
            onClick={handleItemClick}
            title="WA! CRM Dashboard"
            style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}
          >
            <img 
              src={activeThemeId === 'deep-espresso' ? "/wa-crm-logo-dark.png" : "/wa-crm-logo-transparent.png"} 
              alt="WA! CRM Logo" 
              style={{
                height: isCollapsed ? '32px' : '40px',
                width: isCollapsed ? '32px' : 'auto',
                maxWidth: isCollapsed ? '32px' : '155px',
                objectFit: 'contain',
                borderRadius: '6px',
                filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.06))',
                transition: 'all 0.2s ease'
              }}
            />
          </NavLink>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {isMobileOpen ? (
              <button 
                type="button"
                onClick={onMobileClose}
                className="collapse-toggle-btn"
                title="Close Menu"
                aria-label="Close Navigation Menu"
              >
                <X size={18} />
              </button>
            ) : (
              <button 
                type="button"
                onClick={toggleSidebar}
                className="collapse-toggle-btn"
                title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                aria-label={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
              >
                {isCollapsed ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />}
              </button>
            )}
          </div>
        </div>

        {/* Scrollable Navigation Items */}
        <nav className="sidebar-nav">
          {/* Main: Dashboard */}
          <NavLink 
            to="/dashboard" 
            onClick={handleItemClick}
            className={({ isActive }) => `sidebar-dashboard-btn ${isActive ? 'active' : ''}`}
            title="Dashboard"
          >
            <div className="icon-wrapper">
              <Home size={20} />
            </div>
            {!isCollapsed && <span>Dashboard</span>}
          </NavLink>

          {/* Section: LEADS */}
          {hasModule('leads') && (
            <SidebarSection
              title="LEADS"
              isOpen={openSections.leads}
              onToggle={() => toggleSection('leads')}
              isCollapsed={isCollapsed}
            >
              {(isAdmin || getScope('leads') !== 'own') && (
                <SidebarItem
                  to="/leads"
                  exactMatch={true}
                  icon={Users}
                  label="All Leads"
                  badgeCount={counts.allLeads}
                  badgeVariant="slate"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              {canAction('leads', 'create') && (
                <SidebarItem
                  to="/leads/create"
                  exactMatch={false}
                  icon={PlusSquare}
                  label="Add / Import Leads"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              <SidebarItem
                to="/leads/my"
                exactMatch={true}
                icon={Star}
                label="Assigned Leads"
                badgeCount={counts.myLeads}
                badgeVariant="yellow"
                isCollapsed={isCollapsed}
                onClick={handleItemClick}
              />
            </SidebarSection>
          )}

          {/* Section: COMMUNICATION */}
          {(hasModule('calls') || hasModule('followups') || hasModule('activities') || hasModule('whatsapp')) && (
            <SidebarSection
              title="COMMUNICATION"
              isOpen={openSections.communication}
              onToggle={() => toggleSection('communication')}
              isCollapsed={isCollapsed}
            >
              {hasModule('calls') && (
                <SidebarItem
                  to="/communication/calls"
                  exactMatch={true}
                  icon={PhoneCall}
                  label="Call Logs"
                  badgeCount={counts.callLogs}
                  badgeVariant="red"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              {hasModule('followups') && (
                <SidebarItem
                  to="/communication/followups"
                  exactMatch={true}
                  icon={CalendarDays}
                  label="Follow-ups"
                  badgeCount={counts.followups}
                  badgeVariant="yellow"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              {hasModule('activities') && (
                <SidebarItem
                  to="/communication/activities"
                  exactMatch={true}
                  icon={ClipboardList}
                  label="Activities"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              {hasModule('whatsapp') && (
                <SidebarItem
                  to="/communication/whatsapp"
                  exactMatch={true}
                  icon={MessageCircle}
                  label="WhatsApp"
                  customIconClass="whatsapp-icon"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
            </SidebarSection>
          )}

          {/* Section: BILLING & OPERATIONS WORKFLOW */}
          {(hasModule('quotations') || hasModule('invoices') || hasModule('payments') || hasModule('support_tickets')) && (
            <SidebarSection
              title="BILLING & WORKFLOW"
              isOpen={openSections.sales}
              onToggle={() => toggleSection('sales')}
              isCollapsed={isCollapsed}
            >
              {!isFinance && (hasModule('quotations') || hasModule('invoices')) && (
                <SidebarItem
                  to="/waquotes"
                  exactMatch={true}
                  icon={FileText}
                  label="Quotes & Invoices"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              {(hasModule('payments') || hasModule('invoices')) && (
                <SidebarItem
                  to="/finance"
                  exactMatch={true}
                  icon={CreditCard}
                  label="Finance Queue"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              {hasModule('support_tickets') && (
                <SidebarItem
                  to="/support"
                  exactMatch={true}
                  icon={LifeBuoy}
                  label="Support Onboarding"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
            </SidebarSection>
          )}

          {/* Section: TEAM INSIGHTS */}
          {(hasModule('employees') || isAdmin || isManager) && (
            <SidebarSection
              title="TEAM INSIGHTS"
              isOpen={openSections.monitoring}
              onToggle={() => toggleSection('monitoring')}
              isCollapsed={isCollapsed}
            >
              <SidebarItem
                to="/employee-monitoring"
                exactMatch={false}
                icon={Activity}
                label="Team Insights"
                isCollapsed={isCollapsed}
                onClick={handleItemClick}
              />
            </SidebarSection>
          )}

          {/* Section: REPORTS & ANALYTICS */}
          {(hasModule('reports') || hasModule('analytics') || isAdmin || isManager) && (
            <SidebarSection
              title="REPORTS & ANALYTICS"
              isOpen={openSections.reports}
              onToggle={() => toggleSection('reports')}
              isCollapsed={isCollapsed}
            >
              <SidebarItem
                to="/reports"
                exactMatch={true}
                icon={BarChart3}
                label="Sales Overview"
                isCollapsed={isCollapsed}
                onClick={handleItemClick}
              />
              <SidebarItem
                to="/reports?tab=revenue"
                exactMatch={true}
                icon={TrendingUp}
                label="Sales Revenue"
                isCollapsed={isCollapsed}
                onClick={handleItemClick}
              />
            </SidebarSection>
          )}

          {/* Section: SETTINGS */}
          {(hasModule('settings') || hasModule('users') || hasModule('roles') || hasModule('integrations') || isAdmin || isManager) && (
            <SidebarSection
              title="SETTINGS"
              isOpen={openSections.settings}
              onToggle={() => toggleSection('settings')}
              isCollapsed={isCollapsed}
            >
              {(hasModule('settings') || isAdmin) && (
                <SidebarItem
                  to="/settings"
                  exactMatch={true}
                  icon={SettingsIcon}
                  label="Settings"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              {(hasModule('users') || hasModule('roles') || isAdmin) && (
                <SidebarItem
                  to="/users"
                  exactMatch={true}
                  icon={ShieldCheck}
                  label="Users & Roles"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              {(isAdmin || isManager) && (
                <SidebarItem
                  to="/settings/delete-requests"
                  exactMatch={true}
                  icon={Trash2}
                  label="Delete Requests"
                  isCollapsed={isCollapsed}
                  onClick={handleItemClick}
                />
              )}
              <SidebarItem
                to="/notifications"
                exactMatch={true}
                icon={Bell}
                label="Notifications"
                isCollapsed={isCollapsed}
                onClick={handleItemClick}
              />
            </SidebarSection>
          )}
        </nav>

        {/* Fixed Sticky Bottom User Profile */}
        <SidebarUser isCollapsed={isCollapsed} />
      </aside>
    </>
  );
};

export default Sidebar;
