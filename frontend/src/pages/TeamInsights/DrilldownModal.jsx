import React, { useState, useEffect } from 'react';
import { 
  X, 
  Search, 
  Download, 
  FileSpreadsheet, 
  FileText, 
  ChevronLeft, 
  ChevronRight, 
  Loader2, 
  Layers, 
  Phone, 
  UserCheck, 
  Clock, 
  CheckCircle2, 
  AlertCircle 
} from 'lucide-react';
import API from '../../services/api';
import { 
  buildParams, 
  formatNumber, 
  renderRecordValue, 
  downloadInsightsExport, 
  apiErrorMessage,
  METRIC_TITLES
} from './insightsUtils';

const PAGE_SIZE = 50;

const DrilldownModal = ({
  isOpen,
  onClose,
  metric,
  filters,
  employeeContext = null,
  totalExpected = null,
}) => {
  const [loading, setLoading] = useState(true);
  const [recordsData, setRecordsData] = useState(null);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!isOpen || !metric) return;
    setPage(0);
    setSearchTerm('');
    fetchRecords(0);
  }, [isOpen, metric, filters, employeeContext]);

  const effectiveFilters = {
    ...filters,
    ...(employeeContext?.employee_id ? { employee_id: employeeContext.employee_id } : {}),
  };

  const fetchRecords = async (targetOffset = 0) => {
    try {
      setLoading(true);
      setError(null);
      const params = {
        ...buildParams(effectiveFilters),
        metric,
        limit: PAGE_SIZE,
        offset: targetOffset,
      };
      const res = await API.get('/team-insights/records', { params });
      setRecordsData(res.data);
    } catch (err) {
      console.error('Error fetching metric records:', err);
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (newPage) => {
    setPage(newPage);
    fetchRecords(newPage * PAGE_SIZE);
  };

  const handleExport = async (format = 'csv') => {
    try {
      setExporting(true);
      await downloadInsightsExport({
        dataset: 'records',
        format,
        metric,
        filters: effectiveFilters,
      });
    } catch (err) {
      console.error('Failed to export drilldown records:', err);
      alert('Failed to export records: ' + apiErrorMessage(err));
    } finally {
      setExporting(false);
    }
  };

  if (!isOpen) return null;

  const title = METRIC_TITLES[metric] || String(metric).replace(/_/g, ' ');
  const items = recordsData?.items || [];
  const columns = recordsData?.columns || [];
  const totalCount = recordsData?.total ?? (totalExpected ?? 0);
  const totalPages = Math.ceil(totalCount / PAGE_SIZE) || 1;

  // Filter in-memory for the current page search
  const filteredItems = searchTerm.trim()
    ? items.filter((row) =>
        Object.values(row).some((val) =>
          String(val || '').toLowerCase().includes(searchTerm.toLowerCase())
        )
      )
    : items;

  return (
    <div className="ti-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="ti-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="ti-modal-header">
          <div className="ti-modal-header-left">
            <div className="ti-modal-icon-badge">
              <Layers size={20} />
            </div>
            <div>
              <div className="ti-modal-title-row">
                <h2 className="ti-modal-title">{title}</h2>
                <span className="ti-modal-count-badge">
                  {formatNumber(totalCount)} record{totalCount === 1 ? '' : 's'}
                </span>
                {employeeContext?.name && (
                  <span className="ti-modal-emp-badge">
                    Employee: {employeeContext.name}
                  </span>
                )}
              </div>
              <p className="ti-modal-subtitle">
                Filtered drill-down based on active scope & date range
              </p>
            </div>
          </div>
          <button 
            type="button" 
            className="ti-modal-close-btn" 
            onClick={onClose} 
            title="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Toolbar */}
        <div className="ti-modal-toolbar">
          <div className="ti-modal-search-box">
            <Search size={16} className="ti-search-icon" />
            <input
              type="text"
              placeholder="Quick search on current page..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="ti-modal-search-input"
            />
            {searchTerm && (
              <button 
                type="button" 
                className="ti-search-clear" 
                onClick={() => setSearchTerm('')}
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div className="ti-modal-actions">
            <button
              type="button"
              className="ti-btn ti-btn-outline ti-btn-sm"
              onClick={() => handleExport('csv')}
              disabled={exporting || totalCount === 0}
              title="Download CSV"
            >
              <FileText size={14} />
              <span>{exporting ? 'Exporting...' : 'Export CSV'}</span>
            </button>
            <button
              type="button"
              className="ti-btn ti-btn-primary ti-btn-sm"
              onClick={() => handleExport('xlsx')}
              disabled={exporting || totalCount === 0}
              title="Download Excel"
            >
              <FileSpreadsheet size={14} />
              <span>{exporting ? 'Exporting...' : 'Export Excel'}</span>
            </button>
          </div>
        </div>

        {/* Modal Content / Table */}
        <div className="ti-modal-body">
          {loading ? (
            <div className="ti-modal-loading">
              <Loader2 size={32} className="ti-spinner" />
              <p>Loading filtered database records...</p>
            </div>
          ) : error ? (
            <div className="ti-modal-error">
              <AlertCircle size={32} className="ti-error-icon" />
              <h3>Failed to load records</h3>
              <p>{error}</p>
              <button
                type="button"
                className="ti-btn ti-btn-outline ti-btn-sm"
                onClick={() => fetchRecords(page * PAGE_SIZE)}
              >
                Try Again
              </button>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="ti-modal-empty">
              <div className="ti-empty-icon-wrap">
                <Layers size={36} />
              </div>
              <h3>No records found</h3>
              <p>
                {searchTerm
                  ? 'No records match your quick search query on this page.'
                  : 'There are no database records matching this metric under the active filters.'}
              </p>
            </div>
          ) : (
            <div className="ti-table-responsive">
              <table className="ti-table">
                <thead>
                  <tr>
                    <th style={{ width: 50 }}>#</th>
                    {columns.map((col) => (
                      <th key={col.key}>{col.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredItems.map((item, idx) => (
                    <tr key={item.id || item.call_id || item.lead_id || idx}>
                      <td className="ti-cell-muted">
                        {page * PAGE_SIZE + idx + 1}
                      </td>
                      {columns.map((col) => (
                        <td key={col.key}>
                          {renderRecordValue(col.key, item[col.key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal Footer / Pagination */}
        <div className="ti-modal-footer">
          <div className="ti-modal-footer-info">
            Showing {filteredItems.length} of {formatNumber(totalCount)} total records
          </div>
          {totalPages > 1 && (
            <div className="ti-pagination">
              <button
                type="button"
                className="ti-pagination-btn"
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 0 || loading}
              >
                <ChevronLeft size={16} />
                <span>Prev</span>
              </button>
              <span className="ti-pagination-pages">
                Page {page + 1} of {totalPages}
              </span>
              <button
                type="button"
                className="ti-pagination-btn"
                onClick={() => handlePageChange(page + 1)}
                disabled={page >= totalPages - 1 || loading}
              >
                <span>Next</span>
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DrilldownModal;
