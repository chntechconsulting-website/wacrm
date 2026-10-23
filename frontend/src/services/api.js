import axios from 'axios';

const API = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to attach JWT token
API.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('crm_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor to handle token expiration
API.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || '';
    const isExcludedFromLogout = 
      url.includes('/auth/login') || 
      url.includes('/auth/token') ||
      url.includes('/doocti/') ||
      url.includes('/integrations/');
    
    // Only handle 401 for authenticated core CRM endpoints, never for login or external integration webhooks
    if (!isExcludedFromLogout && error.response && error.response.status === 401) {
      localStorage.removeItem('crm_token');
      localStorage.removeItem('crm_user');
      
      const currentPath = (window.location.pathname || '').replace(/\/+$/, '');
      if (currentPath !== '/login' && !currentPath.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default API;
