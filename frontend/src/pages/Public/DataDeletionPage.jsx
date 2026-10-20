import React from 'react';

const DataDeletionPage = () => {
  return (
    <div style={{ maxWidth: '800px', margin: '40px auto', padding: '32px 20px', fontFamily: "var(--font-family, 'Plus Jakarta Sans', system-ui, sans-serif)", color: '#1e293b', lineHeight: 1.6 }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '8px', color: '#0f172a' }}>User Data Deletion Instructions</h1>
      <p style={{ color: '#64748b', marginBottom: '24px' }}>Compliance with Meta Platform Data Policy</p>

      <section style={{ marginBottom: '24px' }}>
        <p>
          If you submitted your contact details through a Facebook or Instagram Lead Ad managed via WA! CRM and wish to have your data deleted from our system, please follow the steps below:
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>How to Request Data Deletion</h2>
        <ol style={{ marginLeft: '20px', marginTop: '8px' }}>
          <li>
            Send an email to <strong>admin@company.com</strong> with the subject <em>"Data Deletion Request"</em>.
          </li>
          <li>
            Provide the phone number or email address that you submitted in the Meta Lead Form so we can identify your lead record.
          </li>
          <li>
            Our administration team will permanently delete your contact record and all associated call logs/messages within 48 hours and send you a confirmation email.
          </li>
        </ol>
      </section>
    </div>
  );
};

export default DataDeletionPage;
