import React, { createContext, useContext, useCallback } from 'react';
import PingoPopupService, { PINGO_POSES } from '../services/pingoPopupService';
import PingoPopup from '../components/Common/PingoPopup';

const PingoPopupContext = createContext(null);

export const PingoPopupProvider = ({ children }) => {
  const triggerStatusUpdate = useCallback((options) => {
    PingoPopupService.triggerStatusUpdate(options);
  }, []);

  const triggerDownloadSuccess = useCallback((options) => {
    PingoPopupService.triggerDownloadSuccess(options);
  }, []);

  const triggerPopup = useCallback((options) => {
    PingoPopupService.trigger(options);
  }, []);

  const value = {
    triggerStatusUpdate,
    triggerDownloadSuccess,
    triggerPopup,
    poses: PINGO_POSES
  };

  return (
    <PingoPopupContext.Provider value={value}>
      {children}
      <PingoPopup />
    </PingoPopupContext.Provider>
  );
};

export const usePingoPopup = () => {
  const context = useContext(PingoPopupContext);
  if (!context) {
    // Graceful fallback to static service if called outside context provider
    return {
      triggerStatusUpdate: PingoPopupService.triggerStatusUpdate.bind(PingoPopupService),
      triggerDownloadSuccess: PingoPopupService.triggerDownloadSuccess.bind(PingoPopupService),
      triggerPopup: PingoPopupService.trigger.bind(PingoPopupService),
      poses: PINGO_POSES
    };
  }
  return context;
};

export default PingoPopupContext;
