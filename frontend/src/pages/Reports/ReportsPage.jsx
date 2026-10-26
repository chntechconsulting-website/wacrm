import React from 'react';
import { useSearchParams } from 'react-router-dom';
import SalesOverviewReport from './SalesOverviewReport';
import SalesRevenueReport from './SalesRevenueReport';
import DataExportPage from './DataExportPage';
import Reports from './index';

const ReportsPage = () => {
  const [searchParams] = useSearchParams();
  const tab = searchParams.get('tab') || 'sales-overview';

  if (tab === 'export' || tab === 'data-export') {
    return <DataExportPage />;
  }

  if (tab === 'revenue' || tab === 'sales-revenue') {
    return <SalesRevenueReport />;
  }

  if (tab === 'sales-overview' || !tab) {
    return <SalesOverviewReport />;
  }

  return <Reports defaultTab={tab} />;
};

export default ReportsPage;
