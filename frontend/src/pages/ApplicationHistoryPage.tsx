import React from 'react';
import type { Application } from '../hooks/useApplications';

interface ApplicationHistoryPageProps {
  applications: Application[];
  loading: boolean;
  onSelect: (id: string) => void;
}

const statusColor: Record<string, string> = {
  draft: '#f59e0b',
  submitted: '#3b82f6',
  under_review: '#8b5cf6',
  approved: '#10b981',
  rejected: '#ef4444',
};

const statusLabel: Record<string, string> = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under Review',
  approved: 'Approved',
  rejected: 'Rejected',
};

// Demo applications shown when no backend data
const DEMO: Application[] = [
  { id:'APP001', type:'Home Loan', amount:3500000, status:'under_review', createdAt:'2025-05-10', propertyAddress:'42, Indiranagar, Bangalore', workflowStep:'Risk Assessment' },
  { id:'APP002', type:'Loan Against Property', amount:1500000, status:'draft', createdAt:'2025-06-01', propertyAddress:'15, Koramangala, Bangalore', workflowStep:'KYC' },
  { id:'APP003', type:'Home Loan', amount:7200000, status:'approved', createdAt:'2025-03-22', propertyAddress:'7, Whitefield, Bangalore', workflowStep:'Completed' },
];

export const ApplicationHistoryPage: React.FC<ApplicationHistoryPageProps> = ({ applications, loading, onSelect }) => {
  const list = applications.length ? applications : DEMO;

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: '#111827' }}>Application History</h2>
        <span style={{ fontSize: 13, color: '#6b7280' }}>{list.length} application{list.length !== 1 ? 's' : ''}</span>
      </div>

      {loading && <p style={{ fontSize: 14, color: '#9ca3af', textAlign: 'center', padding: 40 }}>Loading…</p>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {list.map(app => (
          <div key={app.id} onClick={() => onSelect(app.id)}
            style={{ background: 'white', borderRadius: 16, border: '1px solid #f3f4f6', padding: 20, cursor: 'pointer', boxShadow: '0 1px 4px rgba(0,0,0,.05)', transition: 'all .15s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 12px rgba(0,0,0,.1)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 1px 4px rgba(0,0,0,.05)'; }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#111827' }}>{app.type}</span>
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999,
                    background: `${statusColor[app.status]}18`,
                    color: statusColor[app.status],
                  }}>{statusLabel[app.status]}</span>
                </div>
                <p style={{ fontSize: 13, color: '#6b7280' }}>{app.propertyAddress}</p>
                <p style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>Applied: {new Date(app.createdAt).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' })}</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: 18, fontWeight: 700, color: '#1e3a6e' }}>₹{(app.amount/100000).toFixed(1)}L</p>
                <p style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>Step: {app.workflowStep}</p>
              </div>
            </div>
            {/* Progress bar */}
            <div style={{ marginTop: 14 }}>
              <div style={{ background: '#f3f4f6', borderRadius: 999, height: 4, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 999,
                  background: statusColor[app.status],
                  width: app.status==='draft'?'15%':app.status==='submitted'?'30%':app.status==='under_review'?'60%':app.status==='approved'?'100%':'100%'
                }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
