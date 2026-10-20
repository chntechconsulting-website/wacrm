import React from 'react';
import { Navigate } from 'react-router-dom';

const ImportLeadsPage = () => {
  return <Navigate to="/leads/create?tab=import" replace />;
};

export default ImportLeadsPage;
