import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  AtSign,
  BadgeCheck,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  Camera,
  CheckCircle2,
  ChevronRight,
  Eye,
  EyeOff,
  Hash,
  ImagePlus,
  KeyRound,
  Loader2,
  Lock,
  Mail,
  MapPin,
  Pencil,
  Phone,
  RefreshCw,
  Save,
  ShieldCheck,
  UserCheck,
  Users,
  X,
} from 'lucide-react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import './ProfilePage.css';

const EMPTY_FORM = {
  name: '',
  email: '',
  phone: '',
  date_of_birth: '',
  gender: '',
  address: '',
};

const GENDERS = ['Male', 'Female', 'Other', 'Prefer not to say'];
const MAX_PHOTO_BYTES = 2 * 1024 * 1024;
const ALLOWED_PHOTO_TYPES = [
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/webp',
];
const ALLOWED_PHOTO_EXTENSION = /\.(jpe?g|png|webp)$/i;

const apiErrorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === 'string' ? item : item?.msg))
      .filter(Boolean);
    if (messages.length) return messages.join(' ');
  }
  return error?.message || fallback;
};

const formatDate = (value, fallback = 'Not provided') => {
  if (!value) return fallback;
  const raw = String(value).slice(0, 10);
  const parsed = new Date(`${raw}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
};

const formatDateTime = (value, fallback = 'No login recorded') => {
  if (!value) return fallback;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const profileToForm = (profile) => ({
  name: profile?.name || '',
  email: profile?.email || '',
  phone: profile?.phone || '',
  date_of_birth: profile?.date_of_birth
    ? String(profile.date_of_birth).slice(0, 10)
    : '',
  gender: profile?.gender || '',
  address: profile?.address || '',
});

const getInitials = (name) => {
  const letters = String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();
  return letters || 'U';
};

const localToday = () => {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
};

const validatePersonalForm = (values) => {
  const errors = {};
  const name = values.name.trim();
  const email = values.email.trim();
  const phone = values.phone.trim();

  if (!name) {
    errors.name = 'Full name is required.';
  } else if (name.length > 100) {
    errors.name = 'Full name cannot exceed 100 characters.';
  }

  if (!email) {
    errors.email = 'Email address is required.';
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = 'Enter a valid email address.';
  }

  if (phone) {
    const digits = phone.replace(/\D/g, '');
    if (digits.length < 7 || digits.length > 15) {
      errors.phone = 'Enter a valid mobile number with 7 to 15 digits.';
    }
  }

  if (values.date_of_birth && values.date_of_birth > localToday()) {
    errors.date_of_birth = 'Date of birth cannot be in the future.';
  }

  if (values.address.trim().length > 500) {
    errors.address = 'Address cannot exceed 500 characters.';
  }

  return errors;
};

const DetailItem = ({ icon: Icon, label, value, full = false }) => (
  <div className={`profile-detail-item${full ? ' full' : ''}`}>
    <span className="profile-detail-label">
      <Icon size={15} />
      {label}
    </span>
    <span className={`profile-detail-value${value ? '' : ' empty'}`}>
      {value || 'Not provided'}
    </span>
  </div>
);

const PasswordInput = ({
  id,
  label,
  value,
  onChange,
  visible,
  onToggle,
  error,
  autoComplete,
}) => (
  <div className={`profile-form-field${error ? ' has-error' : ''}`}>
    <label htmlFor={id}>{label}</label>
    <div className="profile-input-wrap">
      <Lock size={16} className="profile-input-icon" />
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        placeholder="Enter password"
      />
      <button
        type="button"
        className="profile-eye-btn"
        onClick={onToggle}
        aria-label={visible ? `Hide ${label}` : `Show ${label}`}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
    {error && <span className="profile-field-error">{error}</span>}
  </div>
);

const ProfilePage = () => {
  const { refreshUser } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  const [photoFile, setPhotoFile] = useState(null);
  const [photoPreview, setPhotoPreview] = useState('');
  const [photoError, setPhotoError] = useState('');
  const [photoUploading, setPhotoUploading] = useState(false);
  const fileInputRef = useRef(null);
  const previewUrlRef = useRef('');

  const [password, setPassword] = useState({
    current: '',
    new: '',
    confirm: '',
  });
  const [passwordErrors, setPasswordErrors] = useState({});
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [showPassword, setShowPassword] = useState({
    current: false,
    new: false,
    confirm: false,
  });

  const initials = useMemo(() => getInitials(profile?.name), [profile?.name]);

  const loadProfile = useCallback(async (showLoading = false) => {
    if (showLoading) {
      setLoading(true);
      setLoadError('');
    }
    try {
      const response = await API.get('/profile');
      setProfile(response.data);
      setForm(profileToForm(response.data));
    } catch (error) {
      setLoadError(
        apiErrorMessage(
          error,
          'Unable to load your profile. Please try again.',
        ),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  useEffect(
    () => () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const clearPreview = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = '';
    }
    setPhotoPreview('');
    setPhotoFile(null);
    setPhotoError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  useEffect(() => {
    if (!photoPreview) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !photoUploading) {
        clearPreview();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [photoPreview, photoUploading, clearPreview]);

  const startEditing = () => {
    setForm(profileToForm(profile));
    setFormErrors({});
    setIsEditing(true);
    setNotice(null);
  };

  const cancelEditing = () => {
    setForm(profileToForm(profile));
    setFormErrors({});
    setIsEditing(false);
  };

  const updateForm = (field) => (event) => {
    const value = event.target.value;
    setForm((previous) => ({ ...previous, [field]: value }));
    setFormErrors((previous) => ({ ...previous, [field]: '', submit: '' }));
  };

  const handlePersonalSubmit = async (event) => {
    event.preventDefault();
    const validationErrors = validatePersonalForm(form);
    if (Object.keys(validationErrors).length) {
      setFormErrors(validationErrors);
      return;
    }

    setSaving(true);
    setFormErrors({});
    try {
      const response = await API.put('/profile', {
        name: form.name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || null,
        date_of_birth: form.date_of_birth || null,
        gender: form.gender || null,
        address: form.address.trim() || null,
      });
      setProfile(response.data);
      setForm(profileToForm(response.data));
      setIsEditing(false);
      setNotice({
        type: 'success',
        text: 'Your personal information has been updated.',
      });
      await refreshUser().catch(() => {});
    } catch (error) {
      setFormErrors({
        submit: apiErrorMessage(
          error,
          'Unable to save your profile changes. Please try again.',
        ),
      });
    } finally {
      setSaving(false);
    }
  };

  const openPhotoPicker = () => {
    setPhotoError('');
    fileInputRef.current?.click();
  };

  const handlePhotoSelected = (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setPhotoError('');
    if (
      !ALLOWED_PHOTO_TYPES.includes(file.type) &&
      !ALLOWED_PHOTO_EXTENSION.test(file.name || '')
    ) {
      setPhotoError('Choose a JPG, PNG or WEBP image.');
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setPhotoError('Profile photo must be 2 MB or smaller.');
      return;
    }

    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }
    const objectUrl = URL.createObjectURL(file);
    previewUrlRef.current = objectUrl;
    setPhotoFile(file);
    setPhotoPreview(objectUrl);
  };

  const uploadPhoto = async () => {
    if (!photoFile) return;
    setPhotoUploading(true);
    setPhotoError('');
    try {
      const data = new FormData();
      data.append('file', photoFile);
      const response = await API.post('/profile/photo', data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setProfile((previous) =>
        previous
          ? { ...previous, photo_url: response.data.photo_url }
          : previous,
      );
      clearPreview();
      setNotice({
        type: 'success',
        text: 'Your profile photo has been updated.',
      });
      await refreshUser().catch(() => {});
    } catch (error) {
      setPhotoError(
        apiErrorMessage(error, 'Unable to upload the photo. Please try again.'),
      );
    } finally {
      setPhotoUploading(false);
    }
  };

  const updatePasswordField = (field) => (event) => {
    const value = event.target.value;
    setPassword((previous) => ({ ...previous, [field]: value }));
    setPasswordErrors((previous) => ({
      ...previous,
      [field]: '',
      submit: '',
    }));
  };

  const validatePasswordForm = () => {
    const errors = {};
    if (!password.current) {
      errors.current = 'Current password is required.';
    }
    if (!password.new) {
      errors.new = 'New password is required.';
    } else if (password.new.length < 6) {
      errors.new = 'New password must be at least 6 characters.';
    } else if (password.new === password.current) {
      errors.new = 'New password must be different from the current password.';
    }
    if (!password.confirm) {
      errors.confirm = 'Confirm your new password.';
    } else if (password.confirm !== password.new) {
      errors.confirm = 'New password and confirmation do not match.';
    }
    return errors;
  };

  const handlePasswordSubmit = async (event) => {
    event.preventDefault();
    const validationErrors = validatePasswordForm();
    if (Object.keys(validationErrors).length) {
      setPasswordErrors(validationErrors);
      return;
    }

    setPasswordSaving(true);
    setPasswordErrors({});
    try {
      await API.post('/auth/change-password', {
        current_password: password.current,
        new_password: password.new,
      });
      setPassword({ current: '', new: '', confirm: '' });
      setShowPassword({ current: false, new: false, confirm: false });
      setNotice({
        type: 'success',
        text: 'Password changed successfully.',
      });
    } catch (error) {
      setPasswordErrors({
        submit: apiErrorMessage(
          error,
          'Unable to change your password. Please try again.',
        ),
      });
    } finally {
      setPasswordSaving(false);
    }
  };

  const pageHeading = (
    <div className="profile-page-heading">
      <nav className="profile-breadcrumb" aria-label="Breadcrumb">
        <Link to="/dashboard">Dashboard</Link>
        <ChevronRight size={14} />
        <span>My Profile</span>
      </nav>
      <h1 className="page-title">My Profile</h1>
      <p className="page-subtitle">
        Manage your personal details, employment information and account
        security.
      </p>
    </div>
  );

  if (loading) {
    return (
      <div className="page-container profile-page">
        {pageHeading}
        <div className="profile-state-card" role="status">
          <span className="profile-state-icon">
            <Loader2 size={28} className="profile-spin" />
          </span>
          <h2>Loading your profile</h2>
          <p>Fetching your employee information securely.</p>
        </div>
      </div>
    );
  }

  if (loadError || !profile) {
    return (
      <div className="page-container profile-page">
        {pageHeading}
        <div className="profile-state-card is-error" role="alert">
          <span className="profile-state-icon error">
            <AlertCircle size={28} />
          </span>
          <h2>We couldn’t load your profile</h2>
          <p>{loadError || 'Your employee profile is unavailable.'}</p>
          <button
            type="button"
            className="profile-btn primary"
            onClick={() => loadProfile(true)}
          >
            <RefreshCw size={16} />
            Try again
          </button>
        </div>
      </div>
    );
  }

  const employmentRows = [
    { icon: Hash, label: 'Employee ID', value: profile.employee_id },
    {
      icon: Building2,
      label: 'Department',
      value: profile.department_label || profile.department,
    },
    { icon: Users, label: 'Team', value: profile.team },
    {
      icon: BriefcaseBusiness,
      label: 'Designation',
      value: profile.designation,
    },
    {
      icon: UserCheck,
      label: 'Reporting manager',
      value: profile.reporting_manager_name,
    },
    {
      icon: CalendarDays,
      label: 'Date of joining',
      value: formatDate(profile.date_of_joining),
    },
  ];

  return (
    <div className="page-container profile-page">
      {pageHeading}

      {notice && (
        <div className={`profile-alert ${notice.type}`} role="status">
          {notice.type === 'success' ? (
            <CheckCircle2 size={18} />
          ) : (
            <AlertCircle size={18} />
          )}
          <span>{notice.text}</span>
          <button
            type="button"
            className="profile-alert-close"
            onClick={() => setNotice(null)}
            aria-label="Dismiss message"
          >
            <X size={15} />
          </button>
        </div>
      )}

      <section className="profile-hero">
        <div className="profile-hero-banner" aria-hidden="true" />
        <div className="profile-hero-body">
          <div className="profile-avatar-wrap">
            <div className="profile-avatar">
              {profile.photo_url ? (
                <img src={profile.photo_url} alt={`${profile.name} profile`} />
              ) : (
                <span>{initials}</span>
              )}
            </div>
            <button
              type="button"
              className="profile-camera-btn"
              onClick={openPhotoPicker}
              title="Change profile photo"
              aria-label="Change profile photo"
            >
              <Camera size={16} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="profile-photo-input"
              onChange={handlePhotoSelected}
            />
          </div>

          <div className="profile-identity">
            <div className="profile-name-row">
              <h2>{profile.name}</h2>
              <span
                className={`profile-status-pill ${
                  profile.account_status === 'ACTIVE' ? 'active' : 'inactive'
                }`}
              >
                <span className="profile-status-dot" />
                {profile.account_status === 'ACTIVE' ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="profile-designation">
              {profile.designation}
              {profile.department_label
                ? ` · ${profile.department_label}`
                : ''}
            </p>
            <div className="profile-meta">
              <span>
                <Hash size={14} />
                Employee ID: {profile.employee_id}
              </span>
              <span>
                <Mail size={14} />
                {profile.email || 'Email not available'}
              </span>
            </div>
          </div>

          <div className="profile-hero-actions">
            {isEditing ? (
              <span className="profile-editing-pill">
                <Pencil size={14} />
                Editing profile
              </span>
            ) : (
              <button
                type="button"
                className="profile-btn primary"
                onClick={startEditing}
              >
                <Pencil size={16} />
                Edit Profile
              </button>
            )}
          </div>
        </div>
        {photoError && !photoPreview && (
          <div className="profile-photo-error" role="alert">
            <AlertCircle size={15} />
            {photoError}
          </div>
        )}
      </section>

      <div className="profile-layout">
        <section className="profile-card profile-personal-card">
          <header className="profile-card-head">
            <span className="profile-card-icon green">
              <UserCheck size={19} />
            </span>
            <div className="profile-card-title">
              <h3>Personal Information</h3>
              <p>Your contact and personal details</p>
            </div>
            {!isEditing && (
              <button
                type="button"
                className="profile-text-btn"
                onClick={startEditing}
              >
                <Pencil size={14} />
                Edit
              </button>
            )}
          </header>

          <div className="profile-card-body">
            {isEditing ? (
              <form className="profile-form" onSubmit={handlePersonalSubmit} noValidate>
                <div className="profile-form-grid">
                  <div
                    className={`profile-form-field${
                      formErrors.name ? ' has-error' : ''
                    }`}
                  >
                    <label htmlFor="profile-name">Full name *</label>
                    <div className="profile-input-wrap">
                      <UserCheck size={16} className="profile-input-icon" />
                      <input
                        id="profile-name"
                        type="text"
                        value={form.name}
                        onChange={updateForm('name')}
                        maxLength={100}
                        autoComplete="name"
                        placeholder="Enter your full name"
                      />
                    </div>
                    {formErrors.name && (
                      <span className="profile-field-error">
                        {formErrors.name}
                      </span>
                    )}
                  </div>

                  <div
                    className={`profile-form-field${
                      formErrors.email ? ' has-error' : ''
                    }`}
                  >
                    <label htmlFor="profile-email">Email address *</label>
                    <div className="profile-input-wrap">
                      <Mail size={16} className="profile-input-icon" />
                      <input
                        id="profile-email"
                        type="email"
                        value={form.email}
                        onChange={updateForm('email')}
                        autoComplete="email"
                        placeholder="name@company.com"
                      />
                    </div>
                    {formErrors.email && (
                      <span className="profile-field-error">
                        {formErrors.email}
                      </span>
                    )}
                  </div>

                  <div
                    className={`profile-form-field${
                      formErrors.phone ? ' has-error' : ''
                    }`}
                  >
                    <label htmlFor="profile-phone">Mobile number</label>
                    <div className="profile-input-wrap">
                      <Phone size={16} className="profile-input-icon" />
                      <input
                        id="profile-phone"
                        type="tel"
                        value={form.phone}
                        onChange={updateForm('phone')}
                        autoComplete="tel"
                        placeholder="Enter mobile number"
                      />
                    </div>
                    {formErrors.phone && (
                      <span className="profile-field-error">
                        {formErrors.phone}
                      </span>
                    )}
                  </div>

                  <div
                    className={`profile-form-field${
                      formErrors.date_of_birth ? ' has-error' : ''
                    }`}
                  >
                    <label htmlFor="profile-dob">Date of birth</label>
                    <div className="profile-input-wrap">
                      <CalendarDays size={16} className="profile-input-icon" />
                      <input
                        id="profile-dob"
                        type="date"
                        value={form.date_of_birth}
                        onChange={updateForm('date_of_birth')}
                        max={localToday()}
                      />
                    </div>
                    {formErrors.date_of_birth && (
                      <span className="profile-field-error">
                        {formErrors.date_of_birth}
                      </span>
                    )}
                  </div>

                  <div className="profile-form-field">
                    <label htmlFor="profile-gender">Gender</label>
                    <div className="profile-input-wrap">
                      <Users size={16} className="profile-input-icon" />
                      <select
                        id="profile-gender"
                        value={form.gender}
                        onChange={updateForm('gender')}
                      >
                        <option value="">Select gender</option>
                        {GENDERS.map((gender) => (
                          <option key={gender} value={gender}>
                            {gender}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div
                    className={`profile-form-field full${
                      formErrors.address ? ' has-error' : ''
                    }`}
                  >
                    <label htmlFor="profile-address">Address</label>
                    <div className="profile-input-wrap textarea">
                      <MapPin size={16} className="profile-input-icon" />
                      <textarea
                        id="profile-address"
                        rows={3}
                        value={form.address}
                        onChange={updateForm('address')}
                        maxLength={500}
                        placeholder="Enter your residential address"
                      />
                    </div>
                    <div className="profile-field-foot">
                      {formErrors.address ? (
                        <span className="profile-field-error">
                          {formErrors.address}
                        </span>
                      ) : (
                        <span />
                      )}
                      <span className="profile-char-count">
                        {form.address.length}/500
                      </span>
                    </div>
                  </div>
                </div>

                {formErrors.submit && (
                  <div className="profile-form-error" role="alert">
                    <AlertCircle size={16} />
                    {formErrors.submit}
                  </div>
                )}

                <div className="profile-form-actions">
                  <button
                    type="button"
                    className="profile-btn secondary"
                    onClick={cancelEditing}
                    disabled={saving}
                  >
                    <X size={16} />
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="profile-btn primary"
                    disabled={saving}
                  >
                    {saving ? (
                      <Loader2 size={16} className="profile-spin" />
                    ) : (
                      <Save size={16} />
                    )}
                    {saving ? 'Saving…' : 'Save changes'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="profile-detail-grid">
                <DetailItem
                  icon={UserCheck}
                  label="Full name"
                  value={profile.name}
                />
                <DetailItem
                  icon={Mail}
                  label="Email address"
                  value={profile.email}
                />
                <DetailItem
                  icon={Phone}
                  label="Mobile number"
                  value={profile.phone}
                />
                <DetailItem
                  icon={CalendarDays}
                  label="Date of birth"
                  value={
                    profile.date_of_birth
                      ? formatDate(profile.date_of_birth)
                      : ''
                  }
                />
                <DetailItem
                  icon={Users}
                  label="Gender"
                  value={profile.gender}
                />
                <DetailItem
                  icon={MapPin}
                  label="Address"
                  value={profile.address}
                  full
                />
              </div>
            )}
          </div>
        </section>

        <section className="profile-card profile-employment-card">
          <header className="profile-card-head">
            <span className="profile-card-icon blue">
              <BriefcaseBusiness size={19} />
            </span>
            <div className="profile-card-title">
              <h3>Employment Information</h3>
              <p>Your role in the organisation</p>
            </div>
            <span className="profile-readonly-badge">
              <Lock size={12} />
              Read only
            </span>
          </header>

          <div className="profile-card-body">
            <div className="profile-employment-list">
              {employmentRows.map(({ icon: RowIcon, label, value }) => (
                <div className="profile-employment-row" key={label}>
                  <span className="profile-employment-icon">
                    <RowIcon size={16} />
                  </span>
                  <span className="profile-employment-label">{label}</span>
                  <span
                    className={`profile-employment-value${
                      value ? '' : ' empty'
                    }`}
                  >
                    {value || 'Not assigned'}
                  </span>
                </div>
              ))}
              <div className="profile-employment-row">
                <span className="profile-employment-icon">
                  <BadgeCheck size={16} />
                </span>
                <span className="profile-employment-label">
                  Employment status
                </span>
                <span
                  className={`profile-employment-value ${
                    profile.employment_status === 'ACTIVE'
                      ? 'status-active'
                      : 'status-inactive'
                  }`}
                >
                  {profile.employment_status === 'ACTIVE'
                    ? 'Active'
                    : 'Inactive'}
                </span>
              </div>
            </div>
            <div className="profile-employment-note">
              <ShieldCheck size={15} />
              <span>
                Employment details are maintained by an authorised
                administrator and cannot be changed from this page.
              </span>
            </div>
          </div>
        </section>

        <section className="profile-card profile-security-card">
          <header className="profile-card-head">
            <span className="profile-card-icon amber">
              <ShieldCheck size={19} />
            </span>
            <div className="profile-card-title">
              <h3>Account &amp; Security</h3>
              <p>Sign-in identity and password management</p>
            </div>
          </header>

          <div className="profile-card-body">
            <div className="profile-security-layout">
              <div className="profile-account-panel">
                <div className="profile-subsection-head">
                  <KeyRound size={16} />
                  <h4>Account details</h4>
                </div>
                <div className="profile-account-list">
                  <div className="profile-account-row">
                    <span>
                      <AtSign size={15} />
                      Username
                    </span>
                    <strong>{profile.username}</strong>
                  </div>
                  <div className="profile-account-row">
                    <span>
                      <Mail size={15} />
                      Email
                    </span>
                    <strong>{profile.email || 'Not provided'}</strong>
                  </div>
                  <div className="profile-account-row">
                    <span>
                      <BadgeCheck size={15} />
                      Role
                    </span>
                    <strong>{profile.role_label}</strong>
                  </div>
                  <div className="profile-account-row">
                    <span>
                      <ShieldCheck size={15} />
                      Account status
                    </span>
                    <strong
                      className={
                        profile.account_status === 'ACTIVE'
                          ? 'status-active'
                          : 'status-inactive'
                      }
                    >
                      {profile.account_status === 'ACTIVE'
                        ? 'Active'
                        : 'Inactive'}
                    </strong>
                  </div>
                  <div className="profile-account-row">
                    <span>
                      <CalendarDays size={15} />
                      Last login
                    </span>
                    <strong>{formatDateTime(profile.last_login)}</strong>
                  </div>
                </div>
              </div>

              <div className="profile-password-panel">
                <div className="profile-subsection-head">
                  <Lock size={16} />
                  <h4>Change password</h4>
                </div>
                <p className="profile-password-help">
                  Use at least 6 characters. Your current password is never
                  displayed.
                </p>
                <form
                  className="profile-password-form"
                  onSubmit={handlePasswordSubmit}
                  noValidate
                >
                  <PasswordInput
                    id="current-password"
                    label="Current password"
                    value={password.current}
                    onChange={updatePasswordField('current')}
                    visible={showPassword.current}
                    onToggle={() =>
                      setShowPassword((previous) => ({
                        ...previous,
                        current: !previous.current,
                      }))
                    }
                    error={passwordErrors.current}
                    autoComplete="current-password"
                  />
                  <PasswordInput
                    id="new-password"
                    label="New password"
                    value={password.new}
                    onChange={updatePasswordField('new')}
                    visible={showPassword.new}
                    onToggle={() =>
                      setShowPassword((previous) => ({
                        ...previous,
                        new: !previous.new,
                      }))
                    }
                    error={passwordErrors.new}
                    autoComplete="new-password"
                  />
                  <PasswordInput
                    id="confirm-password"
                    label="Confirm new password"
                    value={password.confirm}
                    onChange={updatePasswordField('confirm')}
                    visible={showPassword.confirm}
                    onToggle={() =>
                      setShowPassword((previous) => ({
                        ...previous,
                        confirm: !previous.confirm,
                      }))
                    }
                    error={passwordErrors.confirm}
                    autoComplete="new-password"
                  />

                  {passwordErrors.submit && (
                    <div className="profile-form-error" role="alert">
                      <AlertCircle size={16} />
                      {passwordErrors.submit}
                    </div>
                  )}

                  <button
                    type="submit"
                    className="profile-btn primary profile-password-submit"
                    disabled={passwordSaving}
                  >
                    {passwordSaving ? (
                      <Loader2 size={16} className="profile-spin" />
                    ) : (
                      <KeyRound size={16} />
                    )}
                    {passwordSaving ? 'Updating…' : 'Update password'}
                  </button>
                </form>
              </div>
            </div>
          </div>
        </section>
      </div>

      {photoPreview && (
        <div
          className="profile-photo-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !photoUploading) {
              clearPreview();
            }
          }}
        >
          <div
            className="profile-photo-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="profile-photo-title"
          >
            <div className="profile-photo-modal-head">
              <div>
                <h3 id="profile-photo-title">Update profile photo</h3>
                <p>Preview your photo before saving it.</p>
              </div>
              <button
                type="button"
                className="profile-modal-close"
                onClick={clearPreview}
                disabled={photoUploading}
                aria-label="Close photo preview"
              >
                <X size={18} />
              </button>
            </div>

            <div className="profile-photo-preview">
              <img src={photoPreview} alt="Selected profile preview" />
            </div>

            {photoError && (
              <div className="profile-form-error" role="alert">
                <AlertCircle size={16} />
                {photoError}
              </div>
            )}

            <div className="profile-photo-modal-actions">
              <button
                type="button"
                className="profile-btn secondary"
                onClick={clearPreview}
                disabled={photoUploading}
              >
                <X size={16} />
                Cancel
              </button>
              <button
                type="button"
                className="profile-btn primary"
                onClick={uploadPhoto}
                disabled={photoUploading}
              >
                {photoUploading ? (
                  <Loader2 size={16} className="profile-spin" />
                ) : (
                  <ImagePlus size={16} />
                )}
                {photoUploading ? 'Uploading…' : 'Save photo'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfilePage;
