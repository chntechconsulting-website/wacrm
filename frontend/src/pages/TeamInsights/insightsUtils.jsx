import API from '../../services/api';
import { formatLeadReceived } from '../../utils/dateUtils';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const IST_DAY = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Kolkata',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

export const METRIC_TITLES = {
  total_employees: 'Total Employees',
  active_employees: 'Active Employees',
  total_assigned_leads: 'Assigned Leads',
  assigned_leads: 'Assigned Leads',
  new_leads: 'New Leads',
  unassigned_leads: 'Unassigned Leads',
  contacted_leads: 'Contacted Leads',
  interested_leads: 'Interested Leads',
  converted_leads: 'Converted Leads',
  lost_leads: 'Lost Leads',
  conversion_percentage: 'Conversion Rate',
  total_calls: 'Total Calls',
  inbound_calls: 'Inbound Calls',
  outbound_calls: 'Outbound Calls',
  answered_calls: 'Answered Calls',
  connected_calls: 'Connected Calls',
  missed_calls: 'Missed Calls',
  failed_calls: 'Failed Calls',
  connected_duration_seconds: 'Connected Call Duration',
  avg_connected_duration_seconds: 'Average Call Duration',
  mobile_calls: 'Mobile Calls',
  doocti_calls: 'Doocti Calls',
  ivr_calls: 'IVR Calls',
  completed_followups: 'Completed Follow-ups',
  pending_followups: 'Pending Follow-ups',
  overdue_followups: 'Overdue Follow-ups',
};

export const PRESETS = [
  { value: 'TODAY', label: 'Today' },
  { value: 'YESTERDAY', label: 'Yesterday' },
  { value: 'LAST_7_DAYS', label: 'Last 7 days' },
  { value: 'LAST_30_DAYS', label: 'Last 30 days' },
  { value: 'THIS_MONTH', label: 'This month' },
  { value: 'PREVIOUS_MONTH', label: 'Previous month' },
  { value: 'CUSTOM', label: 'Custom range' },
  { value: 'ALL_TIME', label: 'All time' },
];

export const EXPORT_DATASETS = [
  { value: 'employees', label: 'Employee performance' },
  { value: 'conversion_employees', label: 'Conversion by employee' },
  { value: 'conversion_sources', label: 'Conversion by lead source' },
  { value: 'timeline', label: 'Activity timeline' },
];

export const DEFAULT_FILTERS = {
  preset: 'LAST_30_DAYS',
  start_date: '',
  end_date: '',
  employee_id: '',
  department: '',
  lead_source: '',
  call_source: '',
};

export const istToday = () => IST_DAY.format(new Date());

export const istDaysAgo = (days) =>
  IST_DAY.format(new Date(Date.now() - Math.max(0, Number(days) || 0) * 86400000));

export const buildParams = (filters = {}) => {
  const params = { preset: filters.preset || DEFAULT_FILTERS.preset };
  if (params.preset === 'CUSTOM') {
    params.start_date = filters.start_date || undefined;
    params.end_date = filters.end_date || undefined;
  }
  if (filters.employee_id) params.employee_id = filters.employee_id;
  if (filters.department) params.department = filters.department;
  if (filters.lead_source) params.lead_source = filters.lead_source;
  if (filters.call_source) params.call_source = filters.call_source;
  return params;
};

export const formatNumber = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString('en-IN') : '0';
};

export const formatPercent = (value, digits = 1) => {
  const number = Number(value);
  return `${Number.isFinite(number) ? number.toFixed(digits) : '0.0'}%`;
};

export const formatDuration = (seconds) => {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  if (minutes < 60) return `${minutes}m ${String(remainder).padStart(2, '0')}s`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${String(mins).padStart(2, '0')}m`;
};

export const formatDateOnly = (value) => {
  if (!value) return '—';
  const raw = String(value).slice(0, 10);
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return String(value);
  const [, year, month, day] = match;
  return `${day} ${MONTHS[Number(month) - 1] || month} ${year}`;
};

export const formatDateTime = (value) => {
  if (!value) return '—';
  const str = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(str)) return formatDateOnly(str);
  const formatted = formatLeadReceived(str);
  return formatted.full || str;
};

const BADGE_TONE = {
  green: 'ti-badge ti-badge-green',
  blue: 'ti-badge ti-badge-blue',
  amber: 'ti-badge ti-badge-amber',
  red: 'ti-badge ti-badge-red',
  violet: 'ti-badge ti-badge-violet',
  slate: 'ti-badge ti-badge-slate',
};

const CONNECTED_STATUSES = new Set(['ANSWERED', 'COMPLETED', 'CONNECTED']);
const MISSED_STATUSES = new Set(['MISSED', 'NO_ANSWER', 'NOANSWER', 'UNANSWERED', 'MISSED_CALL']);
const FAILED_STATUSES = new Set(['FAILED', 'BUSY', 'CANCEL', 'CANCELLED', 'ERROR', 'REJECTED', 'ABORTED']);
const CONVERTED_STATUSES = new Set([
  'WON', 'CONVERTED', 'CLOSED_WON', 'PENDING_ONBOARDING',
  'ONBOARDING_IN_PROGRESS', 'COMPLETED_ONBOARDING',
]);
const LOST_STATUSES = new Set(['LOST', 'LOST_LEAD', 'NOT_INTERESTED', 'JUNK', 'SPAM', 'INVALID']);

const norm = (value) => String(value || '').trim().toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_|_$/g, '');

export const statusTone = (status) => {
  const token = norm(status);
  if (CONNECTED_STATUSES.has(token) || CONVERTED_STATUSES.has(token)) return 'green';
  if (MISSED_STATUSES.has(token)) return 'amber';
  if (FAILED_STATUSES.has(token) || LOST_STATUSES.has(token)) return 'red';
  if (['NO_ANSWER', 'RINGING', 'PENDING'].includes(token)) return 'amber';
  if (['INBOUND'].includes(token)) return 'violet';
  if (['OUTBOUND'].includes(token)) return 'blue';
  if (['MOBILE', 'MOBILE_SIM', 'DIRECT_DIAL', 'SIM', 'DEVICE'].includes(token)) return 'green';
  if (['DOOCTI'].includes(token)) return 'blue';
  return 'slate';
};

export const badgeClass = (tone) => BADGE_TONE[tone] || BADGE_TONE.slate;

export const renderRecordValue = (key, value) => {
  if (value === null || value === undefined || value === '') return <span className="ti-muted">—</span>;
  if (key.endsWith('_at') || key === 'timestamp') return formatDateTime(value);
  if (key === 'followup_date' || key.endsWith('_date')) return formatDateOnly(value);
  if (key === 'duration_seconds' || key === 'connected_duration_seconds' || key === 'avg_duration_seconds') {
    return formatDuration(value);
  }
  if (key === 'conversion_percentage') return formatPercent(value);
  if (typeof value === 'boolean') {
    return <span className={badgeClass(value ? 'green' : 'slate')}>{value ? 'Yes' : 'No'}</span>;
  }
  if (['call_status', 'call_direction', 'provider', 'status', 'priority', 'role', 'department'].includes(key)) {
    return <span className={badgeClass(statusTone(value))}>{String(value).replace(/_/g, ' ')}</span>;
  }
  if (typeof value === 'number') return formatNumber(value);
  return String(value);
};

export const readFilename = (headers, fallback) => {
  const disposition = headers?.['content-disposition'] || headers?.['Content-Disposition'] || '';
  const match = String(disposition).match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
};

export const downloadInsightsExport = async ({ dataset, format = 'csv', metric, filters }) => {
  const params = { ...buildParams(filters), dataset, format };
  if (metric) params.metric = metric;
  const response = await API.get('/team-insights/export', {
    params,
    responseType: 'blob',
    timeout: 90000,
  });
  const fallback = `team_insights_${dataset}_${new Date().toISOString().slice(0, 10)}.${format}`;
  const filename = readFilename(response.headers, fallback);
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return filename;
};

export const apiErrorMessage = (error) => {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || String(item)).join(', ');
  if (typeof detail === 'string') return detail;
  return error?.message || 'Something went wrong while loading analytics.';
};
