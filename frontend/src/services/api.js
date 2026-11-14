import axios from 'axios';

const API = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000, // 15-second timeout prevents promises hanging indefinitely
  headers: {
    'Content-Type': 'application/json',
  },
});

// ---------------------------------------------------------------------------
// GET request dedupe + short-lived cache
// ---------------------------------------------------------------------------
// React StrictMode (dev) and several dashboard events can fire the same GET
// within a few milliseconds. Without this layer every caller opens its own
// socket and hits the database, which is the main source of duplicate traffic.
// Non-GET responses clear the cache so a mutation is never followed by a stale
// read.

const DEFAULT_GET_TTL_MS = 1000;
const LONG_GET_TTL_MS = 30000;
const LONG_TTL_PATHS = [
  '/leads/sales-managers',
  '/leads/support/team-members',
  '/leads/trial/support-options',
  '/roles',
  '/doocti/config',
];

const getCache = new Map();
const inFlightGets = new Map();

const stableStringify = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value !== 'object') return String(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  const keys = Object.keys(value);
  // Treat {} and undefined as the same so callers that pass an empty params
  // object share the dedupe entry with callers that pass no params at all.
  if (keys.length === 0) return '';
  return `{${keys.sort().map((key) => `${key}:${stableStringify(value[key])}`).join(',')}}`;
};

const buildCacheKey = (config) => {
  const method = (config.method || 'get').toLowerCase();
  const params = stableStringify(config.params);
  const auth = config.headers?.Authorization || '';
  return `${method}|${config.baseURL || ''}|${config.url || ''}|${params}|${config.responseType || ''}|${auth}`;
};

const resolveTtl = (config) => {
  if (config.cacheTTL !== undefined) return Number(config.cacheTTL);
  const url = config.url || '';
  return LONG_TTL_PATHS.some((path) => url.includes(path))
    ? LONG_GET_TTL_MS
    : DEFAULT_GET_TTL_MS;
};

export const invalidateApiCache = (urlFragment) => {
  if (!urlFragment) {
    getCache.clear();
    return;
  }
  for (const key of getCache.keys()) {
    if (key.includes(urlFragment)) getCache.delete(key);
  }
};

const baseAdapter = axios.getAdapter(API.defaults.adapter);

API.defaults.adapter = async (config) => {
  const method = (config.method || 'get').toLowerCase();

  // Force a network read (used by polling/manual refresh paths).
  if (method !== 'get' || config.skipCache === true) {
    const response = await baseAdapter(config);
    if (method !== 'get') invalidateApiCache();
    return response;
  }

  const key = buildCacheKey(config);
  const ttl = resolveTtl(config);
  const now = Date.now();
  const cached = getCache.get(key);

  if (cached && now - cached.time < ttl) {
    return cached.response;
  }

  if (inFlightGets.has(key)) {
    return inFlightGets.get(key);
  }

  const request = baseAdapter(config)
    .then((response) => {
      getCache.set(key, { time: Date.now(), response });
      return response;
    })
    .finally(() => {
      inFlightGets.delete(key);
    });

  inFlightGets.set(key, request);
  return request;
};

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
  (response) => {
    if ((response.config?.method || 'get').toLowerCase() !== 'get') {
      invalidateApiCache();
    }
    return response;
  },
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
      invalidateApiCache();
      
      const currentPath = (window.location.pathname || '').replace(/\/+$/, '');
      if (currentPath !== '/login' && !currentPath.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default API;
