import React, { createContext, useContext, useState, useEffect } from 'react';
import API from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('crm_user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem('crm_token') || null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const verifyToken = async () => {
      const storedToken = localStorage.getItem('crm_token');
      if (storedToken) {
        try {
          const res = await API.get('/auth/me');
          setUser(res.data);
          localStorage.setItem('crm_user', JSON.stringify(res.data));
        } catch (err) {
          console.error('Token verification failed:', err);
          // Only log out if the backend explicitly reports that the token is unauthorized (401 or 403)
          // Do NOT log out on network disconnects, timeouts, or 502 Bad Gateway
          if (err.response && (err.response.status === 401 || err.response.status === 403)) {
            logout();
          }
        }
      } else {
        setUser(null);
      }
      setLoading(false);
    };

    verifyToken();
  }, []);

  const login = async (username, password) => {
    const res = await API.post('/auth/login', { username, password });
    const { access_token, user: userData } = res.data;

    localStorage.setItem('crm_token', access_token);
    localStorage.setItem('crm_user', JSON.stringify(userData));

    setToken(access_token);
    setUser(userData);
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
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
