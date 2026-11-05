import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LifeBuoy,
  Clock,
  CheckCircle,
  AlertCircle,
  PhoneCall,
  Users,
  ArrowUpRight,
  Layers,
  Calendar,
  MessageCircle,
  Award,
} from 'lucide-react';
import { formatDateDDMMYYYY, formatTime12Hour } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const SupportDashboard = ({ data }) => {
  const navigate = useNavigate();
  const support = data || {};

  const totalTickets = support.total_tickets ?? 0;
  const openTickets = support.open_tickets ?? 0;
  const resolvedTickets = support.resolved_tickets ?? 0;
  const pendingTickets = support.pending_tickets ?? 0;
  const customerFollowups = support.customer_followups ?? 0;
  const averageResolution = support.average_resolution_display || '—';
  const statusBreakdown = support.status_breakdown || [];
  const agentWorkload = support.agent_workload || [];
  const recentTickets = support.recent_tickets || [];
  const upcomingFollowups = support.upcoming_followups || [];

  const completionRate = totalTickets > 0
    ? Math.round((resolvedTickets / totalTickets) * 100)
    : 0;

  const kpis = [
    {
      key: 'total',
      label: 'Total Support Tickets',
      value: totalTickets,
      subtext: 'All tickets in your scope',
      icon: LifeBuoy,
      color: '#2563eb',
      bg: 'rgba(37, 99, 235, 0.12)',
      onClick: () => navigate('/support'),
    },
    {
      key: 'open',
      label: 'Open Tickets',
      value: openTickets,
      subtext: 'Onboarding, training or issues',
      icon: Clock,
      color: '#8b5cf6',
      bg: 'rgba(139, 92, 246, 0.12)',
      onClick: () => navigate('/support'),
    },
    {
      key: 'resolved',
      label: 'Resolved Tickets',
      value: resolvedTickets,
      subtext: 'Support lifecycle resolved',
      icon: CheckCircle,
      color: '#16a34a',
      bg: 'rgba(22, 163, 74, 0.12)',
      onClick: () => navigate('/support?status=RESOLVED'),
    },
    {
      key: 'pending',
      label: 'Pending Tickets',
      value: pendingTickets,
      subtext: 'Awaiting first contact',
      icon: AlertCircle,
      color: '#f59e0b',
      bg: 'rgba(245, 158, 11, 0.12)',
      onClick: () => navigate('/support?status=NEW'),
    },
    {
      key: 'followups',
      label: 'Customer Follow-ups',
      value: customerFollowups,
      subtext: 'Pending customer follow-ups',
      icon: PhoneCall,
      color: '#0ea5e9',
      bg: 'rgba(14, 165, 233, 0.12)',
      onClick: () => navigate('/communication/followups'),
    },
    {
      key: 'resolution',
      label: 'Average Resolution Time',
      value: averageResolution,
      subtext: 'Completed tickets only',
      icon: Award,
      color: '#db2777',
      bg: 'rgba(219, 39, 119, 0.12)',
      onClick: null,
    },
  ];

  // Canonical Support statuses; legacy values are normalised only for display
  // so historical rows remain readable without changing stored data.
  const getStatusStyle = (status) => {
    const key = String(status || 'NEW').toUpperCase().replace(/[\s-]/g, '_');
    const normalized =
      {
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
      }[key] || key;

    if (normalized === 'RESOLVED' || normalized === 'ACTIVE') {
      return { backgroundColor: '#dcfce7', color: '#15803d' };
    }
    if (normalized === 'ISSUE_RAISED') {
      return { backgroundColor: '#fee2e2', color: '#b91c1c' };
    }
    if (normalized === 'ONBOARDING') {
      return { backgroundColor: '#dbeafe', color: '#1d4ed8' };
    }
    if (normalized === 'TRAINING') {
      return { backgroundColor: '#e0e7ff', color: '#4338ca' };
    }
    if (
      normalized === 'INSTALLATION_PENDING' ||
      normalized === 'INSTALLATION_COMPLETED'
    ) {
      return { backgroundColor: '#ede9fe', color: '#6d28d9' };
    }
    return { backgroundColor: '#fef3c7', color: '#b45309' };
  };

  return (
    <div>
      {/* SUPPORT KPI CARDS */}
      <div className="dashboard-kpi-grid">
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          const isClickable = typeof kpi.onClick === 'function';
          return (
            <div
              key={kpi.key}
              className="stat-card"
              onClick={kpi.onClick || undefined}
              role={isClickable ? 'button' : undefined}
              tabIndex={isClickable ? 0 : undefined}
              onKeyDown={isClickable ? (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  kpi.onClick();
                }
              } : undefined}
              style={{
                padding: '18px 20px',
                borderRadius: '16px',
                cursor: isClickable ? 'pointer' : 'default',
                transition: 'all 0.2s ease',
              }}
              title={isClickable ? kpi.subtext : undefined}
            >
              <div style={{
                width: '46px',
                height: '46px',
                borderRadius: '14px',
                backgroundColor: kpi.bg,
                color: kpi.color,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                <Icon size={22} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>
                  {kpi.label}
                </div>
                <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>
                  {typeof kpi.value === 'number' ? kpi.value.toLocaleString() : kpi.value}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px', fontWeight: '500' }}>
                  {kpi.subtext}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* SUPPORT VISUALS */}
      <div className="dashboard-charts-grid">
        {/* Ticket status breakdown */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={20} style={{ color: '#2563eb' }} />
              <span>Ticket Status Breakdown</span>
            </h3>
            <span style={{ fontSize: '0.74rem', fontWeight: '700', color: '#475569', backgroundColor: '#f1f5f9', borderRadius: '9999px', padding: '4px 10px' }}>
              {totalTickets} total
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, justifyContent: 'center' }}>
            {totalTickets === 0 ? (
              <PingoEmptyState
                pose="playful"
                height={90}
                compact={true}
                title="No Support Tickets Yet"
                description="New onboarding tickets will appear here automatically."
              />
            ) : (
              statusBreakdown.map((item) => (
                <div key={item.status}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ width: '9px', height: '9px', borderRadius: '50%', backgroundColor: item.color, flexShrink: 0 }} />
                      <span style={{ fontSize: '0.82rem', fontWeight: '700', color: '#334155' }}>{item.label}</span>
                    </div>
                    <span style={{ fontSize: '0.8rem', fontWeight: '700', color: '#0f172a' }}>
                      {item.count}
                      <span style={{ color: '#94a3b8', fontWeight: '500' }}> ({item.percentage}%)</span>
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '8px', backgroundColor: '#f1f5f9', borderRadius: '9999px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${Math.min(100, Math.max(0, item.percentage))}%`,
                      height: '100%',
                      backgroundColor: item.color,
                      borderRadius: '9999px',
                      transition: 'width 0.4s ease',
                    }} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Agent workload */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Users size={20} style={{ color: '#10b981' }} />
              <span>Agent Workload</span>
            </h3>
            <button
              type="button"
              onClick={() => navigate('/support')}
              style={{ border: 'none', background: 'transparent', color: '#2563eb', fontSize: '0.78rem', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              View Queue <ArrowUpRight size={14} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
            {agentWorkload.length === 0 ? (
              <PingoEmptyState
                pose="playful"
                height={90}
                compact={true}
                title="No Agent Assignments"
                description="Tickets assigned to support agents will show here."
              />
            ) : (
              agentWorkload.map((agent, index) => (
                <div
                  key={`${agent.name}-${index}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 12px',
                    backgroundColor: '#f8fafc',
                    borderRadius: '12px',
                    border: '1px solid #e2e8f0',
                  }}
                >
                  <div style={{
                    width: '34px',
                    height: '34px',
                    borderRadius: '50%',
                    backgroundColor: '#dbeafe',
                    color: '#1d4ed8',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.8rem',
                    fontWeight: '800',
                    flexShrink: 0,
                  }}>
                    {(agent.name || 'U')[0].toUpperCase()}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '0.82rem', fontWeight: '700', color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {agent.name}
                      </span>
                      <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#0f172a', flexShrink: 0 }}>
                        {agent.count}
                      </span>
                    </div>
                    <div style={{ width: '100%', height: '5px', backgroundColor: '#e2e8f0', borderRadius: '9999px', overflow: 'hidden', marginTop: '5px' }}>
                      <div style={{
                        width: `${Math.min(100, Math.max(0, agent.percentage))}%`,
                        height: '100%',
                        backgroundColor: '#3b82f6',
                        borderRadius: '9999px',
                      }} />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Resolution performance */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={20} style={{ color: '#db2777' }} />
              <span>Resolution Performance</span>
            </h3>
          </div>

          <div style={{ textAlign: 'center', padding: '10px 0 18px' }}>
            <div style={{ fontSize: '2.2rem', fontWeight: '800', color: '#be185d', lineHeight: 1.1 }}>
              {averageResolution}
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600', marginTop: '5px' }}>
              Average Resolution Time
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '10px', marginBottom: '14px' }}>
            <div style={{ padding: '10px 12px', backgroundColor: '#f0fdf4', borderRadius: '10px', border: '1px solid #dcfce7' }}>
              <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: '700', textTransform: 'uppercase' }}>Resolved</div>
              <div style={{ fontSize: '1.15rem', fontWeight: '800', color: '#15803d' }}>{resolvedTickets}</div>
            </div>
            <div style={{ padding: '10px 12px', backgroundColor: '#fff7ed', borderRadius: '10px', border: '1px solid #ffedd5' }}>
              <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: '700', textTransform: 'uppercase' }}>Open Load</div>
              <div style={{ fontSize: '1.15rem', fontWeight: '800', color: '#c2410c' }}>{openTickets + pendingTickets}</div>
            </div>
          </div>

          <div style={{ marginTop: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#475569' }}>Completion Rate</span>
              <span style={{ fontSize: '0.8rem', fontWeight: '800', color: completionRate >= 100 ? '#16a34a' : '#2563eb' }}>
                {completionRate}%
              </span>
            </div>
            <div style={{ width: '100%', height: '8px', backgroundColor: '#e2e8f0', borderRadius: '9999px', overflow: 'hidden' }}>
              <div style={{
                width: `${Math.min(100, completionRate)}%`,
                height: '100%',
                background: completionRate >= 100 ? '#16a34a' : 'linear-gradient(90deg, #2563eb, #3b82f6)',
                borderRadius: '9999px',
                transition: 'width 0.5s ease',
              }} />
            </div>
          </div>
        </div>
      </div>

      {/* RECENT TICKETS & FOLLOW-UPS */}
      <div className="dashboard-tables-grid">
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <LifeBuoy size={20} style={{ color: '#2563eb' }} /> Recent Support Tickets
            </h3>
            <button
              type="button"
              onClick={() => navigate('/support')}
              style={{ border: 'none', background: 'transparent', color: '#2563eb', fontSize: '0.82rem', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              View All <ArrowUpRight size={15} />
            </button>
          </div>

          <div className="table-responsive" style={{ flex: 1 }}>
            <table className="custom-table" style={{ width: '100%', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                  <th style={{ padding: '8px 10px' }}>#</th>
                  <th style={{ padding: '8px 10px' }}>Customer</th>
                  <th style={{ padding: '8px 10px' }}>Product / Service</th>
                  <th style={{ padding: '8px 10px' }}>Status</th>
                  <th style={{ padding: '8px 10px' }}>Assigned Agent</th>
                  <th style={{ padding: '8px 10px' }}>Created</th>
                </tr>
              </thead>
              <tbody>
                {recentTickets.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="text-center py-4 text-muted">No support tickets found.</td>
                  </tr>
                ) : (
                  recentTickets.map((ticket, index) => (
                    <tr
                      key={ticket.id}
                      style={{ borderBottom: '1px solid #f1f5f9', cursor: 'pointer', transition: 'background-color 0.15s ease' }}
                      onClick={() => navigate('/support')}
                      onMouseEnter={(event) => { event.currentTarget.style.backgroundColor = '#f8fafc'; }}
                      onMouseLeave={(event) => { event.currentTarget.style.backgroundColor = 'transparent'; }}
                      title={`Open ticket #${ticket.id} in the Support Queue`}
                    >
                      <td style={{ padding: '10px' }}>{index + 1}</td>
                      <td style={{ padding: '10px' }}>
                        <div style={{ fontWeight: '700', color: '#1e40af' }}>{ticket.customer_name || 'Customer'}</div>
                        <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{ticket.company_name || ticket.phone || '-'}</div>
                      </td>
                      <td style={{ padding: '10px', color: '#475569' }}>{ticket.product_service || '-'}</td>
                      <td style={{ padding: '10px' }}>
                        <span style={{
                          padding: '3px 9px',
                          borderRadius: '10px',
                          fontSize: '0.72rem',
                          fontWeight: '700',
                          ...getStatusStyle(ticket.support_status || ticket.onboarding_status),
                        }}>
                          {ticket.status_label ||
                            ticket.support_status ||
                            ticket.onboarding_status ||
                            'New'}
                        </span>
                      </td>
                      <td style={{ padding: '10px', color: '#475569' }}>{ticket.assigned_agent_name || 'Unassigned'}</td>
                      <td style={{ padding: '10px', color: '#64748b' }}>{formatDateDDMMYYYY(ticket.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Calendar size={20} style={{ color: '#f59e0b' }} /> Customer Follow-ups
            </h3>
            <button
              type="button"
              onClick={() => navigate('/communication/followups')}
              style={{ border: 'none', background: 'transparent', color: '#2563eb', fontSize: '0.82rem', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              View All <ArrowUpRight size={15} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
            {upcomingFollowups.length === 0 ? (
              <PingoEmptyState
                pose="playful"
                height={85}
                compact={true}
                title="No Pending Follow-ups"
                description="Your support follow-up queue is clear right now."
              />
            ) : (
              upcomingFollowups.map((item) => (
                <div
                  key={item.id}
                  onClick={() => navigate('/communication/followups')}
                  style={{
                    background: '#f8fafc',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    border: '1px solid #e2e8f0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '10px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(event) => {
                    event.currentTarget.style.backgroundColor = '#f1f5f9';
                    event.currentTarget.style.borderColor = '#cbd5e1';
                  }}
                  onMouseLeave={(event) => {
                    event.currentTarget.style.backgroundColor = '#f8fafc';
                    event.currentTarget.style.borderColor = '#e2e8f0';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
                    <div style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      backgroundColor: 'rgba(37, 99, 235, 0.12)',
                      color: '#2563eb',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      {item.lead_phone ? <PhoneCall size={18} /> : <MessageCircle size={18} />}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#0f172a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {item.lead_name || 'Customer'}
                      </div>
                      <div style={{ fontSize: '0.78rem', color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {item.notes || 'Customer follow-up call'}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                    <span style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: '500' }}>
                      {item.followup_date ? `${formatDateDDMMYYYY(item.followup_date)} ${formatTime12Hour(item.followup_time)}` : '-'}
                    </span>
                    <span style={{
                      padding: '3px 10px',
                      borderRadius: '10px',
                      fontSize: '0.72rem',
                      fontWeight: '700',
                      backgroundColor: (item.priority || '').toUpperCase() === 'HIGH' ? '#ffe4e6' : (item.priority || '').toUpperCase() === 'MEDIUM' ? '#fef3c7' : '#e0f2fe',
                      color: (item.priority || '').toUpperCase() === 'HIGH' ? '#e11d48' : (item.priority || '').toUpperCase() === 'MEDIUM' ? '#d97706' : '#0284c7',
                    }}>
                      {item.priority || 'Medium'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SupportDashboard;
