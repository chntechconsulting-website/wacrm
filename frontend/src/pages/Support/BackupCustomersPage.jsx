import React from 'react';
import BackupCustomersPanel from '../../components/Support/BackupCustomersPanel';
import './SupportManagerPage.css';

export default function BackupCustomersPage() {
  return (
    <div className="support-manager-page">
      <div className="support-manager-page-header">
        <div>
          <h1>Backup Customers</h1>
          <p>
            Customers temporarily covered during an approved leave. Full authorized Support history,
            package details, unresolved issues and pending actions are shown below.
          </p>
        </div>
      </div>
      <BackupCustomersPanel />
    </div>
  );
}
