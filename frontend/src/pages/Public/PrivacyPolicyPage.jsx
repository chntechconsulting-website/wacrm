import React from 'react';

const PrivacyPolicyPage = () => {
  return (
    <div style={{ maxWidth: '800px', margin: '40px auto', padding: '32px 20px', fontFamily: "var(--font-family, 'Plus Jakarta Sans', system-ui, sans-serif)", color: '#1e293b', lineHeight: 1.6 }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '8px', color: '#0f172a' }}>Privacy Policy</h1>
      <p style={{ color: '#64748b', marginBottom: '24px' }}>Last Updated: September 29, 2026</p>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>1. Introduction</h2>
        <p>
          This Privacy Policy explains how WA! CRM ("we", "our", or "us") collects, uses, and safeguards information when you interact with our Lead Management and CRM platform, including lead generation forms via Meta Ads (Facebook & Instagram Lead Ads).
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>2. Information We Collect</h2>
        <p>
          When you submit an inquiry through Meta Lead Ads or contact forms, we may collect:
        </p>
        <ul style={{ marginLeft: '20px', marginTop: '8px' }}>
          <li>Full Name</li>
          <li>Phone Number & WhatsApp contact information</li>
          <li>Email Address</li>
          <li>Company Name and City / Location</li>
          <li>Campaign and inquiry details</li>
        </ul>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>3. How We Use Information</h2>
        <p>
          Collected lead information is processed solely for business communication, responding to sales inquiries, scheduling follow-ups, and providing requested services through authorized sales representatives.
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>4. Data Protection & Deletion</h2>
        <p>
          We do not sell, rent, or trade your personal data to third parties. Users have the right to request deletion of their submitted contact records at any time by contacting our support team or visiting our Data Deletion page.
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>5. Contact Information</h2>
        <p>
          For privacy inquiries or data requests, please contact our administrator at <strong>admin@company.com</strong>.
        </p>
      </section>
    </div>
  );
};

export default PrivacyPolicyPage;
