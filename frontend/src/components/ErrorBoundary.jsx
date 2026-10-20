import React from 'react';
import { AlertCircle, RefreshCw, Home } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '60vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px'
        }}>
          <div style={{
            maxWidth: '520px',
            width: '100%',
            backgroundColor: '#ffffff',
            border: '1px solid #fecaca',
            borderRadius: '16px',
            padding: '32px',
            textAlign: 'center',
            boxShadow: '0 10px 25px rgba(0,0,0,0.05)'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              backgroundColor: '#fee2e2',
              color: '#dc2626',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px auto'
            }}>
              <AlertCircle size={26} />
            </div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1e293b', marginBottom: '8px' }}>
              Something went wrong
            </h3>
            <p style={{ color: '#64748b', fontSize: '0.88rem', marginBottom: '20px', lineHeight: 1.5 }}>
              An error occurred while loading this section: <br />
              <code style={{ color: '#dc2626', background: '#fef2f2', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem' }}>
                {this.state.error?.message || 'Unknown runtime error'}
              </code>
            </p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="btn btn-primary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
              >
                <RefreshCw size={14} /> Reload Page
              </button>
              <button
                type="button"
                onClick={() => { window.location.href = '/dashboard'; }}
                className="btn btn-outline"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
              >
                <Home size={14} /> Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
