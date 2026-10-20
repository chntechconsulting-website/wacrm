import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../services/api';
import { useAuth } from './AuthContext';
import { playReminderChime, stopReminderChime } from '../utils/sound';

const FollowupReminderContext = createContext();

export const useFollowupReminder = () => {
  const context = useContext(FollowupReminderContext);
  if (!context) {
    throw new Error('useFollowupReminder must be used within a FollowupReminderProvider');
  }
  return context;
};

export const FollowupReminderProvider = ({ children }) => {
  const [activeReminders, setActiveReminders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();
  const isFetchingRef = useRef(false);
  const alarmIntervalRef = useRef(null);

  const fetchActiveReminders = useCallback(async () => {
    // Only fetch if authenticated and user session exists
    const token = localStorage.getItem('crm_token');
    if (!token || !user) {
      setActiveReminders([]);
      return;
    }

    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    try {
      const res = await API.get('/followups/reminders/active');
      if (Array.isArray(res.data)) {
        setActiveReminders(res.data);
      }
    } catch (err) {
      // Background check error handled silently to prevent UI disruption
      console.warn('Error checking followup reminders:', err?.response?.data || err.message);
    } finally {
      isFetchingRef.current = false;
      setLoading(false);
    }
  }, [user]);

  // CONTINUOUS ALARM LOOP:
  // Ring loudly and repeat every 5.5 seconds UNTIL status is updated, dismissed, or muted
  useEffect(() => {
    const hasActiveReminders = activeReminders && activeReminders.length > 0;

    if (hasActiveReminders && !isMuted) {
      // Play immediately
      playReminderChime(true);

      // Clear any previous interval
      if (alarmIntervalRef.current) {
        clearInterval(alarmIntervalRef.current);
      }

      // Repeat chime continuously every 5.5s until handled
      alarmIntervalRef.current = setInterval(() => {
        playReminderChime(true);
      }, 5500);
    } else {
      // Stop repeating and silence any playing notes
      if (alarmIntervalRef.current) {
        clearInterval(alarmIntervalRef.current);
        alarmIntervalRef.current = null;
      }
      stopReminderChime();
    }

    return () => {
      if (alarmIntervalRef.current) {
        clearInterval(alarmIntervalRef.current);
        alarmIntervalRef.current = null;
      }
    };
  }, [activeReminders.length > 0, isMuted]);

  // Reset mute status when all reminders are handled so future reminders ring normally
  useEffect(() => {
    if (activeReminders.length === 0) {
      setIsMuted(false);
      stopReminderChime();
    }
  }, [activeReminders.length]);

  // Periodic polling: check every 30 seconds
  useEffect(() => {
    fetchActiveReminders();

    const interval = setInterval(() => {
      fetchActiveReminders();
    }, 30000);

    // Also check when tab becomes visible again
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchActiveReminders();
      }
    };

    // Custom events to force refresh reminders (e.g. after creating/updating a follow-up or lead)
    const handleCustomRefresh = () => {
      fetchActiveReminders();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('followupReminderRefresh', handleCustomRefresh);
    window.addEventListener('leadStatsUpdated', handleCustomRefresh);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('followupReminderRefresh', handleCustomRefresh);
      window.removeEventListener('leadStatsUpdated', handleCustomRefresh);
    };
  }, [fetchActiveReminders]);

  // Update Status directly (e.g., to "Completed" or "Cancelled")
  // Automatically stops alarm immediately
  const completeFollowup = async (followupId) => {
    try {
      // Optimistically remove from active list immediately to silence alarm instantly
      setActiveReminders(prev => prev.filter(r => r.id !== followupId));
      stopReminderChime();

      await API.put(`/followups/${followupId}`, { status: 'Completed' });
      window.dispatchEvent(new CustomEvent('followupReminderRefresh'));
      window.dispatchEvent(new CustomEvent('leadStatsUpdated'));
    } catch (err) {
      console.error('Failed to mark follow-up as completed:', err);
      fetchActiveReminders();
    }
  };

  const updateFollowupStatus = async (followupId, status) => {
    try {
      if (status !== 'Pending') {
        setActiveReminders(prev => prev.filter(r => r.id !== followupId));
        stopReminderChime();
      }
      await API.put(`/followups/${followupId}`, { status });
      window.dispatchEvent(new CustomEvent('followupReminderRefresh'));
      window.dispatchEvent(new CustomEvent('leadStatsUpdated'));
    } catch (err) {
      console.error('Failed to update follow-up status:', err);
      fetchActiveReminders();
    }
  };

  const snoozeReminder = async (followupId, minutes = 15) => {
    try {
      // Optimistically remove from visible list immediately
      setActiveReminders(prev => prev.filter(r => r.id !== followupId));
      stopReminderChime();
      await API.post(`/followups/${followupId}/snooze`, { minutes });
    } catch (err) {
      console.error('Failed to snooze reminder:', err);
      fetchActiveReminders();
    }
  };

  const dismissReminder = async (followupId) => {
    try {
      // Optimistically remove from visible list immediately
      setActiveReminders(prev => prev.filter(r => r.id !== followupId));
      stopReminderChime();
      await API.post(`/followups/${followupId}/dismiss-reminder`);
    } catch (err) {
      console.error('Failed to dismiss reminder:', err);
      fetchActiveReminders();
    }
  };

  const toggleMute = () => {
    setIsMuted(prev => {
      const next = !prev;
      if (next) {
        stopReminderChime();
      }
      return next;
    });
  };

  const viewLead = (leadId) => {
    if (!leadId) return;
    // Dispatch custom event for pages that already have the lead drawer loaded
    window.dispatchEvent(new CustomEvent('openLeadDrawer', { detail: { leadId } }));
    // Navigate to leads list with openLeadId search param
    navigate(`/leads?openLeadId=${leadId}`);
  };

  return (
    <FollowupReminderContext.Provider
      value={{
        activeReminders,
        loading,
        isMuted,
        toggleMute,
        completeFollowup,
        updateFollowupStatus,
        snoozeReminder,
        dismissReminder,
        viewLead,
        playChime: () => playReminderChime(true),
        stopAlarm: stopReminderChime,
        refetchReminders: fetchActiveReminders
      }}
    >
      {children}
    </FollowupReminderContext.Provider>
  );
};
