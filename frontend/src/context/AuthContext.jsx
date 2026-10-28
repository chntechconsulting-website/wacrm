import React, { createContext, useContext, useState, useEffect } from 'react';
import API from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    try {
      const savedUser = localStorage.getItem('crm_user');
      return savedUser ? JSON.parse(savedUser) : null;
    } catch {
      return null;
    }
  });
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem('crm_token') || null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  const verifyToken = async () => {
    setLoading(true);
    setAuthError(null);

    const storedToken = localStorage.getItem('crm_token');
    if (!storedToken) {
      setUser(null);
      setToken(null);
      setLoading(false);
      return;
    }

    try {
      const res = await API.get('/auth/me');
      setUser(res.data);
      setToken(storedToken);
      localStorage.setItem('crm_user', JSON.stringify(res.data));
      setAuthError(null);
    } catch (err) {
      console.error('Token verification failed:', err);
      const status = err.response?.status;
      
      if (status === 401 || status === 403) {
        // Token is definitively invalid or expired -> purge session
        localStorage.removeItem('crm_token');
        localStorage.removeItem('crm_user');
        setToken(null);
        setUser(null);
        setAuthError(null);
      } else {
        // Backend offline / 502 Bad Gateway / Network timeout
        // Check if we have cached user details from previous successful login
        const cachedUserStr = localStorage.getItem('crm_user');
        if (cachedUserStr) {
          try {
            const cachedUser = JSON.parse(cachedUserStr);
            setUser(cachedUser);
            // Allow user to proceed with cached credentials while noting connection error
            setAuthError(null);
          } catch {
            setAuthError(err.message || 'Server connection error');
          }
        } else {
          setAuthError(err.message || 'Server connection error');
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    verifyToken();
  }, []);

  const login = async (username, password) => {
    const res = await API.post('/auth/login', { username, password });
    const { access_token, user: userData } = res.data;

    localStorage.setItem('crm_token', access_token);
    localStorage.setItem('crm_user', JSON.stringify(userData));

    setToken(access_token);
    setUser(userData);
    setAuthError(null);
    return userData;
  };

  const logout = async () => {
    try {
      await API.post('/auth/logout');
    } catch (e) {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('crm_token');
      localStorage.removeItem('crm_user');
      setToken(null);
      setUser(null);
      setAuthError(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, authError, retryAuth: verifyToken, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
