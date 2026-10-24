import React from 'react';

const TermsAndConditionsPage = () => {
  return (
    <div style={{ maxWidth: '800px', margin: '40px auto', padding: '32px 20px', fontFamily: "var(--font-family, 'Plus Jakarta Sans', system-ui, sans-serif)", color: '#1e293b', lineHeight: 1.6 }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '8px', color: '#0f172a' }}>Terms & Conditions</h1>
      <p style={{ color: '#64748b', marginBottom: '24px' }}>Last Updated: October 24, 2026</p>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>1. Agreement to Terms</h2>
        <p>
          By accessing or using WA! CRM ("Platform", "we", "us", or "our"), including submitting inquiries through Meta Lead Ads (Facebook & Instagram), our website, or communication channels, you agree to be bound by these Terms and Conditions.
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>2. Services & Use of Platform</h2>
        <p>
          WA! CRM provides customer relationship management, lead management, telephony integration, and sales workflow automation tools. You agree to use the Platform only for lawful business purposes and in compliance with all applicable regulations.
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>3. Lead Submissions & Communications</h2>
        <p>
          By submitting your contact details (including phone number and WhatsApp number) through our Meta Lead Ads or website, you consent to receive business communications, sales follow-ups, quotes, and product information from our authorized representatives.
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>4. Intellectual Property</h2>
        <p>
          All content, software, branding, trademarks, and documentation provided on the Platform are the exclusive property of WA! CRM and its licensors. Unauthorized copying or distribution is strictly prohibited.
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>5. Limitation of Liability</h2>
        <p>
          To the maximum extent permitted by law, WA! CRM and its affiliates shall not be liable for any indirect, incidental, special, consequential, or punitive damages resulting from your use of or inability to use the platform.
        </p>
      </section>

      <section style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', color: '#0f172a' }}>6. Contact Information</h2>
        <p>
          If you have any questions or concerns regarding these Terms & Conditions, please contact us at <strong>legal@chntechnologies.com</strong> or reach out to our administration team.
        </p>
      </section>
    </div>
  );
};

export default TermsAndConditionsPage;
