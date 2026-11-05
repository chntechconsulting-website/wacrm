import React, { useCallback, useEffect, useMemo, useState } from 'react';
import API from '../../services/api';
import {
  Activity,
  AlertCircle,
  ArrowRightLeft,
  BarChart3,
  Building2,
  CalendarClock,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Target,
  TrendingUp,
  UserCheck,
  Users,
  X,
} from 'lucide-react';
import './AdminPanelPage.css';

const TABS = [
  { key: 'departments', label: 'Departments', icon: Building2 },
  { key: 'employees', label: 'Employees', icon: Users },
  { key: 'teams', label: 'Teams', icon: ShieldCheck },
  { key: 'handovers', label: 'Handovers', icon: ArrowRightLeft },
  { key: 'reports', label: 'Reports', icon: BarChart3 },
];

const DEPARTMENT_OPTIONS = [
  { value: 'ALL', label: 'All Departments' },
  { value: 'SALES', label: 'Sales' },
  { value: 'SUPPORT', label: 'Support' },
];

const DEPARTMENT_ROLE_OPTIONS = {
  SALES: [
    { value: 'SALES_EXECUTIVE', label: 'Sales Executive' },
    { value: 'SALES_MANAGER', label: 'Sales Manager' },
  ],
  SUPPORT: [
    { value: 'SUPPORT_EXECUTIVE', label: 'Support Executive' },
    { value: 'SUPPORT_MANAGER', label: 'Support Manager' },
  ],
};

// Canonical Support statuses. These are independent from the Sales status on
// the same handover row; the Admin table shows both.
const HANDOVER_STATUSES = [
  { value: 'all', label: 'All Support Statuses' },
  { value: 'NEW', label: 'New' },
  { value: 'ONBOARDING', label: 'Onboarding' },
  { value: 'INSTALLATION_PENDING', label: 'Installation Pending' },
  { value: 'INSTALLATION_COMPLETED', label: 'Installation Completed' },
  { value: 'TRAINING', label: 'Training' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'ISSUE_RAISED', label: 'Issue Raised' },
  { value: 'RESOLVED', label: 'Resolved' },
];

const LEGACY_HANDOVER_STATUS_MAP = {
  PENDING_ONBOARDING: 'NEW',
  PENDING_CONTACT: 'NEW',
  CONTACTED: 'ONBOARDING',
  ONBOARDING_IN_PROGRESS: 'ONBOARDING',
  IN_PROGRESS: 'ONBOARDING',
  IN_TRAINING: 'TRAINING',
  LIVE: 'ACTIVE',
  COMPLETED: 'RESOLVED',
  COMPLETE: 'RESOLVED',
  DONE: 'RESOLVED',
};

const normalizeHandoverSupportStatus = (status) => {
  const key = String(status || 'NEW').trim().toUpperCase().replace(/[\s-]/g, '_');
  return LEGACY_HANDOVER_STATUS_MAP[key] || key;
};

const handoverSupportStatusLabel = (status) => {
  const canonical = normalizeHandoverSupportStatus(status);
  return (
    HANDOVER_STATUSES.find((item) => item.value === canonical)?.label ||
    canonical.replace(/_/g, ' ')
  );
};

const ROLE_LABELS = {
  ADMIN: 'Administrator',
  SALES_MANAGER: 'Sales Manager',
  SALES_EXECUTIVE: 'Sales Executive',
  SUPPORT_MANAGER: 'Support Manager',
  SUPPORT_EXECUTIVE: 'Support Executive',
  MANAGER: 'Manager',
  SALES: 'Sales',
  SUPPORT: 'Support',
  EMPLOYEE: 'Employee',
  FINANCE: 'Finance',
};

const cannedRole = (role) => {
  const value = (role || '').toUpperCase();
  if (value === 'MANAGER') return 'SALES_MANAGER';
  if (value === 'SALES' || value === 'EMPLOYEE') return 'SALES_EXECUTIVE';
  if (value === 'SUPPORT') return 'SUPPORT_EXECUTIVE';
  return value;
};

const roleLabel = (role) => ROLE_LABELS[(role || '').toUpperCase()] || role || '—';

const formatDateTime = (value) => {
  if (!value) return '—';
  const normalized = /Z$|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatCurrency = (value) => {
  const number = Number(value || 0);
  return number.toLocaleString('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  });
};

const handoverStatusClass = (status) => {
  const value = normalizeHandoverSupportStatus(status);
  if (value === 'RESOLVED' || value === 'ACTIVE') return 'admin-pill green';
  if (value === 'TRAINING') return 'admin-pill purple';
  if (value === 'ISSUE_RAISED') return 'admin-pill red';
  if (value === 'ONBOARDING') return 'admin-pill blue';
  if (value === 'INSTALLATION_PENDING' || value === 'INSTALLATION_COMPLETED') {
    return 'admin-pill amber';
  }
  return 'admin-pill slate';
};

const salesStatusClass = (status) => {
  const value = String(status || '').trim().toUpperCase();
  if (value === 'WON' || value === 'CONVERTED') return 'admin-pill green';
  if (value === 'LOST') return 'admin-pill red';
  if (value === 'PROPOSAL SENT' || value === 'PROPOSAL_SENT') return 'admin-pill blue';
  return 'admin-pill slate';
};

const departmentBadgeClass = (department) =>
  `admin-pill ${(department || '').toUpperCase() === 'SUPPORT' ? 'green' : 'blue'}`;

const errorMessage = (error, fallback) =>
  error?.response?.data?.detail || error?.message || fallback;

const MetricCard = ({ icon: Icon, label, value, sub, tone = 'blue' }) => (
  <div className={`admin-kpi-card ${tone}`}>
    <div className="admin-kpi-icon">
      <Icon size={18} />
    </div>
    <div className="admin-kpi-label">{label}</div>
    <div className="admin-kpi-value">{value}</div>
    {sub ? <div className="admin-kpi-sub">{sub}</div> : null}
  </div>
);

const SegmentedFilter = ({ value, onChange, options = DEPARTMENT_OPTIONS }) => (
  <div className="admin-segmented" role="tablist" aria-label="Department filter">
    {options.map((option) => (
      <button
        key={option.value}
        type="button"
        className={value === option.value ? 'active' : ''}
        onClick={() => onChange(option.value)}
      >
        {option.label}
      </button>
    ))}
  </div>
);

const EmptyState = ({ title, subtitle }) => (
  <div className="admin-empty">
    <ShieldCheck size={28} />
    <strong>{title}</strong>
    <span>{subtitle}</span>
  </div>
);

const AdminPanelPage = () => {
  const [activeTab, setActiveTab] = useState('departments');

  // Shared notices
  const [notice, setNotice] = useState(null);

  // Department overview
  const [overview, setOverview] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState('');

  // Employees
  const [employeeDepartment, setEmployeeDepartment] = useState('ALL');
  const [employeeStatus, setEmployeeStatus] = useState('ACTIVE');
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [employees, setEmployees] = useState([]);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [employeesError, setEmployeesError] = useState('');
  const [transferEmployee, setTransferEmployee] = useState(null);
  const [transferForm, setTransferForm] = useState({
    department: 'SALES',
    role: 'SALES_EXECUTIVE',
    reporting_manager_id: '',
  });
  const [managerOptions, setManagerOptions] = useState([]);
  const [managerLoading, setManagerLoading] = useState(false);
  const [transferConfirmed, setTransferConfirmed] = useState(false);
  const [transferSaving, setTransferSaving] = useState(false);
  const [transferError, setTransferError] = useState('');

  // Teams
  const [teamDepartment, setTeamDepartment] = useState('ALL');
  const [teams, setTeams] = useState([]);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [teamsError, setTeamsError] = useState('');
  const [showTeamModal, setShowTeamModal] = useState(false);
  const [teamForm, setTeamForm] = useState({
    name: '',
    department: 'SALES',
    manager_id: '',
    description: '',
  });
  const [createManagers, setCreateManagers] = useState([]);
  const [createManagersLoading, setCreateManagersLoading] = useState(false);
  const [teamSaving, setTeamSaving] = useState(false);
  const [teamFormError, setTeamFormError] = useState('');

  // Handovers
  const [handovers, setHandovers] = useState([]);
  const [handoverStatusCounts, setHandoverStatusCounts] = useState({});
  const [handoverStatus, setHandoverStatus] = useState('all');
  const [handoverSearch, setHandoverSearch] = useState('');
  const [handoverPage, setHandoverPage] = useState(1);
  const [handoverTotal, setHandoverTotal] = useState(0);
  const [handoverLimit] = useState(25);
  const [handoversLoading, setHandoversLoading] = useState(false);
  const [handoversError, setHandoversError] = useState('');

  // Reports
  const [reportDepartment, setReportDepartment] = useState('ALL');
  const [reportFrom, setReportFrom] = useState('');
  const [reportTo, setReportTo] = useState('');
  const [reports, setReports] = useState(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState('');

  const fetchOverview = useCallback(async () => {
    setOverviewLoading(true);
    setOverviewError('');
    try {
      const response = await API.get('/admin/overview');
      setOverview(response.data);
    } catch (error) {
      setOverviewError(errorMessage(error, 'Failed to load department overview.'));
    } finally {
      setOverviewLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  const fetchEmployees = useCallback(async () => {
    setEmployeesLoading(true);
    setEmployeesError('');
    try {
      const response = await API.get('/admin/employees', {
        params: {
          department: employeeDepartment,
          status: employeeStatus,
        },
      });
      setEmployees(response.data?.items || []);
    } catch (error) {
      setEmployeesError(errorMessage(error, 'Failed to load employees.'));
    } finally {
      setEmployeesLoading(false);
    }
  }, [employeeDepartment, employeeStatus]);

  useEffect(() => {
    if (activeTab === 'employees') fetchEmployees();
  }, [activeTab, fetchEmployees]);

  const filteredEmployees = useMemo(() => {
    const term = employeeSearch.trim().toLowerCase();
    if (!term) return employees;
    return employees.filter((employee) =>
      [
        employee.name,
        employee.email,
        employee.phone,
        employee.username,
        employee.role,
        employee.department,
        employee.manager_name,
        employee.team_name,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term))
    );
  }, [employees, employeeSearch]);

  const employeeCounts = useMemo(() => {
    const counts = Object.fromEntries(
      (overview?.departments || []).map((department) => [
        department.key,
        department.employees.total,
      ])
    );
    return {
      sales: counts.SALES ?? 0,
      support: counts.SUPPORT ?? 0,
    };
  }, [overview]);

  const openTransferModal = (employee) => {
    const department = employee.department === 'SUPPORT' ? 'SUPPORT' : 'SALES';
    const options = DEPARTMENT_ROLE_OPTIONS[department];
    const currentRole = cannedRole(employee.role);
    const role = options.some((option) => option.value === currentRole)
      ? currentRole
      : options[0].value;
    setTransferEmployee(employee);
    setTransferForm({
      department,
      role,
      reporting_manager_id: employee.reporting_manager_id
        ? String(employee.reporting_manager_id)
        : '',
    });
    setManagerOptions([]);
    setTransferConfirmed(false);
    setTransferError('');
  };

  const closeTransferModal = () => {
    if (transferSaving) return;
    setTransferEmployee(null);
    setManagerOptions([]);
    setTransferConfirmed(false);
    setTransferError('');
  };

  useEffect(() => {
    let cancelled = false;
    if (!transferEmployee) return undefined;

    const loadManagers = async () => {
      setManagerLoading(true);
      setTransferError('');
      try {
        const response = await API.get('/users/eligible-managers', {
          params: {
            role: transferForm.role,
            department: transferForm.department,
            exclude_user_id: transferEmployee.user_id,
          },
        });
        if (cancelled) return;
        const options = response.data || [];
        setManagerOptions(options);
        setTransferForm((previous) => {
          const kept = options.some(
            (option) => String(option.id) === String(previous.reporting_manager_id)
          );
          return {
            ...previous,
            reporting_manager_id: kept
              ? previous.reporting_manager_id
              : options[0]
                ? String(options[0].id)
                : '',
          };
        });
      } catch (error) {
        if (!cancelled) {
          setManagerOptions([]);
          setTransferError(errorMessage(error, 'Failed to load eligible managers.'));
        }
      } finally {
        if (!cancelled) setManagerLoading(false);
      }
    };

    loadManagers();
    return () => {
      cancelled = true;
    };
  }, [
    transferEmployee,
    transferForm.department,
    transferForm.role,
  ]);

  const handleTransferDepartmentChange = (department) => {
    const options = DEPARTMENT_ROLE_OPTIONS[department];
    setTransferForm({
      department,
      role: options[0].value,
      reporting_manager_id: '',
    });
    setTransferConfirmed(false);
  };

  const handleTransferRoleChange = (role) => {
    setTransferForm((previous) => ({
      ...previous,
      role,
      reporting_manager_id: '',
    }));
    setTransferConfirmed(false);
  };

  const submitTransfer = async () => {
    if (!transferEmployee || !transferConfirmed) return;
    if (!transferForm.reporting_manager_id) {
      setTransferError('Select an active reporting manager for the new department.');
      return;
    }
    setTransferSaving(true);
    setTransferError('');
    try {
      await API.put(`/users/${transferEmployee.user_id}`, {
        department: transferForm.department,
        role: transferForm.role,
        reporting_manager_id: parseInt(transferForm.reporting_manager_id, 10),
      });
      const employeeName = transferEmployee.name;
      setTransferEmployee(null);
      setNotice({
        type: 'success',
        message: `${employeeName} was moved to ${transferForm.department === 'SUPPORT' ? 'Support' : 'Sales'}. Existing employee record and history were preserved.`,
      });
      fetchEmployees();
      fetchOverview();
    } catch (error) {
      setTransferError(errorMessage(error, 'Failed to transfer employee.'));
    } finally {
      setTransferSaving(false);
    }
  };

  const fetchTeams = useCallback(async () => {
    setTeamsLoading(true);
    setTeamsError('');
    try {
      const response = await API.get('/admin/teams', {
        params: { department: teamDepartment },
      });
      setTeams(response.data?.items || []);
    } catch (error) {
      setTeamsError(errorMessage(error, 'Failed to load teams.'));
    } finally {
      setTeamsLoading(false);
    }
  }, [teamDepartment]);

  useEffect(() => {
    if (activeTab === 'teams') fetchTeams();
  }, [activeTab, fetchTeams]);

  const groupedTeams = useMemo(
    () => ({
      SALES: teams.filter((team) => team.department === 'SALES'),
      SUPPORT: teams.filter((team) => team.department === 'SUPPORT'),
    }),
    [teams]
  );

  const openTeamModal = () => {
    const department = teamDepartment === 'SUPPORT' ? 'SUPPORT' : 'SALES';
    setTeamForm({
      name: '',
      department,
      manager_id: '',
      description: '',
    });
    setCreateManagers([]);
    setTeamFormError('');
    setShowTeamModal(true);
  };

  const closeTeamModal = () => {
    if (teamSaving) return;
    setShowTeamModal(false);
    setTeamFormError('');
  };

  useEffect(() => {
    let cancelled = false;
    if (!showTeamModal) return undefined;

    const loadCreateManagers = async () => {
      setCreateManagersLoading(true);
      setTeamFormError('');
      try {
        const response = await API.get('/admin/managers', {
          params: { department: teamForm.department },
        });
        if (cancelled) return;
        const options = (response.data?.items || []).filter(
          (manager) => manager.can_create_team
        );
        setCreateManagers(options);
        setTeamForm((previous) => ({
          ...previous,
          manager_id: options.some(
            (manager) => String(manager.id) === String(previous.manager_id)
          )
            ? previous.manager_id
            : options[0]
              ? String(options[0].id)
              : '',
        }));
      } catch (error) {
        if (!cancelled) {
          setCreateManagers([]);
          setTeamFormError(errorMessage(error, 'Failed to load department managers.'));
        }
      } finally {
        if (!cancelled) setCreateManagersLoading(false);
      }
    };

    loadCreateManagers();
    return () => {
      cancelled = true;
    };
  }, [showTeamModal, teamForm.department]);

  const submitTeam = async (event) => {
    event.preventDefault();
    if (!teamForm.name.trim()) {
      setTeamFormError('Enter a team name.');
      return;
    }
    if (!teamForm.manager_id) {
      setTeamFormError('Select an active department manager.');
      return;
    }
    setTeamSaving(true);
    setTeamFormError('');
    try {
      const response = await API.post('/admin/teams', {
        name: teamForm.name.trim(),
        department: teamForm.department,
        manager_id: parseInt(teamForm.manager_id, 10),
        description: teamForm.description.trim() || null,
      });
      setShowTeamModal(false);
      setNotice({
        type: 'success',
        message: `Team '${response.data?.name || teamForm.name}' was registered under ${teamForm.department === 'SUPPORT' ? 'Support' : 'Sales'} using the existing manager hierarchy.`,
      });
      fetchTeams();
      fetchOverview();
    } catch (error) {
      setTeamFormError(errorMessage(error, 'Failed to create team.'));
    } finally {
      setTeamSaving(false);
    }
  };

  const fetchHandovers = useCallback(async () => {
    setHandoversLoading(true);
    setHandoversError('');
    try {
      const params = {
        status: handoverStatus,
        page: handoverPage,
        limit: handoverLimit,
      };
      if (handoverSearch.trim()) params.search = handoverSearch.trim();
      const response = await API.get('/admin/handovers', { params });
      setHandovers(response.data?.items || []);
      setHandoverTotal(response.data?.total || 0);
      setHandoverStatusCounts(response.data?.status_counts || {});
    } catch (error) {
      setHandoversError(errorMessage(error, 'Failed to load handovers.'));
    } finally {
      setHandoversLoading(false);
    }
  }, [handoverStatus, handoverPage, handoverLimit, handoverSearch]);

  useEffect(() => {
    if (activeTab !== 'handovers') return undefined;
    const timer = setTimeout(fetchHandovers, 300);
    return () => clearTimeout(timer);
  }, [activeTab, fetchHandovers]);

  const totalHandoverPages = Math.max(
    Math.ceil(handoverTotal / handoverLimit),
    1
  );

  const handoverAllCount = useMemo(
    () =>
      Object.values(handoverStatusCounts).reduce(
        (sum, count) => sum + Number(count || 0),
        0
      ),
    [handoverStatusCounts]
  );

  const fetchReports = useCallback(async () => {
    setReportsLoading(true);
    setReportsError('');
    try {
      const params = { department: reportDepartment };
      if (reportFrom) params.date_from = reportFrom;
      if (reportTo) params.date_to = reportTo;
      const response = await API.get('/admin/reports', { params });
      setReports(response.data);
    } catch (error) {
      setReportsError(errorMessage(error, 'Failed to load department reports.'));
    } finally {
      setReportsLoading(false);
    }
  }, [reportDepartment, reportFrom, reportTo]);

  useEffect(() => {
    if (activeTab === 'reports') fetchReports();
  }, [activeTab, fetchReports]);

  const reportColumns = useMemo(() => {
    if (!reports) return [];
    const columns = [...(reports.departments || [])];
    if (reports.combined) columns.push(reports.combined);
    if (reports.company) columns.push(reports.company);
    return columns;
  }, [reports]);

  const reportScope = useMemo(() => {
    if (!reports || (reportDepartment !== 'SALES' && reportDepartment !== 'SUPPORT')) {
      return null;
    }
    return reports.departments.find((item) => item.key === reportDepartment) || null;
  }, [reports, reportDepartment]);

  const reportKpis = useMemo(() => {
    if (!reports) return [];

    if (reportScope) {
      return [
        {
          icon: TrendingUp,
          label: `${reportScope.label} Calls`,
          value: reportScope.calls.total,
          sub: `${reportScope.calls.connected} connected`,
          tone: reportScope.key === 'SUPPORT' ? 'green' : 'blue',
        },
        {
          icon: CalendarClock,
          label: `${reportScope.label} Follow-ups`,
          value: reportScope.followups.total,
          sub: `${reportScope.followups.overdue} overdue`,
          tone: 'amber',
        },
        {
          icon: ArrowRightLeft,
          label: `${reportScope.label} Handovers`,
          value: reportScope.handovers.total,
          sub: `${reportScope.handovers.completed} completed`,
          tone: 'purple',
        },
        {
          icon: Users,
          label: `${reportScope.label} Employees`,
          value: reportScope.employees.total,
          sub: `${reportScope.employees.active} active`,
          tone: reportScope.key === 'SUPPORT' ? 'green' : 'blue',
        },
        {
          icon: Activity,
          label: 'Company Calls',
          value: reports.company.calls.total,
          sub: `${reports.company.calls.connected} connected`,
          tone: 'green',
        },
        {
          icon: Building2,
          label: 'Company Employees',
          value: reports.company.employees.total,
          sub: `${reports.company.employees.active} active`,
          tone: 'blue',
        },
      ];
    }

    const sales = reports.departments.find((item) => item.key === 'SALES');
    const support = reports.departments.find((item) => item.key === 'SUPPORT');
    return [
      {
        icon: TrendingUp,
        label: 'Sales Calls',
        value: sales?.calls.total ?? 0,
        sub: 'Department-scoped',
        tone: 'blue',
      },
      {
        icon: CalendarClock,
        label: 'Sales Follow-ups',
        value: sales?.followups.total ?? 0,
        sub: 'Department-scoped',
        tone: 'amber',
      },
      {
        icon: ShieldCheck,
        label: 'Support Calls',
        value: support?.calls.total ?? 0,
        sub: 'Department-scoped',
        tone: 'green',
      },
      {
        icon: ArrowRightLeft,
        label: 'Handovers',
        value: reports.company.handovers.total,
        sub: `${reports.company.handovers.completed} completed`,
        tone: 'purple',
      },
      {
        icon: Users,
        label: 'Company Employees',
        value: reports.company.employees.total,
        sub: `${reports.company.employees.active} active`,
        tone: 'blue',
      },
      {
        icon: Activity,
        label: 'Company Calls',
        value: reports.company.calls.total,
        sub: `${reports.company.calls.connected} connected`,
        tone: 'green',
      },
    ];
  }, [reports, reportScope]);

  const reportRows = useMemo(
    () => [
      {
        label: 'Employees',
        render: (stat) => `${stat.employees.active} active / ${stat.employees.total} total`,
      },
      {
        label: 'Managers / Executives',
        render: (stat) => `${stat.employees.managers} / ${stat.employees.executives}`,
      },
      {
        label: 'Teams',
        render: (stat) =>
          `${stat.teams.total} (${stat.teams.registered} registered, ${stat.teams.implicit} hierarchy)`,
      },
      {
        label: 'People in teams',
        render: (stat) => stat.teams.people,
      },
      {
        label: 'Calls',
        render: (stat) =>
          `${stat.calls.total} (${stat.calls.inbound} in / ${stat.calls.outbound} out)`,
      },
      {
        label: 'Connected / Missed',
        render: (stat) => `${stat.calls.connected} / ${stat.calls.missed}`,
      },
      {
        label: 'Follow-ups',
        render: (stat) =>
          `${stat.followups.total} (${stat.followups.pending} pending, ${stat.followups.overdue} overdue)`,
      },
      {
        label: 'Leads',
        render: (stat) => `${stat.leads.total} (${stat.leads.converted} converted)`,
      },
      {
        label: 'Handovers',
        render: (stat) =>
          `${stat.handovers.total} (${stat.handovers.pending} pending, ${stat.handovers.completed} completed)`,
      },
    ],
    []
  );

  const renderDepartmentCards = () => {
    if (overviewLoading) {
      return (
        <div className="admin-loading">
          <RefreshCw size={20} className="spin" /> Loading department statistics...
        </div>
      );
    }
    if (overviewError) {
      return (
        <div className="admin-error">
          <AlertCircle size={18} /> {overviewError}
        </div>
      );
    }
    if (!overview) return null;

    return (
      <>
        <div className="admin-dept-grid">
          {overview.departments.map((department) => (
            <div
              key={department.key}
              className={`admin-dept-card ${department.key.toLowerCase()}`}
            >
              <div className="admin-dept-head">
                <div className="admin-dept-title">
                  <span className="admin-dept-icon">
                    {department.key === 'SALES' ? (
                      <TrendingUp size={20} />
                    ) : (
                      <ShieldCheck size={20} />
                    )}
                  </span>
                  <div>
                    <h3>{department.label} Department</h3>
                    <span>{department.key}</span>
                  </div>
                </div>
                <span className={`admin-pill ${department.key === 'SUPPORT' ? 'green' : 'blue'}`}>
                  {department.employees.active} active
                </span>
              </div>

              <div className="admin-dept-kpis">
                <div>
                  <span>Employees</span>
                  <strong>{department.employees.total}</strong>
                  <small>
                    {department.employees.managers} managers · {department.employees.executives} executives
                  </small>
                </div>
                <div>
                  <span>Teams</span>
                  <strong>{department.teams.total}</strong>
                  <small>{department.teams.people} people in teams</small>
                </div>
                <div>
                  <span>Calls</span>
                  <strong>{department.calls.total}</strong>
                  <small>
                    {department.calls.inbound} in · {department.calls.outbound} out
                  </small>
                </div>
                <div>
                  <span>Follow-ups</span>
                  <strong>{department.followups.total}</strong>
                  <small>
                    {department.followups.pending} pending · {department.followups.overdue} overdue
                  </small>
                </div>
              </div>

              <div className="admin-dept-footer">
                <span>
                  <Target size={14} /> Leads: <strong>{department.leads.total}</strong>
                </span>
                <span>
                  <ArrowRightLeft size={14} /> Handovers: <strong>{department.handovers.total}</strong>
                </span>
                <span>
                  <Activity size={14} /> Connected: <strong>{department.calls.connected}</strong>
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="admin-section-card">
          <div className="admin-section-head">
            <div>
              <h2>Company-wide Overview</h2>
              <p>
                Combined visibility for Administrators. Sales/Support record pages use the same
                employee-ID department scoping.
              </p>
            </div>
            <button type="button" className="admin-btn ghost" onClick={fetchOverview}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          <div className="admin-kpi-grid">
            <MetricCard
              icon={Users}
              label="Total Employees"
              value={overview.company.employees.total}
              sub={`${overview.company.employees.active} active`}
              tone="blue"
            />
            <MetricCard
              icon={ShieldCheck}
              label="Teams"
              value={overview.company.teams.total}
              sub={`${overview.company.teams.people} people`}
              tone="green"
            />
            <MetricCard
              icon={Activity}
              label="Calls"
              value={overview.company.calls.total}
              sub={`${overview.company.calls.connected} connected`}
              tone="purple"
            />
            <MetricCard
              icon={CalendarClock}
              label="Follow-ups"
              value={overview.company.followups.total}
              sub={`${overview.company.followups.pending} pending`}
              tone="amber"
            />
            <MetricCard
              icon={Target}
              label="Leads"
              value={overview.company.leads.total}
              sub={`${overview.company.leads.converted} converted`}
              tone="blue"
            />
            <MetricCard
              icon={ArrowRightLeft}
              label="Handovers"
              value={overview.company.handovers.total}
              sub={`${overview.company.handovers.pending} pending`}
              tone="green"
            />
          </div>

          <div className="admin-combined-strip">
            <span>Sales + Support combined</span>
            <strong>{overview.combined.employees.total} employees</strong>
            <strong>{overview.combined.teams.total} teams</strong>
            <strong>{overview.combined.calls.total} calls</strong>
            <strong>{overview.combined.followups.total} follow-ups</strong>
            <strong>{overview.combined.handovers.total} handovers</strong>
          </div>
        </div>
      </>
    );
  };

  const renderEmployeesTab = () => (
    <>
      <div className="admin-section-card">
        <div className="admin-section-head">
          <div>
            <h2>Employee Management</h2>
            <p>
              Existing employee records are reused. Transfers update the department, role and
              reporting manager without creating duplicates.
            </p>
          </div>
          <button type="button" className="admin-btn ghost" onClick={fetchEmployees}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <div className="admin-toolbar">
          <SegmentedFilter value={employeeDepartment} onChange={setEmployeeDepartment} />
          <div className="admin-toolbar-right">
            <div className="admin-search">
              <Search size={15} />
              <input
                type="text"
                placeholder="Search name, email, role, manager..."
                value={employeeSearch}
                onChange={(event) => setEmployeeSearch(event.target.value)}
              />
            </div>
            <select
              value={employeeStatus}
              onChange={(event) => setEmployeeStatus(event.target.value)}
            >
              <option value="ACTIVE">Active employees</option>
              <option value="INACTIVE">Inactive employees</option>
              <option value="ALL">All statuses</option>
            </select>
          </div>
        </div>

        <div className="admin-scope-note">
          <Users size={15} />
          <span>
            Sales: <strong>{employeeCounts.sales}</strong> · Support:{' '}
            <strong>{employeeCounts.support}</strong> · Showing{' '}
            <strong>{filteredEmployees.length}</strong> records
          </span>
        </div>

        {employeesError ? (
          <div className="admin-error">
            <AlertCircle size={18} /> {employeesError}
          </div>
        ) : null}

        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Department</th>
                <th>Role</th>
                <th>Reporting Manager</th>
                <th>Registered Team</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {employeesLoading ? (
                <tr>
                  <td colSpan={7}>
                    <div className="admin-loading small">
                      <RefreshCw size={16} className="spin" /> Loading employees...
                    </div>
                  </td>
                </tr>
              ) : filteredEmployees.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      title="No employees found"
                      subtitle="Try a different department, status or search term."
                    />
                  </td>
                </tr>
              ) : (
                filteredEmployees.map((employee) => (
                  <tr key={employee.id}>
                    <td>
                      <div className="admin-person">
                        <span className="admin-avatar">
                          {employee.photo_url ? (
                            <img src={employee.photo_url} alt="" />
                          ) : (
                            (employee.name || '?').slice(0, 1).toUpperCase()
                          )}
                        </span>
                        <div>
                          <strong>{employee.name}</strong>
                          <small>
                            {employee.email || employee.username} · #{employee.id}
                          </small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={departmentBadgeClass(employee.department)}>
                        {employee.department}
                      </span>
                    </td>
                    <td>
                      <span className="admin-role-text">{roleLabel(employee.role)}</span>
                      {employee.direct_reports_count > 0 ? (
                        <small className="admin-block-sub">
                          {employee.direct_reports_count} direct report(s)
                        </small>
                      ) : null}
                    </td>
                    <td>{employee.reporting_manager_name || employee.manager_name || '—'}</td>
                    <td>{employee.team_name || 'Hierarchy team'}</td>
                    <td>
                      <span
                        className={`admin-pill ${
                          employee.status === 'ACTIVE' ? 'green' : 'slate'
                        }`}
                      >
                        {employee.status}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        type="button"
                        className="admin-btn small"
                        disabled={!employee.user_id}
                        title={
                          !employee.user_id
                            ? 'This employee record has no linked login user.'
                            : employee.direct_reports_count > 0
                              ? 'Reassign direct reports in Users & Roles before transferring this manager.'
                              : 'Assign or transfer this employee between Sales and Support.'
                        }
                        onClick={() => openTransferModal(employee)}
                      >
                        <ArrowRightLeft size={13} />
                        {employee.department === 'SALES' ? 'Transfer' : 'Assign'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {transferEmployee ? (
        <div className="modal-backdrop" role="presentation">
          <div className="modal-content admin-modal" role="dialog" aria-modal="true">
            <div className="admin-modal-head">
              <div>
                <h3>Assign / Transfer Employee</h3>
                <p>
                  {transferEmployee.name} · Employee #{transferEmployee.id}
                </p>
              </div>
              <button type="button" className="admin-icon-btn" onClick={closeTransferModal}>
                <X size={18} />
              </button>
            </div>

            {transferEmployee.direct_reports_count > 0 ? (
              <div className="admin-warning">
                <AlertCircle size={16} />
                This manager has {transferEmployee.direct_reports_count} direct report(s). Reassign
                their reports in Users &amp; Roles first to avoid cross-department reporting. The
                backend transfer validation will still enforce role and manager rules.
              </div>
            ) : null}

            <div className="admin-form-grid">
              <label>
                Current Department
                <input value={transferEmployee.department || '—'} disabled />
              </label>
              <label>
                New Department
                <select
                  value={transferForm.department}
                  onChange={(event) => handleTransferDepartmentChange(event.target.value)}
                >
                  <option value="SALES">Sales</option>
                  <option value="SUPPORT">Support</option>
                </select>
              </label>
              <label>
                Role
                <select
                  value={transferForm.role}
                  onChange={(event) => handleTransferRoleChange(event.target.value)}
                >
                  {(DEPARTMENT_ROLE_OPTIONS[transferForm.department] || []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Reporting Manager
                <select
                  value={transferForm.reporting_manager_id}
                  onChange={(event) =>
                    setTransferForm((previous) => ({
                      ...previous,
                      reporting_manager_id: event.target.value,
                    }))
                  }
                  disabled={managerLoading}
                >
                  {managerOptions.length === 0 ? (
                    <option value="">
                      {managerLoading ? 'Loading managers...' : 'No eligible manager found'}
                    </option>
                  ) : null}
                  {managerOptions.map((manager) => (
                    <option key={manager.id} value={manager.id}>
                      {manager.name} ({roleLabel(manager.role)})
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="admin-transfer-summary">
              <CheckCircle size={16} />
              <span>
                Existing employee record <strong>#{transferEmployee.id}</strong> is reused. Leads,
                calls, follow-ups and team history remain attached to the same employee ID.
              </span>
            </div>

            <label className="admin-confirm-row">
              <input
                type="checkbox"
                checked={transferConfirmed}
                onChange={(event) => setTransferConfirmed(event.target.checked)}
              />
              <span>
                I confirm moving this employee to{' '}
                <strong>{transferForm.department === 'SUPPORT' ? 'Support' : 'Sales'}</strong>{' '}
                with the selected role and reporting manager.
              </span>
            </label>

            {transferError ? (
              <div className="admin-error">
                <AlertCircle size={16} /> {transferError}
              </div>
            ) : null}

            <div className="admin-modal-actions">
              <button type="button" className="admin-btn ghost" onClick={closeTransferModal}>
                Cancel
              </button>
              <button
                type="button"
                className="admin-btn primary"
                disabled={!transferConfirmed || transferSaving || managerLoading || !transferForm.reporting_manager_id}
                onClick={submitTransfer}
              >
                {transferSaving ? <RefreshCw size={14} className="spin" /> : <ArrowRightLeft size={14} />}
                Confirm Transfer
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );

  const renderTeamSection = (departmentKey, label) => {
    const departmentTeams = groupedTeams[departmentKey] || [];
    return (
      <div className="admin-team-section" key={departmentKey}>
        <div className="admin-team-section-head">
          <h3>
            <span className={`admin-pill ${departmentKey === 'SUPPORT' ? 'green' : 'blue'}`}>
              {label}
            </span>
            {departmentTeams.length} team{departmentTeams.length === 1 ? '' : 's'}
          </h3>
        </div>
        {departmentTeams.length === 0 ? (
          <EmptyState
            title={`No ${label} teams`}
            subtitle="Create a team from an existing department manager or adjust the filter."
          />
        ) : (
          <div className="admin-team-grid">
            {departmentTeams.map((team) => (
              <div className="admin-team-card" key={team.key}>
                <div className="admin-team-head">
                  <div>
                    <h4>{team.name}</h4>
                    <span>
                      Manager: <strong>{team.manager_name}</strong> · {roleLabel(team.manager_role)}
                    </span>
                  </div>
                  <span className={`admin-pill ${team.registered ? 'purple' : 'slate'}`}>
                    {team.registered ? 'Registered' : 'Hierarchy'}
                  </span>
                </div>
                {team.description ? (
                  <p className="admin-team-desc">{team.description}</p>
                ) : null}
                <div className="admin-team-meta">
                  <span>
                    <Users size={14} /> {team.member_count} member{team.member_count === 1 ? '' : 's'}
                  </span>
                  <span>
                    <UserCheck size={14} /> Manager: {team.manager?.email || team.manager?.phone || '—'}
                  </span>
                </div>
                <div className="admin-member-list">
                  {team.members.length === 0 ? (
                    <span className="admin-muted">No reportees in this department yet.</span>
                  ) : (
                    team.members.map((member) => (
                      <span key={member.id} className="admin-member-chip">
                        <strong>{member.name}</strong>
                        <small>{roleLabel(member.role)}</small>
                      </span>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderTeamsTab = () => (
    <>
      <div className="admin-section-card">
        <div className="admin-section-head">
          <div>
            <h2>Team Management</h2>
            <p>
              Teams are manager-led hierarchies. Registering a team only adds a name and does not
              duplicate or reassign employee records.
            </p>
          </div>
          <div className="admin-head-actions">
            <button type="button" className="admin-btn ghost" onClick={fetchTeams}>
              <RefreshCw size={14} /> Refresh
            </button>
            <button type="button" className="admin-btn primary" onClick={openTeamModal}>
              <Plus size={14} /> Create Team
            </button>
          </div>
        </div>

        <div className="admin-toolbar">
          <SegmentedFilter value={teamDepartment} onChange={setTeamDepartment} />
          <span className="admin-scope-note inline">
            <ShieldCheck size={15} /> Cross-department managers are rejected by the backend.
          </span>
        </div>

        {teamsError ? (
          <div className="admin-error">
            <AlertCircle size={18} /> {teamsError}
          </div>
        ) : null}

        {teamsLoading ? (
          <div className="admin-loading">
            <RefreshCw size={18} className="spin" /> Loading teams...
          </div>
        ) : (
          <>
            {(teamDepartment === 'ALL' || teamDepartment === 'SALES') &&
              renderTeamSection('SALES', 'Sales')}
            {(teamDepartment === 'ALL' || teamDepartment === 'SUPPORT') &&
              renderTeamSection('SUPPORT', 'Support')}
          </>
        )}
      </div>

      {showTeamModal ? (
        <div className="modal-backdrop" role="presentation">
          <div className="modal-content admin-modal" role="dialog" aria-modal="true">
            <div className="admin-modal-head">
              <div>
                <h3>Create Department Team</h3>
                <p>The selected manager must already exist in the chosen department.</p>
              </div>
              <button type="button" className="admin-icon-btn" onClick={closeTeamModal}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={submitTeam}>
              <div className="admin-form-grid">
                <label>
                  Department
                  <select
                    value={teamForm.department}
                    onChange={(event) => {
                      const department = event.target.value;
                      setTeamForm((previous) => ({
                        ...previous,
                        department,
                        manager_id: '',
                      }));
                    }}
                  >
                    <option value="SALES">Sales</option>
                    <option value="SUPPORT">Support</option>
                  </select>
                </label>
                <label>
                  Team Name
                  <input
                    type="text"
                    placeholder="e.g. Enterprise Sales Team"
                    value={teamForm.name}
                    maxLength={100}
                    onChange={(event) =>
                      setTeamForm((previous) => ({ ...previous, name: event.target.value }))
                    }
                  />
                </label>
                <label className="span-2">
                  Team Manager
                  <select
                    value={teamForm.manager_id}
                    onChange={(event) =>
                      setTeamForm((previous) => ({
                        ...previous,
                        manager_id: event.target.value,
                      }))
                    }
                    disabled={createManagersLoading}
                  >
                    {createManagers.length === 0 ? (
                      <option value="">
                        {createManagersLoading
                          ? 'Loading managers...'
                          : 'No unregistered manager in this department'}
                      </option>
                    ) : null}
                    {createManagers.map((manager) => (
                      <option key={manager.id} value={manager.id}>
                        {manager.name} ({roleLabel(manager.role)})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="span-2">
                  Description (optional)
                  <textarea
                    rows={3}
                    placeholder="Team responsibility or focus area"
                    value={teamForm.description}
                    onChange={(event) =>
                      setTeamForm((previous) => ({
                        ...previous,
                        description: event.target.value,
                      }))
                    }
                  />
                </label>
              </div>

              <div className="admin-transfer-summary">
                <CheckCircle size={16} />
                <span>
                  Team membership is resolved from <code>Employee.manager_id</code>. Existing
                  employees keep their IDs, leads, calls and follow-up history.
                </span>
              </div>

              {teamFormError ? (
                <div className="admin-error">
                  <AlertCircle size={16} /> {teamFormError}
                </div>
              ) : null}

              <div className="admin-modal-actions">
                <button type="button" className="admin-btn ghost" onClick={closeTeamModal}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="admin-btn primary"
                  disabled={teamSaving || createManagersLoading || !teamForm.manager_id}
                >
                  {teamSaving ? <RefreshCw size={14} className="spin" /> : <Plus size={14} />}
                  Create Team
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );

  const renderHandoversTab = () => (
    <div className="admin-section-card">
      <div className="admin-section-head">
        <div>
          <h2>Sales → Support Handover Monitoring</h2>
          <p>
            Read-only view of existing handover records. Customer ownership and lead history are
            preserved; rows without an explicit Sales attribution fall back to the lead owner.
          </p>
        </div>
        <button type="button" className="admin-btn ghost" onClick={fetchHandovers}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="admin-toolbar">
        <div className="admin-status-pills">
          <button
            type="button"
            className={handoverStatus === 'all' ? 'active' : ''}
            onClick={() => {
              setHandoverStatus('all');
              setHandoverPage(1);
            }}
          >
            All <strong>{handoverAllCount}</strong>
          </button>
          {HANDOVER_STATUSES.filter((status) => status.value !== 'all').map((status) => (
            <button
              key={status.value}
              type="button"
              className={handoverStatus === status.value ? 'active' : ''}
              onClick={() => {
                setHandoverStatus(status.value);
                setHandoverPage(1);
              }}
            >
              {status.label}{' '}
              <strong>{handoverStatusCounts[status.value] || 0}</strong>
            </button>
          ))}
        </div>
        <div className="admin-toolbar-right">
          <div className="admin-search">
            <Search size={15} />
            <input
              type="text"
              placeholder="Search customer, product, employee..."
              value={handoverSearch}
              onChange={(event) => {
                setHandoverSearch(event.target.value);
                setHandoverPage(1);
              }}
            />
          </div>
        </div>
      </div>

      {handoversError ? (
        <div className="admin-error">
          <AlertCircle size={18} /> {handoversError}
        </div>
      ) : null}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Customer</th>
              <th>Sales Employee</th>
              <th>Support Employee</th>
              <th>Product / Service</th>
              <th>Handover Date</th>
              <th>Deal Value</th>
              <th>Sales Status</th>
              <th>Support Status</th>
            </tr>
          </thead>
          <tbody>
            {handoversLoading ? (
              <tr>
                <td colSpan={8}>
                  <div className="admin-loading small">
                    <RefreshCw size={16} className="spin" /> Loading handovers...
                  </div>
                </td>
              </tr>
            ) : handovers.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  <EmptyState
                    title="No handovers found"
                    subtitle="No Sales → Support handover matches the current filter."
                  />
                </td>
              </tr>
            ) : (
              handovers.map((handover) => (
                <tr key={handover.id}>
                  <td>
                    <div className="admin-person">
                      <span className="admin-avatar">
                        {(handover.customer_name || '?').slice(0, 1).toUpperCase()}
                      </span>
                      <div>
                        <strong>{handover.customer_name}</strong>
                        <small>
                          {handover.company_name || '—'} · Lead #{handover.lead_id} · Customer #
                          {handover.customer_id}
                        </small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <strong>{handover.sales_employee_name}</strong>
                    <small className="admin-block-sub">
                      {handover.sales_employee_source === 'LEAD_OWNER'
                        ? 'Lead owner fallback'
                        : handover.sales_employee_source === 'HANDOFF'
                          ? 'Handoff attribution'
                          : 'No Sales owner'}
                    </small>
                  </td>
                  <td>
                    <strong>{handover.support_employee_name}</strong>
                    <small className="admin-block-sub">
                      Manager: {handover.support_manager_name}
                      {handover.assigned_agent_id
                        ? ` · Agent: ${handover.assigned_agent_name}`
                        : ' · Not assigned'}
                    </small>
                  </td>
                  <td>
                    <strong>{handover.product_service || handover.selected_bundle || '—'}</strong>
                    <small className="admin-block-sub">{handover.product_category || '—'}</small>
                  </td>
                  <td>{formatDateTime(handover.handover_date)}</td>
                  <td>{formatCurrency(handover.total_deal_amount)}</td>
                  <td>
                    <span className={salesStatusClass(handover.sales_status ?? handover.lead_status)}>
                      {String(handover.sales_status ?? handover.lead_status ?? 'N/A').replaceAll('_', ' ')}
                    </span>
                  </td>
                  <td>
                    <span
                      className={handoverStatusClass(
                        handover.support_status || handover.onboarding_status
                      )}
                    >
                      {handoverSupportStatusLabel(
                        handover.support_status || handover.onboarding_status
                      )}
                    </span>
                    <small className="admin-block-sub">Support lifecycle only</small>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="admin-pagination">
        <span>
          Page {handoverPage} of {totalHandoverPages} · {handoverTotal} handover
          {handoverTotal === 1 ? '' : 's'}
        </span>
        <div>
          <button
            type="button"
            className="admin-btn ghost small"
            disabled={handoverPage <= 1}
            onClick={() => setHandoverPage((page) => Math.max(1, page - 1))}
          >
            <ChevronLeft size={14} /> Previous
          </button>
          <button
            type="button"
            className="admin-btn ghost small"
            disabled={handoverPage >= totalHandoverPages}
            onClick={() => setHandoverPage((page) => Math.min(totalHandoverPages, page + 1))}
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );

  const renderReportsTab = () => (
    <>
      <div className="admin-section-card">
        <div className="admin-section-head">
          <div>
            <h2>Department Reports</h2>
            <p>
              Counts are calculated from the same department employee-ID sets used to filter Call
              Logs and Follow-ups. Sales and Support statistics remain separate, with combined and
              company-wide totals for Administrators.
            </p>
          </div>
          <button type="button" className="admin-btn ghost" onClick={fetchReports}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <div className="admin-toolbar">
          <SegmentedFilter value={reportDepartment} onChange={setReportDepartment} />
          <div className="admin-toolbar-right">
            <label className="admin-inline-field">
              From
              <input type="date" value={reportFrom} onChange={(event) => setReportFrom(event.target.value)} />
            </label>
            <label className="admin-inline-field">
              To
              <input type="date" value={reportTo} onChange={(event) => setReportTo(event.target.value)} />
            </label>
            {(reportFrom || reportTo) && (
              <button
                type="button"
                className="admin-btn ghost small"
                onClick={() => {
                  setReportFrom('');
                  setReportTo('');
                }}
              >
                <X size={13} /> Clear dates
              </button>
            )}
          </div>
        </div>

        {reportsError ? (
          <div className="admin-error">
            <AlertCircle size={18} /> {reportsError}
          </div>
        ) : null}

        {reportsLoading ? (
          <div className="admin-loading">
            <RefreshCw size={18} className="spin" /> Calculating department reports...
          </div>
        ) : reports ? (
          <>
            <div className="admin-kpi-grid">
              {reportKpis.map((kpi) => (
                <MetricCard key={kpi.label} {...kpi} />
              ))}
            </div>

            <div className="admin-table-wrap report-table">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    {reportColumns.map((column) => (
                      <th key={`${column.key}-${column.label}`}>
                        {column.label}
                        {column.key === 'COMPANY' ? (
                          <small className="admin-block-sub">All departments</small>
                        ) : null}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {reportRows.map((row) => (
                    <tr key={row.label}>
                      <td>
                        <strong>{row.label}</strong>
                      </td>
                      {reportColumns.map((column) => (
                        <td key={`${column.key}-${row.label}`}>{row.render(column)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="admin-report-footnote">
              <Clock size={14} />
              <span>
                Date range applies to call creation, follow-up schedule, and handover creation.
                Department counts use current employee department assignments; transferred
                employees move with their full history, which is why totals can change after a
                transfer.
              </span>
            </div>
          </>
        ) : null}
      </div>
    </>
  );

  return (
    <div className="page-container admin-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Admin Panel</h1>
          <p className="page-subtitle">
            Sales and Support department segregation, employee transfers, team registry, call and
            follow-up scoping, handover monitoring and combined reports.
          </p>
        </div>
        <div className="header-actions">
          <span className="admin-admin-badge">
            <ShieldCheck size={15} /> Admin only
          </span>
        </div>
      </div>

      <div className="admin-tabs" role="tablist" aria-label="Admin Panel sections">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              type="button"
              className={activeTab === tab.key ? 'active' : ''}
              onClick={() => setActiveTab(tab.key)}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {notice ? (
        <div className={`admin-notice ${notice.type}`}>
          <CheckCircle size={17} />
          <span>{notice.message}</span>
          <button type="button" onClick={() => setNotice(null)} title="Dismiss">
            <X size={15} />
          </button>
        </div>
      ) : null}

      {activeTab === 'departments' ? renderDepartmentCards() : null}
      {activeTab === 'employees' ? renderEmployeesTab() : null}
      {activeTab === 'teams' ? renderTeamsTab() : null}
      {activeTab === 'handovers' ? renderHandoversTab() : null}
      {activeTab === 'reports' ? renderReportsTab() : null}
    </div>
  );
};

export default AdminPanelPage;
