import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import PingoPopupService from '../../services/pingoPopupService';
import { 
  Download, 
  FileSpreadsheet, 
  FileText, 
  Filter, 
  Calendar, 
  PhoneCall, 
  Users, 
  Layers, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw,
  Database,
  ShieldCheck,
  ArrowRight
} from 'lucide-react';
import './DataExportPage.css';

const LEAD_STATUS_OPTIONS = [
  'ALL',
  'NEW',
  'CONTACTED',
  'INTERESTED',
  'RNR',
  'DEMO / MEETING',
  'PROPOSAL SENT',
  'NEGOTIATION',
  'FOLLOW-UP',
  'WON',
  'LOST',
  'JUNK'
];

const CALL_STATUS_OPTIONS = [
  'ALL',
  'COMPLETED',
  'NO_ANSWER',
  'MISSED',
  'BUSY',
  'FAILED',
  'INITIATED'
];

const DataExportPage = () => {
  const [stats, setStats] = useState({
    matching_leads: 0,
    matching_calls: 0,
    total_database_leads: 0,
    total_database_calls: 0
  });
  const [employees, setEmployees] = useState([]);
  const [loadingStats, setLoadingStats] = useState(true);

  // Leads Export Filter State
  const [leadFormat, setLeadFormat] = useState('xlsx'); // 'xlsx' | 'csv'
  const [leadStatus, setLeadStatus] = useState('ALL');
  const [leadStartDate, setLeadStartDate] = useState('');
  const [leadEndDate, setLeadEndDate] = useState('');
  const [exportingLeads, setExportingLeads] = useState(false);

  // Calls Export Filter State
  const [callFormat, setCallFormat] = useState('xlsx'); // 'xlsx' | 'csv'
  const [callStatus, setCallStatus] = useState('ALL');
  const [callEmployeeId, setCallEmployeeId] = useState('');
  const [callStartDate, setCallStartDate] = useState('');
  const [callEndDate, setCallEndDate] = useState('');
  const [exportingCalls, setExportingCalls] = useState(false);

  // Alerts
  const [alert, setAlert] = useState(null);

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 6000);
  };

  const fetchStats = async () => {
    try {
      setLoadingStats(true);
      const params = {};
      if (leadStatus && leadStatus !== 'ALL') params.lead_status = leadStatus;
      if (leadStartDate) params.lead_start_date = leadStartDate;
      if (leadEndDate) params.lead_end_date = leadEndDate;

      if (callStatus && callStatus !== 'ALL') params.call_status = callStatus;
      if (callEmployeeId) params.call_employee_id = callEmployeeId;
      if (callStartDate) params.call_start_date = callStartDate;
      if (callEndDate) params.call_end_date = callEndDate;

      const res = await API.get('/reports/export/stats', { params });
      if (res.data) {
        setStats(res.data);
      }
    } catch (err) {
      console.error('Failed to fetch export stats:', err);
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchEmployees = async () => {
    try {
      const res = await API.get('/employees/?status_filter=ACTIVE');
      if (res.data) {
        setEmployees(res.data);
      }
    } catch (err) {
      console.error('Failed to load employees for export filters:', err);
    }
  };

  useEffect(() => {
    fetchEmployees();
  }, []);

  useEffect(() => {
    fetchStats();
  }, [leadStatus, leadStartDate, leadEndDate, callStatus, callEmployeeId, callStartDate, callEndDate]);

  // Handle All Leads Export
  const handleExportLeads = async () => {
    try {
      setExportingLeads(true);
      const params = { format: leadFormat };
      if (leadStatus && leadStatus !== 'ALL') params.status = leadStatus;
      if (leadStartDate) params.start_date = leadStartDate;
      if (leadEndDate) params.end_date = leadEndDate;

      const response = await API.get('/reports/export/leads', {
        params,
        responseType: 'blob'
      });

      const todayStr = new Date().toISOString().split('T')[0];
      const filename = `WACRM_All_Leads_${todayStr}.${leadFormat}`;
      const mimeType = leadFormat === 'xlsx' 
        ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        : 'text/csv';

      const blob = new Blob([response.data], { type: mimeType });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);

      showAlert('success', `Successfully exported ${stats.matching_leads} leads into ${filename}!`);
      PingoPopupService.triggerDownloadSuccess({
        docType: `All Leads (${leadFormat.toUpperCase()})`,
        reference: filename,
        customMessage: `Exported ${stats.matching_leads} leads successfully!`
      });
    } catch (err) {
      console.error('Failed to export leads:', err);
      showAlert('error', err.response?.data?.detail || 'Failed to generate Leads export file.');
    } finally {
      setExportingLeads(false);
    }
  };

  // Handle All Call Logs Export
  const handleExportCalls = async () => {
    try {
      setExportingCalls(true);
      const params = { format: callFormat };
      if (callStatus && callStatus !== 'ALL') params.status = callStatus;
      if (callEmployeeId) params.employee_id = callEmployeeId;
      if (callStartDate) params.start_date = callStartDate;
      if (callEndDate) params.end_date = callEndDate;

      const response = await API.get('/reports/export/call-logs', {
        params,
        responseType: 'blob'
      });

      const todayStr = new Date().toISOString().split('T')[0];
      const filename = `WACRM_All_Call_Logs_${todayStr}.${callFormat}`;
      const mimeType = callFormat === 'xlsx' 
        ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        : 'text/csv';

      const blob = new Blob([response.data], { type: mimeType });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);

      showAlert('success', `Successfully exported ${stats.matching_calls} call logs into ${filename}!`);
      PingoPopupService.triggerDownloadSuccess({
        docType: `All Call Logs (${callFormat.toUpperCase()})`,
        reference: filename,
        customMessage: `Exported ${stats.matching_calls} call logs successfully!`
      });
    } catch (err) {
      console.error('Failed to export call logs:', err);
      showAlert('error', err.response?.data?.detail || 'Failed to generate Call Logs export file.');
    } finally {
      setExportingCalls(false);
    }
  };

  return (
    <div className="data-export-container">
      {/* Header Banner */}
      <div className="data-export-header">
        <div className="header-left">
          <div className="header-icon-box">
            <Database className="w-6 h-6 text-indigo-600" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="header-title">Admin Data Export Module</h1>
              <span className="admin-badge">
                <ShieldCheck className="w-3.5 h-3.5" />
                ADMIN ONLY
              </span>
            </div>
            <p className="header-subtitle">
              Export complete database records for all Leads and Call Logs directly into structured Excel (.xlsx) and CSV spreadsheets.
            </p>
          </div>
        </div>

        <button 
          onClick={fetchStats}
          disabled={loadingStats}
          className="refresh-btn"
          title="Refresh Record Counts"
        >
          <RefreshCw className={`w-4 h-4 ${loadingStats ? 'animate-spin' : ''}`} />
          <span>Refresh Counts</span>
        </button>
      </div>

      {/* Alert Notification */}
      {alert && (
        <div className={`export-alert ${alert.type === 'success' ? 'alert-success' : 'alert-error'}`}>
          {alert.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          )}
          <span>{alert.message}</span>
        </div>
      )}

      {/* Main Export Grid */}
      <div className="export-grid">
        
        {/* CARD 1: ALL LEADS EXPORT */}
        <div className="export-card leads-card">
          <div className="card-top">
            <div className="card-badge leads-badge">
              <Users className="w-4 h-4" />
              <span>LEADS MODULE</span>
            </div>
            <div className="total-counter">
              <span className="counter-label">In Database:</span>
              <span className="counter-val">{stats.total_database_leads}</span>
            </div>
          </div>

          <h2 className="card-title">All Leads Export</h2>
          <p className="card-desc">
            Exports full lead profiles, Meta Ads form details, source attribution, contact info, assignment, and status timeline across all database pages.
          </p>

          {/* Filters Form */}
          <div className="filters-box">
            <div className="filter-group">
              <label className="filter-label">Lead Status Filter</label>
              <select 
                value={leadStatus} 
                onChange={(e) => setLeadStatus(e.target.value)}
                className="filter-input"
              >
                {LEAD_STATUS_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt === 'ALL' ? 'All Statuses (No Filter)' : opt}</option>
                ))}
              </select>
            </div>

            <div className="filter-row">
              <div className="filter-group">
                <label className="filter-label">Start Date</label>
                <input 
                  type="date"
                  value={leadStartDate}
                  onChange={(e) => setLeadStartDate(e.target.value)}
                  className="filter-input"
                />
              </div>
              <div className="filter-group">
                <label className="filter-label">End Date</label>
                <input 
                  type="date"
                  value={leadEndDate}
                  onChange={(e) => setLeadEndDate(e.target.value)}
                  className="filter-input"
                />
              </div>
            </div>

            {/* Format Selection */}
            <div className="filter-group">
              <label className="filter-label">Export File Format</label>
              <div className="format-toggle-group">
                <button
                  type="button"
                  className={`format-btn ${leadFormat === 'xlsx' ? 'active-xlsx' : ''}`}
                  onClick={() => setLeadFormat('xlsx')}
                >
                  <FileSpreadsheet className="w-4 h-4" />
                  <span>Excel (.xlsx)</span>
                </button>
                <button
                  type="button"
                  className={`format-btn ${leadFormat === 'csv' ? 'active-csv' : ''}`}
                  onClick={() => setLeadFormat('csv')}
                >
                  <FileText className="w-4 h-4" />
                  <span>CSV (.csv)</span>
                </button>
              </div>
            </div>
          </div>

          {/* Card Footer & Action */}
          <div className="card-footer">
            <div className="matching-stat">
              <span className="matching-text">Ready to export:</span>
              <span className="matching-number text-blue-600">
                {loadingStats ? '...' : stats.matching_leads} leads
              </span>
            </div>

            <button
              onClick={handleExportLeads}
              disabled={exportingLeads || stats.matching_leads === 0}
              className="export-action-btn leads-btn"
            >
              {exportingLeads ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Generating {leadFormat.toUpperCase()}...</span>
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  <span>Export All Leads ({leadFormat.toUpperCase()})</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* CARD 2: ALL CALL LOGS EXPORT */}
        <div className="export-card calls-card">
          <div className="card-top">
            <div className="card-badge calls-badge">
              <PhoneCall className="w-4 h-4" />
              <span>CALL LOGS MODULE</span>
            </div>
            <div className="total-counter">
              <span className="counter-label">In Database:</span>
              <span className="counter-val">{stats.total_database_calls}</span>
            </div>
          </div>

          <h2 className="card-title">All Call Logs Export</h2>
          <p className="card-desc">
            Exports complete telephony history, caller/receiver numbers, call duration, direction, recording URLs, AI transcripts, and assigned reps.
          </p>

          {/* Filters Form */}
          <div className="filters-box">
            <div className="filter-row">
              <div className="filter-group">
                <label className="filter-label">Call Status Filter</label>
                <select 
                  value={callStatus} 
                  onChange={(e) => setCallStatus(e.target.value)}
                  className="filter-input"
                >
                  {CALL_STATUS_OPTIONS.map(opt => (
                    <option key={opt} value={opt}>{opt === 'ALL' ? 'All Call Statuses' : opt}</option>
                  ))}
                </select>
              </div>

              <div className="filter-group">
                <label className="filter-label">Employee / Agent</label>
                <select 
                  value={callEmployeeId} 
                  onChange={(e) => setCallEmployeeId(e.target.value)}
                  className="filter-input"
                >
                  <option value="">All Employees</option>
                  {employees.map(emp => (
                    <option key={emp.id} value={emp.id}>{emp.name} ({emp.employee_id || emp.id})</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="filter-row">
              <div className="filter-group">
                <label className="filter-label">Start Date</label>
                <input 
                  type="date"
                  value={callStartDate}
                  onChange={(e) => setCallStartDate(e.target.value)}
                  className="filter-input"
                />
              </div>
              <div className="filter-group">
                <label className="filter-label">End Date</label>
                <input 
                  type="date"
                  value={callEndDate}
                  onChange={(e) => setCallEndDate(e.target.value)}
                  className="filter-input"
                />
              </div>
            </div>

            {/* Format Selection */}
            <div className="filter-group">
              <label className="filter-label">Export File Format</label>
              <div className="format-toggle-group">
                <button
                  type="button"
                  className={`format-btn ${callFormat === 'xlsx' ? 'active-xlsx' : ''}`}
                  onClick={() => setCallFormat('xlsx')}
                >
                  <FileSpreadsheet className="w-4 h-4" />
                  <span>Excel (.xlsx)</span>
                </button>
                <button
                  type="button"
                  className={`format-btn ${callFormat === 'csv' ? 'active-csv' : ''}`}
                  onClick={() => setCallFormat('csv')}
                >
                  <FileText className="w-4 h-4" />
                  <span>CSV (.csv)</span>
                </button>
              </div>
            </div>
          </div>

          {/* Card Footer & Action */}
          <div className="card-footer">
            <div className="matching-stat">
              <span className="matching-text">Ready to export:</span>
              <span className="matching-number text-teal-600">
                {loadingStats ? '...' : stats.matching_calls} call logs
              </span>
            </div>

            <button
              onClick={handleExportCalls}
              disabled={exportingCalls || stats.matching_calls === 0}
              className="export-action-btn calls-btn"
            >
              {exportingCalls ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Generating {callFormat.toUpperCase()}...</span>
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  <span>Export All Call Logs ({callFormat.toUpperCase()})</span>
                </>
              )}
            </button>
          </div>
        </div>

      </div>

      {/* Safety & Integrity Notice */}
      <div className="integrity-notice">
        <ShieldCheck className="w-5 h-5 text-indigo-600 flex-shrink-0" />
        <div className="notice-text">
          <strong>Production Data Safety & Compliance:</strong> Exports query live records directly across all pages without limiting results to browser view. Tokens, passwords, and API secrets are never included. Zero database modifications occur during export.
        </div>
      </div>
    </div>
  );
};

export default DataExportPage;
