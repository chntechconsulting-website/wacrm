import React from 'react';
import Leads from './index';

const MyLeadsPage = () => {
  return <Leads defaultFilter="my-leads" pageTitle="Assigned Leads" pageSubtitle="Filtered list of leads specifically assigned to your account." />;
};

export default MyLeadsPage;
