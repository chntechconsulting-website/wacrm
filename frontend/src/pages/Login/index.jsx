import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { 
  Mail, 
  Lock, 
  Eye, 
  EyeOff, 
  Moon, 
  Sun, 
  ArrowRight, 
  Users, 
  PhoneCall, 
  BarChart3, 
  AlertCircle,
  X,
  ShieldCheck,
  Check,
  ChevronRight
} from 'lucide-react';
import './Login.css';

// WhatsApp SVG Icon
const WhatsAppIcon = ({ size = 20, color = 'currentColor' }) => (
  <svg 
    width={size} 
    height={size} 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke={color} 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round"
  >
    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
  </svg>
);

// Google 4-Color Logo
const GoogleLogo = () => (
  <svg width="18" height="18" viewBox="0 0 24 24">
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
    />
  </svg>
);

const Login = () => {
  const [username, setUsername] = useState(() => {
    try {
      const saved = localStorage.getItem('crm_remember_user');
      // Purge any legacy 'admin' value from localStorage
      if (saved === 'admin') {
        localStorage.removeItem('crm_remember_user');
        return '';
      }
      return saved || '';
    } catch (_) {
      return '';
    }
  });
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(() => {
    try {
      const saved = localStorage.getItem('crm_remember_user');
      return !!(saved && saved !== 'admin');
    } catch (_) {
      return false;
    }
  });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeModal, setActiveModal] = useState(null); // 'forgot' | 'admin' | 'google'

  // Dark Mode State
  const [isDarkMode, setIsDarkMode] = useState(() => {
    return localStorage.getItem('crm_login_theme') === 'dark';
  });

  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // If user is already authenticated, redirect immediately to dashboard without showing login form
    if (user && localStorage.getItem('crm_token')) {
      navigate('/dashboard', { replace: true });
    }
  }, [user, navigate]);

  useEffect(() => {
    localStorage.setItem('crm_login_theme', isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  const toggleTheme = () => {
    setIsDarkMode((prev) => !prev);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!username.trim() || !password) {
      setError('Please enter both your email/username and password.');
      return;
    }

    try {
      setIsSubmitting(true);
      await login(username.trim(), password);

      // Handle Remember Me
      if (rememberMe) {
        localStorage.setItem('crm_remember_user', username.trim());
      } else {
        localStorage.removeItem('crm_remember_user');
      }

      navigate('/dashboard');
    } catch (err) {
      console.error('Login error:', err);
      if (!err.response) {
        setError('Network Error: Unable to connect to CRM API server. Please ensure the backend service is running.');
      } else {
        setError(err.response?.data?.detail || 'Incorrect username/email or password.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFillDemo = (demoUsername, demoPassword) => {
    setUsername(demoUsername);
    setPassword(demoPassword);
    setError('');
  };

  return (
    <div className={`wa-login-viewport ${isDarkMode ? 'dark-theme' : ''}`}>
      {/* Decorative Dot Matrix Background Patterns */}
      <div className="wa-dot-pattern-top" />
      <div className="wa-dot-pattern-bottom" />
      <div className="wa-dot-pattern-right" />

      <div className="wa-login-container">
        
        {/* ================= LEFT HERO SHOWCASE PANEL ================= */}
        <div className="wa-hero-panel">
          {/* Top Section: Brand + Headline + Description */}
          <div className="wa-hero-top-group">
            <div className="wa-brand-wrapper">
              <img 
                src={isDarkMode ? "/wa-crm-logo-dark.png" : "/wa-crm-logo-transparent.png"} 
                alt="WA! CRM Logo" 
                className="wa-brand-image-logo" 
              />
              <div className="wa-brand-tagline">CONNECT &middot; CONVERT &middot; GROW</div>
            </div>

            {/* Headline */}
            <h1 className="wa-hero-title">
              Turn Conversations <br />
              into <span className="wa-highlight-opportunity">
                Opportunities
                <svg className="wa-opportunity-swoosh" viewBox="0 0 258 14" fill="none" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2 4Q130 14 258 3Q130 9 2 4Z" fill="#ff1e38" />
                </svg>
              </span>
            </h1>

            {/* Description */}
            <p className="wa-hero-desc">
              Manage leads, track calls, automate follow-ups and grow your business &mdash; all in one powerful CRM platform.
            </p>
          </div>

          {/* 4 Feature Badges with Arrows */}
          <div className="wa-features-grid">
            <div className="wa-feature-pill">
              <div className="wa-feature-icon-box red">
                <Users size={20} />
              </div>
              <span className="wa-feature-text">
                Lead<br />Management
              </span>
              <ChevronRight size={16} className="wa-feature-arrow" />
            </div>

            <div className="wa-feature-pill">
              <div className="wa-feature-icon-box blue">
                <PhoneCall size={20} />
              </div>
              <span className="wa-feature-text">
                Call Tracking &amp;<br />Recording
              </span>
              <ChevronRight size={16} className="wa-feature-arrow" />
            </div>

            <div className="wa-feature-pill">
              <div className="wa-feature-icon-box green">
                <WhatsAppIcon size={20} color="#16a34a" />
              </div>
              <span className="wa-feature-text">
                WhatsApp<br />Integration
              </span>
              <ChevronRight size={16} className="wa-feature-arrow" />
            </div>

            <div className="wa-feature-pill">
              <div className="wa-feature-icon-box amber">
                <BarChart3 size={20} />
              </div>
              <span className="wa-feature-text">
                Sales<br />Analytics
              </span>
              <ChevronRight size={16} className="wa-feature-arrow" />
            </div>
          </div>

          {/* Bottom Statistics Bar */}
          <div className="wa-hero-stats">
            <div className="wa-stat-item">
              <div className="wa-stat-bar" />
              <div className="wa-stat-number">10K+</div>
              <div className="wa-stat-label">Leads<br />Managed</div>
            </div>

            <div className="wa-stat-item">
              <div className="wa-stat-bar" />
              <div className="wa-stat-number">99%</div>
              <div className="wa-stat-label">Customer<br />Satisfaction</div>
            </div>

            <div className="wa-stat-item">
              <div className="wa-stat-bar" />
              <div className="wa-stat-number">3X</div>
              <div className="wa-stat-label">Faster<br />Conversions</div>
            </div>
          </div>
        </div>

        {/* ================= CENTER: 3D BRAND MASCOT (PINNGO) ================= */}
        <div className="wa-center-mascot-section">
          <div className="wa-mascot-floor-shadow" />
          <img 
            src="/crm-mascot.png" 
            alt="WA! CRM Mascot Pinngo" 
            className="wa-center-mascot-img"
          />
        </div>

        {/* ================= RIGHT: AUTHENTICATION CARD ================= */}
        <div className="wa-auth-section">
          <div className="wa-login-card">
            {/* Ambient Fluid Waves inside Card */}
            <div className="wa-card-fluid-blob-top" />
            <div className="wa-card-fluid-blob-bottom" />

            {/* Top Bar: Theme Switcher */}
            <div className="wa-card-top-bar">
              <button 
                type="button" 
                className="wa-theme-toggle" 
                onClick={toggleTheme}
                aria-label="Toggle theme"
              >
                {isDarkMode ? (
                  <>
                    <Sun size={14} color="#f59e0b" />
                    <span>Light Mode</span>
                  </>
                ) : (
                  <>
                    <Moon size={14} color="#64748b" />
                    <span>Dark Mode</span>
                  </>
                )}
              </button>
            </div>

            {/* Card Header */}
            <div className="wa-card-header">
              <div className="wa-card-logo-container">
                <img 
                  src={isDarkMode ? "/wa-crm-logo-dark.png" : "/wa-crm-logo-transparent.png"} 
                  alt="WA! CRM Logo" 
                  className="wa-card-image-logo" 
                />
              </div>
              <h2 className="wa-card-title">Welcome Back</h2>
              <p className="wa-card-subtitle">Sign in to access your CRM dashboard</p>
            </div>

            {/* Error Message */}
            {error && (
              <div className="wa-login-error">
                <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                <span>{error}</span>
              </div>
            )}

            {/* Login Form */}
            <form onSubmit={handleSubmit}>
              {/* Email / Username Field */}
              <div className="wa-form-group">
                <div className="wa-input-wrapper">
                  <Mail size={18} className="wa-input-icon" />
                  <input
                    id="username"
                    type="text"
                    className="wa-input"
                    placeholder="Email Address / Username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={isSubmitting}
                    autoComplete="username"
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="wa-form-group">
                <div className="wa-input-wrapper">
                  <Lock size={18} className="wa-input-icon" />
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    className="wa-input"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isSubmitting}
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="wa-password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex="-1"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              {/* Options Row: Remember Me & Forgot Password */}
              <div className="wa-options-row">
                <label className="wa-remember-me">
                  <input
                    type="checkbox"
                    className="wa-checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                  />
                  <span>Remember me</span>
                </label>

                <button
                  type="button"
                  className="wa-forgot-link"
                  onClick={() => setActiveModal('forgot')}
                >
                  Forgot password?
                </button>
              </div>

              {/* Sign In Primary Button */}
              <button
                type="submit"
                className="wa-submit-btn"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <span className="spinner-sm"></span> Signing In...
                  </>
                ) : (
                  <>
                    Sign In <ArrowRight size={18} />
                  </>
                )}
              </button>

              {/* OR Divider */}
              <div className="wa-divider">
                <span>OR</span>
              </div>

              {/* Continue with Google */}
              <button
                type="button"
                className="wa-google-btn"
                onClick={() => setActiveModal('google')}
              >
                <GoogleLogo />
                <span>Continue with Google</span>
              </button>
            </form>

            {/* Footer */}
            <div className="wa-card-footer">
              <span>Don't have an account? </span>
              <button
                type="button"
                className="wa-admin-link"
                onClick={() => setActiveModal('admin')}
              >
                Contact your administrator
              </button>
            </div>
          </div>
        </div>

      </div>

      {/* ================= MODAL DIALOGS ================= */}
      {activeModal && (
        <div className="wa-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="wa-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="wa-modal-header">
              <h3 className="wa-modal-title">
                {activeModal === 'forgot' && 'Password Assistance'}
                {activeModal === 'admin' && 'Contact Administrator'}
                {activeModal === 'google' && 'Google SSO Sign In'}
              </h3>
              <button 
                type="button" 
                className="wa-modal-close" 
                onClick={() => setActiveModal(null)}
              >
                <X size={20} />
              </button>
            </div>

            <div className="wa-modal-body">
              {activeModal === 'forgot' && (
                <>
                  <p>
                    To reset your WA! CRM account password, please reach out to your organizational CRM administrator or IT helpdesk.
                  </p>
                  <div className="wa-modal-info-box">
                    <strong>Admin Email:</strong> admin@wacrm.local<br />
                    <strong>Support Desk:</strong> ext. 101 or WhatsApp CRM Admin
                  </div>
                </>
              )}

              {activeModal === 'admin' && (
                <>
                  <p>
                    New employee onboarding and CRM user accounts are provisioned directly by your company administrator.
                  </p>
                  <div className="wa-modal-info-box">
                    <strong>Contact IT Department:</strong> support@wacrm.local<br />
                    <strong>Admin Portal:</strong> Settings &gt; User Management
                  </div>
                </>
              )}

              {activeModal === 'google' && (
                <>
                  <p>
                    Google Workspace Single Sign-On (SSO) is enabled for verified company email domains.
                  </p>
                  <p>
                    Please ensure your Google account email matches your registered employee profile in WA! CRM.
                  </p>
                </>
              )}
            </div>

            <button 
              type="button" 
              className="wa-modal-btn" 
              onClick={() => setActiveModal(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Login;
