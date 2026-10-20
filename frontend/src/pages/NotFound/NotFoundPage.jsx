import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Home, ArrowLeft } from 'lucide-react';
import PingoMascot from '../../components/Common/PingoMascot';

const NotFoundPage = () => {
  const navigate = useNavigate();

  return (
    <div className="page-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 120px)' }}>
      <div className="content-card" style={{ maxWidth: '540px', width: '100%', textAlign: 'center', padding: '40px 32px' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
          <PingoMascot
            pose="playful"
            height={160}
            speechBubble="Oops! Pingo couldn't find this route."
            speechBubblePosition="top"
          />
        </div>
        <h1 style={{ fontSize: '3rem', fontWeight: 800, color: '#0f172a', lineHeight: 1, marginBottom: '8px' }}>404</h1>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: '#1e293b', marginBottom: '12px' }}>Page Not Found</h2>
        <p style={{ color: '#64748b', fontSize: '0.92rem', marginBottom: '28px', lineHeight: 1.5 }}>
          The CRM page or route you are looking for does not exist, has been moved, or you may not have authorization to view it.
        </p>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '14px' }}>
          <button onClick={() => navigate(-1)} className="btn btn-secondary">
            <ArrowLeft size={18} />
            <span>Go Back</span>
          </button>
          <Link to="/dashboard" className="btn btn-primary">
            <Home size={18} />
            <span>Go to Dashboard</span>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default NotFoundPage;
